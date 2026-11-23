"""Loans and leasing: payments from transactions (rules.json loan_rules), contract data and schedules (store loans/*.json).

Datasets: loans, future_loans (principal and interest per month), future_balance, loan_contracts, loan_cost, loan_cost_total.
Loan file fields: name, family, kind, monthly, status, note, balance, balance_note, rate, apr, rate_note, end, balloon,
amount, start, n, interest_total, fees, total, last_payment, fee_month, oneoff_fees [{year, amount}],
contract [{name, value}], schedule [{month, balance, payment?, interest?, insurance?}], no_transactions, balance_source: card.
"""
import collections
import glob
import os

from common import load_json, r2
from monthly import label, months_between

ACTIVE = ("Aktiivne", "active")
ENDED = ("Lõppenud", "ended")
# APR from which a loan counts as costly.
COSTLY_APR = 10
# Loan file fields copied to the loans dataset.
LOAN_FIELDS = [
    "family", "kind", "monthly", "status", "note", "balance", "balance_note", "rate", "apr", "rate_note",
    "end", "balloon", "amount", "start", "n", "interest_total", "fees", "total",
]


def read_loan_files(store_root):
    """Loans from loans/<name>.json (one loan or {"loans": [...]}); ended.json last. Largest monthly payment first."""
    def order(path):
        return (os.path.splitext(os.path.basename(path))[0] == "ended", path)

    loans = {}
    for path in sorted(glob.glob(os.path.join(store_root, "loans", "*.json")), key=order):
        data = load_json(path, {}) or {}
        for loan in data["loans"] if "loans" in data else [data]:
            loans[loan["name"]] = loan
    return dict(sorted(loans.items(), key=lambda item: -(item[1].get("monthly") or 0)))


def interest_from_balances(payment, previous_balance, balance):
    """Interest = payment minus the drop in balance (never below zero)."""
    return max(0.0, payment - (previous_balance - balance))


class Loans:
    def __init__(self, store_root, rules, transactions, balances, pending, current, last_full):
        self.R = rules
        self.cur = current
        self.last_full = last_full
        self.data = read_loan_files(store_root)
        self.txs = transactions
        self.balances = balances
        self.pending = pending
        self.rules = rules.raw.get("loan_rules") or []

    def schedule(self, name):
        return {str(row["month"]): row for row in self.data[name].get("schedule") or []}

    def fees(self):
        """Monthly fees {loan: amount} and one-off fees {(loan, year): amount}."""
        monthly = {}
        oneoff = {}
        for name, loan in self.data.items():
            if loan.get("fee_month"):
                monthly[name] = loan["fee_month"]
            for fee in loan.get("oneoff_fees") or []:
                oneoff[(name, int(fee["year"]))] = fee["amount"]
        return monthly, oneoff

    def with_schedule(self):
        """(name, kind, {month: balance}, start month, amount) of loans with a schedule."""
        out = []
        for name, loan in self.data.items():
            if not loan.get("schedule"):
                continue
            balances = {month: row["balance"] for month, row in self.schedule(name).items()}
            out.append((name, loan["kind"], balances, str(loan["start"])[:7], loan["amount"]))
        return out

    def scheduled_payment(self, name, row, is_last):
        """Payment of a schedule row without insurance (and without the balloon in the last month)."""
        loan = self.data[name]
        if not row:
            return 0
        if "payment" in row:
            balloon = (loan.get("balloon") or 0) if is_last else 0
            return round(row["payment"] - (row.get("insurance") or 0) - balloon, 2)
        if is_last:
            return loan.get("last_payment", loan["monthly"])
        return loan["monthly"]

    def future_payments(self, first_month):
        schedules = {name: self.schedule(name) for name, loan in self.data.items() if loan.get("schedule")}
        if not schedules:
            return []
        last_month = max(max(schedule) for schedule in schedules.values())
        out = []
        for month in months_between(first_month, last_month):
            for name, schedule in schedules.items():
                amount = self.scheduled_payment(name, schedule.get(month), month == max(schedule))
                out.append(dict(month=month, label=label(month), loan=name, amount=amount))
        return out

    def rule_of(self, transaction):
        return next((rule for rule in self.rules if self.R.matches(transaction, rule)), None)

    def loan_of(self, transaction):
        """(loan, family) of a loan payment, or None."""
        rule = self.rule_of(transaction)
        if not rule:
            return None
        name = rule["loan"]
        if name in self.data:
            return (name, self.data[name]["family"])
        return (name, name)

    def paid(self, name, month):
        """True if this month's payment of the loan is in the transactions."""
        for transaction in self.txs:
            if transaction["date"][:7] != month or transaction["amount"] >= 0 or transaction.get("oneoff"):
                continue
            rule = self.rule_of(transaction)
            if rule and rule["loan"] == name:
                return True
        return False

    def card_debt(self):
        """Credit card debt now including pending card payments (positive)."""
        account = self.R.settings.get("card_account")
        balance = self.balances.get(account)
        if balance is None:
            return 0.0
        pending = sum(payment["amount"] for payment in self.pending if payment["account"] == account)
        return r2(-(balance + pending))

    def balance(self, name):
        loan = self.data[name]
        if loan.get("schedule"):
            balances = {month: row["balance"] for month, row in self.schedule(name).items()}
            if self.cur in balances and self.paid(name, self.cur):
                return balances[self.cur]
            if self.last_full in balances:
                return balances[self.last_full]
            return balances[min(balances)]
        if loan.get("balance_source") == "card":
            return self.card_debt()
        return loan.get("balance")


