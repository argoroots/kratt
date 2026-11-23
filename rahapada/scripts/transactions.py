"""Load transactions from WORK/tx/*.json and make them ready for the calculations.

Steps:
  0. booked card payments and pending reservations in one list; the reservation times are kept in state
     (card_times). If a card description's time differs from the reservation by whole hours (a payment
     provider's time zone) or the booked row has no time, date and time come from the reservation (local time).
  1. card payment date = purchase date from the description (bank date stays in `booked`)
  2. internal transfers: own accounts, `internal` conditions, and pairs between own accounts
  3. categories (rules.py), lunch rule, one-offs
  4. loan payments that include insurance: insurance as its own row (loans[].insurance)
"""
import collections
import datetime as dt
import glob
import os
import re
from zoneinfo import ZoneInfo

from common import load_json

# "(..1234) 2026-11-02 12:30 PLACE\ADDRESS": card number, date, time, seconds, rest
CARD = re.compile(r"(\(\.\.\d+\))\s+(\d{4}-\d\d-\d\d) (\d\d:\d\d)(:\d\d)?(\s.*)$")
CARD_DATE = re.compile(r"\(\.\.\d+\)\s+(\d{4}-\d\d-\d\d)\s")
PENDING_CARD = re.compile(r"(\(\.\.\d+\))\s+(\d{4}-\d\d-\d\d) (\d\d:\d\d)(?::\d\d)?\s+(.*)$")
DAY_SECONDS = 86400
MAX_ZONE_HOURS = 14
CLOCK_TOLERANCE_SECONDS = 120


def merchant(text):
    """First word of the place in a card description."""
    return re.split(r"[\s\\>]+", text.strip())[0].upper()


class CardTimes:
    """Reservation times of card payments, to correct the time written in booked card payments."""

    def __init__(self, archive, timezone):
        self.timezone = ZoneInfo(timezone)
        self.archive = archive
        self.times = collections.defaultdict(list)
        for reservation in archive:
            self._add(reservation)

    def _add(self, reservation):
        card = CARD.match(reservation["description"])
        if not card:
            return
        moment = dt.datetime.fromisoformat(reservation["time"].replace("Z", "+00:00"))
        local = moment.astimezone(self.timezone).replace(tzinfo=None)
        self.times[(card.group(1), merchant(card.group(5)), reservation["amount"])].append(local)

    def remember(self, rows):
        known = {(item["account"], item["amount"], item["description"]) for item in self.archive}
        for row in rows:
            if not CARD.match(row["description"]) or not row.get("reserved_at"):
                continue
            if (row["account"], row["amount"], row["description"]) in known:
                continue
            reservation = dict(account=row["account"], time=row["reserved_at"], amount=row["amount"], description=row["description"])
            self.archive.append(reservation)
            self._add(reservation)

    def correct(self, description, amount):
        """Description with the reservation's date and time, when the written time is off by whole hours or missing."""
        card = CARD.match(description or "")
        if not card:
            return description
        number, date, time, seconds, rest = card.groups()
        written = dt.datetime.fromisoformat(f"{date}T{time}{seconds or ':00'}")
        reserved = self.times.get((number, merchant(rest), amount), [])
        differences = [((moment - written).total_seconds(), moment) for moment in reserved]
        if not differences:
            return description
        difference, moment = min(differences, key=lambda item: abs(item[0]))
        corrected = f"{number} {moment:%Y-%m-%d %H:%M}{rest}"

        no_time_written = time == "00:00" and not seconds
        if no_time_written and 0 <= difference < DAY_SECONDS:
            return corrected
        hours = round(difference / 3600)
        whole_hours_off = abs(difference - hours * 3600) <= CLOCK_TOLERANCE_SECONDS
        if hours and abs(hours) <= MAX_ZONE_HOURS and whole_hours_off:
            return corrected
        return description


def load_raw(work):
    """All rows of tx/*.json by id (a later file replaces an earlier row with the same id)."""
    rows = {}
    for path in sorted(glob.glob(os.path.join(work, "tx", "*.json"))):
        for row in load_json(path, []):
            row.setdefault("counterparty", "")
            row.setdefault("counterparty_account", "")
            row.setdefault("description", "")
            row.setdefault("currency", "EUR")
            row["amount"] = round(float(row["amount"]), 2)
            row["booked"] = row.get("booked") or row.get("date")
            rows[str(row["id"])] = row
    return list(rows.values())


def booked_day(transaction):
    return transaction.get("booked", transaction["date"])


def card_counterparty(description):
    """Place from a card description: "(..1234) date time PLACE\\ADDRESS" -> PLACE."""
    parts = description.split(" ", 3)
    if description.startswith("(..") and len(parts) > 3:
        return parts[3].split("\\")[0]
    return description


