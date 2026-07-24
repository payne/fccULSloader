"""
FCC ULS Downloader and Loader
Author: Tiran Dagan
Contact: tiran@tirandagan.com

Description: Unit tests for loader module.
"""

import unittest
import os
from modules.loader import load_data
from modules.database import CallsignLookupDatabase

class TestLoader(unittest.TestCase):
    def setUp(self):
        self.db_path = "test_fcc_uls.db"
        self.db = CallsignLookupDatabase(self.db_path)
        self.db.create_tables()
        self.am_file_path = "test_AM.dat"
        with open(self.am_file_path, 'w') as f:
            f.write("AM|215000|||AA0A|E|A|10||||||||||\n")

    def tearDown(self):
        if os.path.exists(self.db_path):
            os.remove(self.db_path)
        if os.path.exists(self.am_file_path):
            os.remove(self.am_file_path)

    def test_load_data(self):
        load_data(self.db, self.am_file_path, 'AM')
        conn = self.db.create_connection()
        c = conn.cursor()
        c.execute("SELECT * FROM AM WHERE unique_system_identifier=215000;")
        self.assertIsNotNone(c.fetchone())
        conn.close()

if __name__ == "__main__":
    unittest.main()
