"""Assets and net worth, cash-flow forecast, trips, pension view, savings rate.

Settings in rules.json:
  worth:     items (assets and debts now), cash_accounts, card_account, deposit, extra_cash, pension2, cars, backfill
  forecast:  months, invest_per_month, trips_per_year, trips_split, tax_rate, refund_month, leasing (Euribor), pension
  trips:     [{name, from, to, start?, transactions?: [conditions]}]
"""
import collections

from common import r2
from monthly import label, month_add, months_between


def is_booked_eur(transaction, account):
    return (transaction["account"] == account
            and not transaction.get("pending")
            and transaction.get("currency", "EUR") == "EUR")


def trip_categories(rules):
    return set(rules.settings.get("trip_categories") or [])


# ---------- assets and net worth ----------

class Worth:
    """Asset and debt items now, and assets, debts and net worth at each month end."""

    def __init__(self, rules, loans, investments, transactions, table, start_balances, current, data_months):
        self.rules = rules
        self.loans = loans
        self.transactions = transactions
        self.table = table
        self.start_balances = start_balances
        self.current = current
        self.settings = rules.raw.get("worth") or {}
        self.portfolio = investments.get("portfolio", [])
        self.pension_funds = {}
        for fund in investments.get("returns", []):
            if fund.get("kind") == "pension":
                self.pension_funds[fund["symbol"]] = fund["value"]
        self.deposit_account = self.settings.get("deposit_account")
        self.cash_accounts = self.settings.get("cash_accounts", [])
        self.portfolio_by_month = investments.get("portfolio_change") or [dict(month=month, value=0.0) for month in data_months]
        self.months = [row["month"] for row in self.portfolio_by_month]

    # ---- items now ----
    def account_total(self, account):
        return sum(transaction["amount"] for transaction in self.transactions if is_booked_eur(transaction, account))

    def item_value(self, item):
        source = item["source"]
        if source == "portfolio":
            return r2(sum(position["value"] for position in self.portfolio))
        if source == "funds":
            return r2(sum(self.pension_funds.get(fund, 0) for fund in item["funds"]))
        if source == "deposit":
            account = self.deposit_account
            return r2(self.start_balances.get(account, 0) + self.account_total(account))
        if source == "accounts":
            cash = sum(self.loans.balances.get(account, 0) for account in self.cash_accounts)
            return r2(cash + float(self.settings.get("extra_cash", 0)))
        if source == "card":
            return self.loans.card_debt()
        if source == "loan":
            return self.loans.balance(item["loan"])
        if source == "manual":
            return item["value"]
        raise SystemExit("worth item: unknown source " + source)

    def items(self):
        out = []
        for item in self.settings.get("items", []):
            out.append(dict(item=item["name"], side=item["side"], value=self.item_value(item), note=item.get("note", "")))
        return out

    # ---- month ends ----
    def month_end_balances(self, account):
        by_month = collections.defaultdict(float)
        for transaction in self.transactions:
            if is_booked_eur(transaction, account):
                by_month[transaction.get("booked", transaction["date"])[:7]] += transaction["amount"]
        balances = {}
        balance = self.start_balances.get(account, 0.0)
        for month in self.months:
            balance += by_month.get(month, 0)
            balances[month] = round(balance, 2)
        return balances

    def zero_by_month(self):
        return {month: 0.0 for month in self.months}

    def balance_from_later_payments(self, flows):
        """Balance of an ended loan at each month end: minus the sum of later payments (0 before the money came)."""
        by_month = collections.defaultdict(float)
        for date, amount in flows:
            by_month[date[:7]] += amount
        first = min(by_month) if by_month else None
        balances = {}
        for month in self.months:
            balances[month] = round(0.0 - sum(amount for other, amount in by_month.items() if other > month), 2)
            if first and month < first and by_month[first] > 0:
                balances[month] = 0.0
        return balances

    def backfilled_loans(self):
        """Ended loans without a schedule (worth.backfill): balance estimated from the payments."""
        result = {}
        for backfill in self.settings.get("backfill", []):
            def belongs(row):
                transaction = dict(row, description=row.get("desc", ""))
                if not self.rules.matches(transaction, backfill.get("when", {})):
                    return False
                return not any(self.rules.matches(transaction, rule) for rule in backfill.get("unless", []))

            flows = []
            for row in self.table:
                if row["category"] == backfill["category"] and belongs(row):
                    flows.append(((row.get("tdate") or row["date"]), row["amount"]))
            balances = self.balance_from_later_payments(flows)
            result[backfill["name"]] = {month: max(0.0, amount) for month, amount in balances.items()}
        return result

    def scheduled_balance(self, month, schedule, start_month, start_balance, paid):
        """Loan balance at a month end from the schedule; this month's balance only after this month's payment."""
        if month < start_month:
            return 0.0
        if month == self.current and month != start_month and not paid:
            previous = self.months[-2]
            return schedule[previous] if previous in schedule else start_balance
        return schedule[month] if month in schedule else start_balance

    def scheduled_loans(self):
        result = {}
        for name, _kind, schedule, start_month, amount in self.loans.with_schedule():
            paid = self.loans.paid(name, self.current)
            result[name] = {month: self.scheduled_balance(month, schedule, start_month, amount, paid) for month in self.months}
        return result

    def car_value(self, month):
        """Value of the car owned in that month; a leased car loses value evenly down to the balloon payment."""
        value = 0.0
        name = ""
        for car in self.settings.get("cars", []):
            if not (str(car["from"]) <= month < str(car.get("until", "9999"))):
                continue
            name = car.get("name", "Auto")
            if car.get("leasing"):
                leasing = self.loans.data[car["leasing"]]
                start_year, start_month = map(int, str(car["from"]).split("-"))
                months_owned = (int(month[:4]) - start_year) * 12 + int(month[5:]) - start_month
                value = round(car["value"] - (car["value"] - leasing["balloon"]) / leasing["n"] * months_owned, 2)
            else:
                value = car["value"]
        return value, name

    def rows(self, items):
        def item_value(name):
            return next((item["value"] for item in items if item["item"] == name), None)

        cash_by_account = {account: self.month_end_balances(account) for account in self.cash_accounts}
        card_account = self.rules.settings.get("card_account")
        card = self.month_end_balances(card_account) if card_account else self.zero_by_month()
        deposit = self.month_end_balances(self.deposit_account) if self.deposit_account else self.zero_by_month()
        # {account: {month: balance}}: month-end balances of accounts that are not in the bank data
        other_balances = self.settings.get("other_balances") or {}
        pension2 = self.settings.get("pension2") or {}
        pension2_total = sum(pension2.get("amounts", []))
        backfilled = self.backfilled_loans()
        scheduled = self.scheduled_loans()

        def other_cash(month):
            return sum((other_balances.get(account) or {}).get(month, 0) for account in other_balances)

        rows = []
        for portfolio_row in self.portfolio_by_month:
            month = portfolio_row["month"]
            investments = portfolio_row["value"]
            pillar2 = pension2_total if pension2 and month < str(pension2.get("until")) else 0.0

            cash = sum(cash_by_account[account][month] for account in self.cash_accounts) + other_cash(month)
            if month == self.current and self.settings.get("cash_item"):
                cash = item_value(self.settings["cash_item"]) + other_cash(month)

            loans_estimated = sum(balances[month] for balances in backfilled.values())
            loans_scheduled = sum(balances[month] for balances in scheduled.values())
            card_debt = max(0.0, -card[month])
            if month == self.current and self.settings.get("card_item"):
                card_debt = item_value(self.settings["card_item"])

            car, car_name = self.car_value(month)
            assets = investments + pillar2 + cash + deposit[month] + car
            debts = loans_estimated + loans_scheduled + card_debt
            rows.append(dict(
                month=month,
                label=label(month),
                car=car,
                car_name=car_name,
                investments=round(investments, 2),
                pension2=round(pillar2, 2),
                cash=round(cash, 2),
                deposit=round(deposit[month], 2),
                assets=round(assets, 2),
                loans=round(loans_estimated + loans_scheduled, 2),
                loans_est=round(loans_estimated, 2),
                card=round(card_debt, 2),
                debts=round(debts, 2),
                net=round(assets - debts, 2),
            ))
        return rows


