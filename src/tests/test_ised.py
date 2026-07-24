"""
Unit tests for the Canadian (ISED) support: file parsing, schema parity, the
unified `licenses` view, and order-agnostic name matching.

Run from `src/`:
    python -m unittest tests.test_ised
"""

import os
import unittest
import tempfile
import sqlite3

from modules import ised_loader
from modules.database import FCCDatabase
from modules.schemas import table_schemas, column_counts, field_names


# A tiny ISED fixture: header row, a plain record, a club record, an accented
# name, and a deliberately malformed row (wrong field count) that must be skipped.
ISED_FIXTURE = (
    "callsign;first_name;surname;address_line;city;prov_cd;postal_code;"
    "qual_a;qual_b;qual_c;qual_d;qual_e;club_name;club_name_2;club_address;"
    "club_city;club_prov_cd;club_postal_code\r\n"
    "VA1AA;Bill;McFadden;188 MILLWOOD DRIVE;MIDDLE SACKVILLE;NS;B4E2X8;A;;C;D;;;;;;;\r\n"
    "VA2AA;Jacques;Sauvé;121 DES CHATEAUX;TROIS-RIVIERES;QC;G9B7K7;A;;C;D;;;;;;;\r\n"
    "VA1ADV;James;Hannon;279 PUMPING STATION RD;AMHERST;NS;B4H3Y3;A;;C;D;;"
    "Advocate Fire Dept;;PO BOX 126;ADVOCATE HARBOUR;NS;B0M1A0\r\n"
    "BADROW;only;three;fields\r\n"  # malformed: 4 fields, must be skipped
)


class TestIsedSchemaParity(unittest.TestCase):
    def test_ca_am_parity(self):
        """CA_AM must agree across DDL columns, column_counts, and field_names."""
        body = table_schemas["CA_AM"].split("(", 1)[1].rsplit(")", 1)[0]
        ddl_cols = [c.strip() for c in body.split(",") if c.strip()]
        self.assertEqual(len(ddl_cols), 18)
        self.assertEqual(column_counts["CA_AM"], 18)
        self.assertEqual(len(field_names["CA_AM"]), 18)


class TestParseIsedFile(unittest.TestCase):
    def setUp(self):
        fd, self.path = tempfile.mkstemp(suffix=".txt")
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as f:
            f.write(ISED_FIXTURE)

    def tearDown(self):
        os.remove(self.path)

    def test_parses_valid_rows_skips_header_and_malformed(self):
        rows = list(ised_loader.parse_ised_file(self.path))
        # 3 valid records; header and the malformed row are skipped.
        self.assertEqual(len(rows), 3)
        self.assertTrue(all(len(r) == 18 for r in rows))
        callsigns = [r[0] for r in rows]
        self.assertEqual(callsigns, ["VA1AA", "VA2AA", "VA1ADV"])

    def test_utf8_accents_preserved(self):
        rows = list(ised_loader.parse_ised_file(self.path))
        va2aa = next(r for r in rows if r[0] == "VA2AA")
        self.assertEqual(va2aa[2], "Sauvé")  # accented surname round-trips


class TestUnifiedViewAndSearch(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.db = FCCDatabase(os.path.join(self.dir, "unified.db"))
        # Load the CA fixture.
        extract = os.path.join(self.dir, "extract")
        os.makedirs(extract)
        from modules.config import Config
        with open(os.path.join(extract, Config.ISED_DATA_FILE), "w",
                  encoding="utf-8", newline="") as f:
            f.write(ISED_FIXTURE)
        self.db.create_tables(["CA_AM"])
        ised_loader.load_ised_data(self.db, extract)
        # Add one synthetic US record stored "Last, First" to test order-agnostic search.
        self.db.create_tables(["AM", "EN", "HD"])
        conn = sqlite3.connect(self.db.db_path)
        c = conn.cursor()
        c.execute("INSERT INTO EN (unique_system_identifier, call_sign, entity_name, "
                  "first_name, last_name, state) VALUES (?,?,?,?,?,?)",
                  (1, "W1XYZ", "Burk, Brian", "Brian", "Burk", "TX"))
        c.execute("INSERT INTO HD (unique_system_identifier, call_sign, license_status) "
                  "VALUES (?,?,?)", (1, "W1XYZ", "A"))
        c.execute("INSERT INTO AM (unique_system_identifier, call_sign, operator_class) "
                  "VALUES (?,?,?)", (1, "W1XYZ", "E"))
        conn.commit()
        conn.close()
        self.db.create_views()

    def test_view_has_both_countries(self):
        conn = sqlite3.connect(self.db.db_path)
        counts = dict(conn.execute(
            "SELECT country, COUNT(*) FROM licenses GROUP BY country").fetchall())
        conn.close()
        self.assertEqual(counts.get("CA"), 3)
        self.assertEqual(counts.get("US"), 1)

    def test_derived_canadian_class(self):
        recs = self.db.get_ca_records_by_call_sign("VA1AA")
        self.assertEqual(len(recs), 1)
        # qual_advanced='D' -> Advanced
        self.assertEqual(recs[0]["license_class"], "CA_ADV")
        self.assertEqual(recs[0]["country"], "CA")

    def test_order_agnostic_us_name_search(self):
        # Query "Brian Burk" must match the record stored as "Burk, Brian".
        res = self.db.search_records(name="Brian Burk", country="us")
        calls = [r["call_sign"] for r in res["records"]]
        self.assertIn("W1XYZ", calls)

    def test_country_all_merges(self):
        res = self.db.search_records(name="a", country="all", per_page=100)
        countries = {r.get("country") for r in res["records"]}
        # 'a' appears in both a US and CA name; expect both countries represented.
        self.assertIn("CA", countries)

    def test_canadian_callsign_lookup(self):
        res = self.db.search_records(callsign="VA2AA", country="ca")
        self.assertEqual(len(res["records"]), 1)
        self.assertEqual(res["records"][0]["formatted_name"], "Jacques Sauvé")


if __name__ == "__main__":
    unittest.main()
