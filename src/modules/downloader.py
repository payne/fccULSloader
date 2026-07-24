"""
FCC ULS Downloader and Loader
Author: Tiran Dagan
Contact: tiran@tirandagan.com

Description: Module to handle downloading the ZIP file.
"""

import requests
import logging
import time
import os
import zipfile
from modules.config import Config
from modules.progress import create_download_progress_bar

def _validate_zip(path):
    """
    Verify that a downloaded file is a complete, uncorrupted zip archive.

    Returns True if the file is a valid zip whose central directory and member
    CRCs check out, False otherwise. Guards against truncated/partial downloads
    masquerading as a complete file.
    """
    if not zipfile.is_zipfile(path):
        logging.error(f"Downloaded file is not a valid zip archive: {path}")
        return False
    try:
        with zipfile.ZipFile(path) as zf:
            bad = zf.testzip()  # returns the first bad member name, or None
            if bad is not None:
                logging.error(f"Zip archive failed CRC check on member '{bad}': {path}")
                return False
    except zipfile.BadZipFile as e:
        logging.error(f"Corrupt zip archive {path}: {e}")
        return False
    return True

def download_file(url, dest_path, retries=3, desc="Downloading data", validate_zip=True):
    """
    Download a file from the given URL to the destination path with a progress bar.

    Crash-safe: the download streams to a temporary ``<dest_path>.part`` file,
    is validated (size vs. Content-Length, and — when ``validate_zip`` — zip
    integrity), and only then atomically renamed onto ``dest_path``. A partial
    or aborted download therefore never masquerades as a complete file, so a
    subsequent run cleanly re-downloads instead of trusting garbage.

    Args:
        url (str): The URL to download from.
        dest_path (str): The path to save the file to.
        retries (int): Number of retry attempts if download fails.
        desc (str): Progress-bar label (identifies the source, e.g. FCC vs ISED).
        validate_zip (bool): Verify the downloaded file is a complete zip archive.

    Returns:
        bool: True if download was successful and validated, False otherwise.
    """
    part_path = dest_path + ".part"
    attempt = 0
    while attempt < retries:
        try:
            # Create directory if it doesn't exist
            os.makedirs(os.path.dirname(dest_path), exist_ok=True)

            # Discard any leftover partial file from a previous aborted run
            # (no HTTP Range/resume support here — always start fresh).
            if os.path.exists(part_path):
                os.remove(part_path)

            # Make a HEAD request first to get the file size
            response_head = requests.head(url, timeout=Config.HTTP_TIMEOUT, allow_redirects=True)
            total_size_in_bytes = int(response_head.headers.get('content-length', 0))

            # Stream the download with progress bar
            response = requests.get(url, stream=True, timeout=Config.HTTP_TIMEOUT)
            response.raise_for_status()

            # Initialize custom progress bar
            progress_bar = create_download_progress_bar(
                total_size=total_size_in_bytes,
                desc=desc
            )

            written = 0
            with open(part_path, 'wb') as file:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:  # filter out keep-alive new chunks
                        file.write(chunk)
                        written += len(chunk)
                        progress_bar.update(len(chunk))

            progress_bar.close()

            # Completeness check: if the server told us the size, enforce it.
            if total_size_in_bytes and written != total_size_in_bytes:
                raise IOError(
                    f"Incomplete download: got {written} bytes, expected "
                    f"{total_size_in_bytes}."
                )

            # Integrity check before trusting the file.
            if validate_zip and not _validate_zip(part_path):
                raise IOError("Downloaded archive failed validation (truncated or corrupt).")

            # Atomically move the validated file into place.
            os.replace(part_path, dest_path)
            logging.info(f"File downloaded successfully: {dest_path}")
            return True

        except (requests.RequestException, IOError, OSError) as e:
            attempt += 1
            logging.error(f"Download attempt {attempt} failed: {e}")
            print(f"Download attempt {attempt} failed: {e}")
            # Clean up the partial file so it can't be mistaken for valid data.
            try:
                if os.path.exists(part_path):
                    os.remove(part_path)
            except OSError:
                pass
            if attempt < retries:
                wait_time = 5
                print(f"Retrying in {wait_time} seconds...")
                time.sleep(wait_time)  # Wait before retrying

    logging.error(f"Failed to download file after {retries} attempts.")
    return False

def _generate_bar(self, width=10):
    """Generate a progress bar string"""
    if self.total and self.total > 0:
        percent = self.n / self.total
        filled_length = int(width * percent)
        bar = '█' * filled_length + ' ' * (width - filled_length)
        return bar
    return ' ' * width