def worth(rules, loans, investments, transactions, table, start_balances, current, data_months):
    calculator = Worth(rules, loans, investments, transactions, table, start_balances, current, data_months)
    items = calculator.items()
    return items, calculator.rows(items)


# ---------- cash-flow forecast ----------

class Leasing:
    """Interest change of a Euribor loan (forecast.leasing)."""

    def __init__(self, settings, loans):
        self.settings = settings
        self.balances = {}
        if settings and settings["loan"] in loans.data:
            self.balances = {month: row["balance"] for month, row in loans.schedule(settings["loan"]).items()}

    def extra_interest(self, month):
        settings = self.settings
        if not settings or month < str(settings["change_from"]):
            return 0.0
        balance = self.balances.get(month_add(month, -1)) or self.balances.get(month) or 0
        return balance * (settings["euribor_new"] - settings["euribor_now"]) / 100 / 12


def cashflow(rules, loans, months_rows, table, summary, window, current):
    forecast = rules.raw.get("forecast") or {}
    by_month = {row["month"]: row for row in months_rows}
    now = {row["metric"]: row["value"] for row in summary}
    window_count = max(1, len(window))

    income = sum(by_month[month]["income"] for month in window) / window_count
    trips = trip_categories(rules)
    trip_spending = sum(
        -row["amount"] for row in table
        if row["date"][:7] in window and row["category"] in trips and not row["oneoff"]
    ) / window_count
    expenses = sum(by_month[month]["expenses"] for month in window) / window_count - trip_spending

    loan_payments = collections.defaultdict(float)
    for payment in loans.future_payments(current):
        loan_payments[payment["month"]] += payment["amount"]

    fixed = min(now["fixed_end"] - loan_payments[current], expenses)
    variable = expenses - fixed
    invest = float(forecast.get("invest_per_month", 0))
    leasing_settings = forecast.get("leasing")
    leasing = Leasing(leasing_settings, loans)

    def pension3_paid(year):
        """Pillar III payments of a year: actual so far plus the planned monthly investment."""
        paid = sum(row["pension3"] for month, row in by_month.items() if month[:4] == year and month <= current)
        if year >= current[:4]:
            paid += sum(invest for month in months_between(month_add(current, 1), f"{year}-12") if month[:4] == year)
        else:
            paid += 0
        return paid

    first_year = min(by_month)[:4]
    months = months_between(current, month_add(current, int(forecast.get("months", 24)) - 1))
    trips_split = {str(key).zfill(2): value for key, value in (forecast.get("trips_split") or {}).items()}
    trips_per_year = float(forecast.get("trips_per_year", 0))
    tax_rate = float(forecast.get("tax_rate", 0))
    refund_month = int(forecast.get("refund_month", 4))

    rows = []
    total = 0.0
    for month in months:
        year, month_number = month[:4], month[5:]
        trip_share = trips_split.get(month_number, 0) if trips_split else 1 / 12
        trip = trips_per_year * trip_share
        euribor = leasing.extra_interest(month)
        previous_year = str(int(year) - 1)
        if int(month_number) == refund_month and previous_year >= first_year:
            refund = pension3_paid(previous_year) * tax_rate
        else:
            refund = 0.0

        if month == current:
            month_income = now["income_end"]
            month_fixed = now["fixed_end"] - loan_payments[month]
            month_loans = loan_payments[month]
            month_variable = now["var_end"]
            month_travel = 0.0
            month_invest = now["invest_end"]
            net = now["forecast_end"]
        else:
            month_income = income
            month_fixed = fixed
            month_loans = loan_payments[month] + euribor
            month_variable = variable
            month_travel = trip
            month_invest = invest
            net = month_income - month_fixed - month_loans - month_variable - month_travel - month_invest + refund
        total += net
        rows.append(dict(
            month=month,
            label=label(month),
            income=r2(month_income),
            fixed=r2(month_fixed),
            loans=r2(month_loans),
            variable=r2(month_variable),
            travel=r2(month_travel),
            invest=r2(month_invest),
            refund=r2(refund),
            euribor=r2(euribor),
            net=r2(net),
            cum=r2(total),
        ))

    future = rows[1:] or rows
    if leasing_settings:
        euribor_month = r2(leasing.extra_interest(str(leasing_settings["change_from"])))
        euribor_new = leasing_settings["margin"] + leasing_settings["euribor_new"]
        euribor_old = leasing_settings["margin"] + leasing_settings["euribor_now"]
    else:
        euribor_month = euribor_new = euribor_old = 0.0
    summary_rows = [
        dict(metric="months", value=len(rows)),
        dict(metric="net_avg", value=r2(sum(row["net"] for row in future) / len(future))),
        dict(metric="net_total", value=r2(total)),
        dict(metric="income", value=r2(income)),
        dict(metric="fixed", value=r2(fixed)),
        dict(metric="loans", value=r2(sum(row["loans"] for row in future) / len(future))),
        dict(metric="variable", value=r2(variable)),
        dict(metric="travel", value=r2(trips_per_year / 12)),
        dict(metric="invest", value=invest),
        dict(metric="refund_total", value=r2(sum(row["refund"] for row in rows))),
        dict(metric="euribor_month", value=euribor_month),
        dict(metric="euribor_new", value=euribor_new),
        dict(metric="euribor_old", value=euribor_old),
        dict(metric="min_cum", value=r2(min(row["cum"] for row in rows))),
    ]
    for row in summary_rows:
        row["value"] = float(row["value"])
    return rows, summary_rows


