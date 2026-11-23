"""Shared helpers for Rahapada scripts: files, dates, months, money."""
import calendar
import collections
import datetime as dt
import glob
import json
import os
import re


def load_json(path, default=None):
    if not path or not os.path.exists(path):
        return default
    with open(path, encoding="utf-8") as file:
        return json.load(file)


def save_json(path, data):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False, separators=(",", ":"), allow_nan=False)


def r2(value):
    """Round to cents (and turn -0.0 into 0.0)."""
    return round(float(value) + 0.0, 2)


def month_of(date):
    return str(date)[:7]


def month_add(month, count):
    """YYYY-MM plus count months."""
    year = int(month[:4])
    index = int(month[5:7]) - 1 + count
    return f"{year + index // 12:04d}-{index % 12 + 1:02d}"


def month_range(first, last):
    """All months from first to last (inclusive)."""
    months = []
    month = first
    while month <= last:
        months.append(month)
        month = month_add(month, 1)
    return months


def days_in(month):
    return calendar.monthrange(int(month[:4]), int(month[5:7]))[1]


def today_str(value=None):
    return value or dt.date.today().isoformat()


def upper(text):
    return re.sub(r"\s+", " ", str(text or "")).strip().upper()


def quantile(values, share):
    """Linear interpolation quantile (share 0..1)."""
    ordered = sorted(values)
    if not ordered:
        return 0.0
    position = (len(ordered) - 1) * share
    low = int(position)
    high = min(low + 1, len(ordered) - 1)
    return ordered[low] + (ordered[high] - ordered[low]) * (position - low)


def mean(values):
    values = list(values)
    return sum(values) / len(values) if values else 0.0


def merge_by_month(rows, tx_dir, today=None):
    """Merge transactions into tx_dir/<YYYY-MM>.json by booking month (pending rows: their date or reservation month).
    A row with the same id replaces the old one. Old pending rows of the accounts in `rows` are dropped (the new
    fetch has the reservations that are still open). Returns the months written."""
    accounts = {row.get("account") for row in rows}
    for path in glob.glob(os.path.join(tx_dir, "*.json")):
        old = load_json(path, []) or []
        keep = [row for row in old if not (row.get("pending") and row.get("account") in accounts)]
        if len(keep) != len(old):
            save_json(path, keep)

    by_month = collections.defaultdict(list)
    for row in rows:
        day = row.get("booked") or row.get("date") or row.get("reserved_at") or today or ""
        by_month[str(day)[:7]].append(row)

    def order(row):
        return (str(row.get("booked") or row.get("date") or ""), str(row["id"]))

    os.makedirs(tx_dir, exist_ok=True)
    for month, month_rows in by_month.items():
        path = os.path.join(tx_dir, month + ".json")
        merged = {str(row["id"]): row for row in load_json(path, []) or []}
        for row in month_rows:
            merged[str(row["id"])] = row
        save_json(path, sorted(merged.values(), key=order))
    return sorted(by_month)
