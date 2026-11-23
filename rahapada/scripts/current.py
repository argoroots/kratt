"""Current month: so far, recurring payments (paid and pending), variable spending and the forecast to month end.

"Typical month" = average of the window (last N full months). Recurring: same name and category in at least
`recurring_min_months` window months; one payee's payments on different days (gap over 5 days) are separate rows.
Variable spending for the remaining days comes from the same part of the window months, aligned to payday
(before and after payday stretched or squeezed). Range: leave-one-out over the window months, start day ±2,
10th and 90th percentile.

Rows: [date, name, category, amount, recurring_candidate] (monthly.compact).
"""
import calendar
import collections
import datetime
import statistics

from common import quantile

# Payments of one payee more than this many days apart are separate recurring rows.
GAP_DAYS = 5
# Start day shifts used for the forecast range.
START_SHIFTS = range(-2, 3)


def row_month(row):
    return row[0][:7]


def row_day(row):
    return int(row[0][8:])


def recurring_key(row):
    """name, category, recurring_candidate"""
    return (row[1], row[2], bool(row[4]))


def month_length(month):
    return calendar.monthrange(int(month[:4]), int(month[5:]))[1]


def previous_month(year, month):
    if month > 1:
        return year, month - 1
    return year - 1, 12


def day_ranges(days):
    """Split sorted days into ranges where neighbours are at most GAP_DAYS apart: [(first, last), ...]."""
    ranges = [[days[0]]]
    for day in days[1:]:
        if day - ranges[-1][-1] > GAP_DAYS:
            ranges.append([day])
        else:
            ranges[-1].append(day)
    return [(min(days_in_range), max(days_in_range)) for days_in_range in ranges]


def find_recurring(rows, window, min_months):
    """Recurring payments of the window months: name, category, median amount and day, day range."""
    by_key = collections.defaultdict(lambda: collections.defaultdict(list))
    for row in rows:
        if row_month(row) in window and row[4]:
            by_key[recurring_key(row)][row_month(row)].append(row)

    recurring = []
    for (name, category, _), by_month in by_key.items():
        if len(by_month) < min_months:
            continue
        days = sorted({row_day(row) for month_rows in by_month.values() for row in month_rows})
        ranges = day_ranges(days)
        for first, last in ranges:
            selected = {}
            for month, month_rows in by_month.items():
                in_range = [row for row in month_rows if first <= row_day(row) <= last]
                if in_range:
                    selected[month] = in_range
            if len(ranges) > 1 and len(selected) < min_months:
                continue
            month_totals = [sum(row[3] for row in month_rows) for month_rows in selected.values()]
            first_days = [int(month_rows[0][0][8:]) for month_rows in selected.values()]
            recurring.append(dict(
                name=name,
                category=category,
                amount=round(statistics.median(month_totals), 2),
                day=int(statistics.median(first_days)),
                lo=first,
                hi=last,
            ))
    return recurring


def recurring_of(row, recurring):
    """(name, category, day) of the recurring payment this row belongs to, or None."""
    candidates = [item for item in recurring if (item["name"], item["category"], True) == recurring_key(row)]
    if not candidates:
        return None
    day = row_day(row)

    def distance(item):
        if item["lo"] <= day <= item["hi"]:
            gap = 0
        else:
            gap = min(abs(day - item["lo"]), abs(day - item["hi"]))
        return (gap, item["day"])

    best = min(candidates, key=distance)
    return (best["name"], best["category"], best["day"])