# ---------- datasets ----------

def loan_rows(loans, years):
    """One row per loan: payments, one-off payments and money received (total and by year) and the loan file fields."""
    by_loan = collections.defaultdict(list)
    for transaction in loans.txs:
        key = loans.loan_of(transaction)
        if key:
            by_loan[key].append(transaction)
    for name, loan in loans.data.items():
        if loan.get("no_transactions") and not any(other == name for other, _ in by_loan):
            by_loan[(name, loan["family"])] = []

    def paid(rows):
        return round(-sum(row["amount"] for row in rows if row["amount"] < 0), 2)

    def paid_oneoff(rows):
        return round(-sum(row["amount"] for row in rows if row["amount"] < 0 and row["oneoff"]), 2)

    def received(rows):
        return round(sum(row["amount"] for row in rows if row["amount"] > 0), 2)

    rows = []
    for (name, family), transactions in by_loan.items():
        loan = loans.data.get(name, {})
        payment_dates = [row["date"] for row in transactions if row["amount"] < 0]
        row = dict(
            loan=name,
            family=family,
            kind=loan.get("kind", "Laen"),
            monthly=loan.get("monthly", 0),
            paid=paid(transactions),
            oneoff=paid_oneoff(transactions),
            received=received(transactions),
            first=min(payment_dates) if payment_dates else "",
            last=max(payment_dates) if payment_dates else "",
            status=loan.get("status", "?"),
            note=loan.get("note", ""),
        )
        for year in years:
            year_rows = [transaction for transaction in transactions if transaction["date"][:4] == year]
            row["paid_" + year] = paid(year_rows)
            row["oneoff_" + year] = paid_oneoff(year_rows)
            row["received_" + year] = received(year_rows)
        for field in LOAN_FIELDS:
            if field not in row:
                row[field] = loan.get(field)
        if name in loans.data:
            row["balance"] = loans.balance(name)
        rows.append(row)
    rows.sort(key=lambda row: (row["status"] not in ACTIVE, -row["monthly"], -row["paid"]))
    return rows


def future_balance_rows(loans, payments):
    months = sorted({payment["month"] for payment in payments})
    labels = {payment["month"]: payment["label"] for payment in payments}
    paths = {}
    for name, _kind, balances, start, amount in loans.with_schedule():
        schedule_start = min(balances)
        paths[name] = [balances.get(month, amount if start <= month < schedule_start else 0) for month in months]
    out = []
    for index, month in enumerate(months):
        out.append(dict(month=month, label=labels[month], balance=round(sum(paths[name][index] for name in paths), 2)))
    return out


def future_loan_rows(loans, payments, monthly_fees):
    """Future payments split into interest (with monthly fees) and principal."""
    schedules = {name: loans.schedule(name) for name in loans.data if loans.data[name].get("schedule")}
    out = []
    for payment in payments:
        schedule = schedules.get(payment["loan"], {})
        month = payment["month"]
        amount = payment["amount"]
        interest = 0.0
        if amount > 0 and month in schedule:
            if "interest" in schedule[month]:
                interest = schedule[month]["interest"]
            else:
                months = sorted(schedule)
                index = months.index(month)
                if index > 0:
                    previous = schedule[months[index - 1]]["balance"]
                else:
                    previous = loans.data[payment["loan"]]["amount"]
                interest = max(0.0, min(amount, amount - (previous - schedule[month]["balance"])))
            interest += monthly_fees.get(payment["loan"], 0)
        out.append(dict(
            month=month,
            label=payment["label"],
            loan=payment["loan"],
            amount=amount,
            interest=round(interest, 2),
            principal=round(amount - interest, 2),
        ))
    return out


def contract_rows(loans):
    out = []
    for name, loan in loans.data.items():
        for index, row in enumerate(loan.get("contract") or []):
            out.append(dict(loan=name, n=float(index), key=row["name"], value=row["value"]))
    return out


