"""Investments: stocks (trades, dividends, fees, prices), pension funds, deposit interest.

Datasets: returns (per instrument, years, XIRR), portfolio_change (per month), portfolio, comparison (indices),
expected_dividends, investment_months, plus investment rows for the transactions table.
Period return = (1 + XIRR)^(years) - 1 (as Portfellow). USD amounts in EUR at LHV's real rates: trade fees at the
trade month's rate (trade_fx), other amounts at the same year's next USD->EUR conversion, otherwise month-end EURUSD.
"""
import collections
import datetime as dt
import re

from common import r2
from monthly import label, month_add, months_between

# Positions smaller than this (shares) count as closed.
MIN_QUANTITY = 0.05
# Start and end values below this (EUR) are left out of return calculations.
MIN_VALUE = 0.5
TINY = 1e-9
INCOME_KINDS = ("dividend", "tax", "interest")
PORTFOLIO_NAME = "Portfell (aktsiad)"
PORTFOLIO_SOURCE = "aktsiakonto, sama arvutus nagu instrumentide tootluses"
DEFAULT_DEPOSIT_INTEREST = ["Konto intress", "Tulumaks konto intressilt"]


# ---------- returns ----------

def xirr(cash_flows):
    """Annual internal rate of return of [(date, amount)], or None."""
    cash_flows = [(date, amount) for date, amount in cash_flows if abs(amount) > TINY]
    if not cash_flows:
        return None
    if all(amount >= 0 for _, amount in cash_flows) or all(amount <= 0 for _, amount in cash_flows):
        return None
    first_date = min(date for date, _ in cash_flows)

    def present_value(rate):
        return sum(amount / (1 + rate) ** ((date - first_date).days / 365) for date, amount in cash_flows)

    low, high = -0.9999, 100.0
    if present_value(low) * present_value(high) > 0:
        return None
    for _ in range(300):
        middle = (low + high) / 2
        if (present_value(middle) > 0) == (present_value(low) > 0):
            low = middle
        else:
            high = middle
    return middle


def compound(rate, first_date, last_date, digits):
    return round((1 + rate) ** ((last_date - first_date).days / 365) - 1, digits)


def period_return(cash_flows):
    """Return over the whole period of the cash flows (5 decimals), or None."""
    rate = xirr(cash_flows)
    if rate is None:
        return None
    dates = [date for date, amount in cash_flows if abs(amount) > TINY]
    return compound(rate, min(dates), max(dates), 5)


def add_start_and_end(cash_flows, start_date, start_value, end_date, end_value):
    if start_value > MIN_VALUE:
        cash_flows.append((start_date, -start_value))
    if end_value > MIN_VALUE:
        cash_flows.append((end_date, end_value))
    return cash_flows


def mid_month(month):
    return dt.date.fromisoformat(month + "-15")


def first_day(month):
    return dt.date(int(month[:4]), int(month[5:]), 1)


# ---------- currencies ----------

class USD:
    """USD -> EUR at the rates LHV actually used."""

    def __init__(self, store):
        self.trade_rates = store.trade_fx()
        self.month_rates = store.month_prices("fx").get("EURUSD", {})
        conversions = []
        for row in store.account():
            description = row["description"]
            if row["currency"] != "USD" or row["kind"] != "conversion":
                continue
            if "EUR ->" in description or "kurss" not in description:
                continue
            rate = float(re.search(r"kurss ([0-9.]+)", description).group(1))
            conversions.append((row["date"], rate))
        self.conversions = sorted(conversions)

    def eur(self, date, amount, description=""):
        if "teenustasu" in description and date[:7] in self.trade_rates:
            return amount / self.trade_rates[date[:7]]
        for conversion_date, rate in self.conversions:
            if conversion_date >= date[:10] and conversion_date[:4] == date[:4]:
                return amount / rate
        return amount / self.month_rates[date[:7]]


class Context:
    """Months, previous months, price month and date, years, currency rates."""

    def __init__(self, store, periods):
        self.store = store
        self.years = periods["years"]
        self.price_month = periods["price_month"]
        self.price_date = dt.date.fromisoformat(periods["price_date"])
        self.data_date = periods["data_date"]
        self.months = months_between(periods["first"], self.price_month)
        self.previous = {self.months[0]: month_add(self.months[0], -1)}
        for index in range(1, len(self.months)):
            self.previous[self.months[index]] = self.months[index - 1]
        self.usd = USD(store)
        self.fx = store.month_prices("fx").get("EURUSD", {})
        self.trade_fx = store.trade_fx()

    def trade_rate(self, month):
        return self.trade_fx.get(month) or self.fx[month]

    def year_ranges(self, prefix):
        """(key, first date, last date) for each year and for all years."""
        ranges = []
        for year in self.years:
            ranges.append((prefix + year, dt.date(int(year), 1, 1), min(dt.date(int(year), 12, 31), self.price_date)))
        ranges.append((prefix + "all", dt.date(int(self.years[0]), 1, 1), self.price_date))
        return ranges


