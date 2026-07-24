"""
ISED (Canada) Amateur Data Loader
=================================

Author: Tiran Dagan (Backstop Radio)
Contact: tiran@tirandagan.com
License: MIT License

Description:
-----------
Parses and loads the Canadian ISED "Amateur Call Sign List" (amateur_delim.txt)
into the CA_AM table of the shared SQLite database.

This is deliberately a SEPARATE module from `loader.py` (which handles FCC .dat
files). The ISED file differs in every mechanical detail — it is semicolon
(";") delimited, UTF-8 encoded, has a header row, uses CRLF line endings, and
has no `unique_system_identifier`, license status, or dates. Overloading the
FCC parser would risk regressing the performance-critical FCC load path, so the
ISED path is kept independent while reusing the FCC loader's interrupt-safe
connection helpers (`create_optimized_connection`, connection registration,
and the shared `is_shutting_down` shutdown flag).

Layout of amateur_delim.txt (";"-delimited, 18 fields, in order):
    call_sign, first_name, surname, street_address, city, province, postal_code,
    qual_basic (A), qual_5wpm (B), qual_12wpm (C), qual_advanced (D),
    qual_honours (E), club_name, club_name_2, club_address, club_city,
    club_province, club_postal_code
"""

import os
import csv
import time
import logging
import sqlite3

from modules import loader  # reuse interrupt-safe connection helpers + shutdown flag
from modules.schemas import table_schemas, field_names, index_schemas

# Number of fields expected in every ISED record.
ISED_FIELD_COUNT = len(field_names["CA_AM"])  # 18

# Batch size for bulk inserts (ISED is ~92k rows; a single batch is fine, but
# keep it batched for consistency and memory friendliness).
BATCH_SIZE = 50000


def parse_ised_file(file_path):
    """
    Parse the ISED amateur_delim.txt file into records.

    Robustness measures (see Task 002 §10.8):
    - Read as ``utf-8-sig`` to tolerate a possible BOM on the header line.
    - Skip the header row (first line is column names, not data).
    - Use ``csv.reader`` with ``delimiter=';'`` rather than naive ``str.split``.
    - Skip any row whose field count != 18 and keep a running count that is
      logged at the end (malformed rows are reported, never silently dropped).

    Args:
        file_path (str): Path to amateur_delim.txt.

    Yields:
        list[str]: A list of exactly ``ISED_FIELD_COUNT`` field values.
    """
    skipped = 0
    total = 0
    with open(file_path, 'r', encoding='utf-8-sig', newline='') as f:
        reader = csv.reader(f, delimiter=';')

        # Skip the header row (e.g. "callsign;first_name;surname;...").
        try:
            next(reader)
        except StopIteration:
            logging.warning(f"ISED data file is empty: {file_path}")
            return

        for row in reader:
            if loader.is_shutting_down:
                break

            # Ignore fully blank lines.
            if not row or (len(row) == 1 and not row[0].strip()):
                continue

            total += 1
            if len(row) != ISED_FIELD_COUNT:
                skipped += 1
                if skipped <= 10:  # avoid log spam; a running total is logged below
                    logging.debug(
                        f"Skipping ISED row with {len(row)} fields (expected "
                        f"{ISED_FIELD_COUNT}): {row[:3]}..."
                    )
                continue

            yield row

    if skipped:
        logging.warning(
            f"ISED parse: skipped {skipped} of {total} rows with an unexpected "
            f"field count (expected {ISED_FIELD_COUNT})."
        )
    else:
        logging.info(f"ISED parse: {total} rows, 0 malformed.")


def load_ised_data(db, extract_path):
    """
    Load the ISED amateur data into the CA_AM table.

    Drops and recreates CA_AM (the DB is a disposable mirror), then bulk-inserts
    all valid records inside a single transaction and rebuilds the CA_AM
    indexes. Interrupt-safe: honors ``loader.is_shutting_down`` and rolls back a
    partial load rather than committing a torn table.

    Args:
        db (FCCDatabase): Database wrapper (provides db_path).
        extract_path (str): Directory containing the extracted ISED data file.

    Returns:
        int: Number of records loaded (0 on failure/interrupt).
    """
    from modules.config import Config

    file_path = os.path.join(extract_path, Config.ISED_DATA_FILE)
    if not os.path.exists(file_path):
        logging.error(f"ISED data file not found: {file_path}")
        print(f"Error: ISED data file not found: {file_path}")
        return 0

    start_time = time.time()
    processed = 0
    records = []
    conn = None
    try:
        conn = loader.create_optimized_connection(db.db_path)

        # Fresh table each load.
        logging.info("Dropping and recreating table CA_AM")
        conn.execute("DROP TABLE IF EXISTS CA_AM")
        conn.execute(table_schemas["CA_AM"])

        conn.execute("BEGIN TRANSACTION")

        placeholders = ','.join(['?'] * ISED_FIELD_COUNT)
        insert_sql = f"INSERT INTO CA_AM VALUES ({placeholders})"
        cursor = conn.cursor()

        for record in parse_ised_file(file_path):
            if loader.is_shutting_down:
                break
            records.append(record)
            processed += 1
            if len(records) >= BATCH_SIZE:
                cursor.executemany(insert_sql, records)
                records = []

        if records and not loader.is_shutting_down:
            cursor.executemany(insert_sql, records)

        if loader.is_shutting_down:
            logging.info("Rolling back CA_AM load due to interrupt")
            conn.rollback()
            return 0

        conn.execute("COMMIT")

        # Rebuild indexes after the bulk load.
        logging.info("Rebuilding indexes for CA_AM")
        for index_sql in index_schemas.get("CA_AM", []):
            conn.execute(index_sql)

        elapsed = time.time() - start_time
        rate = processed / elapsed if elapsed > 0 else 0
        logging.info(
            f"Loaded {processed} records into CA_AM in {elapsed:.2f} seconds "
            f"({rate:.2f} records/sec)"
        )
        return processed
    except sqlite3.Error as e:
        logging.error(f"SQLite error during CA_AM load: {e}")
        if conn:
            try:
                conn.rollback()
            except sqlite3.Error:
                pass
        raise
    except KeyboardInterrupt:
        logging.info("Interrupted during CA_AM load. Cleaning up...")
        if conn:
            try:
                conn.rollback()
            except sqlite3.Error:
                pass
        raise
    finally:
        if conn:
            try:
                conn.close()
                loader.unregister_connection(conn)
            except sqlite3.Error:
                pass
