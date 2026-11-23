"""Reading the Rahapada store (the user's data folder, kept in the companion storage artifact).

Layout (all optional except rules.json and tx/):
  rules.json                  rules
  tx/*.json                   bank transactions (reference/store.md)
  card_times.json             reservation times of card payments
  prices.json                 [{month, source, symbol, price, date}]  sources: stocks, funds, indices, fx
  balances.json               [{month, account, currency, start, end}]
  invest/trades.json          [{executedAt, symbol, instrumentName, currency, actionType, quantity, price}]
  invest/account.json         investment account statement [{time, description, amount, currency, counterparty}]
  invest/portfolio.json       current positions [{symbol, qty, value, pl, cost}]
  invest/instruments.json     {instruments: {symbol: {name, country, sector, region, aliases}}, trade_fx: {month: rate},
                               indices: [{name, source}], dividends_declared: [{symbol, date, per_share}]}
  invest/funds.json           {funds: [{code, name, match, start_units}], tx: [{fund, date, units, price}],
                               account_fund_payee?: counterparty of fund purchases on the investment account}
  invest/deposit.json         {name, symbol, rows: [{time, description, amount}]}
"""
import os
import re

from common import load_json

# Kinds of investment account rows by the start of the LHV statement text.
ACCOUNT_KINDS = [
    ("Väärtpaberite ost", "buy"),
    ("Väärtpaberite müük", "sell"),
    ("Ost-müük tehingu teenustasu", "fee"),
    ("Dividendid", "dividend"),
    ("Kinnipeetud tulumaks", "tax"),
    ("Intress (", "interest"),
    ("Konto intress", "account_interest"),
    ("Makstud intress", "paid_interest"),
    ("Konverteerimine", "conversion"),
]
SYMBOL_IN_TEXT = re.compile(r"\(([A-Z0-9-]+)\)")

_cache = {}


class Store:
    def __init__(self, root):
        self.root = root

    def path(self, *parts):
        return os.path.join(self.root, *parts)

    def json(self, relative_path, default=None):
        """Contents of a store file (read once per run)."""
        key = ("j", relative_path)
        if key not in _cache:
            _cache[key] = load_json(self.path(relative_path), default)
        return _cache[key]

    # ---- prices ----
    def prices(self):
        return self.json("prices.json", []) or []

    def month_prices(self, source):
        """{symbol: {month: price}}"""
        out = {}
        for row in self.prices():
            if row["source"] == source:
                out.setdefault(row["symbol"], {})[row["month"]] = row["price"]
        return out

    def price_date(self):
        dates = [row["date"] for row in self.prices() if row["source"] == "stocks" and row.get("date")]
        return max(dates) if dates else None

    # ---- investments ----
    def instruments_file(self):
        return self.json("invest/instruments.json", {}) or {}

    def instruments(self):
        return self.instruments_file().get("instruments", {})

    def aliases(self):
        """{alias: symbol}"""
        out = {}
        for symbol, instrument in self.instruments().items():
            for alias in (instrument.get("aliases") or "").split():
                out[alias] = symbol
        return out

    def trade_fx(self):
        return self.instruments_file().get("trade_fx", {})

    def trades(self):
        return sorted(self.json("invest/trades.json", []) or [], key=lambda trade: trade["executedAt"])

    def portfolio(self):
        instruments = self.instruments()
        out = []
        for position in self.json("invest/portfolio.json", []) or []:
            instrument = instruments.get(position["symbol"], {})
            out.append(dict(
                symbol=position["symbol"],
                name=instrument.get("name", position.get("name", position["symbol"])),
                value=position["value"],
                pl=position["pl"],
                cost=position["cost"],
                country=instrument.get("country", ""),
                sector=instrument.get("sector", ""),
                region=instrument.get("region", ""),
                qty=position["qty"],
            ))
        return out

    def account_kind(self, row, fund_payee):
        """Row kind: given in the row, a fund purchase (counterparty is the fund payee), or from the statement text."""
        if row.get("kind"):
            return row["kind"]
        if fund_payee and (row.get("counterparty") or "").startswith(fund_payee):
            return "fund"
        description = row.get("description") or ""
        for text, kind in ACCOUNT_KINDS:
            if description.startswith(text):
                return kind
        return "other"

    def account(self):
        """Investment account rows: date, time, description, amount, currency, kind, symbol.
        kind/symbol may be given; otherwise they come from LHV statement texts."""
        fund_payee = (self.json("invest/funds.json", {}) or {}).get("account_fund_payee")
        out = []
        for row in self.json("invest/account.json", []) or []:
            description = row.get("description") or ""
            symbol = row.get("symbol")
            if not symbol:
                found = SYMBOL_IN_TEXT.search(description)
                symbol = found.group(1) if found else ""
            out.append(dict(
                date=row["time"][:10],
                time=row["time"],
                description=description,
                amount=row["amount"],
                currency=row["currency"],
                counterparty=row.get("counterparty", ""),
                kind=self.account_kind(row, fund_payee),
                symbol=symbol,
            ))
        return out
