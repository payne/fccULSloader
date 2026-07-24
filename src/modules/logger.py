"""
FCC Logger Module - Logging Configuration for FCC Database Tools
===============================================================

Author: Tiran Dagan (Backstop Radio)
Contact: tiran@tirandagan.com
License: MIT License

Description:
-----------
This module provides logging configuration for the FCC database tools.
It sets up logging with appropriate handlers and log levels, and provides
functions to manage the logging behavior.

Functions:
---------
- setup_logging(verbose): Set up logging configuration with specified verbosity
- set_log_level(level): Set the log level for the root logger
- get_log_level(): Get the current log level for the root logger

Usage:
-----
1. Set up logging at the beginning of your script:
   logger.setup_logging(verbose=False)  # Use INFO level
   logger.setup_logging(verbose=True)   # Use DEBUG level

2. Change log level during execution:
   logger.set_log_level(logging.WARNING)  # Only show WARNING and above

3. Get current log level:
   current_level = logger.get_log_level()

Log Output:
----------
Logs are written to both:
- Standard output (console)
- Log file (./logs/callsign_lookup.log)

The log directory is automatically created if it doesn't exist.

Log Format:
----------
Logs use the format: '%(asctime)s - %(levelname)s - %(message)s'
Example: '2025-03-07 12:34:56 - INFO - Starting database update'
"""

import logging
import sys
import os
from modules.filesystemtools import ensure_directory

def setup_logging(verbose=False):
    """
    Set up logging configuration.
    
    :param verbose: If True, set log level to DEBUG. Otherwise, set to INFO.
    """
    log_level = logging.DEBUG if verbose else logging.INFO
    
    # Ensure logs directory exists
    ensure_directory('logs')
    
    log_file_path = os.path.join("./logs", "callsign_lookup.log")
    
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(log_file_path, mode='a')
        ]
    )

def set_log_level(level):
    """
    Set the log level for the root logger.

    :param level: Log level (e.g., logging.INFO, logging.DEBUG).
    """
    logging.getLogger().setLevel(level)

def get_log_level():
    """
    Get the current log level for the root logger.

    :return: Current log level.
    """
    return logging.getLogger().getEffectiveLevel()