def next_interest(loans, name, schedule, amount, balance, payments_by_month, monthly_fees):
    """Interest of the next unpaid schedule payment, else balance × rate / 12."""
    loan = loans.data[name]
    rate = loan.get("rate") or 0

    def is_next(month):
        if schedule[month].get("payment") == 0:
            return False
        return month > loans.cur or (month == loans.cur and not loans.paid(name, loans.cur))

    upcoming = next((schedule[month] for month in sorted(schedule) if is_next(month)), None)
    if upcoming and upcoming.get("interest"):
        return upcoming["interest"]
    if not upcoming:
        return balance * rate / 100 / 12

    months = sorted(schedule)
    index = months.index(str(upcoming["month"]))
    previous = schedule[months[index - 1]]["balance"] if index > 0 else amount
    payment = upcoming.get("payment") or payments_by_month[name].get(str(upcoming["month"])) or loan.get("monthly", 0)
    if not payment:
        return balance * rate / 100 / 12
    return interest_from_balances(payment, previous, upcoming["balance"]) - monthly_fees.get(name, 0)


def interest_paid_in_year(loans, name, schedule, amount, payments_by_month, year):
    """Interest paid in a year (up to the last full month), from the schedule."""
    loan = loans.data[name]
    months = sorted(schedule)
    total = 0.0
    for index, month in enumerate(months):
        if month[:4] != year or month > loans.last_full:
            continue
        row = schedule[month]
        if "interest" in row:
            total += row["interest"]
            continue
        previous = schedule[months[index - 1]]["balance"] if index > 0 else amount
        payment = row.get("payment") or payments_by_month[name].get(month) or loan.get("monthly", 0)
        if month == months[0] and index == 0:
            payment = row.get("payment") or loan.get("monthly", 0)
        total += interest_from_balances(payment, previous, row["balance"])
    return total


def cost_rows(loans, rows, payments, years):
    """Cost of borrowing: interest and fees per month and year; ended loans: paid minus received."""
    monthly_fees, oneoff_fees = loans.fees()
    rows_by_loan = {row["loan"]: row for row in rows}
    payments_by_month = collections.defaultdict(dict)
    for payment in payments:
        payments_by_month[payment["loan"]][payment["month"]] = payment["amount"]

    cost = []
    for name, kind, _balances, _start, amount in loans.with_schedule():
        loan = loans.data[name]
        schedule = loans.schedule(name)
        balance = rows_by_loan.get(name, {}).get("balance") or 0
        rate = loan.get("rate") or 0
        interest = next_interest(loans, name, schedule, amount, balance, payments_by_month, monthly_fees)
        fee = monthly_fees.get(name, 0)
        by_year = {}
        for year in years:
            paid = interest_paid_in_year(loans, name, schedule, amount, payments_by_month, year)
            by_year["paid_" + year] = r2(paid + oneoff_fees.get((name, int(year)), 0))
        cost.append(dict(
            loan=name,
            kind=kind,
            balance=r2(balance),
            rate=rate,
            apr=loan.get("apr") or rate,
            interest_month=r2(interest),
            fee_month=fee,
            cost_month=r2(interest + fee),
            cost_year=r2((interest + fee) * 12),
            **by_year,
            note="maksegraafiku järgi",
        ))

    scheduled = {row["loan"] for row in cost}
    for name, row in rows_by_loan.items():
        if row["status"] not in ENDED or not row.get("received") or name in scheduled:
            continue
        if row["received"] < 0.8 * row["paid"]:
            continue
        total = r2(row["paid"] - row["received"])
        if total <= 0:
            continue
        last_year = row.get("last", "")[:4]
        cost.append(dict(
            loan=name,
            kind=row["kind"],
            balance=0.0,
            rate=None,
            apr=None,
            interest_month=0.0,
            fee_month=0.0,
            cost_month=0.0,
            cost_year=0.0,
            **{"paid_" + year: total if last_year == year else 0.0 for year in years},
            note="makstud miinus saadud, kokku " + str(total) + " €",
        ))
    cost.sort(key=lambda row: -row["cost_year"])
    return cost


def cost_total_rows(cost, years):
    cost_month = sum(row["cost_month"] for row in cost)
    interest_month = sum(row["interest_month"] for row in cost)
    rows = [
        dict(metric="cost_month", value=r2(cost_month)),
        dict(metric="cost_year", value=r2(cost_month * 12)),
        dict(metric="interest_month", value=r2(interest_month)),
        dict(metric="fees_month", value=r2(cost_month - interest_month)),
    ]
    for year in years:
        rows.append(dict(metric="paid_" + year, value=r2(sum(row["paid_" + year] for row in cost))))
    rows.append(dict(metric="costly_month", value=r2(sum(row["cost_month"] for row in cost if (row["apr"] or 0) >= COSTLY_APR))))
    rows.append(dict(metric="balance", value=r2(sum(row["balance"] for row in cost))))
    return rows


def build(loans, years):
    rows = loan_rows(loans, years)
    payments = loans.future_payments(loans.cur)
    monthly_fees, _oneoff_fees = loans.fees()
    cost = cost_rows(loans, rows, payments, years)
    return {
        "loans": rows,
        "future_balance": future_balance_rows(loans, payments),
        "future_loans": future_loan_rows(loans, payments, monthly_fees),
        "loan_contracts": contract_rows(loans),
        "loan_cost": cost,
        "loan_cost_total": cost_total_rows(cost, years),
    }
