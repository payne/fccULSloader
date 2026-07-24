""" 
FCC Updater Module - FCC Amateur Radio License Database Update Management
========================================================================

Author: Tiran Dagan (Backstop Radio)
Contact: tiran@tirandagan.com
License: MIT License

Description:
-----------
This module manages the process of updating the FCC Amateur Radio License database.
It handles checking for updates, downloading new data, extracting files, and loading
data into the SQLite database.

Functions:
---------
Metadata Management:
- save_download_metadata(last_modified_time): Save metadata about the download
- get_last_download_metadata(): Get metadata about the last download

Update Process:
- check_for_update(): Check if a new version of the data is available
- update_data(skip_download, keep_files, force_download, quiet, active_only): Update the database

Usage:
-----
1. Check if an update is available:
   update_available = updater.check_for_update()

2. Update the database:
   updater.update_data(
       skip_download=False,  # Whether to skip the download step
       keep_files=False,     # Whether to keep temporary files
       force_download=False, # Whether to force download regardless of update status
       quiet=False,          # Whether to suppress INFO log messages
       active_only=False     # Whether to only keep active license records (license_status="A")
   )

Dependencies:
------------
- requests: For HTTP requests to check and download updates
- modules.downloader: For downloading the data file
- modules.extractor: For extracting the downloaded zip file
- modules.loader: For loading data into the database
- modules.config: For configuration settings
- modules.logger: For logging
- modules.database: For database operations
- modules.filesystemtools: For file system operations
"""

import logging
import os
import requests
import json
import time
from datetime import datetime
from email.utils import parsedate_to_datetime
from modules import downloader, extractor, loader, ised_loader, config, logger
from modules.database import FCCDatabase
from modules.filesystemtools import (
    ensure_directory, ensure_directory_exists, cleanup_temp_files, file_exists
)

# Path to the FCC metadata file (kept for backward compatibility; canonical value in Config).
METADATA_FILE = config.Config.METADATA_FILE

def save_download_metadata(last_modified_time, metadata_file=None, source_url=None):
    """
    Save metadata about a download to a JSON file.

    Args:
        last_modified_time (float): Timestamp of the last modified time of the remote file
        metadata_file (str): Path to the metadata JSON file (defaults to FCC metadata)
        source_url (str): Source URL to record (defaults to FCC URL)
    """
    metadata_file = metadata_file or config.Config.METADATA_FILE
    source_url = source_url or config.Config.ZIP_FILE_URL

    metadata = {
        'last_download_timestamp': time.time(),
        'last_modified_timestamp': last_modified_time,
        'download_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'source_url': source_url
    }

    # Ensure data directory exists
    ensure_directory('data')

    try:
        with open(metadata_file, 'w') as f:
            json.dump(metadata, f, indent=4)
        logging.info(f"Saved download metadata to {metadata_file}")
    except Exception as e:
        logging.error(f"Error saving metadata: {e}")

def get_last_download_metadata(metadata_file=None):
    """
    Get metadata about the last download from the JSON file.

    Args:
        metadata_file (str): Path to the metadata JSON file (defaults to FCC metadata)

    Returns:
        dict: Metadata about the last download, or None if the file doesn't exist
    """
    metadata_file = metadata_file or config.Config.METADATA_FILE
    if not file_exists(metadata_file):
        return None

    try:
        with open(metadata_file, 'r') as f:
            return json.load(f)
    except Exception as e:
        logging.error(f"Error reading metadata file: {e}")
        return None

def _remote_last_modified(url):
    """
    Fetch the remote file's Last-Modified time as a POSIX timestamp.
    Falls back to the current time if the header is missing or the request fails.
    """
    try:
        response = requests.head(url, timeout=config.Config.HTTP_TIMEOUT, allow_redirects=True)
        response.raise_for_status()
        remote_last_modified = response.headers.get('Last-Modified')
        if remote_last_modified:
            return parsedate_to_datetime(remote_last_modified).timestamp()
    except requests.RequestException as e:
        logging.error(f"Error getting last modified time from {url}: {e}")
    return time.time()

def check_for_update(url=None, metadata_file=None):
    """
    Check if a new version of the data file is available by comparing the remote
    file's Last-Modified time with the last download time stored in the metadata.

    Args:
        url (str): The remote file URL (defaults to the FCC URL).
        metadata_file (str): Path to the metadata JSON file (defaults to FCC metadata).

    Returns:
        bool: True if an update is available (or cannot be ruled out), False otherwise.
    """
    url = url or config.Config.ZIP_FILE_URL
    metadata_file = metadata_file or config.Config.METADATA_FILE

    logging.info(f"Checking for updates: {url}")
    try:
        # Get the last modified time of the remote file
        response = requests.head(url, timeout=config.Config.HTTP_TIMEOUT, allow_redirects=True)
        response.raise_for_status()
        remote_last_modified = response.headers.get('Last-Modified')

        if not remote_last_modified:
            logging.warning("Could not determine the last modified date of the remote file.")
            return True

        remote_last_modified_time = parsedate_to_datetime(remote_last_modified).timestamp()

        # Get the last download metadata
        metadata = get_last_download_metadata(metadata_file)

        if metadata is None:
            logging.info("No previous download metadata found. Downloading new file.")
            return True

        last_modified_timestamp = metadata.get('last_modified_timestamp')

        if last_modified_timestamp is None:
            logging.info("No last modified timestamp in metadata. Downloading new file.")
            return True

        # Compare the timestamps
        if remote_last_modified_time > last_modified_timestamp:
            logging.info("A new version of the data file is available.")
            return True
        else:
            logging.info("The data file is up to date.")
            return False

    except requests.RequestException as e:
        logging.error(f"Error checking for updates: {e}")
        return False

