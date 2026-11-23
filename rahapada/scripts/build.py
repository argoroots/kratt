"""Rahapada: categorise transactions and build the dashboard datasets.

The work folder is a copy of the store (reference/store.md): rules.json, tx/*.json, card_times.json and the
optional investment, loan and balance files. Everything is recalculated from the full history on every run.

Usage:
  python3 build.py WORK [--today YYYY-MM-DD] [--store STORE_SLUG]

Writes WORK/out/datasets/<id>.json, WORK/out/config.js, WORK/out/card_times.json, WORK/out/state.json
and WORK/out/report.json.
"""
import argparse
import collections
import hashlib
import json
import os

import current
import invest
import loans
import monthly
import outlook
import transactions
from common import load_json, save_json, today_str
from rules import Rules
from store import Store

ALL_DATASETS = [
    "month_days", "month_recurring", "month_summary", "month_categories", "month_groups", "months", "categories",
    "groups", "group_months", "recurring", "oneoffs", "transactions", "returns", "portfolio_change", "portfolio",
    "comparison", "expected_dividends", "investment_months", "loans", "future_loans", "future_balance",
    "loan_contracts", "loan_cost", "loan_cost_total", "assets", "net_worth", "pension_view", "cashflow",
    "cashflow_summary", "trips", "trip_transactions", "savings_rate", "events", "logos",
]
INVESTMENT_DATASETS = ["returns", "portfolio_change", "portfolio", "comparison", "expected_dividends"]
GOALS = ["month_net", "buffer", "net_worth", "costly_loans"]
# Card reservation times are needed only until the payment is booked.
CARD_TIMES_MONTHS = 3


class Output:
    """Writes datasets to WORK/out/datasets and remembers which ones are empty and their hashes."""

    def __init__(self, work):
        self.directory = os.path.join(work, "out", "datasets")
        if os.path.isdir(self.directory):
            for name in os.listdir(self.directory):
                os.remove(os.path.join(self.directory, name))
        os.makedirs(self.directory, exist_ok=True)
        self.hashes = {}
        self.empty = set()

    def put(self, dataset, rows):
        save_json(os.path.join(self.directory, dataset + ".json"), rows)
        if rows:
            self.empty.discard(dataset)
        else:
            self.empty.add(dataset)
        text = json.dumps(rows, sort_keys=True, ensure_ascii=False)
        self.hashes[dataset] = hashlib.sha1(text.encode()).hexdigest()

    def read(self, dataset):
        return load_json(os.path.join(self.directory, dataset + ".json"), [])

    def fill_missing(self):
        """Every dataset exists, empty when there is no data for it, so the page can hide what is not used."""
        for dataset in ALL_DATASETS:
            if dataset not in self.hashes:
                self.put(dataset, [])


def parse_arguments():
    parser = argparse.ArgumentParser()
    parser.add_argument("work")
    parser.add_argument("--today", default=None)
    parser.add_argument("--store", default=None, help="slug of the storage artifact, kept in config.js")
    return parser.parse_args()


def account_balances(work):
    """Balances of EUR accounts now (last month's end) and at the start of the data."""
    rows = load_json(os.path.join(work, "balances.json"), []) or []
    now, start = {}, {}
    for row in sorted(rows, key=lambda row: row["month"]):
        if row.get("currency", "EUR") != "EUR":
            continue
        now[row["account"]] = row["end"]
        start.setdefault(row["account"], row["start"])
    return now, start


def page_config(rules, periods, store_slug, empty):
    goals = rules.raw.get("goals") or {}
    hidden_parts = {"goal_" + goal for goal in GOALS if not goals.get(goal)}
    pension = (rules.raw.get("forecast") or {}).get("pension") or {}
    if not pension.get("pillar2_withdrawn"):
        # page parts about a withdrawn II pillar are hidden like empty datasets
        hidden_parts.add("pillar2_withdrawn")
    return {
        "periods": periods,
        "goals": goals,
        "store": store_slug,
        # goals not set are hidden on the page like empty datasets
        "empty": sorted(empty | hidden_parts),
        "labels": rules.labels,
        "recurring_kinds": rules.raw.get("recurring_kinds") or [],
        "subscription_groups": rules.settings.get("subscription_groups") or [],
        "icons": rules.settings.get("icons") or {},
    }


