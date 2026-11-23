"""Months, categories, groups, recurring payments, the transactions table and one-off payments.

Closed months are summarised into state (summary + compact rows for the last months), so later
updates need only the current month's transactions. All numbers are the same as computed from
the full history.
"""
import collections
import re
import statistics

from common import month_add, month_range as months_between, r2

MONTH_NAMES = ["jaan", "veebr", "märts", "apr", "mai", "juuni", "juuli", "aug", "sept", "okt", "nov", "dets"]
UNNAMED = "(nimeta)"
CARD_DESCRIPTION = re.compile(r"\(\.\.\d+\)\s+(\d{4}-\d\d-\d\d)\s+(\d\d:\d\d)\s+(.*)$")
SMALL = 0.005


def label(month):
    """Short month label, e.g. "nov 26"."""
    return MONTH_NAMES[int(month[5:7]) - 1] + " " + month[2:4]


def rounded_nonzero(values):
    return {key: r2(value) for key, value in values.items() if abs(value) >= SMALL}


# ---------- transaction kinds ----------

def is_internal(rules, category):
    return rules.role(category, "internal")


def is_investment(rules, category):
    return rules.role(category, "investment") and not rules.role(category, "pension")


def regular(rules, transaction):
    """True if the transaction counts in the month's result (current month view)."""
    category = transaction["category"]
    if is_internal(rules, category) or is_investment(rules, category):
        return False
    if transaction["oneoff"] or rules.role(category, "oneoff_income"):
        return False
    if rules.role(category, "loan") and transaction["amount"] > 0:
        return False
    return True


def display_name(rules, transaction):
    return rules.payee_name((transaction.get("counterparty") or "").strip() or transaction["category"])


def salary_categories(rules):
    return set(rules.settings.get("salary_categories") or [])


def subscription_kinds(rules):
    return {kind["kind"] for kind in rules.raw.get("recurring_kinds") or [] if kind.get("subscription")}


# ---------- month summary (kept in state) ----------

def summarise(rules, month, rows, recurring_items):
    sums = dict(income=0.0, expenses=0.0, loans=0.0, oneoff=0.0, oneoff_income=0.0, financing=0.0, pension3=0.0)
    categories = collections.defaultdict(float)
    categories_oneoff = collections.defaultdict(float)
    groups = collections.defaultdict(float)

    for transaction in rows:
        category = transaction["category"]
        amount = transaction["amount"]
        if is_internal(rules, category) or is_investment(rules, category):
            continue
        if rules.role(category, "loan") and amount > 0:
            sums["financing"] += amount
            continue
        if rules.role(category, "oneoff_income"):
            sums["oneoff_income"] += amount
            continue

        if rules.role(category, "income"):
            sums["income"] += amount
        elif rules.role(category, "pension"):
            sums["pension3"] += -amount
        elif transaction["oneoff"]:
            sums["oneoff"] += -amount
            categories[category] += -amount
            categories_oneoff[category] += -amount
        elif rules.role(category, "loan"):
            sums["loans"] += -amount
            categories[category] += -amount
        else:
            sums["expenses"] += -amount
            categories[category] += -amount

        counts_in_groups = not (rules.role(category, "income") or rules.role(category, "pension") or transaction["oneoff"])
        if counts_in_groups:
            groups[rules.group(category)] += -amount

    recurring = collections.defaultdict(float)
    for transaction in rows:
        if transaction["amount"] >= 0 or transaction["oneoff"] or is_internal(rules, transaction["category"]):
            continue
        for item in recurring_items:
            if any(rules.matches(transaction, condition) for condition in item.get("transactions") or []):
                recurring[item["name"]] += -transaction["amount"]

    salary = salary_categories(rules)
    salary_days = sorted(int(transaction["date"][8:10]) for transaction in rows if transaction["category"] in salary)
    return dict(
        sums={key: r2(value) for key, value in sums.items()},
        categories=rounded_nonzero(categories),
        categories_oneoff=rounded_nonzero(categories_oneoff),
        groups=rounded_nonzero(groups),
        recurring={key: r2(value) for key, value in recurring.items()},
        payday=salary_days[0] if salary_days else None,
    )