def _extract_dir_ready(extract_path):
    """Return True if the extraction directory exists and is non-empty."""
    if not os.path.exists(extract_path):
        logging.error("Extraction directory does not exist. Cannot proceed with loading data.")
        print("Error: Extraction directory does not exist. Cannot proceed with loading data.")
        print("Try running without --skip-download (optionally with --force-download) for a fresh download.")
        return False
    if not os.listdir(extract_path):
        logging.error("Extraction directory is empty. Cannot proceed with loading data.")
        print("Error: Extraction directory is empty. Cannot proceed with loading data.")
        print("Try running without --skip-download (optionally with --force-download) for a fresh download.")
        return False
    return True

def update_data(skip_download=False, keep_files=False, force_download=False, quiet=False, active_only=False):
    """
    Update the FCC data by downloading, extracting, and loading it into the database.

    Args:
        skip_download (bool): Whether to skip the download step
        keep_files (bool): Whether to keep the downloaded and extracted files after loading
        force_download (bool): Whether to force download even if no update is available
        quiet (bool): Whether to suppress INFO log messages (only show WARNING and above)
        active_only (bool): Whether to only keep active license records (license_status="A").
                           Command-line parameter is --active-only

    Returns:
        bool: True on success, False on failure (download failed, no data, etc.).
    """
    # Set up logging with appropriate level
    logger.setup_logging(verbose=False)

    # If quiet mode is enabled, set log level to WARNING
    if quiet:
        logger.set_log_level(logging.WARNING)

    logging.info("Starting the FCC ULS data downloader and loader.")
    db = FCCDatabase(config.Config.DB_PATH)

    # Metadata is written only AFTER a successful load, so an interrupted or
    # failed run never records false "up to date" state.
    remote_last_modified_time = None
    downloaded = False

    if not skip_download:
        # When force_download is True, we download regardless of update status
        if force_download or check_for_update(config.Config.ZIP_FILE_URL, config.Config.METADATA_FILE):
            if force_download:
                logging.info("Forcing download regardless of update status.")
            else:
                logging.info("Downloading the latest data file.")

            # Get the remote Last-Modified time before downloading (recorded after load)
            remote_last_modified_time = _remote_last_modified(config.Config.ZIP_FILE_URL)

            # Ensure data directory exists
            ensure_directory('data')

            # Download the file; abort cleanly (no metadata written) on failure.
            if not downloader.download_file(
                url=config.Config.ZIP_FILE_URL,
                dest_path=config.Config.ZIP_FILE_PATH,
                desc="Downloading FCC data"
            ):
                logging.error("FCC download failed; aborting update without recording metadata.")
                print("Error: FCC data download failed. No changes were made; please try again.")
                return False
            downloaded = True

            # Create extraction directory before extracting
            ensure_directory('extraction')

            logging.info("Extracting data file.")
            extractor.extract_data(config.Config.ZIP_FILE_PATH, config.Config.EXTRACT_PATH)
        else:
            logging.info("Skipping download as no new update is available.")
    else:
        logging.info("Skipping download step as requested.")

    if not _extract_dir_ready(config.Config.EXTRACT_PATH):
        return False

    tables_to_process = config.Config.TABLES_TO_PROCESS

    logging.info("Creating database tables.")
    db.create_tables(tables_to_process)
    db.disable_indexes(tables_to_process)

    logging.info(f"Loading data into the database for tables: {tables_to_process}.")
    loader.load_all_data(db, config.Config.EXTRACT_PATH, config.Config.USE_MULTITHREADING, tables_to_process, active_only)

    logging.info("Applying indexes.")
    db.enable_indexes(tables_to_process)

    # Refresh the unified US+CA read model.
    db.create_views()

    # Record success metadata only now that the load completed.
    if downloaded and remote_last_modified_time is not None:
        save_download_metadata(remote_last_modified_time,
                               config.Config.METADATA_FILE,
                               config.Config.ZIP_FILE_URL)

    # Clean up temporary files after successful database loading if keep_files is False
    if not keep_files:
        cleanup_temp_files(config.Config.ZIP_FILE_PATH, config.Config.EXTRACT_PATH)
        logging.info("Temporary files cleaned up.")
    else:
        logging.info("Keeping temporary files as requested.")

    logging.info("FCC process completed successfully.")
    print("FCC data loading completed successfully.")
    return True