def print_summary(current_month, summary, window, closed, changed, uncategorised):
    print(f"Kuu {current_month}: tulem seni {summary['net_so_far']:.2f}, kuu lõpuks {summary['forecast_end']:.2f} "
          f"({summary['forecast_lo']} … {summary['forecast_hi']}); aken {len(window)} kuud")
    if closed:
        print(f"Täiskuud: {closed[0]} … {closed[-1]} ({len(closed)})")
    print("Muutunud andmestikud:", ", ".join(changed) or "-")
    if uncategorised:
        print(f"Kategooriata {len(uncategorised)} kannet:")
        for row in uncategorised[:60]:
            print(f"  {row['date']} {row['amount']:>9.2f}  {row['payee']} | {row['desc'][:60]}")


def main():
    arguments = parse_arguments()
    work = arguments.work
    today = today_str(arguments.today)
    rules_path = os.path.join(work, "rules.json")
    if not os.path.exists(rules_path):
        raise SystemExit(f"{work}: rules.json puudub")
    rules = Rules(load_json(rules_path, {}))
    store = Store(work)

    # Everything is recalculated from the full history in the store; state keeps only card times and hashes.
    old_state = load_json(os.path.join(work, "state.json"), None) or {}
    card_times = load_json(os.path.join(work, "card_times.json"), None) or old_state.get("card_times", [])
    state = {
        "version": 3, "months": {}, "recent": {}, "archives": {}, "oneoffs": [],
        "hashes": old_state.get("hashes", {}), "card_times": card_times,
    }
    all_transactions = transactions.prepare(work, rules, state)
    # Accounts kept only for balances (e.g. a savings deposit) are not part of income and spending.
    txs = [row for row in all_transactions if row["account"] not in rules.track_only]
    by_month = collections.defaultdict(list)
    for row in txs:
        by_month[row["date"][:7]].append(row)

    if arguments.today is None:
        real = [row for row in txs if not monthly.is_internal(rules, row["category"])]
        current_month = max([row["date"][:7] for row in real] + [today[:7]])
    else:
        current_month = today[:7]
    output = Output(work)
    put = output.put

    # ---------- closed months ----------
    recurring_items = rules.raw.get("recurring") or []
    closed = []
    for month in sorted(by_month):
        if month >= current_month:
            continue
        rows = by_month[month]
        state["months"][month] = monthly.summarise(rules, month, rows, recurring_items)
        state["recent"][month] = monthly.compact(rules, rows)
        table = monthly.table_rows(rules, rows)
        state["archives"][month] = table
        other_oneoffs = [row for row in state["oneoffs"] if row["date"][:7] != month]
        state["oneoffs"] = other_oneoffs + monthly.oneoff_rows(rules, table)
        closed.append(month)

    last_full = monthly.month_add(current_month, -1)
    window_size = int(rules.settings.get("window_months", 3))
    window_first = monthly.month_add(last_full, -(window_size - 1))
    window = [month for month in monthly.months_between(window_first, last_full) if month in state["months"]]
    keep = set(window) | {last_full}
    state["recent"] = {month: rows for month, rows in state["recent"].items() if month in keep}

    # ---------- current month ----------
    current_rows = by_month.get(current_month, [])
    current_summary = monthly.summarise(rules, current_month, current_rows, recurring_items)
    compact_rows = [row for month in sorted(state["recent"]) for row in state["recent"][month]]
    compact_rows += monthly.compact(rules, current_rows)
    last_date = None
    if current_rows:
        real_dates = [row["date"][:10] for row in current_rows if not monthly.is_internal(rules, row["category"])]
        last_date = max(real_dates or [None])
    month_view = current.build(rules, compact_rows, window, current_month, today, last=last_date)
    put("month_days", month_view["days"])
    put("month_recurring", month_view["expected"])
    put("month_summary", month_view["summary"])
    put("month_categories", month_view["categories"])
    put("month_groups", month_view["groups"])

    # ---------- months, categories, recurring, one-offs ----------
    first = min(state["months"]) if state["months"] else current_month
    periods, years = monthly.periods(first, last_full)
    months_rows = monthly.months_rows(state, current_summary, current_month)
    put("months", months_rows)
    categories, groups = monthly.categories_rows(rules, state, current_summary, current_month, periods)
    put("categories", categories)
    put("groups", groups)
    put("group_months", monthly.group_months_rows(rules, state))
    put("recurring", monthly.recurring_rows(rules, state, current_summary, current_month))
    table = monthly.table_rows(rules, current_rows)
    table_all = [row for month in sorted(state["archives"]) for row in state["archives"][month]] + table
    oneoffs = state["oneoffs"] + monthly.oneoff_rows(rules, table)
    put("oneoffs", sorted(oneoffs, key=lambda row: row["date"]))

    keep_from = monthly.month_add(current_month, -CARD_TIMES_MONTHS)
    state["card_times"] = [row for row in state.get("card_times", []) if row["time"][:7] >= keep_from]

    # ---------- investments ----------
    investments = {}
    if store.trades() or store.json("invest/funds.json"):
        price_date = store.price_date() or today
        data_date = max(row.get("booked", row["date"]) for row in txs if not row.get("pending"))
        investment_periods = dict(
            first=first, years=years, price_month=price_date[:7], price_date=price_date,
            data_date=data_date, last_full=last_full,
        )
        investments = invest.build(store, investment_periods)
        for dataset in INVESTMENT_DATASETS:
            put(dataset, investments[dataset])
        put("investment_months", invest.investment_months(rules, months_rows, investments, last_full))
        table_all = table_all + invest.table_rows(rules, store, investments)

    # ---------- loans, assets, forecast, trips ----------
    full_table = sorted(table_all, key=lambda row: (row["date"], str(row["id"])))
    put("transactions", full_table)
    balances_now, balances_start = account_balances(work)
    pending = [row for row in txs if row.get("pending")]
    loan_data = loans.Loans(work, rules, txs, balances_now, pending, current_month, last_full)
    if loan_data.data:
        for dataset, rows in loans.build(loan_data, years).items():
            put(dataset, rows)

    if rules.raw.get("worth"):
        data_months = [row["month"] for row in months_rows]
        items, net_worth = outlook.worth(rules, loan_data, investments, all_transactions, full_table, balances_start, current_month, data_months)
        put("assets", items)
        put("net_worth", net_worth)
        pension = outlook.pension_view(rules, items, investments.get("returns", []), current_month)
        if pension:
            put("pension_view", pension)
    if rules.raw.get("forecast") or loan_data.data:
        cashflow, cashflow_summary = outlook.cashflow(rules, loan_data, months_rows, full_table, month_view["summary"], window, current_month)
        put("cashflow", cashflow)
        put("cashflow_summary", cashflow_summary)
    trip_rows, trip_transactions = outlook.trips(rules, full_table)
    put("trips", trip_rows)
    put("trip_transactions", trip_transactions)
    if investments and loan_data.data:
        savings = outlook.savings_rate(rules, loan_data, months_rows, output.read("investment_months"), current_month[:4], last_full)
        put("savings_rate", savings)
    events = load_json(os.path.join(work, "events.json"), None)
    if events is not None:
        put("events", events)
    put("logos", load_json(os.path.join(work, "logos.json"), []) or [])
    output.fill_missing()

    # ---------- page config ----------
    price_date = store.price_date() or (last_date or today)
    if window:
        window_range = [window[0], window[-1]]
        window_previous = [monthly.month_add(window[0], -12), monthly.month_add(window[-1], -12)]
    else:
        window_range = window_previous = [last_full, last_full]
    page_periods = {
        "data_date": last_date or today,
        "current": current_month,
        "last_full": last_full,
        "price_date": price_date,
        "price_month": price_date[:7],
        "first": first,
        "years": years,
        "window": window_range,
        "window_prev": window_previous,
        "periods": {key: list(value) for key, value in periods.items()},
    }
    config = page_config(rules, page_periods, arguments.store, output.empty)
    with open(os.path.join(work, "out", "config.js"), "w", encoding="utf-8") as file:
        file.write("window.RAHAPADA = " + json.dumps(config, ensure_ascii=False) + ";\n")

    # ---------- state and report ----------
    previous_hashes = state.get("hashes", {})
    changed = sorted(dataset for dataset, value in output.hashes.items() if previous_hashes.get(dataset) != value)
    hashes = {**previous_hashes, **output.hashes}
    save_json(os.path.join(work, "out", "state.json"), {"version": 3, "hashes": hashes, "updated": today})
    save_json(os.path.join(work, "out", "card_times.json"), state["card_times"])
    uncategorised = []
    for row in txs:
        if row.get("uncategorised") and not monthly.is_internal(rules, row["category"]) and row["amount"]:
            uncategorised.append(monthly.table_rows(rules, [row])[0])
    summary = {row["metric"]: row["value"] for row in month_view["summary"]}
    report = {"months": closed, "changed_datasets": changed, "uncategorised": uncategorised, "current": summary}
    save_json(os.path.join(work, "out", "report.json"), report)
    print_summary(current_month, summary, window, closed, changed, uncategorised)


if __name__ == "__main__":
    main()