def compact(rules, rows):
    """Regular rows of a month for the current-month forecast: date, name, category, amount, recurring candidate."""
    not_recurring = rules.raw.get("not_recurring") or []
    out = []
    for transaction in rows:
        if not regular(rules, transaction):
            continue
        recurring = rules.role(transaction["category"], "recurring")
        if recurring and any(rules.matches(transaction, condition) for condition in not_recurring):
            recurring = False
        out.append([
            transaction["date"][:10],
            display_name(rules, transaction),
            transaction["category"],
            r2(transaction["amount"]),
            1 if recurring else 0,
        ])
    return out


# ---------- datasets ----------

def months_rows(state, current_summary, current):
    out = []
    for month in sorted(state["months"]) + [current]:
        summary = current_summary if month == current else state["months"][month]
        sums = summary["sums"]
        out.append(dict(
            month=month,
            label=label(month),
            income=sums["income"],
            expenses=sums["expenses"],
            loans=sums["loans"],
            oneoff=sums["oneoff"],
            oneoff_income=sums["oneoff_income"],
            financing=sums["financing"],
            pension3=sums["pension3"],
            net=r2(sums["income"] - sums["expenses"] - sums["loans"] - sums["oneoff"]),
        ))
    return out


def periods(first, last_full):
    """Half years p1, p2, ... and quarters q1, q2, ... from the first year; they end at the last full month."""
    first_year = int(first[:4])
    last_year = int(month_add(last_full, 1)[:4])
    years = [str(year) for year in range(first_year, last_year + 1)]

    result = {}
    for index, year in enumerate(years):
        for half in range(2):
            start = f"{year}-{half * 6 + 1:02d}"
            end = min(f"{year}-{half * 6 + 6:02d}", last_full)
            result[f"p{index * 2 + half + 1}"] = (start, end)
    for index, year in enumerate(years):
        for quarter in range(4):
            start = f"{year}-{quarter * 3 + 1:02d}"
            end = min(f"{year}-{quarter * 3 + 3:02d}", last_full)
            result[f"q{index * 4 + quarter + 1}"] = (start, end)

    started = {key: value for key, value in result.items() if value[0] <= last_full}
    return started, years


def categories_rows(rules, state, current_summary, current, periods_by_key):
    months = sorted(state["months"]) + [current]

    def summary_of(month):
        return current_summary if month == current else state["months"][month]

    months_by_period = {}
    for key, (start, end) in periods_by_key.items():
        months_by_period[key] = [month for month in months if start <= month <= end]

    all_categories = {category for month in months for category in summary_of(month)["categories"]}
    categories = []
    for category in all_categories:
        values = {month: summary_of(month)["categories"].get(category, 0.0) for month in months}
        oneoff = {month: summary_of(month)["categories_oneoff"].get(category, 0.0) for month in months}
        total = sum(values.values())
        if abs(total) < 0.5:
            continue
        per_period = {}
        for key, period_months in months_by_period.items():
            if period_months:
                regular_total = sum(values[month] for month in period_months) - sum(oneoff[month] for month in period_months)
                per_period[key] = r2(regular_total / len(period_months))
            else:
                per_period[key] = 0.0
        kind = rules.label("loans") if rules.role(category, "loan") else rules.label("expenses")
        categories.append(dict(
            category=category,
            group=kind,
            total=r2(total),
            oneoff=r2(sum(oneoff.values())),
            **per_period,
            grp=rules.group(category),
        ))
    categories.sort(key=lambda item: -item["total"])

    groups = []
    for group in rules.group_order:
        members = [item for item in categories if item["grp"] == group]
        per_period = {key: r2(sum(item[key] for item in members)) for key in periods_by_key}
        groups.append(dict(grp=group, **per_period, total=r2(sum(item["total"] for item in members))))
    return categories, groups


def group_months_rows(rules, state):
    out = []
    for month in sorted(state["months"]):
        groups = state["months"][month]["groups"]
        for group in rules.group_order:
            if group in groups:
                out.append(dict(month=month, label=label(month), grp=group, amount=groups[group]))
    return out