# ---------- trips ----------

def trip_transactions(rows):
    def order(row):
        return ((row.get("tdate") or row["date"]), row.get("time") or "")

    out = []
    for row in sorted(rows, key=order):
        out.append(dict(
            date=row.get("tdate") or row["date"],
            time=row.get("time") or "",
            payee=row["payee"],
            desc=row.get("desc") or "",
            amount=row["amount"],
        ))
    return out


def trip_row(name, rows):
    return dict(
        trip=name,
        date=min(row["date"] for row in rows),
        end=max(row["date"] for row in rows),
        cost=round(-sum(row["amount"] for row in rows), 2),
        n=len(rows),
        tx=trip_transactions(rows),
    )


def trips(rules, table):
    """Trip spending by the trips in rules.json; other trip-category rows each as an unassigned trip."""
    categories = trip_categories(rules)
    trip_rows = [row for row in table if row["category"] in categories]
    unassigned = rules.label("unassigned_trip") + ": "

    def as_transaction(row):
        return dict(row, counterparty=row.get("name", ""), description=row.get("desc", ""))

    out = []
    used = set()
    for trip in rules.raw.get("trips") or []:
        first, last = str(trip["from"]), str(trip["to"])
        conditions = trip.get("transactions")
        rows = []
        for row in trip_rows:
            if not (first <= row["date"] <= last):
                continue
            if conditions is None or any(rules.matches(as_transaction(row), condition) for condition in conditions):
                rows.append(row)
        for row in rows:
            used.add(id(row))
        if rows:
            out.append(trip_row(trip["name"], rows))

    for row in trip_rows:
        if id(row) not in used:
            out.append(trip_row(unassigned + row["payee"], [row]))

    starts = {trip["name"]: str(trip["start"]) for trip in rules.raw.get("trips") or [] if trip.get("start")}
    for row in out:
        row["trip_start"] = starts.get(row["trip"], row["date"])
    out.sort(key=lambda row: row["trip_start"], reverse=True)

    transactions = []
    for trip in out:
        for transaction in trip.pop("tx"):
            transactions.append(dict(trip=trip["trip"], start=trip["date"], **transaction))
    return out, transactions


