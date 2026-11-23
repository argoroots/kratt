"""Payees of the user's transactions, for proposing groups, categories and rules.

Usage:
  python3 payees.py WORK [--out WORK/payees.json] [--top 80]
  python3 payees.py WORK --groups        # proposal table: group -> category -> monthly average, biggest payees

Reads WORK/rules.json and WORK/tx/*.json like build.py. For every payee (name after rules.json `names`
and `payees`): number of transactions, money out and in, months with payments, typical (median) amount,
whether it looks monthly, the category the rules give now, accounts and a few descriptions.
Writes all payees to --out (largest money first) and prints the top ones.
"""
import argparse
import collections
import os
import statistics

import transactions
from common import load_json, r2, save_json
from rules import Rules

SAMPLE_DESCRIPTIONS = 3
# A payee looks monthly when it has payments in at least this many months
# and in most months between its first and last payment.
MONTHLY_MIN_MONTHS = 3
MONTHLY_COVERAGE = 0.75


def month_number(month):
    return int(month[:4]) * 12 + int(month[5:7])


def looks_monthly(rows):
    months = {row["date"][:7] for row in rows}
    if len(months) < MONTHLY_MIN_MONTHS:
        return False
    span = month_number(max(months)) - month_number(min(months)) + 1
    return len(months) / span >= MONTHLY_COVERAGE


def summary(name, rows, label_other):
    money_out = -sum(row["amount"] for row in rows if row["amount"] < 0)
    money_in = sum(row["amount"] for row in rows if row["amount"] > 0)
    months = sorted({row["date"][:7] for row in rows})
    categories = collections.Counter(row["category"] for row in rows)
    category, _ = categories.most_common(1)[0]
    descriptions = []
    for row in rows:
        text = (row.get("description") or "").strip()
        if text and text not in descriptions:
            descriptions.append(text)
        if len(descriptions) == SAMPLE_DESCRIPTIONS:
            break
    return dict(
        payee=name,
        count=len(rows),
        out=r2(money_out),
        **{"in": r2(money_in)},
        months=len(months),
        first=rows[0]["date"],
        last=rows[-1]["date"],
        median=r2(statistics.median(row["amount"] for row in rows)),
        monthly=looks_monthly(rows),
        card=sum(1 for row in rows if (row.get("description") or "").startswith("(..")),
        category=None if category == label_other else category,
        internal=all(row.get("internal") for row in rows),
        accounts=sorted({row["account"] for row in rows}),
        counterparty_accounts=sorted({row["counterparty_account"] for row in rows if row.get("counterparty_account")})[:3],
        descriptions=descriptions,
    )


def group_table(rules, rows):
    """Group -> category -> average per month and the biggest payees, for showing the proposal to the user."""
    months = len({row["date"][:7] for row in rows}) or 1
    by_category = collections.defaultdict(list)
    for row in rows:
        if row.get("internal") or rules.role(row["category"], "internal"):
            continue
        by_category[row["category"]].append(row)

    def group_of(category):
        if rules.role(category, "income") or rules.role(category, "oneoff_income"):
            return rules.label("income")
        return rules.group(category)

    groups = collections.defaultdict(list)
    for category, category_rows in by_category.items():
        total = sum(row["amount"] for row in category_rows)
        payees = collections.Counter()
        for row in category_rows:
            payees[row["payee_bank"] or "(nimeta)"] += abs(row["amount"])
        top = ", ".join(name for name, _ in payees.most_common(4))
        groups[group_of(category)].append((category, total / months, len(category_rows), top))

    order = [rules.label("income")] + list(rules.group_order) + sorted(groups)
    printed = set()
    print(f"{months} kuud; keskmine kuus (miinus = kulu)")
    for group in order:
        if group in printed or group not in groups:
            continue
        printed.add(group)
        items = sorted(groups[group], key=lambda item: item[1])
        print(f"\n{group}: {sum(item[1] for item in items):.0f} € kuus")
        for category, average, count, top in items:
            print(f"  {category[:34]:34} {average:>8.0f} € {count:>5} kannet  {top}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("work")
    parser.add_argument("--out", default=None)
    parser.add_argument("--top", type=int, default=80)
    parser.add_argument("--groups", action="store_true", help="print the group and category table instead")
    arguments = parser.parse_args()

    rules = Rules(load_json(os.path.join(arguments.work, "rules.json"), {}))
    rows = transactions.prepare(arguments.work, rules, {"card_times": []})
    rows = [row for row in rows if not row.get("pending") and row["account"] not in rules.track_only]

    if arguments.groups:
        group_table(rules, rows)
        return

    by_payee = collections.defaultdict(list)
    for row in sorted(rows, key=lambda row: row["date"]):
        by_payee[row["payee_bank"] or "(nimeta)"].append(row)
    payees = [summary(name, payee_rows, rules.label("other")) for name, payee_rows in by_payee.items()]
    payees.sort(key=lambda item: -(item["out"] + item["in"]))

    out = arguments.out or os.path.join(arguments.work, "payees.json")
    save_json(out, payees)
    total_out = sum(item["out"] for item in payees if not item["internal"])
    print(f"{len(payees)} saajat, {len(rows)} kannet, välja kokku {total_out:.0f} € -> {out}")
    print(f"{'saaja':32} {'kandeid':>7} {'välja':>9} {'sisse':>9} {'kuid':>4}  kuine  kategooria")
    for item in payees[:arguments.top]:
        flags = "jah" if item["monthly"] else ""
        if item["internal"]:
            flags = "oma"
        print(f"{item['payee'][:32]:32} {item['count']:>7} {item['out']:>9.0f} {item['in']:>9.0f} {item['months']:>4}  {flags:5}  {item['category'] or '-'}")


if __name__ == "__main__":
    main()
