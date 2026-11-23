"""Rahapada rules: payee names, conditions, categories, groups and roles (rules.json).

Order for each transaction (first match wins):
  1. internal: own accounts (accounts, own_ibans) and `internal` conditions
  2. exceptions
  3. payee_rules: payees whose transactions split by conditions (then that payee's default)
  4. payees: payee name -> category
  5. keywords in counterparty or description
  6. otherwise the "other" label (uncategorised)
Then: lunch rule, one-off rules.

Every name shown to the user (labels, categories, holidays) comes from rules.json.
"""
import datetime as dt
import re

from common import upper

# Keys in a rule that describe the result, not a condition.
OUTPUT_KEYS = {
    "category", "sub", "note", "lunch", "name", "kind", "loan", "transactions", "yearly",
    "ended", "rules", "match", "bank_names", "oneoff", "trip",
}

# settings.labels keys the scripts need.
LABEL_KEYS = ["income", "expenses", "loans", "investments", "other", "internal", "unassigned_trip"]

CARD_DESCRIPTION = re.compile(r"\(\.\.\d+\) (\d{4})-(\d\d)-(\d\d) (\d\d):(\d\d) (.*)")


def as_list(value):
    """Return value as a list: None -> [], a single value -> [value]."""
    if isinstance(value, list):
        return value
    if value is None:
        return []
    return [value]


