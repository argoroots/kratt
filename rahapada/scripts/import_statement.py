"""Convert a bank statement file into Rahapada transactions (JSON).

Supported: ISO 20022 camt.053 / camt.052 XML (all Estonian banks offer it) and CSV
exports (Swedbank, SEB, LHV, Coop, Luminor and others with similar columns).

Usage:
  python3 import_statement.py FILE --account NAME [--iban IBAN] [--out tx.json | --tx WORK/tx]
  python3 import_statement.py FILE --account NAME --map 'date=Kuupäev,amount=Summa,...'

Output rows (one per transaction):
  id, account, date, time, booked, amount, currency, counterparty,
  counterparty_account, description, pending
"""
import argparse
import csv
import io
import json
import re
import sys
import xml.etree.ElementTree as ET

from common import merge_by_month, save_json

DATE_TIME = re.compile(r"\b(20\d\d-\d\d-\d\d)[ T](\d\d:\d\d)")
DATE_TIME_DOT = re.compile(r"\b(\d\d)\.(\d\d)\.(20\d\d|\d\d)\s+(\d\d:\d\d)")


def card_details(description):
    """Purchase date, time and merchant from a card payment description, if present."""
    found = DATE_TIME.search(description or "")
    if found:
        date, time = found.group(1), found.group(2)
    else:
        found = DATE_TIME_DOT.search(description or "")
        if not found:
            return None, "", ""
        day, month, year, time = found.groups()
        if len(year) == 2:
            year = "20" + year
        date = f"{year}-{month}-{day}"
    rest = description[found.end():]
    rest = re.sub(r"^:\d\d", "", rest)
    merchant = re.split(r"\\|>|\s{2,}", rest.strip())[0].strip()
    return date, time, merchant


def finish(row):
    date, time, merchant = card_details(row["description"])
    if date:
        row["date"], row["time"] = date, time
        if not row["counterparty"] and merchant:
            row["counterparty"] = merchant
    row.setdefault("time", "")
    return row


# ---------- camt.053 ----------

def strip_ns(tree):
    """Remove XML namespaces from tag names."""
    for element in tree.iter():
        if isinstance(element.tag, str) and "}" in element.tag:
            element.tag = element.tag.split("}", 1)[1]
    return tree


def text(element, path):
    found = element.find(path)
    return found.text.strip() if found is not None and found.text else ""


def related_party(details, sign):
    """Name and IBAN of the other party: creditor of a payment out, debtor of a payment in."""
    role = "Cdtr" if sign < 0 else "Dbtr"
    name = text(details, f"RltdPties/{role}/Nm") or text(details, f"RltdPties/{role}/Pty/Nm")
    return name, text(details, f"RltdPties/{role}Acct/Id/IBAN")


def read_camt(data, account, iban):
    root = strip_ns(ET.ElementTree(ET.fromstring(data))).getroot()
    rows = []
    for statement in root.iter():
        if statement.tag not in ("Stmt", "Rpt"):
            continue
        statement_iban = text(statement, "Acct/Id/IBAN")
        if iban and statement_iban and statement_iban != iban:
            continue
        for entry in statement.findall("Ntry"):
            sign = -1 if text(entry, "CdtDbtInd") == "DBIT" else 1
            amount_element = entry.find("Amt")
            amount = sign * float(amount_element.text)
            booked = text(entry, "BookgDt/Dt") or text(entry, "BookgDt/DtTm")[:10]
            pending = text(entry, "Sts/Cd") == "PDNG" or text(entry, "Sts") == "PDNG"
            details = entry.find("NtryDtls/TxDtls")
            if details is None:
                details = entry
            party, party_account = related_party(details, sign)
            remittance = [line.text.strip() for line in details.findall("RmtInf/Ustrd") if line.text]
            description = " ".join(remittance) or text(entry, "AddtlNtryInf")
            reference = text(entry, "AcctSvcrRef") or text(details, "Refs/AcctSvcrRef") or text(entry, "NtryRef")
            rows.append(finish({
                "id": reference or f"{account}:{booked}:{amount}:{description[:40]}",
                "account": account,
                "date": text(entry, "ValDt/Dt") or booked,
                "booked": None if pending else booked,
                "amount": round(amount, 2),
                "currency": amount_element.get("Ccy", "EUR"),
                "counterparty": party,
                "counterparty_account": party_account,
                "description": description,
                "pending": pending,
            }))
    return rows


# ---------- CSV ----------

