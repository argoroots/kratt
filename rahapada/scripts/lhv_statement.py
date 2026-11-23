"""Convert LHV connection statements (get_account_statement results) into Rahapada transactions.

A large statement result does not come into the conversation: the tool saves it to a file and says where. Give those
files to this script as they are (the plain JSON, or the saved [{"type": "text", "text": ...}] form).

Usage:
  python3 lhv_statement.py WORK --account NAME FILE [FILE ...] [--balances] [--as tx|invest|deposit] [--symbol SYM]

--as tx       (default) bank account: rows into WORK/tx/
--as invest   investment (stock) account: rows into WORK/invest/account.json, not into tx/
--as deposit  savings deposit: rows into tx/ (mark the account track_only in rules.json)
              and into WORK/invest/deposit.json for its interest

Writes the rows into WORK/tx/<YYYY-MM>.json (merge_by_month: the same id replaces the old row, old pending rows of the
account are dropped). With --balances (call the statements with includeBalances=true) also writes the account's
month start and end balances into WORK/balances.json, from the statement's starting balance and its transactions.
Rows in another currency than EUR keep their currency; the calculations use EUR rows only.
"""
import argparse
import collections
import json
import os

from common import load_json, merge_by_month, month_add, save_json


def read_statement(path):
    with open(path, encoding="utf-8") as file:
        data = json.load(file)
    if isinstance(data, list):
        # saved tool result: [{"type": "text", "text": "<json>"}]
        data = json.loads("".join(part.get("text", "") for part in data if isinstance(part, dict)))
    if not data.get("success", True) or data.get("error"):
        raise SystemExit(f"{path}: {data.get('error')}")
    return data["statement"]


def replace_period(old, new):
    """Rows of new, plus old rows outside the days new covers."""
    if not new:
        return old
    first = min(row["time"][:10] for row in new)
    last = max(row["time"][:10] for row in new)
    return [row for row in old if not (first <= row["time"][:10] <= last)] + new


def counterparty(transaction):
    """The other party: creditor of a payment out, debtor of a payment in."""
    payment = transaction.get("paymentData") or {}
    party = payment.get("creditor") if transaction["amount"] < 0 else payment.get("debtor")
    return party or {}


def rows_of(statement, account):
    out = []
    # One reference can have several rows (e.g. interest and its income tax): later ones get ":2", ":3", ...
    seen = collections.Counter()
    for transaction in statement.get("transactions") or []:
        party = counterparty(transaction)
        reference = str(transaction["bankReference"])
        seen[reference] += 1
        row_id = reference if seen[reference] == 1 else f"{reference}:{seen[reference]}"
        out.append(dict(
            id=row_id,
            account=account,
            booked=transaction["settlementDtime"][:10],
            amount=round(float(transaction["amount"]), 2),
            currency=transaction.get("currency") or "EUR",
            counterparty=party.get("name") or "",
            counterparty_account=party.get("accountNo") or "",
            description=transaction.get("description") or "",
            card=(transaction.get("transactionType") or {}).get("family") == "CCRD",
        ))
    for reservation in statement.get("reservations") or []:
        out.append(dict(
            id="res:" + str(reservation.get("bankReference") or reservation["reservationDtime"]),
            account=account,
            booked=None,
            amount=round(float(reservation["amount"]), 2),
            currency=reservation.get("currency") or "EUR",
            counterparty="",
            counterparty_account="",
            description=reservation.get("description") or "",
            card=True,
            pending=True,
            reserved_at=reservation["reservationDtime"],
        ))
    return out