def update_ised_data(skip_download=False, keep_files=False, force_download=False, quiet=False):
    """
    Update the Canadian (ISED) amateur data by downloading, extracting, and
    loading it into the CA_AM table of the shared database.

    Mirrors update_data() but for the ISED "Amateur Call Sign List". ISED
    publishes only assigned callsigns (all effectively active), so there is no
    active_only concept.

    Returns:
        bool: True on success, False on failure.
    """
    logger.setup_logging(verbose=False)
    if quiet:
        logger.set_log_level(logging.WARNING)

    logging.info("Starting the ISED (Canada) amateur data downloader and loader.")
    db = FCCDatabase(config.Config.DB_PATH)

    remote_last_modified_time = None
    downloaded = False

    if not skip_download:
        if force_download or check_for_update(config.Config.ISED_ZIP_FILE_URL,
                                              config.Config.ISED_METADATA_FILE):
            if force_download:
                logging.info("Forcing ISED download regardless of update status.")
            else:
                logging.info("Downloading the latest ISED data file.")

            remote_last_modified_time = _remote_last_modified(config.Config.ISED_ZIP_FILE_URL)
            ensure_directory('data')

            if not downloader.download_file(
                url=config.Config.ISED_ZIP_FILE_URL,
                dest_path=config.Config.ISED_ZIP_FILE_PATH,
                desc="Downloading ISED (Canada) data"
            ):
                logging.error("ISED download failed; aborting update without recording metadata.")
                print("Error: ISED (Canada) data download failed. No changes were made; please try again.")
                return False
            downloaded = True

            ensure_directory_exists(config.Config.ISED_EXTRACT_PATH)
            logging.info("Extracting ISED data file.")
            extractor.extract_data(config.Config.ISED_ZIP_FILE_PATH, config.Config.ISED_EXTRACT_PATH)
        else:
            logging.info("Skipping ISED download as no new update is available.")
    else:
        logging.info("Skipping ISED download step as requested.")

    if not _extract_dir_ready(config.Config.ISED_EXTRACT_PATH):
        return False

    logging.info("Loading ISED data into table CA_AM.")
    db.create_tables(["CA_AM"])
    ised_loader.load_ised_data(db, config.Config.ISED_EXTRACT_PATH)

    # Refresh the unified US+CA read model.
    db.create_views()

    if downloaded and remote_last_modified_time is not None:
        save_download_metadata(remote_last_modified_time,
                               config.Config.ISED_METADATA_FILE,
                               config.Config.ISED_ZIP_FILE_URL)

    if not keep_files:
        cleanup_temp_files(config.Config.ISED_ZIP_FILE_PATH, config.Config.ISED_EXTRACT_PATH)
        logging.info("ISED temporary files cleaned up.")
    else:
        logging.info("Keeping ISED temporary files as requested.")

    logging.info("ISED process completed successfully.")
    print("ISED (Canada) data loading completed successfully.")
    return True

def update_country(country="us", skip_download=False, keep_files=False,
                   force_download=False, quiet=False, active_only=False):
    """
    Dispatch update(s) based on the requested country scope.

    Sources load in independent steps/connections, so a failure in one leaves
    the other's tables intact. Per-source outcomes are reported and the overall
    result is False if any requested source failed.

    Args:
        country (str): 'us' (FCC only), 'ca' (ISED only), or 'all' (both).

    Returns:
        bool: True only if every requested source updated successfully.
    """
    country = (country or "us").lower()
    if country not in ("us", "ca", "all"):
        logging.error(f"Unknown country scope '{country}'. Use us | ca | all.")
        print(f"Error: unknown --country '{country}'. Use one of: us, ca, all.")
        return False

    do_us = country in ("us", "all")
    do_ca = country in ("ca", "all")
    results = {}

    if do_us:
        try:
            results['US (FCC)'] = update_data(
                skip_download=skip_download, keep_files=keep_files,
                force_download=force_download, quiet=quiet, active_only=active_only
            )
        except Exception as e:
            logging.error(f"FCC update failed: {e}")
            print(f"Error: FCC update failed: {e}")
            results['US (FCC)'] = False

    if do_ca:
        if active_only:
            logging.info("--active-only has no effect on ISED data (all published Canadian "
                         "callsigns are active); ignoring for Canada.")
        try:
            results['CA (ISED)'] = update_ised_data(
                skip_download=skip_download, keep_files=keep_files,
                force_download=force_download, quiet=quiet
            )
        except Exception as e:
            logging.error(f"ISED update failed: {e}")
            print(f"Error: ISED update failed: {e}")
            results['CA (ISED)'] = False

    # Report per-source outcomes.
    print("\nUpdate summary:")
    for source, ok in results.items():
        print(f"  {source}: {'OK' if ok else 'FAILED'}")

    return all(results.values()) if results else False