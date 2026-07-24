"""
FCC ULS Downloader and Loader
Author: Tiran Dagan
Contact: tiran@tirandagan.com

Description: Unit tests for database operations.
"""

import unittest
import os
import sqlite3
from modules.database import CallsignLookupDatabase

class TestCallsignLookupDatabase(unittest.TestCase):
    def setUp(self):
        self.db_path = "test_fcc_uls.db"
        self.db = CallsignLookupDatabase(self.db_path)
        self.db.create_tables()

    def tearDown(self):
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

    def test_create_connection(self):
        conn = self.db.create_connection()
        self.assertIsNotNone(conn)
        conn.close()

    def test_create_tables(self):
        conn = self.db.create_connection()
        c = conn.cursor()
        c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='AM';")
        self.assertIsNotNone(c.fetchone())
        conn.close()

    def test_insert_record(self):
        record = [
            'AM', 215000, '', '', 'AA0A', 'E', 'A', 10, '', '', '', '', '', '', '', '', '', ''
        ]
        self.db.insert_record('AM', record)
        conn = self.db.create_connection()
        c = conn.cursor()
        c.execute("SELECT * FROM AM WHERE unique_system_identifier=215000;")
        self.assertIsNotNone(c.fetchone())
        conn.close()

if __name__ == "__main__":
    unittest.main()