# ---------- pension view ----------

def pension_view(rules, items, returns, current):
    forecast = rules.raw.get("forecast") or {}
    settings = forecast.get("pension")
    if not settings:
        return []
    tax_rate = float(forecast.get("tax_rate", 0))
    item_values = {row["item"]: row["value"] for row in items}
    returns_by_symbol = {row["symbol"]: row for row in returns}

    def items_total(key):
        return sum(item_values.get(name, 0) or 0 for name in settings.get(key, []))

    def gain_total(key):
        return sum(returns_by_symbol[symbol]["total"] for symbol in settings.get(key, []) if symbol in returns_by_symbol)

    pillar3_now = items_total("pillar3_items")
    funds_now = items_total("fund_items")
    pillar3_paid = pillar3_now - gain_total("pillar3_funds")
    funds_paid = funds_now - gain_total("other_funds")
    value_now = pillar3_now + funds_now

    contribution = float(settings["contribution_month"])
    born_year, born_month = map(int, str(settings["born"]).split("-"))
    year, month = map(int, current.split("-"))
    months_left = (born_year + int(settings["pension_age"]) - year) * 12 + (born_month - month)
    monthly_return = float(settings["return"]) / 12
    growth = (1 + monthly_return) ** months_left
    future_value = value_now * growth + contribution * ((growth - 1) / monthly_return)
    future_paid = value_now + contribution * months_left
    age_now = year - born_year - (1 if month < born_month else 0)

    rows = [
        dict(metric="p3_value", value=r2(pillar3_now)),
        dict(metric="funds_value", value=r2(funds_now)),
        dict(metric="total", value=r2(value_now)),
        dict(metric="paid_p3", value=r2(pillar3_paid)),
        dict(metric="paid_funds", value=r2(funds_paid)),
        dict(metric="gain", value=r2(value_now - pillar3_paid - funds_paid)),
        dict(metric="contrib_month", value=contribution),
        dict(metric="contrib_year", value=contribution * 12),
        dict(metric="refund_year", value=r2(contribution * 12 * tax_rate)),
        dict(metric="tax_rate", value=tax_rate),
        dict(metric="net_cost_month", value=r2(contribution * (1 - tax_rate))),
        dict(metric="age_now", value=float(age_now)),
        dict(metric="pension_age", value=float(settings["pension_age"])),
        dict(metric="years_left", value=r2(months_left / 12)),
        dict(metric="return", value=settings["return"]),
        dict(metric="fv", value=r2(future_value)),
        dict(metric="fv_paid", value=r2(future_paid)),
        # paid out over 20 years
        dict(metric="fv_month", value=r2(future_value / 20 / 12)),
    ]
    withdrawn = settings.get("pillar2_withdrawn")
    if withdrawn:
        rows.append(dict(metric="ii_withdrawn", value=r2(sum(withdrawn["amounts"]))))
        rows.append(dict(metric="ii_rejoin_year", value=float(month_add(str(withdrawn["month"]), 120)[:4])))
    return rows


