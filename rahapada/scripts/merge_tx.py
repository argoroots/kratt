"""Merge transactions (a JSON array, e.g. written from a bank connection) into the store's month files.

Usage:
  python3 merge_tx.py ROWS.json WORK/tx

Rows are grouped by booking month (pending rows by their date) into WORK/tx/<YYYY-MM>.json; the same id replaces the old row.
"""
import sys

from common import load_json, merge_by_month

if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit(__doc__)
    print("Kuud:", ", ".join(merge_by_month(load_json(sys.argv[1], []), sys.argv[2])))