SYNONYMS = {
    "date": ["kuupäev", "kuupaev", "date", "booking date", "tehingu kuupäev", "kande kuupäev"],
    "amount": ["summa", "amount", "summa eur"],
    "currency": ["valuuta", "currency"],
    "dc": ["deebet/kreedit", "d/k", "debit/credit", "deebet/kreedit (d/c)", "tüüp"],
    "counterparty": ["saaja/maksja", "saaja/maksja nimi", "saaja / maksja", "counterparty", "beneficiary/payer", "saaja/maksja nimi"],
    "counterparty_account": ["saaja/maksja konto", "counterparty account", "saaja/maksja kontonumber"],
    "description": ["selgitus", "description", "details", "makse selgitus"],
    "id": ["arhiveerimistunnus", "dokumendi number", "kande viide", "reference", "archive id", "viitenumber", "tehingu id"],
    "row_type": ["reatüüp", "reatyyp", "row type"],
    "account_iban": ["kliendi konto", "konto", "account"],
}


def parse_amount(value):
    """Amount with a decimal comma or point and optional thousands separators."""
    number = str(value or "").replace("\u00a0", "").replace(" ", "")
    if "," in number and "." in number:
        if number.rfind(",") > number.rfind("."):
            number = number.replace(".", "").replace(",", ".")
        else:
            number = number.replace(",", "")
    else:
        number = number.replace(",", ".")
    return float(number) if number not in ("", "-") else 0.0


def parse_date(value):
    """YYYY-MM-DD from YYYY-MM-DD... or DD.MM.YYYY / DD/MM/YYYY."""
    text_value = str(value or "").strip()
    found = re.match(r"(\d{4})-(\d\d)-(\d\d)", text_value)
    if found:
        return found.group(0)
    found = re.match(r"(\d\d)[./](\d\d)[./](\d{4})", text_value)
    if found:
        return f"{found.group(3)}-{found.group(2)}-{found.group(1)}"
    raise ValueError(f"unknown date: {text_value!r}")


def find_columns(headers, mapping):
    """Column names by field: known header names (SYNONYMS), then --map."""
    columns = {}
    for field, names in SYNONYMS.items():
        for name in names:
            if name in headers:
                columns[field] = headers[name]
                break
    columns.update(mapping)
    return columns


def read_csv(data, account, iban, mapping):
    text_data = data.decode("utf-8-sig", errors="replace")
    sample = text_data[:4000]
    delimiter = max([";", ",", "\t"], key=sample.count)
    reader = csv.DictReader(io.StringIO(text_data), delimiter=delimiter)
    headers = {header.strip().lower(): header for header in reader.fieldnames or []}
    columns = find_columns(headers, mapping)
    missing = [field for field in ("date", "amount") if field not in columns]
    if missing:
        sys.exit(f"Columns not found: {missing}. Headers: {list(headers.values())}. Use --map.")

    def value(record, field):
        return str(record.get(columns.get(field, ""), "") or "").strip()

    rows = []
    for number, record in enumerate(reader):
        # LHV CSV: row type 20 = transaction
        if "row_type" in columns and str(record.get(columns["row_type"], "")).strip() not in ("20", ""):
            continue
        if iban and "account_iban" in columns and record.get(columns["account_iban"]) and record[columns["account_iban"]].strip() != iban:
            continue
        try:
            date = parse_date(record[columns["date"]])
        except (ValueError, KeyError):
            continue
        amount = parse_amount(record[columns["amount"]])
        if value(record, "dc").upper() in ("D", "DEBIT", "DBIT") and amount > 0:
            amount = -amount
        row_id = value(record, "id")
        rows.append(finish({
            "id": row_id or f"{account}:{date}:{amount}:{number}",
            "account": account,
            "date": date,
            "booked": date,
            "amount": round(amount, 2),
            "currency": value(record, "currency") or "EUR",
            "counterparty": value(record, "counterparty"),
            "counterparty_account": value(record, "counterparty_account"),
            "description": value(record, "description"),
            "pending": False,
        }))
    return rows


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("file")
    parser.add_argument("--account", required=True, help="account name as in rules.json")
    parser.add_argument("--iban", default="", help="keep only this account (multi-account files)")
    parser.add_argument("--map", default="", help="CSV columns, e.g. 'date=Kuupäev,amount=Summa'")
    parser.add_argument("--out", default="")
    parser.add_argument("--tx", default="", help="merge into month files <dir>/<YYYY-MM>.json (the store layout)")
    arguments = parser.parse_args()

    with open(arguments.file, "rb") as file:
        data = file.read()
    if data.lstrip()[:1] == b"<":
        rows = read_camt(data, arguments.account, arguments.iban)
    else:
        mapping = dict(pair.split("=", 1) for pair in arguments.map.split(",") if "=" in pair)
        rows = read_csv(data, arguments.account, arguments.iban, mapping)
    rows.sort(key=lambda row: (row["date"], row["time"]))

    if arguments.out:
        save_json(arguments.out, rows)
    if arguments.tx:
        print("Kuud:", ", ".join(merge_by_month(rows, arguments.tx)))
    months = sorted({row["date"][:7] for row in rows})
    print(f"{len(rows)} transactions, {months[0] if months else '-'} … {months[-1] if months else '-'}")
    if not arguments.out and not arguments.tx:
        json.dump(rows, sys.stdout, ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
