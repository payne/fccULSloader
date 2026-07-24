"""
FCC Tool - FCC Amateur Radio License Database Management Tool
============================================================

Author: Tiran Dagan (Backstop Radio)
Contact: tiran@tirandagan.com
License: MIT License

Copyright (c) 2025 Tiran Dagan

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.

Description:
-----------
This script provides a unified command-line interface for managing and querying the FCC Amateur Radio
License database. It combines database management and query functionality in a single tool.

Features:
--------
1. Database Management:
   - Download and update the FCC database from the official source
   - Compact the database to reduce file size
   - Optimize the database by removing unused tables and columns
   - Rebuild indexes to improve search performance

2. Database Queries:
   - Look up amateur radio call signs
   - Search for records by name (case-insensitive wildcard search)
   - Search for records by state
   - Combine name and state filters for more specific searches
   - Display detailed or summarized information

Functions:
---------
- signal_handler(sig, frame): Handles interrupt signals during long-running operations
- main(): Main function that parses command-line arguments and executes the appropriate action

Usage:
-----
The tool uses modules from the 'modules' directory:
- config: Configuration settings
- database: Database operations (FCCDatabase class)
- updater: Database update functionality
- logger: Logging configuration
- filesystemtools: File system operations

Command Line Options:
-------------------
Database Management:
  --update                : Check for and download updates to the FCC database
  --force-download        : Force download even if data is up to date
  --skip-download         : Skip download and use existing data files
  --check-update          : Check if an update is available without downloading
  --keep-files            : Keep downloaded and extracted files after processing
  --quiet                 : Suppress INFO log messages (only show WARNING and above)
  --compact               : Compact the database to reduce file size
  --optimize              : Remove unused tables and compact the database
  --rebuild-indexes       : Rebuild database indexes to improve search performance
  --active-only           : Only keep active license records (license_status="A") in the database

  --country {us,ca,all}   : Which country's data to download/load/query — us (FCC,
                            default), ca (Canada/ISED), or all (both). Canadian data
                            loads into the SAME database alongside the FCC data.

Queries:
  --callsign CALLSIGN     : Look up a specific amateur radio call sign
  --name NAME             : Search for records by name (case-insensitive, order-agnostic:
                            "Brian Burk" matches a record stored as "Burk, Brian")
  --state STATE           : Filter by two-letter state (US) or province (CA) code
  --verbose               : Display all fields for each record

Examples:
--------
python fcc_tool.py --update
python fcc_tool.py --update --country all        # download + load both US and Canada
python fcc_tool.py --update --country ca         # Canada (ISED) only
python fcc_tool.py --callsign W1AW
python fcc_tool.py --callsign VE3XYZ --country ca
python fcc_tool.py --name "Smith"
python fcc_tool.py --name "Brian Burk"           # matches "Burk, Brian" too
python fcc_tool.py --state CA
python fcc_tool.py --name "Tremblay" --state QC --country ca
python fcc_tool.py --compact
python fcc_tool.py --optimize
"""

import argparse
import signal
import logging
import sys
import os
from modules import config, fcc_code_defs
from modules import updater, logger
from modules.database import FCCDatabase
from modules.filesystemtools import ensure_directory

# Version information
__version__ = "2.1.0"
APP_NAME = "FCC Tool"

# Utility functions

def display_header():
    """
    Display a nice framed header with program name, copyright, and version information.
    """
    terminal_width = 80
    try:
        # Try to get the terminal width on supported platforms
        if sys.platform != "win32":
            import shutil
            terminal_width = shutil.get_terminal_size().columns
        else:
            # On Windows, try to use os.get_terminal_size
            terminal_width = os.get_terminal_size().columns
    except (ImportError, AttributeError, OSError):
        # Fall back to default width if we can't get the terminal width
        pass
    
    # Ensure minimum width
    terminal_width = max(terminal_width, 60)
    
    # Create the header content
    header_lines = [
        f"{APP_NAME} v{__version__}",
        f"Copyright © 2025 Tiran Dagan (Backstop Radio)",
        "All rights reserved."
    ]
    
    # Calculate the box width (content + padding)
    content_width = max(len(line) for line in header_lines)
    box_width = min(content_width + 4, terminal_width)
    
    # Create the box
    horizontal_line = "+" + "-" * (box_width - 2) + "+"
    empty_line = "|" + " " * (box_width - 2) + "|"
    
    # Print the header
    print(horizontal_line)
    print(empty_line)
    for line in header_lines:
        padding = (box_width - 2 - len(line)) // 2
        print("|" + " " * padding + line + " " * (box_width - 2 - padding - len(line)) + "|")
    print(empty_line)
    print(horizontal_line)
    print()