# ---------- pension funds ----------

class PensionFunds:
    """Pension fund units and values by month; returns per fund and year.
    Funds are followed from the first month whose previous month has a price for every fund."""

    def __init__(self, context):
        self.context = context
        data = context.store.json("invest/funds.json", {}) or {}
        self.nav = context.store.month_prices("funds")
        self.funds = {fund["code"]: fund for fund in data.get("funds", [])}
        self.transactions = collections.defaultdict(list)
        for row in data.get("tx", []):
            self.transactions[row["fund"]].append((row["date"][:7], row["units"], row["price"]))
        self.units = {code: float(fund.get("start_units", 0)) for code, fund in self.funds.items()}
        self.start_units = dict(self.units)
        self.by_year = {}
        self.month_flows = collections.defaultdict(list)
        self.flow_total = {code: 0.0 for code in self.funds}
        self.months = self.followed_months()
        self.month_rows = []
        for month in self.months:
            self.add_month(month)

    def followed_months(self):
        if not self.funds:
            return []
        first_prices = [min(self.nav[code]) for code in self.funds if self.nav.get(code)]
        previous = self.context.previous
        return [month for month in self.context.months if not first_prices or previous[month] >= max(first_prices)]

    def add_month(self, month):
        previous = self.context.previous[month]
        start_value = sum(self.units[code] * self.nav[code][previous] for code in self.funds if previous in self.nav.get(code, {}))
        flow = 0
        year = month[:4]
        for code in self.funds:
            fund_start = self.units[code] * self.nav[code].get(previous, 0)
            fund_flow = 0
            buys = 0
            for transaction_month, units, price in self.transactions[code]:
                if transaction_month != month:
                    continue
                self.units[code] += units
                flow += units * price
                self.flow_total[code] += units * price
                fund_flow += units * price
                buys += max(0, units * price)
            year_totals = self.by_year.setdefault((code, year), dict(start=None, buys=0.0, gain=0.0))
            if year_totals["start"] is None:
                year_totals["start"] = fund_start
            year_totals["buys"] += buys
            year_totals["gain"] += self.units[code] * self.nav[code][month] - fund_start - fund_flow
            self.month_flows[code].append((month, fund_start, fund_flow))
        value = sum(self.units[code] * self.nav[code][month] for code in self.funds)
        self.month_rows.append(dict(
            month=month,
            pension_flow=r2(flow),
            pension=r2(value - start_value - flow),
            pension_value=r2(value),
        ))

    def average_base(self, code, year):
        """Average invested amount: start value plus flows weighted by the part of the period they were in."""
        flows = [row for row in self.month_flows[code] if year == "all" or row[0][:4] == year]
        if not flows:
            return 0
        months = [month for month in self.months if year == "all" or month[:4] == year]
        count = len(months)
        index = {month: position for position, month in enumerate(months)}
        return r2(flows[0][1] + sum(flow * (count - index[month] - 0.5) / count for month, _value, flow in flows))

    def year_return(self, code, year, value_now):
        context = self.context
        flows = [row for row in self.month_flows[code] if year == "all" or row[0][:4] == year]
        start_values = {row[0]: row[1] for row in self.month_flows[code]}
        first = self.months[0] if self.months else context.months[0]
        from_first = year in ("all", first[:4])
        is_last = year == "all" or year == context.years[-1]
        start_date = first_day(first) if from_first else dt.date(int(year), 1, 1)
        end_date = context.price_date if is_last else dt.date(int(year), 12, 31)
        if from_first:
            start_value = self.start_units[code] * self.nav[code].get(context.previous[first], 0)
        else:
            start_value = start_values.get(year + "-01", 0)
        end_value = value_now if is_last else start_values.get(f"{int(year) + 1}-01", 0)
        cash_flows = [(mid_month(month), -flow) for month, _value, flow in flows if abs(flow) > TINY]
        return period_return(add_start_and_end(cash_flows, start_date, start_value, end_date, end_value))

    def return_rows(self):
        context = self.context
        rows = []
        for code, fund in self.funds.items():
            if self.months:
                start_value = self.start_units[code] * self.nav[code].get(context.previous[self.months[0]], 0)
            else:
                start_value = 0
            value_now = self.units[code] * self.nav[code][context.price_month]
            gain = value_now - start_value - self.flow_total[code]
            bought = sum(units * price for _month, units, price in self.transactions[code] if units > 0)
            row = dict(
                symbol=code,
                name=fund["name"],
                held=True,
                cost=r2(start_value + bought),
                price=r2(gain),
                dividends=0,
                fx=0,
                total=r2(gain),
                kind="pension",
            )
            for year in context.years:
                totals = self.by_year.get((code, year), dict(start=0, buys=0, gain=0))
                row["price_" + year] = r2(totals["gain"])
                row["fx_" + year] = 0
                row["dividends_" + year] = 0
                row["base_" + year] = r2((totals["start"] or 0) + totals["buys"])
            for year in context.years + ["all"]:
                row["avgb_" + year] = self.average_base(code, year)
                row["xr_" + year] = self.year_return(code, year, value_now)
            row["qty"] = round(self.units[code], 3)
            row["value"] = round(self.units[code] * self.nav[code][context.price_month], 2)
            rows.append(row)
        return rows