def month_balances(statement, account, rows):
    """Month start and end balances from the statement's starting balance and its EUR rows."""
    balances = statement.get("balances") or []
    start = next((b for b in balances if b["balanceType"] == "STARTING_BALANCE" and b["currency"] == "EUR"), None)
    if not start:
        return []
    # The starting balance is at the start of the first day (local midnight, shown in UTC the evening before).
    first = min((row["booked"] for row in rows if row["booked"]), default=None)
    if not first:
        return []
    by_month = collections.defaultdict(float)
    for row in rows:
        if row["booked"] and row["currency"] == "EUR":
            by_month[row["booked"][:7]] += row["amount"]

    out = []
    balance = float(start["amount"])
    month = first[:7]
    while month <= max(by_month):
        end = round(balance + by_month.get(month, 0.0), 2)
        out.append(dict(month=month, account=account, currency="EUR", start=round(balance, 2), end=end))
        balance = end
        month = month_add(month, 1)
    return out


def statement_rows(statements, fields):
    """Plain rows of all statements: time, description, amount (+ currency and counterparty for the investment account)."""
    out = []
    for statement in statements:
        for transaction in statement.get("transactions") or []:
            row = dict(
                time=transaction["settlementDtime"],
                description=transaction.get("description") or "",
                amount=round(float(transaction["amount"]), 2),
            )
            if "currency" in fields:
                row["currency"] = transaction.get("currency") or "EUR"
            if "counterparty" in fields:
                row["counterparty"] = counterparty(transaction).get("name") or ""
            out.append(row)
    return out


def save_investment_account(work, account, statements):
    # All rows of the statements replace the old rows of the same period (one reference can have several rows).
    new = statement_rows(statements, ("currency", "counterparty"))
    path = os.path.join(work, "invest", "account.json")
    rows = replace_period(load_json(path, []) or [], new)
    save_json(path, sorted(rows, key=lambda row: row["time"]))
    print(f"{account}: {len(new)} rida -> invest/account.json")


def save_deposit(work, account, symbol, statements):
    path = os.path.join(work, "invest", "deposit.json")
    deposit = load_json(path, None) or dict(name=account, symbol=symbol, rows=[])
    new = statement_rows(statements, ())
    deposit["rows"] = sorted(replace_period(deposit["rows"], new), key=lambda row: row["time"])
    save_json(path, deposit)
    print(f"{account}: {len(deposit['rows'])} rida -> invest/deposit.json")


def save_balances(work, account, statements):
    new = []
    for statement in statements:
        new += month_balances(statement, account, rows_of(statement, account))
    path = os.path.join(work, "balances.json")
    new_months = {row["month"] for row in new}
    old = [row for row in load_json(path, []) or [] if not (row["account"] == account and row["month"] in new_months)]
    save_json(path, sorted(old + new, key=lambda row: (row["account"], row["month"])))
    if new:
        print(f"Jäägid: {new[0]['month']} … {new[-1]['month']}, lõpus {new[-1]['end']}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("work")
    parser.add_argument("--account", required=True, help="account name as in rules.json")
    parser.add_argument("files", nargs="+")
    parser.add_argument("--balances", action="store_true")
    parser.add_argument("--as", dest="kind", default="tx", choices=["tx", "invest", "deposit"])
    parser.add_argument("--symbol", default="DEP", help="deposit symbol for --as deposit")
    arguments = parser.parse_args()

    statements = [read_statement(path) for path in arguments.files]
    statements.sort(key=lambda statement: min((t["settlementDtime"] for t in statement.get("transactions") or []), default="9"))

    if arguments.kind == "invest":
        save_investment_account(arguments.work, arguments.account, statements)
    else:
        rows = [row for statement in statements for row in rows_of(statement, arguments.account)]
        months = merge_by_month(rows, os.path.join(arguments.work, "tx"))
        pending = sum(1 for row in rows if row.get("pending"))
        print(f"{arguments.account}: {len(rows)} kannet ({pending} ootel), kuud {months[0]} … {months[-1]}")
    if arguments.kind == "deposit":
        save_deposit(arguments.work, arguments.account, arguments.symbol, statements)
    if arguments.balances:
        save_balances(arguments.work, arguments.account, statements)


if __name__ == "__main__":
    main()