def signal_handler(sig, frame):
    """
    Handle interrupt signals (Ctrl+C) during long-running operations.
    
    Args:
        sig: Signal number
        frame: Current stack frame
    """
    print("\nProcess interrupted. Press ESC again to exit or any other key to continue.")
    key = input()
    if key.lower() == 'esc':
        print("Exiting. The data might be corrupt.")
        logging.warning("Process interrupted by user. Exiting. The data might be corrupt.")
        sys.exit(0)
    else:
        print("Resuming process.")

def gather_query_records(db, args, country):
    """
    Collect query results across the requested country scope.

    Runs the US (FCC) and/or CA (ISED) queries as dictated by `country`
    (us | ca | all), tags each record with its country, and returns the
    combined list. For Canadian queries the `--state` value is treated as a
    province code.

    Args:
        db (FCCDatabase): The database instance.
        args: Parsed argparse namespace (uses callsign/name/state).
        country (str): 'us', 'ca', or 'all'.

    Returns:
        list[dict]: Combined, country-tagged result records.
    """
    want_us = country in ('us', 'all')
    want_ca = country in ('ca', 'all')
    records = []

    if args.callsign:
        call_sign = args.callsign.upper()
        if want_us:
            rec = db.get_record_by_call_sign(call_sign)
            if rec:
                rec['call_sign'] = call_sign
                rec['country'] = 'US'
                records.append(rec)
        if want_ca:
            records.extend(db.get_ca_records_by_call_sign(call_sign))
    else:
        if want_us:
            if args.name and args.state:
                us = db.search_records_by_name_and_state(args.name, args.state)
            elif args.name:
                us = db.search_records_by_name(args.name)
            elif args.state:
                us = db.search_records_by_state(args.state)
            else:
                us = []
            for r in us:
                r['country'] = 'US'
            records.extend(us)
        if want_ca and (args.name or args.state):
            records.extend(db.search_ca_records(name=args.name, province=args.state))

    return records