# ---------- stocks ----------

class AccountIncome:
    """Dividends (with tax and interest) and fees from the investment account, by symbol and month, in EUR."""

    def __init__(self, context, account, aliases):
        self.dividends = collections.defaultdict(float)
        self.dividends_by_month = collections.defaultdict(float)
        self.dividends_by_symbol_month = collections.defaultdict(float)
        self.fees = collections.defaultdict(float)
        self.fees_by_month = collections.defaultdict(float)
        self.fees_by_symbol_month = collections.defaultdict(float)
        for row in account:
            if not row["symbol"]:
                continue
            symbol = aliases.get(row["symbol"], row["symbol"])
            month = row["time"][:7]
            amount = row["amount"]
            if row["currency"] == "USD":
                amount = context.usd.eur(row["time"], amount, row["description"])
            if row["kind"] in INCOME_KINDS:
                self.dividends[symbol] += amount
                self.dividends_by_month[month] += amount
                self.dividends_by_symbol_month[(symbol, month)] += amount
            elif row["kind"] == "fee" or "teenustasu" in row["description"]:
                self.fees[symbol] += -amount
                self.fees_by_month[month] += -amount
                self.fees_by_symbol_month[(symbol, month)] += -amount

    def fee(self, symbol, month):
        return self.fees_by_symbol_month.get((symbol, month), 0)


def signed_quantity(trade):
    return trade["quantity"] if trade["actionType"] == "BUY" else -abs(trade["quantity"])


