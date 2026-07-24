"""
FCC Filesystem Tools Module - File System Operations for FCC Database Tools
=========================================================================

Author: Tiran Dagan (Backstop Radio)
Contact: tiran@tirandagan.com
License: MIT License

Description:
-----------
This module provides utility functions for file system operations used by the FCC database tools.
It handles directory creation, path management, file deletion, and other file system related tasks.

Functions:
---------
Directory Management:
- ensure_directory_exists(directory_path): Ensure a directory exists, create if not
- ensure_directory(directory_type, path=None): Ensure a specific type of directory exists

File Operations:
- file_exists(file_path): Check if a file exists
- delete_file(file_path): Delete a file with error handling
- delete_directory(directory_path): Delete a directory with error handling
- cleanup_temp_files(): Delete temporary files and directories

Usage:
-----
Import the functions and use them to manage directories and files:

    from modules.filesystemtools import ensure_directory, file_exists
    
    # Ensure data directory exists before performing operations
    ensure_directory('data')
    
    # Ensure a custom directory exists
    ensure_directory('custom', '/path/to/custom/directory')
    
    # Check if a file exists
    if file_exists('/path/to/file.txt'):
        print('File exists')

Dependencies:
------------
- os: For file system operations
- shutil: For directory operations
- logging: For logging
- modules.config: For configuration settings
"""

import os
import shutil
import logging
from modules import config

def ensure_directory_exists(directory_path):
    """
    Ensure that a directory exists, create it if it doesn't.
    
    Args:
        directory_path (str): Path to the directory to ensure exists
        
    Returns:
        bool: True if the directory exists or was created successfully, False otherwise
    """
    try:
        if not os.path.exists(directory_path):
            os.makedirs(directory_path, exist_ok=True)
            logging.info(f"Created directory: {directory_path}")
        return True
    except OSError as e:
        logging.error(f"Error creating directory {directory_path}: {e}")
        print(f"Error: Could not create directory {directory_path}: {e}")
        return False

def ensure_directory(directory_type, path=None):
    """
    Ensure that a specific type of directory exists.
    
    Args:
        directory_type (str): Type of directory ('data', 'logs', 'extraction', 'db', 'custom')
        path (str, optional): Path to use for 'db' or 'custom' directory types
        
    Returns:
        bool: True if the directory exists or was created successfully, False otherwise
        
    Raises:
        ValueError: If an invalid directory type is provided
    """
    if directory_type == 'data':
        return ensure_directory_exists(config.Config.DATA_PATH)
    elif directory_type == 'logs':
        return ensure_directory_exists("./logs")
    elif directory_type == 'extraction':
        return ensure_directory_exists(config.Config.EXTRACT_PATH)
    elif directory_type == 'db':
        if path is None:
            raise ValueError("Path must be provided for 'db' directory type")
        return ensure_directory_exists(os.path.dirname(path))
    elif directory_type == 'custom':
        if path is None:
            raise ValueError("Path must be provided for 'custom' directory type")
        return ensure_directory_exists(path)
    else:
        raise ValueError(f"Invalid directory type: {directory_type}")

def file_exists(file_path):
    """
    Check if a file exists.
    
    Args:
        file_path (str): Path to the file to check
        
    Returns:
        bool: True if the file exists, False otherwise
    """
    return os.path.exists(file_path) and os.path.isfile(file_path)

def delete_file(file_path):
    """
    Delete a file with error handling.
    
    Args:
        file_path (str): Path to the file to delete
        
    Returns:
        bool: True if the file was deleted successfully, False otherwise
    """
    if not file_exists(file_path):
        logging.info(f"File does not exist, nothing to delete: {file_path}")
        return True
        
    try:
        os.remove(file_path)
        logging.info(f"Deleted file: {file_path}")
        return True
    except OSError as e:
        logging.error(f"Error deleting file {file_path}: {e}")
        print(f"Warning: Could not delete file {file_path}: {e}")
        return False

def delete_directory(directory_path):
    """
    Delete a directory with error handling.
    
    Args:
        directory_path (str): Path to the directory to delete
        
    Returns:
        bool: True if the directory was deleted successfully, False otherwise
    """
    if not os.path.exists(directory_path):
        logging.info(f"Directory does not exist, nothing to delete: {directory_path}")
        return True
        
    try:
        shutil.rmtree(directory_path)
        logging.info(f"Deleted directory: {directory_path}")
        return True
    except OSError as e:
        logging.error(f"Error deleting directory {directory_path}: {e}")
        print(f"Warning: Could not delete directory {directory_path}: {e}")
        return False

def cleanup_temp_files(zip_path=None, extract_path=None):
    """
    Delete temporary files and directories after successful database loading.
    This includes a downloaded zip file and its extracted directory.

    Args:
        zip_path (str): Zip file to delete (defaults to the FCC zip).
        extract_path (str): Extraction directory to delete (defaults to FCC extract dir).

    Returns:
        bool: True if all files were deleted successfully, False otherwise
    """
    zip_path = zip_path or config.Config.ZIP_FILE_PATH
    extract_path = extract_path or config.Config.EXTRACT_PATH

    logging.info("Cleaning up temporary files...")

    # Delete the zip file
    zip_deleted = delete_file(zip_path)
    if zip_deleted:
        print(f"Deleted zip file: {os.path.basename(zip_path)}")

    # Delete the extracted directory
    extract_deleted = delete_directory(extract_path)
    if extract_deleted:
        print(f"Deleted extracted directory: {os.path.basename(extract_path)}")

    return zip_deleted and extract_deleted