class Paydays:
    """Payday of a month: the first salary row, else settings.payday, else the usual first salary day (or the 10th).
    A payday on a weekend or holiday moves to the working day before."""

    def __init__(self, rules, rows, salary_categories):
        self.rules = rules
        self.rows = rows
        self.salary = salary_categories
        self.default_day = rules.settings.get("payday")

    def usual_day(self):
        salary_months = {row_month(row) for row in self.rows if row[2] in self.salary}
        first_days = []
        for month in salary_months:
            first_days.append(min(row_day(row) for row in self.rows if row_month(row) == month and row[2] in self.salary))
        first_days.sort()
        if first_days:
            return first_days[len(first_days) // 2]
        return 10

    def of(self, year, month):
        key = f"{year}-{month:02d}"
        salary_days = sorted(row_day(row) for row in self.rows if row_month(row) == key and row[2] in self.salary)
        if salary_days:
            return salary_days[0]
        day = self.default_day or self.usual_day()
        day = int(day)
        while not self.rules.is_working_day(datetime.date(year, month, day)):
            day -= 1
        return day


def expected_payments(recurring, month_rows, current, salary, payday, open_day, month_days):
    """Recurring payments of the current month: paid (from the data) or pending (expected date and amount)."""
    expected = []
    for item in sorted(recurring, key=lambda item: item["day"]):
        key = (item["name"], item["category"], item["day"])
        paid = [row for row in month_rows if recurring_of(row, recurring) == key]
        if paid:
            expected.append(dict(
                date=paid[0][0],
                name=item["name"],
                category=item["category"],
                amount=round(sum(row[3] for row in paid), 2),
                status="paid",
            ))
            continue
        usual_day = payday if item["category"] in salary else item["day"]
        day = max(usual_day, open_day)
        expected.append(dict(
            date=f"{current}-{min(day, month_days):02d}",
            name=item["name"],
            category=item["category"],
            amount=item["amount"],
            status="pending",
        ))
    expected.sort(key=lambda payment: payment["date"])
    return expected


class VariableSpending:
    """Variable (not recurring) spending of the window months, aligned to payday."""

    def __init__(self, rows, window, recurring_keys, paydays, payday, month_days):
        self.window = window
        self.payday = payday
        self.month_days = month_days

        by_date = collections.defaultdict(float)
        for row in rows:
            if recurring_key(row) not in recurring_keys:
                by_date[row[0][:10]] += row[3]

        self.window_payday = {}
        self.cumulative = {}
        for month in window:
            self.window_payday[month] = paydays.of(int(month[:4]), int(month[5:]))
            totals = [0.0]
            for day in range(1, month_length(month) + 1):
                totals.append(totals[-1] + by_date[f"{month}-{day:02d}"])
            self.cumulative[month] = totals

    def window_time(self, day, month):
        """Day of the current month mapped to the same point (relative to payday) in a window month."""
        window_payday = self.window_payday[month]
        window_days = month_length(month)
        if day <= self.payday:
            return day * window_payday / max(1, self.payday)
        return window_payday + (day - self.payday) * (window_days - window_payday) / max(1, self.month_days - self.payday)

    def cumulative_at(self, month, time):
        totals = self.cumulative[month]
        index = min(int(time), len(totals) - 1)
        fraction = time - index
        if index + 1 < len(totals):
            return totals[index] + fraction * (totals[index + 1] - totals[index])
        return totals[index] + 0

    def between(self, month, first_day, last_day):
        """Spending of a window month between two days of the current month (aligned)."""
        end = self.cumulative_at(month, self.window_time(last_day, month))
        start = self.cumulative_at(month, self.window_time(first_day, month))
        return end - start

    def expected_by_day(self):
        expected = {}
        for day in range(1, self.month_days + 1):
            if self.window:
                expected[day] = sum(self.between(month, day - 1, day) for month in self.window) / len(self.window)
            else:
                expected[day] = 0.0
        return expected

    def leave_one_out(self, open_day):
        """Differences of each window month from the average of the others, by number of days from open_day."""
        differences = collections.defaultdict(list)
        if len(self.window) <= 1:
            return differences
        for shift in START_SHIFTS:
            start = min(max(open_day - 1 + shift, 0), self.month_days - 1)
            for month in self.window:
                others = [other for other in self.window if other != month]
                for length in range(1, self.month_days - start + 1):
                    own = self.between(month, start, start + length)
                    others_average = sum(self.between(other, start, start + length) for other in others) / len(others)
                    differences[length].append(own - others_average)
        return differences


class PreviousMonth:
    """Running total of the previous month, aligned to payday, for the comparison line."""

    def __init__(self, rows, year, month, paydays, payday, month_days):
        prev_year, prev_month = previous_month(year, month)
        key = f"{prev_year}-{prev_month:02d}"
        self.present = any(row_month(row) == key for row in rows)
        self.days = calendar.monthrange(prev_year, prev_month)[1]
        self.payday = paydays.of(prev_year, prev_month)
        self.current_payday = payday
        self.current_days = month_days

        by_day = collections.defaultdict(float)
        for row in rows:
            if row_month(row) == key:
                by_day[row_day(row)] += row[3]
        self.cumulative = {}
        total = 0
        for day in range(1, self.days + 1):
            total += by_day.get(day, 0)
            self.cumulative[day] = total

    def at(self, day):
        if not self.present:
            return None
        if day <= self.current_payday:
            time = 1 + (day - 1) * (self.payday - 1) / max(1, self.current_payday - 1)
        else:
            time = self.payday + (day - self.current_payday) * (self.days - self.payday) / max(1, self.current_days - self.current_payday)
        return round(self.cumulative[min(self.days, int(time + 1e-9))], 2)


def build(rules, rows, window, current, today, last=None):
    """rows: compact rows of the window months, the previous month and the current month."""
    settings = rules.settings
    min_months = int(settings.get("recurring_min_months", 3))
    salary = set(settings.get("salary_categories") or [])

    def is_income(category):
        return rules.role(category, "income")

    def is_pension(category):
        return rules.role(category, "pension")

    month_rows = [row for row in rows if row_month(row) == current]
    last_date = last or max([row[0] for row in month_rows] or [f"{current}-01"])
    year, month = int(current[:4]), int(current[5:7])
    month_days = calendar.monthrange(year, month)[1]
    data_day = int(last_date[8:10]) if (month_rows or last) else 0
    # The first day that can still get new rows.
    open_day = data_day if last_date == today else data_day + 1

    recurring = find_recurring(rows, window, min_months)
    recurring_keys = {(item["name"], item["category"], True) for item in recurring}

    def is_recurring(row):
        return recurring_key(row) in recurring_keys

    paydays = Paydays(rules, rows, salary)
    payday = paydays.of(year, month)
    expected = expected_payments(recurring, month_rows, current, salary, payday, open_day, month_days)
    pending = [payment for payment in expected if payment["status"] == "pending"]

    def pending_on(day):
        return sum(payment["amount"] for payment in pending if int(payment["date"][8:]) == day)

    # Variable spending per category per day in the window.
    window_days = sum(month_length(window_month) for window_month in window)
    variable_by_category = collections.defaultdict(float)
    for row in rows:
        if row_month(row) in window and not is_recurring(row):
            variable_by_category[row[2]] += row[3] / window_days
    variable_per_day = sum(variable_by_category.values())

    actual_by_day = collections.defaultdict(float)
    for row in month_rows:
        actual_by_day[row_day(row)] += row[3]

    previous = PreviousMonth(rows, year, month, paydays, payday, month_days)
    variable = VariableSpending(rows, window, recurring_keys, paydays, payday, month_days)
    expected_variable = variable.expected_by_day()
    differences = variable.leave_one_out(open_day)

    variable_today = sum(row[3] for row in month_rows if row_day(row) == data_day and not is_recurring(row))
    if open_day == data_day and data_day:
        rest_of_today = min(0, expected_variable[data_day] - variable_today)
    else:
        rest_of_today = 0
    variable_rest = sum(expected_variable[day] for day in range(data_day + 1, month_days + 1))

    days = []
    running = 0
    forecast = 0.0
    for day in range(1, month_days + 1):
        date = f"{current}-{day:02d}"
        if day <= data_day:
            running += actual_by_day.get(day, 0)
            if day == data_day:
                forecast = running + rest_of_today + pending_on(day)
            day_forecast = round(forecast, 2) if day == data_day else None
            row = dict(day=day, date=date, actual=round(running, 2), forecast=day_forecast, prev=previous.at(day))
        else:
            forecast += expected_variable[day] + pending_on(day)
            row = dict(day=day, date=date, actual=None, forecast=round(forecast, 2), prev=previous.at(day))

        days_ahead = day - open_day + 1
        if day >= data_day and days_ahead >= 1 and differences.get(days_ahead):
            row["lo"] = round(row["forecast"] + quantile(differences[days_ahead], 0.1), 2)
            row["hi"] = round(row["forecast"] + quantile(differences[days_ahead], 0.9), 2)
        elif day == data_day:
            row["lo"] = row["hi"] = row["forecast"]
        else:
            row["lo"] = row["hi"] = None
        days.append(row)

    # Summary numbers.
    window_count = max(1, len(window))
    days_left = month_days - data_day
    income_so_far = sum(row[3] for row in month_rows if is_income(row[2]))
    spent_so_far = sum(row[3] for row in month_rows if not is_income(row[2]))
    expected_income = round(sum(payment["amount"] for payment in pending if payment["amount"] > 0), 2)
    expected_fixed = round(-sum(payment["amount"] for payment in pending if payment["amount"] < 0), 2)
    expected_variable_total = round(-rest_of_today - variable_rest, 2)
    recurring_spent = sum(row[3] for row in month_rows if is_recurring(row) and not is_income(row[2]))
    variable_spent = sum(row[3] for row in month_rows if not is_recurring(row) and not is_income(row[2]))
    fixed_so_far = round(-recurring_spent, 2)
    var_so_far = round(-variable_spent, 2)
    invest_so_far = -sum(row[3] for row in month_rows if is_pension(row[2]))
    invest_expected = -sum(payment["amount"] for payment in pending if is_pension(payment["category"]))
    income_end = round(round(income_so_far, 2) + expected_income, 2)
    fixed_end = round(fixed_so_far + expected_fixed, 2)
    var_end = round(var_so_far + expected_variable_total, 2)

    summary = [
        dict(metric="income_so_far", value=round(income_so_far, 2)),
        dict(metric="spent_so_far", value=round(-spent_so_far, 2)),
        dict(metric="net_so_far", value=round(income_so_far + spent_so_far, 2)),
        dict(metric="expected_income", value=expected_income),
        dict(metric="expected_fixed", value=expected_fixed),
        dict(metric="expected_variable", value=expected_variable_total),
        dict(metric="var_per_day", value=round(-variable_rest / max(1, days_left), 2)),
        dict(metric="forecast_end", value=round(forecast, 2)),
        dict(metric="forecast_lo", value=days[-1]["lo"]),
        dict(metric="forecast_hi", value=days[-1]["hi"]),
        dict(metric="days_left", value=days_left),
        dict(metric="today", value=data_day),
        # Pension payments are shown as investments, not as fixed costs.
        dict(metric="fixed_so_far", value=round(fixed_so_far - invest_so_far, 2)),
        dict(metric="var_so_far", value=var_so_far),
        dict(metric="typical_net", value=round(sum(row[3] for row in rows if row_month(row) in window) / window_count, 2)),
        dict(metric="income_end", value=income_end),
        dict(metric="fixed_end", value=round(fixed_end - invest_so_far - invest_expected, 2)),
        dict(metric="var_end", value=var_end),
        dict(metric="invest_so_far", value=round(invest_so_far, 2)),
        dict(metric="invest_end", value=round(invest_so_far + invest_expected, 2)),
    ]

    categories, groups = category_forecast(
        rules, rows, window, month_rows, pending, variable_by_category,
        days_left, variable_rest + rest_of_today, variable_per_day,
    )
    return dict(days=days, expected=expected, summary=summary, categories=categories, groups=groups)


def category_forecast(rules, rows, window, month_rows, pending, variable_by_category, days_left, variable_left, variable_per_day):
    """Per category and group: actual so far, forecast to month end and the typical month."""
    income_label = rules.label("income")

    def is_income(category):
        return rules.role(category, "income")

    def group_of(category):
        return income_label if is_income(category) else rules.group(category)

    window_count = max(1, len(window))
    # The aligned variable forecast differs from the plain daily average; scale categories to match it.
    if variable_per_day and days_left:
        scale = variable_left / (variable_per_day * days_left)
    else:
        scale = 1

    actual = collections.defaultdict(float)
    typical = collections.defaultdict(float)
    pending_by_category = collections.defaultdict(float)
    for row in month_rows:
        actual[row[2]] += row[3]
    for row in rows:
        if row_month(row) in window:
            typical[row[2]] += row[3] / window_count
    for payment in pending:
        pending_by_category[payment["category"]] += payment["amount"]

    categories = []
    for category in sorted(set(actual) | set(typical) | set(pending_by_category) | set(variable_by_category)):
        sign = 1 if is_income(category) else -1
        so_far = actual.get(category, 0)
        forecast = so_far + pending_by_category.get(category, 0) + variable_by_category.get(category, 0) * days_left * scale
        categories.append(dict(
            category=category,
            grp=group_of(category),
            actual=round(sign * so_far, 2),
            forecast=round(sign * forecast, 2),
            typical=round(sign * typical.get(category, 0), 2),
        ))

    order = [income_label] + list(rules.group_order) + [rules.label("investments")]
    groups = []
    for group in order:
        members = [item for item in categories if item["grp"] == group]
        if members:
            groups.append(dict(
                grp=group,
                actual=round(sum(item["actual"] for item in members), 2),
                forecast=round(sum(item["forecast"] for item in members), 2),
                typical=round(sum(item["typical"] for item in members), 2),
            ))
    return categories, groups