# ---------- savings rate ----------

def principal_paid(schedules, month):
    """Loan principal paid in a month: balance at the previous month end minus balance at this month end."""
    previous = month_add(month, -1)
    paid = 0.0
    for schedule, start, start_balance in schedules:
        if previous in schedule:
            before = schedule[previous]
        elif previous >= start:
            before = start_balance
        else:
            before = None
        after = schedule[month] if month in schedule else None
        if before is not None and after is not None:
            paid += before - after
    return paid


def savings_rate(rules, loans, months_rows, investment_months, year, last_full):
    """Investments and loan principal (leasing excluded) as a share of income."""
    leasing_kinds = set(rules.settings.get("leasing_kinds") or [])
    by_month = {row["month"]: row for row in months_rows}
    investments_by_month = {row["month"]: row for row in investment_months}
    schedules = []
    for _name, kind, schedule, start, amount in loans.with_schedule():
        if kind not in leasing_kinds:
            schedules.append((schedule, start, amount))

    rows = []
    for month in sorted(by_month):
        if not (f"{year}-01" <= month <= last_full) or month not in investments_by_month:
            continue
        principal = principal_paid(schedules, month)
        invested = investments_by_month[month]["stocks_net"] + investments_by_month[month]["pension3"]
        income = by_month[month]["income"]
        rows.append(dict(
            month=month,
            label=by_month[month]["label"],
            income=round(income, 2),
            invest=round(invested, 2),
            principal=round(principal, 2),
            rate=round((invested + principal) / income, 4) if income else None,
        ))
    return rows