class Stocks:
    """Stock positions month by month: value, flows, price gain, currency effect; per symbol and year."""

    def __init__(self, context, trades, currencies, portfolio, income):
        self.context = context
        self.trades = trades
        self.currency = currencies
        self.portfolio = portfolio
        self.income = income
        self.prices = context.store.month_prices("stocks")
        self.quantity = collections.defaultdict(float)
        self.last_price = {}
        self.cost_eur = collections.defaultdict(float)
        self.cost_usd = collections.defaultdict(float)
        self.proceeds_eur = collections.defaultdict(float)
        self.proceeds_usd = collections.defaultdict(float)
        # USD paid for the shares still held (for the currency effect)
        self.held_usd = collections.defaultdict(float)
        self.by_year = collections.defaultdict(lambda: dict(start=0.0, buys=0.0, price=0.0, fx=0.0, dividends=0.0))
        self.month_flows = collections.defaultdict(list)
        self.rows = []
        self.next_trade = 0
        fx = context.fx
        # months before the first rate: no USD positions yet, the rate does not matter
        self.first_rate = fx[min(fx)] if fx else 1.0
        for month in context.months:
            self.add_month(month)

    def price(self, symbol, month):
        if symbol in self.prices and month in self.prices[symbol]:
            return self.prices[symbol][month]
        return self.last_price.get(symbol)

    def value(self, symbol, month, quantity, rate):
        """(value in EUR, value in USD) of a position at a month end; the price month uses the portfolio value."""
        if month == self.context.price_month and symbol in self.portfolio:
            value = self.portfolio[symbol]["value"]
            return value, (value * rate if self.currency[symbol] == "USD" else 0)
        price = self.price(symbol, month)
        if price is None:
            return 0, 0
        if self.currency[symbol] == "USD":
            return quantity * price / rate, quantity * price
        return quantity * price, 0

    def add_month(self, month):
        context = self.context
        previous = context.previous[month]
        rate_before = context.fx.get(previous, self.first_rate)
        rate_after = context.fx.get(month, self.first_rate)
        quantity_before = dict(self.quantity)
        flow = 0
        symbol_flow = collections.defaultdict(float)
        symbol_buys = collections.defaultdict(float)

        start_value = 0
        start_values = {}
        for symbol, quantity in quantity_before.items():
            if abs(quantity) < MIN_QUANTITY:
                continue
            value_eur, value_usd = self.value(symbol, previous, quantity, rate_before)
            start_value += value_eur
            start_values[symbol] = (value_eur, value_usd)

        currency_effect = collections.defaultdict(float)
        for symbol, usd in self.held_usd.items():
            currency_effect[symbol] += usd * (1 / rate_after - 1 / rate_before)

        while self.next_trade < len(self.trades) and self.trades[self.next_trade]["executedAt"][:7] <= month:
            trade = self.trades[self.next_trade]
            self.next_trade += 1
            eur = self.apply_trade(trade, rate_after, currency_effect)
            symbol = trade["symbol"]
            sign = 1 if trade["actionType"] == "BUY" else -1
            flow += sign * eur
            self.quantity[symbol] += sign * abs(trade["quantity"])
            self.last_price[symbol] = trade["price"]
            symbol_flow[symbol] += sign * eur
            if sign > 0:
                symbol_buys[symbol] += eur

        end_value = 0
        for symbol, quantity in self.quantity.items():
            if abs(quantity) < MIN_QUANTITY:
                continue
            value_eur, _value_usd = self.value(symbol, month, quantity, rate_after)
            end_value += value_eur
        gain = end_value - start_value - flow

        year = month[:4]
        for symbol in set(list(quantity_before) + list(self.quantity)):
            symbol_start, _start_usd = start_values.get(symbol, (0, 0))
            if abs(self.quantity[symbol]) >= MIN_QUANTITY:
                symbol_end, _end_usd = self.value(symbol, month, self.quantity[symbol], rate_after)
            else:
                symbol_end = 0
            symbol_currency = currency_effect.get(symbol, 0.0)
            symbol_gain = symbol_end - symbol_start - symbol_flow[symbol]
            fee = self.income.fee(symbol, month)
            totals = self.by_year[(symbol, year)]
            if month[5:] == "01":
                totals["start"] = symbol_start
            totals["buys"] += symbol_buys[symbol] + fee
            totals["price"] += symbol_gain - symbol_currency - fee
            totals["fx"] += symbol_currency
            totals["dividends"] += self.income.dividends_by_symbol_month.get((symbol, month), 0)
            self.month_flows[symbol].append((month, symbol_start, symbol_flow[symbol] + fee))

        total_currency = sum(currency_effect.values())
        fees = self.income.fees_by_month.get(month, 0)
        self.rows.append(dict(
            month=month,
            flow=r2(flow + fees),
            price=r2(gain - total_currency),
            fx=r2(total_currency),
            dividends=r2(self.income.dividends_by_month.get(month, 0)),
            fees=r2(-fees),
            value=r2(end_value),
        ))

    def apply_trade(self, trade, rate_after, currency_effect):
        """Book a trade's cost or proceeds; returns the amount in EUR."""
        symbol = trade["symbol"]
        amount = abs(trade["quantity"]) * trade["price"]
        is_buy = trade["actionType"] == "BUY"
        if self.currency[symbol] != "USD":
            if is_buy:
                self.cost_eur[symbol] += amount
            else:
                self.proceeds_eur[symbol] += amount
            return amount

        rate = self.context.trade_rate(trade["executedAt"][:7])
        eur = amount / rate
        if is_buy:
            self.cost_usd[symbol] += amount
            self.cost_eur[symbol] += eur
            self.held_usd[symbol] += amount
            currency_effect[symbol] += amount * (1 / rate_after - 1 / rate)
        else:
            self.proceeds_usd[symbol] += amount
            self.proceeds_eur[symbol] += eur
            held = self.quantity[symbol]
            sold_usd = self.held_usd[symbol] * min(1, abs(trade["quantity"]) / held) if held > TINY else 0
            self.held_usd[symbol] -= sold_usd
            currency_effect[symbol] -= sold_usd * (1 / rate_after - 1 / rate)
        return eur

    def is_held(self, symbol):
        return self.quantity[symbol] > MIN_QUANTITY


