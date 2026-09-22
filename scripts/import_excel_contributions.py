import argparse
import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

import pandas as pd
import pyodbc


DEFAULT_WORKBOOK = Path(
    r"C:\Users\sarangs\OneDrive - Hewlett Packard Enterprise\dump\My Moi_Sei.xlsx"
)
HOST_PHONE = "7411346811"
DUMMY_PHONE_START = 9_900_000_001


def nullable_text(value):
    if value is None or pd.isna(value):
        return None
    text = str(value).strip()
    return text or None


def normalize_phone(value):
    text = nullable_text(value)
    if text is None:
        return None
    if re.fullmatch(r"\d+\.0", text):
        text = text[:-2]
    digits = re.sub(r"\D", "", text)
    if len(digits) == 12 and digits.startswith("91"):
        digits = digits[2:]
    return digits or None


def load_rows(workbook):
    frame = pd.read_excel(workbook, dtype=object)
    required = {
        "Initial / Code",
        "husband_name",
        "wife_name",
        "husband_job",
        "phone_number",
        "current_place",
        "Moy Amount (₹)",
    }
    missing = required.difference(frame.columns)
    if missing:
        raise ValueError(f"Workbook is missing columns: {', '.join(sorted(missing))}")

    real_phones = {
        phone
        for phone in (normalize_phone(value) for value in frame["phone_number"])
        if phone
    }
    if HOST_PHONE in real_phones:
        raise ValueError(
            f"Workbook contains host phone {HOST_PHONE}; the host cannot contribute to their own event."
        )

    rows = []
    assigned_phones = set()
    next_dummy = DUMMY_PHONE_START
    for index, record in frame.iterrows():
        husband_name = nullable_text(record["husband_name"])
        if husband_name is None:
            raise ValueError(f"Excel row {index + 2} has no husband_name.")

        phone = normalize_phone(record["phone_number"])
        if phone is None:
            while str(next_dummy) in real_phones or str(next_dummy) in assigned_phones:
                next_dummy += 1
            phone = str(next_dummy)
            next_dummy += 1
        if phone in assigned_phones:
            raise ValueError(f"Excel row {index + 2} repeats phone number {phone}.")

        try:
            amount_text = str(record["Moy Amount (₹)"]).replace(",", "").replace("₹", "").strip()
            amount = Decimal(amount_text).quantize(Decimal("0.01"))
        except (InvalidOperation, ValueError):
            raise ValueError(f"Excel row {index + 2} has an invalid contribution amount.")
        if not amount.is_finite() or amount <= 0:
            raise ValueError(f"Excel row {index + 2} must have a positive contribution amount.")

        assigned_phones.add(phone)
        rows.append(
            {
                "initial": nullable_text(record["Initial / Code"]),
                "husband_name": husband_name,
                "wife_name": nullable_text(record["wife_name"]),
                "husband_job": nullable_text(record["husband_job"]),
                "phone_number": phone,
                "current_place": nullable_text(record["current_place"]),
                "amount": amount,
                "is_dummy_phone": normalize_phone(record["phone_number"]) is None,
            }
        )
    return rows


def connect():
    return pyodbc.connect(
        r"DRIVER={ODBC Driver 18 for SQL Server};"
        r"SERVER=JNPR-WIN-MPRZ09\SQLEXPRESS;"
        r"DATABASE=MoiSei;Trusted_Connection=yes;TrustServerCertificate=yes;"
    )


def import_rows(rows):
    connection = connect()
    cursor = connection.cursor()
    backup_suffix = datetime.now().strftime("%Y%m%d_%H%M%S")
    try:
        cursor.execute(
            "SELECT husband_name, wife_name, husband_job, place, family_deity, email, "
            "search_alias, native_place, current_place, wife_job, others "
            "FROM dbo.users WHERE phone_number = ?",
            HOST_PHONE,
        )
        host = cursor.fetchone()
        if host is None:
            host = ("Host User", None, None, None, None, None, None, None, None, None, None)

        for table in ("users", "event", "transactions", "journal_entries"):
            cursor.execute(
                f"SELECT * INTO dbo.{table}_backup_{backup_suffix} FROM dbo.{table}"
            )

        cursor.execute(
            "IF COL_LENGTH('dbo.users', 'initial') IS NULL "
            "ALTER TABLE dbo.users ADD initial NVARCHAR(50) NULL"
        )
        cursor.execute("DELETE FROM dbo.journal_entries")
        cursor.execute("DELETE FROM dbo.transactions")
        cursor.execute("DELETE FROM dbo.event")
        cursor.execute("DELETE FROM dbo.users")

        cursor.execute(
            "INSERT INTO dbo.users "
            "(husband_name, wife_name, husband_job, phone_number, place, family_deity, email, "
            "search_alias, native_place, current_place, wife_job, others, initial) "
            "OUTPUT INSERTED.id VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL)",
            host[0], host[1], host[2], HOST_PHONE, host[3], host[4], host[5], host[6],
            host[7], host[8], host[9], host[10],
        )
        host_id = cursor.fetchone()[0]

        cursor.execute(
            "INSERT INTO dbo.event "
            "(event_name, event_date, event_place, event_location, host_user_id) "
            "OUTPUT INSERTED.event_id VALUES (?, ?, ?, ?, ?)",
            "Imported Moi Contributions 2026",
            date.today(),
            "Moi Sei",
            "Excel import",
            host_id,
        )
        event_id = cursor.fetchone()[0]

        for row in rows:
            cursor.execute(
                "INSERT INTO dbo.users "
                "(initial, husband_name, wife_name, husband_job, phone_number, current_place) "
                "OUTPUT INSERTED.id VALUES (?, ?, ?, ?, ?, ?)",
                row["initial"], row["husband_name"], row["wife_name"], row["husband_job"],
                row["phone_number"], row["current_place"],
            )
            contributor_id = cursor.fetchone()[0]
            cursor.execute(
                "EXEC dbo.sp_ProcessContribution "
                "@ContributorId=?, @ReceiverId=?, @EventId=?, @Amount=?",
                contributor_id, host_id, event_id, row["amount"],
            )

        connection.commit()
        return host_id, event_id, backup_suffix
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def main():
    parser = argparse.ArgumentParser(description="Replace Moi Sei data from the Excel workbook.")
    parser.add_argument("--workbook", type=Path, default=DEFAULT_WORKBOOK)
    parser.add_argument("--execute", action="store_true", help="Apply the destructive import.")
    args = parser.parse_args()

    rows = load_rows(args.workbook)
    dummy_count = sum(row["is_dummy_phone"] for row in rows)
    total_amount = sum((row["amount"] for row in rows), Decimal("0"))
    print(f"Validated {len(rows)} contributors totaling {total_amount:.2f}.")
    print(f"Real phones: {len(rows) - dummy_count}; dummy phones: {dummy_count}.")
    if dummy_count:
        dummy_phones = [row["phone_number"] for row in rows if row["is_dummy_phone"]]
        print(f"Dummy sequence: {dummy_phones[0]} through {dummy_phones[-1]}.")

    if not args.execute:
        print("Dry run only. Re-run with --execute to replace the database data.")
        return

    host_id, event_id, backup_suffix = import_rows(rows)
    print(f"Import complete. Host user ID: {host_id}; event ID: {event_id}.")
    print(f"Backup table suffix: {backup_suffix}.")


if __name__ == "__main__":
    main()