"""
FCC Config Module - Configuration Settings for FCC Database Tools
================================================================

Author: Tiran Dagan (Backstop Radio)
Contact: tiran@tirandagan.com
License: MIT License

Description:
-----------
This module provides configuration settings for the FCC database tools.
It defines paths, URLs, and other settings used throughout the application.

Classes:
-------
Config: Main configuration class with static attributes

    Attributes:
    ----------
    - BASE_DIR: Base directory of the application
    - DATA_PATH: Path to the data directory
    - ZIP_FILE_PATH: Path to the downloaded zip file
    - EXTRACT_PATH: Path to the directory for extracted files
    - DB_PATH: Path to the SQLite database file
    - ZIP_FILE_URL: URL for downloading the FCC database file
    - USE_MULTITHREADING: Whether to use multithreading for data loading
    - TABLES_TO_PROCESS: List of tables to process during data loading

Usage:
-----
Import the Config class and access its attributes:

    from modules.config import Config
    
    # Access database path
    db_path = Config.DB_PATH
    
    # Access download URL
    url = Config.ZIP_FILE_URL
    
    # Access data directory
    data_dir = Config.DATA_PATH

Customization:
------------
To customize the configuration, modify the attributes in this file.
For example, to change the database path or the tables to process.
"""

import os

class Config:
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    DATA_PATH = os.path.join(BASE_DIR, "data")
    ZIP_FILE_PATH = os.path.join(DATA_PATH, "l_amat.zip")
    EXTRACT_PATH = os.path.join(DATA_PATH, "extracted")
    DB_PATH = os.path.join(DATA_PATH, "callsign_data.db")
    ZIP_FILE_URL = 'https://data.fcc.gov/download/pub/uls/complete/l_amat.zip'  # URL for the file
    METADATA_FILE = os.path.join(DATA_PATH, "fcc_metadata.json")
    USE_MULTITHREADING = False

    # Network timeouts for all HTTP requests: (connect_timeout, read_timeout) in seconds.
    # Prevents a hung/slow server (e.g. a foreign download host) from blocking the process forever.
    HTTP_TIMEOUT = (10, 60)

    # For just the tables needed for the Offline Callsign Lookup, uncomment the following line and comment the one above it
    TABLES_TO_PROCESS = ["AM","EN","HD"]
    # For a full download into the database of all FCC files, uncomment the following line and comment the one above it
    # TABLES_TO_PROCESS = ["AM", "CO", "EN", "HD", "HS", "LA", "SC", "SF"]

    # ------------------------------------------------------------------
    # ISED (Innovation, Science and Economic Development Canada) — OPTIONAL
    # Canadian amateur "Amateur Call Sign List". Loaded into the SAME DB_PATH
    # alongside the FCC data and exposed through the unified `licenses` view.
    # Enabled only via the --country ca|all CLI flag (default: us => FCC only).
    # ------------------------------------------------------------------
    ISED_ZIP_FILE_URL = 'https://apc-cap.ic.gc.ca/datafiles/amateur_delim.zip'
    ISED_ZIP_FILE_PATH = os.path.join(DATA_PATH, "amateur_delim.zip")
    ISED_EXTRACT_PATH = os.path.join(DATA_PATH, "extracted_ca")  # kept separate from FCC EXTRACT_PATH
    ISED_DATA_FILE = "amateur_delim.txt"                          # the delimited file inside the zip
    ISED_METADATA_FILE = os.path.join(DATA_PATH, "ised_metadata.json")
    ISED_TABLES_TO_PROCESS = ["CA_AM"]

    # Default country scope when --country is not supplied. Keeps historical (US-only) behavior.
    DEFAULT_COUNTRY = "us"  # one of: us | ca | all