class StockReturns:
    """Average invested amount and returns (XIRR) per symbol and period."""

    def __init__(self, context, trades, currencies, account, aliases, stocks):
        self.context = context
        self.trades = trades
        self.currency = currencies
        self.stocks = stocks

        self.trade_flows = collections.defaultdict(list)
        for trade in trades:
            amount = abs(trade["quantity"]) * trade["price"]
            sign = 1 if trade["actionType"] == "BUY" else -1
            if currencies[trade["symbol"]] == "USD":
                amount /= context.trade_rate(trade["executedAt"][:7])
            self.trade_flows[trade["symbol"]].append((dt.date.fromisoformat(trade["executedAt"][:10]), sign * amount))

        self.cash_flows = collections.defaultdict(list)
        for row in account:
            if not row["symbol"]:
                continue
            symbol = aliases.get(row["symbol"], row["symbol"])
            amount = row["amount"]
            if row["currency"] == "USD":
                amount = context.usd.eur(row["time"], amount, row["description"])
            if row["kind"] in INCOME_KINDS + ("fee",) or "teenustasu" in row["description"]:
                self.cash_flows[symbol].append((dt.date.fromisoformat(row["time"][:10]), amount))
        for symbol, flows in self.trade_flows.items():
            for date, amount in flows:
                self.cash_flows[symbol].append((date, -amount))

        # Dates when a symbol was bought again after being sold out: returns are chained over these.
        self.rebuys = collections.defaultdict(list)
        held = collections.defaultdict(float)
        for trade in trades:
            symbol = trade["symbol"]
            date = dt.date.fromisoformat(trade["executedAt"][:10])
            bought_before = self.trade_flows[symbol] and min(day for day, _ in self.trade_flows[symbol]) < date
            if trade["actionType"] == "BUY" and held[symbol] <= TINY and bought_before:
                self.rebuys[symbol].append(date)
            held[symbol] += signed_quantity(trade)

    def average_base(self, symbol):
        """Average daily invested amount (cost of the shares held) per period."""
        events = collections.defaultdict(list)
        for trade in self.trades:
            if trade["symbol"] != symbol:
                continue
            amount = abs(trade["quantity"]) * trade["price"]
            if self.currency[symbol] == "USD":
                amount = amount / self.context.trade_rate(trade["executedAt"][:7])
            events[dt.date.fromisoformat(trade["executedAt"][:10])].append((trade["actionType"], abs(trade["quantity"]), amount))
        ranges = self.context.year_ranges("avgb_")
        if not events:
            return {key: 0 for key, _, _ in ranges}

        held = self.stocks.is_held(symbol)
        end = self.context.price_date if held else max(events)
        day = min(events)
        quantity = 0
        base = 0
        daily = {}
        while day <= end:
            for action, count, amount in events.get(day, []):
                if action == "BUY":
                    quantity += count
                    base += amount
                else:
                    base -= base * min(1, count / quantity) if quantity else 0
                    quantity -= count
            if day < end or held:
                daily[day] = max(0.0, base)
            day += dt.timedelta(1)

        out = {}
        for key, first, last in ranges:
            values = [value for date, value in daily.items() if first <= date <= last]
            out[key] = r2(sum(values) / len(values)) if values else 0
        return out

    def returns(self, symbol, portfolio):
        held = self.stocks.is_held(symbol)
        value_now = portfolio[symbol]["value"] if held and symbol in portfolio else 0
        start_values = {row[0]: row[1] for row in self.stocks.month_flows[symbol]}
        out = {}
        for key, first, last in self.context.year_ranges("xr_"):
            start_value = start_values.get(f"{first.year}-01", 0)
            is_last = key == "xr_all" or str(first.year) == self.context.years[-1]
            end_value = value_now if is_last else start_values.get(f"{first.year + 1}-01", 0)
            cash_flows = [(date, amount) for date, amount in self.cash_flows[symbol] if first <= date <= last]
            add_start_and_end(cash_flows, first, start_value, last, end_value)
            rebuys = [date for date in self.rebuys.get(symbol, []) if first < date <= last]
            if not rebuys:
                out[key] = period_return(cash_flows)
                continue
            out[key] = chained_return(cash_flows, rebuys)
        return out


def chained_return(cash_flows, rebuys):
    """Return over segments split at rebuy dates, multiplied together."""
    segments = collections.defaultdict(list)
    for date, amount in cash_flows:
        segment = sum(1 for rebuy in rebuys if rebuy <= date)
        segments[segment].append((date, amount))
    product = 1.0
    found = False
    for segment in sorted(segments):
        rate = period_return(segments[segment])
        if rate is not None:
            product *= 1 + rate
            found = True
    return round(product - 1, 5) if found else None


def stock_return_rows(context, stocks, returns, income, names, instruments, portfolio):
    rows = []
    for symbol in names:
        held = stocks.is_held(symbol)
        if symbol in instruments:
            name = instruments[symbol]["name"]
        elif symbol in portfolio:
            name = portfolio[symbol]["name"]
        else:
            name = names[symbol]
        row = dict(symbol=symbol, name=name, held=held, cost=r2(stocks.cost_eur[symbol] + income.fees[symbol]))
        for year in context.years:
            totals = stocks.by_year[(symbol, year)]
            for key in ("price", "fx", "dividends"):
                row[key + "_" + year] = r2(totals[key])
            year_fees = sum(value for (other, month), value in income.fees_by_symbol_month.items() if other == symbol and month[:4] == year)
            row["fees_" + year] = r2(-year_fees)
            row["price_" + year] = r2(totals["price"] + year_fees)
            row["base_" + year] = r2(totals["start"] + totals["buys"])
        row.update(returns.average_base(symbol))
        row.update(returns.returns(symbol, portfolio))
        for key in ("price", "fx", "dividends", "fees"):
            row[key] = r2(sum(row[key + "_" + year] for year in context.years))
        row["total"] = r2(row["price"] + row["fx"] + row["dividends"] + row["fees"])
        rows.append(row)
    return rows