def recurring_rows(rules, state, current_summary, current):
    items = rules.raw.get("recurring") or []
    subscriptions = subscription_kinds(rules)
    months = sorted(state["months"]) + [current]
    years = sorted({month[:4] for month in state["months"]})

    def summary_of(month):
        return current_summary if month == current else state["months"][month]

    out = []
    for item in items:
        name = item["name"]
        amounts = {month: summary_of(month)["recurring"][name] for month in months if name in summary_of(month)["recurring"]}
        if not amounts:
            continue
        row = dict(
            name=name,
            kind=item.get("kind", ""),
            yearly=bool(item.get("yearly")),
            first=min(amounts),
            last=max(amounts),
        )
        for year in years:
            year_amounts = [amount for month, amount in amounts.items() if month[:4] == year]
            row["months_" + year] = len(year_amounts)
            row["total_" + year] = round(sum(year_amounts), 2)
            row["med_" + year] = round(statistics.median(year_amounts), 2) if year_amounts else 0
        row["last_amt"] = round(amounts[max(amounts)], 2)
        if item.get("kind") in subscriptions:
            row["sub"] = item.get("sub", rules.label("other"))
        if item.get("ended"):
            row["ended"] = True
        out.append(row)
    return out


# ---------- transactions table ----------

def table_payee(rules, counterparty):
    """Counterparty without card or order numbers; names.rewrite rules first."""
    name = counterparty.strip()
    for rewrite in (rules.raw.get("names") or {}).get("rewrite") or []:
        name = re.sub(rewrite["match"], rewrite["name"], name)
    name = re.sub(r"[\s/*#_-]*\d{5,}.*$", "", name)
    name = re.sub(r"\s{2,}", " ", name).strip(" ,.-")
    return name or UNNAMED


def group_of(rules, category):
    if rules.role(category, "income") or rules.role(category, "oneoff_income"):
        return rules.label("income")
    group = rules.group(category)
    if group != rules.label("other"):
        return group
    if rules.role(category, "investment"):
        return rules.label("investments")
    if rules.role(category, "loan"):
        return rules.label("loans")
    return rules.label("other")


def payee_from_description(rules, category, description):
    """Payee for a row without a counterparty: a donation name, the bank fee payee, or the start of the description."""
    donation = re.match(r"Annetus:\s*(.+)", description)
    if donation:
        return donation.group(1).strip()
    fees = rules.settings.get("bank_fees") or {}
    if category in (fees.get("categories") or []):
        return fees.get("payee")
    return re.sub(r"[\d.,/-]+.*$", "", description).strip()[:40] or UNNAMED


def table_rows(rules, rows):
    out = []
    for transaction in rows:
        category = transaction["category"]
        if transaction["amount"] == 0 or is_internal(rules, category):
            continue
        description = transaction.get("description") or ""
        payee = table_payee(rules, transaction.get("counterparty") or "")
        if payee == UNNAMED:
            payee = payee_from_description(rules, category, description)

        card = CARD_DESCRIPTION.match(description)
        if card:
            parts = [part.strip() for part in card.group(3).split("\\")]
            name = parts[0]
            address = [part for part in parts[1:-1] if part]
            purchase_date, purchase_time, details = card.group(1), card.group(2), ", ".join(address)
        else:
            name = (transaction.get("counterparty") or "").strip()
            purchase_date, purchase_time, details = transaction["date"][:10], "", description

        booked = "" if transaction.get("pending") else (transaction.get("booked") or transaction["date"])[:10]
        out.append(dict(
            id=transaction["id"],
            date=transaction["date"][:10],
            bdate=booked,
            tdate=purchase_date,
            time=purchase_time,
            name=name or payee,
            payee=rules.payee_name(payee),
            amount=round(transaction["amount"], 2),
            desc=details[:120],
            category=category,
            grp=group_of(rules, category),
            oneoff=bool(transaction["oneoff"]),
        ))
    out.sort(key=lambda row: (row["date"], row["id"]))
    return out


def oneoff_kind(rules, row):
    category = row["category"]
    if rules.role(category, "oneoff_income"):
        return "Ühekordne tulu"
    if rules.role(category, "loan"):
        return "Laenuraha" if row["amount"] > 0 else "Laenu tagastus"
    return category


def is_oneoff_row(rules, row):
    category = row["category"]
    if row["oneoff"] or rules.role(category, "oneoff_income"):
        return True
    return rules.role(category, "loan") and row["amount"] > 0


def oneoff_rows(rules, table):
    out = []
    for row in table:
        if not is_oneoff_row(rules, row):
            continue
        out.append(dict(
            id=row["id"],
            date=row["date"],
            what=row["payee"],
            category=row["category"],
            type=oneoff_kind(rules, row),
            amount=row["amount"],
        ))
    return out