def easter(year):
    """Easter Sunday (Gregorian calendar, anonymous algorithm)."""
    golden = year % 19
    century = year // 100
    year_in_century = year % 100
    leap_centuries = century // 4
    century_rest = century % 4
    correction = (century + 8) // 25
    moon_correction = (century - correction + 1) // 3
    epact = (19 * golden + century - leap_centuries - moon_correction + 15) % 30
    leap_years = year_in_century // 4
    year_rest = year_in_century % 4
    weekday = (32 + 2 * century_rest + 2 * leap_years - epact - year_rest) % 7
    shift = (golden + 11 * epact + 22 * weekday) // 451
    month_day = epact + weekday - 7 * shift + 114
    return dt.date(year, month_day // 31, month_day % 31 + 1)


def holidays(year, settings):
    """Public holidays of a year from settings.holidays.

    settings.holidays = {"dates": ["MM-DD", ...], "easter_days": [days from Easter Sunday, ...]}
    No setting means no holidays (only weekends count as days off).
    """
    days = set()
    for text in settings.get("dates") or []:
        month, day = (int(part) for part in str(text).split("-"))
        days.add(dt.date(year, month, day))
    easter_sunday = easter(year)
    for offset in settings.get("easter_days") or []:
        days.add(easter_sunday + dt.timedelta(days=int(offset)))
    return days


def is_working_day(date, settings):
    return date.weekday() < 5 and date not in holidays(date.year, settings)


def description_day(transaction):
    """Day of month written in the description (card payments), else the booking day."""
    found = re.search(r"\d{4}-\d{2}-(\d{2})", transaction.get("description") or "")
    if found:
        return int(found.group(1))
    return int(transaction["date"][8:10])


class Facts:
    """Values of one transaction that conditions compare against."""

    def __init__(self, transaction, payee):
        self.transaction = transaction
        self.counterparty = (transaction.get("counterparty") or "").upper()
        self.description = transaction.get("description") or ""
        self.text = self.counterparty + " | " + self.description.upper()
        self.amount = round(transaction["amount"], 2)
        self.date = transaction["date"][:10]
        self.payee = payee

    def get(self, key):
        return self.transaction.get(key)


def _any_in(words, text):
    return any(word.upper() in text for word in words)


# Each condition: (facts, list of values, raw value) -> bool. A list matches any of its items.
CONDITIONS = {
    "id": lambda f, vs, v: str(f.get("id")) in [str(i) for i in vs],
    "payee": lambda f, vs, v: f.payee in vs,
    "payee_not": lambda f, vs, v: f.payee not in vs,
    "counterparty_contains": lambda f, vs, v: _any_in(vs, f.counterparty),
    "counterparty_starts": lambda f, vs, v: any(f.counterparty.strip().startswith(s.upper()) for s in vs),
    "counterparty_is": lambda f, vs, v: f.counterparty.strip() in [s.upper() for s in vs],
    "counterparty_account": lambda f, vs, v: f.get("counterparty_account") in vs,
    "description_is": lambda f, vs, v: f.description.strip().lower() in [s.lower() for s in vs],
    "description_contains": lambda f, vs, v: _any_in(vs, f.description.upper()),
    "description_not_contains": lambda f, vs, v: not _any_in(vs, f.description.upper()),
    "description_starts": lambda f, vs, v: any(f.description.startswith(s) for s in vs),
    "text_contains": lambda f, vs, v: _any_in(vs, f.text),
    "text_contains_all": lambda f, vs, v: all(s.upper() in f.text for s in vs),
    "text_not_contains": lambda f, vs, v: not _any_in(vs, f.text),
    "text_nospace_contains": lambda f, vs, v: _any_in(vs, f.text.replace(" ", "")),
    "amount": lambda f, vs, v: f.amount in [round(float(s), 2) for s in vs],
    "amount_max": lambda f, vs, v: f.amount <= float(v),
    "amount_min": lambda f, vs, v: f.amount >= float(v),
    "sign": lambda f, vs, v: f.amount > 0 if v == "+" else f.amount < 0,
    "date": lambda f, vs, v: any(f.date.startswith(str(s)) for s in vs),
    "date_from": lambda f, vs, v: f.date >= str(v),
    "date_before": lambda f, vs, v: f.date < str(v),
    "day": lambda f, vs, v: int(f.date[8:10]) in [int(s) for s in vs],
    "description_day_max": lambda f, vs, v: description_day(f.transaction) <= int(v),
    "description_day_over": lambda f, vs, v: description_day(f.transaction) > int(v),
    "account": lambda f, vs, v: f.get("account") in vs,
    "category_is": lambda f, vs, v: f.get("category") in vs,
    "category_starts": lambda f, vs, v: any((f.get("category") or "").startswith(s) for s in vs),
    "category_not": lambda f, vs, v: f.get("category") not in vs,
    "sub_is": lambda f, vs, v: f.get("sub") in vs,
    "sub_not": lambda f, vs, v: f.get("sub") not in vs,
}


def in_category_set(category, definition):
    """True if category is listed in definition.categories or starts with one of definition.prefixes."""
    for prefix in as_list(definition.get("prefixes")):
        if category.startswith(prefix):
            return True
    return category in as_list(definition.get("categories"))


class Rules:
    def __init__(self, raw):
        self.raw = raw or {}
        self.settings = self.raw.get("settings") or {}
        self.start = str(self.settings.get("data_start", "2000-01-01"))
        self.holiday_settings = self.settings.get("holidays") or {}
        self.labels = self._load_labels()

        self._load_payees()
        self._load_names()
        self._load_accounts()

        self.split = {}
        for payee_rule in self.raw.get("payee_rules") or []:
            self.split[payee_rule["payee"]] = payee_rule

        self.groups = self.raw.get("groups") or []
        self.group_order = self.raw.get("group_order") or [group["name"] for group in self.groups]
        self.roles = self.raw.get("roles") or {}

    # ---- setup ----
    def _load_labels(self):
        labels = self.settings.get("labels") or {}
        missing = [key for key in LABEL_KEYS if not labels.get(key)]
        if missing:
            raise SystemExit(f"rules.json: settings.labels is missing {', '.join(missing)}")
        return labels

    def _load_payees(self):
        payees = self.raw.get("payees") or []
        self._patterns = []
        self._exact = {}
        self.payee_category = {}
        for payee in payees:
            for pattern in as_list(payee.get("match")):
                self._patterns.append((re.compile(pattern), payee["name"]))
            for bank_name in as_list(payee.get("bank_names")):
                self._exact[bank_name] = payee["name"]
            if payee.get("category"):
                self.payee_category[payee["name"]] = payee["category"]
        self._pattern_names = {name for _, name in self._patterns}

    def _load_names(self):
        names = self.raw.get("names") or {}
        prefix = names.get("strip_prefix")
        self._strip = re.compile(prefix) if prefix else None
        self._spelled = {key.upper(): value for key, value in (names.get("spelled") or {}).items()}
        self._upper = {word.upper() for word in names.get("keep_upper") or []}

    def _load_accounts(self):
        accounts = self.raw.get("accounts") or []
        self.accounts = {account["iban"]: account["name"] for account in accounts if account.get("iban")}
        self.own = set(self.accounts) | set(self.raw.get("own_ibans") or [])
        self.track_only = {account["name"] for account in accounts if account.get("track_only")}

    def label(self, key):
        return self.labels[key]

    def is_holiday(self, date):
        return date in holidays(date.year, self.holiday_settings)

    def is_working_day(self, date):
        return is_working_day(date, self.holiday_settings)

    # ---- names ----
    def normalise(self, counterparty):
        """Payee name from the first `match` pattern that fits, else the counterparty as is."""
        text = upper(counterparty)
        for pattern, name in self._patterns:
            if pattern.search(text):
                return name
        return counterparty

    def pretty(self, name):
        """Readable payee name: bank_names, then strip_prefix, spelled and keep_upper words."""
        if name in self._exact:
            return self._exact[name]
        has_lower_case = re.search(r"[a-zäöüõšž]", name)
        if name in self._pattern_names or has_lower_case:
            return name
        if self._strip:
            name = self._strip.sub("", name)
        words = []
        for word in name.split():
            word_upper = word.upper()
            if word_upper in self._spelled:
                words.append(self._spelled[word_upper])
            elif word_upper in self._upper:
                words.append(word_upper)
            else:
                words.append(word[:1] + word[1:].lower())
        return " ".join(words)

    def payee_name(self, counterparty):
        return self.pretty(self.normalise(counterparty or "")).strip()

    # ---- conditions ----
    def matches(self, transaction, rule):
        """True if the transaction meets every condition in the rule."""
        if "payee" in transaction:
            payee = transaction.get("payee")
        else:
            payee = self.payee_name(transaction.get("counterparty"))
        facts = Facts(transaction, payee)
        for key, value in rule.items():
            if key in OUTPUT_KEYS:
                continue
            condition = CONDITIONS.get(key)
            if condition is None:
                raise SystemExit(f"rules.json: unknown condition {key!r}")
            if not condition(facts, as_list(value), value):
                return False
        return True

    # ---- groups and roles ----
    def group(self, category):
        for group in self.groups:
            if in_category_set(category, group):
                return group["name"]
        return self.label("other")

    def role(self, category, name):
        """Roles: income, oneoff_income, internal, loan, investment, pension, recurring."""
        if name == "internal" and category == self.label("internal"):
            return True
        definition = self.roles.get(name)
        if not definition:
            return False
        return in_category_set(category, definition)

    # ---- categories ----
    def find(self, transaction):
        """The first rule that fits the transaction, or None."""
        if transaction.get("internal"):
            return {"category": self.label("internal")}

        for exception in self.raw.get("exceptions") or []:
            if self.matches(transaction, exception):
                return exception

        payee = transaction["payee_bank"]
        payee_rule = self.split.get(payee)
        if payee_rule:
            for rule in payee_rule.get("rules") or []:
                if self.matches(transaction, rule):
                    return rule
            if payee_rule.get("category"):
                return payee_rule

        if payee in self.payee_category:
            return {"category": self.payee_category[payee]}

        text = upper(transaction.get("counterparty")) + " " + upper(transaction.get("description"))
        for keyword in self.raw.get("keywords") or []:
            if _any_in(keyword.get("words") or [], text):
                return keyword
        return None

    def lunch(self, transaction):
        """A card payment in lunch.from_category, on a working day, at lunch time, in lunch.places -> lunch.category."""
        settings = self.raw.get("lunch")
        if not settings:
            return
        if transaction["category"] != settings["from_category"] or transaction.get("_no_lunch"):
            return
        card = CARD_DESCRIPTION.match(transaction.get("description") or "")
        if not card:
            return
        year, month, day, hour, _minute, place = card.groups()
        date = dt.date(int(year), int(month), int(day))
        at_lunch_time = settings["from_hour"] <= int(hour) < settings["to_hour"]
        in_lunch_place = _any_in(as_list(settings.get("places")), place.upper())
        if at_lunch_time and self.is_working_day(date) and in_lunch_place:
            transaction["category"] = settings["category"]

    def mark_internal(self, transaction):
        if transaction.get("internal"):
            return
        if any(self.matches(transaction, rule) for rule in self.raw.get("internal") or []):
            transaction["internal"] = True

    def mark_oneoff(self, transaction):
        rules = self.raw.get("oneoff") or []
        transaction["oneoff"] = any(self.matches(transaction, rule) for rule in rules)

    def categorise(self, transaction):
        transaction["payee_bank"] = self.payee_name(transaction.get("counterparty"))
        rule = self.find(transaction)
        transaction["uncategorised"] = rule is None
        if rule is None:
            rule = {"category": self.label("other")}

        transaction["category"] = rule["category"]
        if rule.get("sub"):
            transaction["sub"] = rule["sub"]
        if rule.get("note"):
            transaction["note"] = rule["note"]
        if rule.get("lunch") is False:
            transaction["_no_lunch"] = True
        self.lunch(transaction)
        transaction.pop("_no_lunch", None)
        return transaction