def add_pension_to_months(rows, pension_rows):
    """Portfolio change rows: stocks plus pension funds (months before the funds count as zero)."""
    zero = dict(pension_flow=0.0, pension=0.0, pension_value=0.0)
    pension = collections.defaultdict(lambda: dict(zero), {row["month"]: row for row in pension_rows})
    for row in rows:
        row["label"] = label(row["month"])
    for row in rows:
        fund = pension[row["month"]]
        row["stock_value"] = row["value"]
        row["stock_price"] = row["price"]
        row["price"] = r2(row["price"] + fund["pension"])
        row["flow"] = r2(row["flow"] + fund["pension_flow"])
        row["value"] = r2(row["value"] + fund["pension_value"])
    return pension


# ---------- deposit ----------

def deposit(context, rows):
    """Deposit interest goes to the investments' income; the balance is not in the portfolio value.
    Adds deposit_int to the month rows and returns the deposit's returns row (or None)."""
    data = context.store.json("invest/deposit.json", None)
    if not data or not data.get("rows"):
        return None
    years = context.years
    deposit_rows = data["rows"]
    prefixes = tuple(data.get("interest_prefixes") or DEFAULT_DEPOSIT_INTEREST)

    interest = collections.defaultdict(float)
    for row in deposit_rows:
        if row["description"].startswith(prefixes):
            interest[row["time"][:7]] += row["amount"]
    for row in rows:
        row["dividends_base"] = row["dividends"]
        row["deposit_int"] = round(interest.get(row["month"], 0), 2)
        row["dividends"] = round(row["dividends_base"] + row["deposit_int"], 2)
    by_year = {year: round(sum(value for month, value in interest.items() if month[:4] == year), 2) for year in years}
    total = round(sum(by_year.values()), 2)

    changes = collections.defaultdict(float)
    for row in deposit_rows:
        changes[dt.date.fromisoformat(row["time"][:10])] += row["amount"]
    day = dt.date(int(years[0]), 1, 1)
    last_row = dt.date.fromisoformat(max(row["time"][:10] for row in deposit_rows))
    last_day = max(last_row, dt.date.fromisoformat(context.data_date))
    balance = 0
    balance_days = collections.defaultdict(float)
    day_count = collections.defaultdict(int)
    while day <= last_day:
        balance += changes.get(day, 0)
        balance_days[str(day.year)] += balance
        day_count[str(day.year)] += 1
        day += dt.timedelta(1)
    average = {year: round(balance_days[year] / day_count[year], 2) for year in balance_days}
    average_all = round(sum(balance_days.values()) / sum(day_count.values()), 2)

    def rate(value, base):
        return round(value / base, 5) if base else None

    row = dict(
        symbol=data.get("symbol", "DEP"),
        name=data.get("name", "Hoius"),
        held=True,
        kind="deposit",
        cost=average_all,
        price=0,
        fx=0,
        dividends=total,
        total=total,
        qty=0,
        value=0,
        avgb_all=average_all,
        xr_all=rate(total, average_all),
    )
    for year in years:
        row.update({
            "price_" + year: 0,
            "fx_" + year: 0,
            "dividends_" + year: by_year[year],
            "base_" + year: average.get(year, 0),
            "avgb_" + year: average.get(year, 0),
            "xr_" + year: rate(by_year[year], average.get(year)),
        })
    return row


# ---------- comparison with indices ----------

def comparison_rows(context, stock_rows):
    """Stock portfolio return vs. the same cash flows put into each index (invest/instruments.json indices)."""
    index_values = context.store.month_prices("indices")
    indices = {}
    for index in context.store.instruments_file().get("indices", []):
        indices[index["name"]] = dict(source=index["source"], values=index_values.get(index["name"], {}))

    def month_end(month):
        if month >= context.price_month:
            return context.price_date
        year, number = int(month[:4]), int(month[5:])
        next_month = dt.date(year + (number == 12), number % 12 + 1, 1)
        return next_month - dt.timedelta(days=1)

    def return_4(cash_flows):
        rate = xirr(cash_flows)
        first = min(date for date, _ in cash_flows)
        last = max(date for date, _ in cash_flows)
        return None if rate is None else compound(rate, first, last, 4)

    def period(rows):
        if not rows:
            return {}
        first_month, last_month = rows[0]["month"], rows[-1]["month"]
        position = stock_rows.index(rows[0])
        start_value = stock_rows[position - 1]["value"] if position > 0 else 0.0
        start_date = first_day(first_month)
        has_start = start_value > MIN_VALUE

        cash_flows = [(start_date, -start_value)] if has_start else []
        cash_flows += [(mid_month(row["month"]), -row["flow"]) for row in rows if row["flow"]]
        cash_flows += [(mid_month(row["month"]), row["dividends"]) for row in rows if row["dividends"]]
        cash_flows += [(month_end(last_month), rows[-1]["value"])]
        result = {PORTFOLIO_NAME: return_4(cash_flows)}

        for name, index in indices.items():
            values = index["values"]
            units = start_value / values[month_add(first_month, -1)] if has_start else 0.0
            index_flows = [(start_date, -start_value)] if has_start else []
            for row in rows:
                if not row["flow"]:
                    continue
                average_price = (values[month_add(row["month"], -1)] + values[row["month"]]) / 2
                units += row["flow"] / average_price
                index_flows.append((mid_month(row["month"]), -row["flow"]))
            index_flows.append((month_end(last_month), units * values[last_month]))
            result[name] = return_4(index_flows)
        return result

    periods = {year: [row for row in stock_rows if row["month"][:4] == year] for year in context.years}
    periods["all"] = stock_rows
    out = []
    for key, rows in periods.items():
        for name, value in period(rows).items():
            out.append(dict(
                period=key,
                name=name,
                ret=value,
                src=indices[name]["source"] if name in indices else PORTFOLIO_SOURCE,
                kind="portfolio" if name == PORTFOLIO_NAME else "index",
            ))
    return out