def booked_rows(raw, rules, card_times):
    out = []
    for row in raw:
        if row.get("pending"):
            continue
        description = card_times.correct(row["description"], row["amount"])
        counterparty = row["counterparty"]
        if not counterparty and row.get("card"):
            counterparty = card_counterparty(description)
        own_account = bool(row["counterparty_account"]) and row["counterparty_account"] in rules.own
        has_purchase_date = row.get("date") and row["date"][:10] != row["booked"][:10]
        out.append(dict(
            id=str(row["id"]),
            account=row["account"],
            date=row["booked"][:10],
            amount=row["amount"],
            currency=row["currency"],
            counterparty=counterparty or "",
            counterparty_account=row["counterparty_account"] or "",
            internal=own_account,
            description=description,
            purchase=row["date"][:10] if has_purchase_date else None,
        ))
    return out


def pending_rows(raw, booked, card_times):
    """Pending card payments with a description in the same form as a booked card payment (unless already booked)."""
    already_booked = {(row["account"], row["amount"], row["description"][:25]) for row in booked}
    out = []
    for row in raw:
        if not row.get("pending"):
            continue
        card = PENDING_CARD.match(row["description"])
        if not card:
            continue
        number, date, time, rest = card.groups()
        name, _, place = rest.partition(">")
        address = "".join("\\" + word for word in place.split())
        description = card_times.correct(f"{number} {date} {time} {name.strip()}" + address, row["amount"])
        if (row["account"], row["amount"], description[:25]) in already_booked:
            continue
        out.append(dict(
            id=str(row["id"]),
            account=row["account"],
            date=description.split()[1],
            amount=row["amount"],
            currency=row["currency"],
            counterparty=name.strip(),
            counterparty_account="",
            internal=False,
            description=description,
            pending=True,
        ))
    return out


def use_purchase_dates(rows, rules):
    """Date = purchase date (from an LHV-style card description, else from an imported statement); bank date in `booked`."""
    for row in rows:
        card = CARD_DATE.match(row["description"])
        day = card.group(1) if card else row.get("purchase")
        row.pop("purchase", None)
        if row.get("pending") or not day:
            continue
        if day != row["date"] and day >= rules.start:
            row["booked"] = row["date"]
            row["date"] = day


def pair_internal(rows, rules):
    """settings.pair_internal [from, to]: same bank day, amount and counterparty out of one and into the other."""
    pair = rules.settings.get("pair_internal") or []
    if not pair:
        return
    from_account, to_account = pair
    incoming = collections.defaultdict(list)
    for row in rows:
        if row["account"] == to_account and row["amount"] > 0 and not row["internal"]:
            incoming[(booked_day(row), row["amount"], row["counterparty"])].append(row)
    for row in rows:
        if row["account"] != from_account or row["amount"] >= 0 or row["internal"]:
            continue
        matches = incoming.get((booked_day(row), -row["amount"], row["counterparty"]))
        if matches:
            row["internal"] = True
            matches.pop(0)["internal"] = True


def insurance_amount(row, insurance, schedule):
    """Insurance inside a loan payment: from the schedule, or the fixed amount (insurance.fixed)."""
    month = booked_day(row)[:7]
    scheduled = schedule.get(month)
    from_schedule = (
        scheduled
        and scheduled.get("insurance")
        and str(month) >= str(insurance.get("schedule_from", "0000"))
        and abs(-row["amount"] - scheduled["payment"]) < 1
    )
    if from_schedule:
        return scheduled["insurance"]
    fixed = insurance.get("fixed")
    if not fixed:
        return None
    low, high = fixed["amount_range"]
    if month < str(fixed["until"]) and low < row["amount"] < high and row["description"].startswith(fixed.get("description_starts", "")):
        return fixed["amount"]
    return None


def split_insurance(rows, rules):
    """Rows for insurance paid inside loan payments (rules.json loans[].insurance); the loan row gets smaller."""
    extra = []
    for loan in rules.raw.get("loans") or []:
        insurance = loan.get("insurance")
        if not insurance:
            continue
        schedule = {str(row["month"]): row for row in loan.get("schedule") or []}
        for row in rows:
            if row["category"] != loan["category"] or row["amount"] >= 0:
                continue
            amount = insurance_amount(row, insurance, schedule)
            if not amount:
                continue
            row["amount"] = round(row["amount"] + amount, 2)
            insurance_row = dict(row)
            insurance_row.update(
                amount=-amount,
                category=insurance["category"],
                description=row["description"] + insurance.get("suffix", " (kindlustus)"),
                id=row["id"] + "-ins",
            )
            extra.append(insurance_row)
    return extra


def prepare(work, rules, state):
    raw = load_raw(work)
    card_times = CardTimes(state.setdefault("card_times", []), rules.settings.get("timezone", "UTC"))
    card_times.remember([row for row in raw if row.get("pending")])

    rows = booked_rows(raw, rules, card_times)
    rows += pending_rows(raw, rows, card_times)
    use_purchase_dates(rows, rules)
    for row in rows:
        rules.mark_internal(row)
    pair_internal(rows, rules)
    for row in rows:
        rules.categorise(row)
    rows += split_insurance(rows, rules)
    for row in rows:
        rules.mark_oneoff(row)
    return rows