def main():
    """
    Main function that parses command-line arguments and executes the appropriate action.
    """
    # Display the header
    display_header()
    
    # Set up signal handler for Ctrl+C
    signal.signal(signal.SIGINT, signal_handler)
    
    # Set up logging
    logger.setup_logging(verbose=False)
    
    # Create argument parser
    parser = argparse.ArgumentParser(
        description="FCC Tool - FCC Amateur Radio License Database Management Tool",
        epilog="For more information, see the README.md file."
    )
    
    # Create argument groups for better organization
    db_group = parser.add_argument_group('Database Management')
    query_group = parser.add_argument_group('Queries')
    
    # Database Management options
    db_group.add_argument('--update', action='store_true', 
                         help='Check for and download updates to the FCC database')
    db_group.add_argument('--force-download', action='store_true', 
                         help='Force download even if data is up to date')
    db_group.add_argument('--skip-download', action='store_true', 
                         help='Skip download and use existing data files')
    db_group.add_argument('--check-update', action='store_true', 
                         help='Check if an update is available without downloading')
    db_group.add_argument('--keep-files', action='store_true', 
                         help='Keep downloaded and extracted files after processing')
    db_group.add_argument('--quiet', action='store_true', 
                         help='Suppress INFO log messages (only show WARNING and above)')
    db_group.add_argument('--compact', action='store_true', 
                         help='Compact the database to reduce file size')
    db_group.add_argument('--optimize', action='store_true', 
                         help='Remove unused tables and compact the database')
    db_group.add_argument('--rebuild-indexes', action='store_true', 
                         help='Rebuild database indexes to improve search performance')
    db_group.add_argument('--active-only', action='store_true',
                         help='Only keep active license records (license_status="A") in the database')
    db_group.add_argument('--non-interactive', action='store_true',
                            help='Automatically accepts all interactive prompts.')
    db_group.add_argument('--country', choices=['us', 'ca', 'all'],
                          default=config.Config.DEFAULT_COUNTRY,
                          help="Which country's data to download/load/query: "
                               "us (FCC, default), ca (Canada/ISED), or all (both). "
                               "Canadian data loads into the same database alongside the FCC data.")

    # Query options
    query_group.add_argument('--callsign', metavar='CALLSIGN', 
                            help='Look up a specific amateur radio call sign')
    query_group.add_argument('--name', metavar='NAME', 
                            help='Search for records by name (case-insensitive wildcard search)')
    query_group.add_argument('--state', metavar='STATE', 
                            help='Filter records by two-letter state code (e.g., CA, NY, TX)')
    query_group.add_argument('--verbose', action='store_true', 
                            help='Display all fields for each record')
    
    # Parse arguments
    args = parser.parse_args()
    
    # Handle the renamed parameter (active-only instead of active_only)
    # This is needed because argparse converts - to _ in attribute names
    args.active_only = args.active_only if hasattr(args, 'active_only') else False
    
    # Get database path from config
    db_path = config.Config.DB_PATH
    
    # Create database object
    db = FCCDatabase(db_path)
    
    # Ensure data directory exists
    ensure_directory('data')
    
    # If quiet mode is enabled, set log level to WARNING
    if args.quiet:
        logger.set_log_level(logging.WARNING)
    
    # Handle database management options
    
    # Check for update
    if args.check_update:
        update_available = updater.check_for_update()
        if update_available:
            print("A new version of the FCC data is available.")
        else:
            print("The FCC data is up to date.")
        return
    
    # Update database
    if args.update:
        print("Checking for updates to the FCC database...")
        
        # Add debugging information for update issues
        metadata_file = os.path.join(config.Config.DATA_PATH, "fcc_metadata.json")
        print(f"Metadata file exists: {os.path.exists(metadata_file)}")
        print(f"Database exists: {db.database_exists()}")
        print(f"Force download: {args.force_download}")
        
        # If active-only is specified, warn the user and ask for confirmation
        # Skip confirmation when --non-interactive is specified
        if args.active_only and not args.non_interactive:
            print("\nWARNING: You have specified the --active-only flag with --update.")
            print("This will filter out all inactive license records during the update process.")
            print("Only records with license_status='A' (Active) will be included in the database.")
            
            # If force-download is also specified, mention that we'll be reloading the tables
            if args.force_download:
                print("\nSince --force-download is also specified, the database will be completely rebuilt")
                print("with only active records. No additional filtering of existing data is needed.")
            
            confirmation = input("\nAre you sure you want to continue? (yes/no): ").strip().lower()
            if confirmation != "yes":
                print("Operation cancelled.")
                return
        
        try:
            ok = updater.update_country(
                country=args.country,
                skip_download=args.skip_download,
                keep_files=args.keep_files,
                force_download=args.force_download,
                quiet=args.quiet,
                active_only=args.active_only
            )
            if not ok:
                sys.exit(1)
        except Exception as e:
            logging.error(f"Error during update process: {e}")
            print(f"Error: {e}")
            sys.exit(1)
        return

    # Handle force-download without update (treat it as an update with force-download)
    if args.force_download and not args.update:
        print("Forcing download of the latest FCC database...")
        
        # If active-only is also specified, warn the user and ask for confirmation
        # Skip confirmation when --non-interactive is specified
        if args.active_only and not args.non_interactive:
            print("\nWARNING: You have specified the --active-only flag with --force-download.")
            print("This will completely rebuild the database with only active license records.")
            print("Only records with license_status='A' (Active) will be included in the database.")
            
            confirmation = input("\nAre you sure you want to continue? (yes/no): ").strip().lower()
            if confirmation != "yes":
                print("Operation cancelled.")
                return
        
        try:
            ok = updater.update_country(
                country=args.country,
                skip_download=False,
                keep_files=args.keep_files,
                force_download=True,
                quiet=args.quiet,
                active_only=args.active_only
            )
            if not ok:
                sys.exit(1)
        except Exception as e:
            logging.error(f"Error during update process: {e}")
            print(f"Error: {e}")
            sys.exit(1)
        return
    
    # Handle active-only without update
    if args.active_only and not args.update and not args.force_download:
        print("Filtering database to keep only active license records...")
        if not db.database_exists():
            print("Error: Database does not exist. Please run with --update first.")
            return
        db.remove_inactive_records(args)
        return
    
    # Rebuild indexes
    if args.rebuild_indexes:
        print("Rebuilding database indexes...")
        if not db.database_exists():
            print("Error: Database does not exist. Please run with --update first.")
            return
        db.rebuild_indexes()
        return
    
    # Optimize database
    if args.optimize:
        print("Optimizing database...")
        if not db.database_exists():
            print("Error: Database does not exist. Please run with --update first.")
            return
        db.optimize_database()
        return
    
    # Compact database
    if args.compact:
        print("Compacting database...")
        if not db.database_exists():
            print("Error: Database does not exist. Please run with --update first.")
            return
        db.compact_database()
        return
    
    # Check if database exists before performing queries
    if not db.database_exists() and (args.callsign or args.name or args.state):
        print("Error: Database does not exist. Please run with --update first.")
        return
    
    # Handle query options (country-aware: us | ca | all)
    if args.callsign or args.name or args.state:
        records = gather_query_records(db, args, args.country)
        if records:
            scope = {'us': 'US', 'ca': 'Canada', 'all': 'US + Canada'}.get(args.country, args.country)
            print(f"Found {len(records)} record(s) [{scope}]")
            for record in records:
                if args.verbose:
                    db.display_verbose_record(record)
                else:
                    FCCDatabase.display_record(record)
        else:
            print("No records found for the given criteria.")
        return

    # If we get here, no valid options were provided
    if not any([args.callsign, args.name, args.state, args.update, args.check_update, 
                args.compact, args.optimize, args.rebuild_indexes, args.active_only,
                args.force_download, args.skip_download, args.keep_files]):
        parser.print_help()
        print("\nError: No valid options provided. Please specify at least one option.")
        return

if __name__ == "__main__":
    main()