# ---------- expected dividends (next 12 months) ----------

def months_apart(first, second):
    return abs((int(first[:4]) * 12 + int(first[5:7])) - (int(second[:4]) * 12 + int(second[5:7])))


def expected_dividend_rows(context, trades, account, aliases, portfolio):
    """Last 12 months' dividends a year later, scaled to the shares held now; declared dividends replace them."""
    last_date = context.data_date
    last = dt.date.fromisoformat(last_date)
    first_date = str(last.replace(year=last.year - 1) + dt.timedelta(days=1))

    def quantity_on(symbol, date):
        quantity = 0
        for trade in trades:
            if trade["symbol"] != symbol and aliases.get(trade["symbol"]) != symbol:
                continue
            if trade["executedAt"][:10] > date:
                break
            quantity += signed_quantity(trade)
        return quantity

    payments = []
    for row in account:
        if not row["symbol"] or row["kind"] not in INCOME_KINDS:
            continue
        amount = row["amount"] / (context.fx[row["date"][:7]] if row["currency"] == "USD" else 1)
        payments.append((row["date"], aliases.get(row["symbol"], row["symbol"]), amount))

    expected = collections.defaultdict(float)
    for date, symbol, amount in payments:
        if not (first_date <= date <= last_date) or symbol not in portfolio:
            continue
        quantity_then = quantity_on(symbol, date)
        quantity_now = portfolio[symbol].get("qty") or quantity_on(symbol, last_date)
        if quantity_then <= 0:
            continue
        expected[(f"{int(date[:4]) + 1}{date[4:7]}", symbol)] += amount * quantity_now / quantity_then

    names = {position["symbol"]: position["name"] for position in portfolio.values()}
    rows = []
    for (month, symbol), amount in sorted(expected.items()):
        if abs(amount) >= 0.005:
            rows.append(dict(month=month, symbol=symbol, name=names.get(symbol, symbol), amount=round(amount, 2), confirmed=False, date=""))

    for declared in context.store.instruments_file().get("dividends_declared", []):
        symbol = declared["symbol"]
        if declared["date"] < last_date or symbol not in portfolio:
            continue
        rows = [
            row for row in rows
            if not (row["symbol"] == symbol and not row["confirmed"] and months_apart(row["month"], declared["date"]) <= 1)
        ]
        rows.append(dict(
            month=declared["date"][:7],
            symbol=symbol,
            name=names.get(symbol, symbol),
            amount=round(declared["per_share"] * portfolio[symbol]["qty"], 2),
            confirmed=True,
            date=declared["date"],
        ))
    rows.sort(key=lambda row: (row["month"], row["symbol"]))
    return rows


# ---------- investments per month ----------

def investment_flows(context, trades, account):
    """{month: {buy, sell, div, fund}} in EUR."""
    flows = collections.defaultdict(lambda: dict(buy=0.0, sell=0.0, div=0.0, fund=0.0))
    for row in account:
        month = row["date"][:7]
        amount = row["amount"]
        kind = row["kind"]
        if row["currency"] == "USD":
            amount = context.usd.eur(row["date"], amount, row["description"])
        if kind in INCOME_KINDS:
            flows[month]["div"] += amount
        elif kind == "fee":
            flows[month]["buy"] += -amount
        elif kind == "fund":
            flows[month]["fund"] += -amount
    for trade in trades:
        month = trade["executedAt"][:7]
        value = trade["price"] * abs(trade["quantity"]) * (1 if trade["actionType"] == "BUY" else -1)
        if trade["currency"] == "USD":
            value = value / context.trade_rate(month)
        if value > 0:
            flows[month]["buy"] += value
        else:
            flows[month]["sell"] += -value
    return flows


def build(store, periods):
    """store: Store; periods: dict(first, years, price_month, price_date, data_date, last_full)."""
    context = Context(store, periods)
    trades = store.trades()
    names = {trade["symbol"]: trade["instrumentName"] for trade in trades}
    currencies = {trade["symbol"]: trade["currency"] for trade in trades}
    instruments = store.instruments()
    aliases = store.aliases()
    account = store.account()
    portfolio = {position["symbol"]: position for position in store.portfolio()}

    funds = PensionFunds(context)
    fund_rows = funds.return_rows()

    income = AccountIncome(context, account, aliases)
    stocks = Stocks(context, trades, currencies, portfolio, income)
    rows = stocks.rows
    stock_rows = [dict(row) for row in rows]
    returns = StockReturns(context, trades, currencies, account, aliases, stocks)
    return_rows = stock_return_rows(context, stocks, returns, income, names, instruments, portfolio)
    pension_by_month = add_pension_to_months(rows, funds.month_rows)

    return_rows = sorted(return_rows + fund_rows, key=lambda row: -row["total"])
    for row in return_rows:
        if row.get("kind") == "pension":
            continue
        if row["symbol"] in portfolio and row.get("held"):
            row["qty"] = portfolio[row["symbol"]]["qty"]
            row["value"] = portfolio[row["symbol"]]["value"]
        else:
            row["qty"] = 0
            row["value"] = 0

    deposit_row = deposit(context, rows)
    if deposit_row:
        return_rows.append(deposit_row)

    instrument_names = {symbol: instrument["name"] for symbol, instrument in instruments.items()}
    for alias, symbol in aliases.items():
        if symbol in instruments:
            instrument_names[alias] = instruments[symbol]["name"]

    return {
        "portfolio": list(portfolio.values()),
        "portfolio_change": rows,
        "returns": return_rows,
        "comparison": comparison_rows(context, stock_rows),
        "expected_dividends": expected_dividend_rows(context, trades, account, aliases, portfolio),
        "_inv": investment_flows(context, trades, account),
        "_pmon": pension_by_month,
        "_names": instrument_names,
    }


def investment_months(rules, months_rows, investments, last_full):
    """Stocks net, cumulative, dividends, pension (III pillar + fund), invest_out (what reduces the month's result)."""
    flows = investments["_inv"]
    pension = investments["_pmon"]
    out = []
    cumulative = 0
    for month_row in months_rows:
        month = month_row["month"]
        if month > last_full:
            continue
        flow = flows[month]
        net = flow["buy"] - flow["sell"]
        cumulative += net
        pension3 = r2(month_row["pension3"] + flow["fund"])
        pension_flow = pension[month]["pension_flow"] if month in pension else pension3
        out.append(dict(
            month=month,
            label=month_row["label"],
            stocks_net=r2(net),
            stocks_cum=r2(cumulative),
            dividends=r2(flow["div"]),
            pension3=pension3,
            income=month_row["income"],
            invest_out=r2(max(0.0, net) + pension3),
            pension_out=r2(min(0, pension_flow - pension3)),
        ))
    return out


def table_rows(rules, store, investments):
    """Investment account rows for the transactions table: buys, sells, dividends, fund payments, paid interest.
    Categories and texts: settings.investment_rows."""
    settings = rules.settings.get("investment_rows") or {}
    usd = USD(store)
    totals = collections.defaultdict(float)
    kinds = {"buy": "buy", "fee": "buy", "sell": "sell", "dividend": "div", "tax": "div", "interest": "div", "fund": "fund"}
    for row in store.account():
        date, amount, kind, symbol = row["date"], row["amount"], row["kind"], row["symbol"]
        if row["currency"] == "USD":
            amount = usd.eur(date, amount, row["description"])
        if kind == "fund":
            totals[(date, "fund", "FUND")] += amount
        elif kind in kinds:
            totals[(date, kinds[kind], symbol)] += amount
        elif kind == "account_interest":
            totals[(date, "div", "Konto intress")] += amount
        elif kind == "paid_interest":
            totals[(date, "fee", "Aktsiakonto intress")] += amount

    stocks = settings.get("stocks", rules.label("investments"))
    texts = {
        "buy": (stocks, "Ost"),
        "sell": (stocks, "Müük"),
        "div": (settings.get("dividends", rules.label("investments")), "Dividend või intress, tulumaks maha arvatud"),
        "fund": (settings.get("funds", rules.label("investments")), settings.get("fund_description", "Fondi sissemakse")),
        "fee": (settings.get("fees", rules.label("other")), "Aktsiakonto miinusjäägi intress"),
    }
    names = investments["_names"]
    out = []
    for number, (date, kind, symbol) in enumerate(sorted(totals)):
        amount = round(totals[(date, kind, symbol)], 2)
        if abs(amount) < 0.005:
            continue
        category, description = texts[kind]
        out.append(dict(
            id=f"inv{number}",
            date=date,
            bdate=date,
            tdate=date,
            time="",
            name=symbol,
            payee=names.get(symbol, symbol),
            amount=amount,
            desc=description + " (aktsiakonto)",
            category=category,
            grp=rules.label("other") if kind == "fee" else rules.label("investments"),
            oneoff=False,
        ))
    return out
