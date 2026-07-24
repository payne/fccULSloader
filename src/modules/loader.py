"""
FCC ULS Downloader and Loader
Author: Tiran Dagan
Contact: tiran@tirandagan.com

Description: Module to handle loading data into the database.
"""

import os
import logging
import mmap
import tempfile
import sqlite3
import time
import re
from datetime import datetime
from modules.database import CallsignLookupDatabase
from modules.schemas import field_names, table_schemas, index_schemas
from modules.progress import create_record_progress_bar
import signal
import sys
from concurrent.futures import ProcessPoolExecutor
from tqdm import tqdm

# Batch size for loading
BATCH_SIZE = 50000

# Global variables to track active connections and state
active_connections = []
is_shutting_down = False

def convert_date(date_str):
    """Convert date string from MM/DD/YYYY to YYYY-MM-DD format."""
    if not date_str or date_str.strip() == '':
        return ''
    try:
        return datetime.strptime(date_str.strip(), '%m/%d/%Y').strftime('%Y-%m-%d')
    except (ValueError, AttributeError):
        return date_str

def signal_handler(sig, frame):
    """Handle interrupt signals (Ctrl+C) gracefully."""
    global is_shutting_down
    
    if is_shutting_down:
        logging.warning("Forced exit requested. Terminating immediately.")
        sys.exit(1)
    
    logging.warning("Interrupt received. Cleaning up and exiting gracefully...")
    is_shutting_down = True
    
    # Close all active database connections
    cleanup_connections()
    
    logging.info("Cleanup complete. Exiting.")
    sys.exit(0)

def cleanup_connections():
    """Close all active database connections."""
    global active_connections
    
    for conn in active_connections:
        try:
            if conn:
                logging.debug("Closing database connection...")
                try:
                    # Try to rollback any active transaction
                    conn.rollback()
                except:
                    pass
                conn.close()
        except Exception as e:
            logging.error(f"Error closing connection: {e}")
    
    # Clear the list
    active_connections = []

def register_connection(conn):
    """Register an active connection for cleanup."""
    global active_connections
    if conn:
        active_connections.append(conn)

def unregister_connection(conn):
    """Remove a connection from the active list."""
    global active_connections
    if conn in active_connections:
        active_connections.remove(conn)

# Register signal handlers
signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

def parse_file(file_path, expected_fields, table, active_only=False, active_records=None):
    """
    Parse a data file efficiently using block reading and in-memory processing.
    
    This optimized version:
    1. Reads large blocks of data at once (10MB chunks)
    2. Processes records in memory
    3. Optionally filters records based on license status if active_only is True
    
    Args:
        file_path: Path to the data file
        expected_fields: Expected number of fields in each record
        table: Table name
        active_only: Whether to only include active license records
                    (corresponds to --active-only command-line parameter)
        active_records: Set of unique_system_identifier values for active records (used for related tables)
    
    Returns:
        Generator yielding processed records
    """
    # If we're filtering for active records in a related table, we need the set of active record IDs
    if active_only and table != "HD" and active_records is None:
        logging.warning(f"Active_only is True for table {table} but no active_records set provided")
    
    # Read the file in chunks
    with open(file_path, 'r', encoding='ISO-8859-1') as f:
        # Use memory mapping for large files
        try:
            mm = mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ)
            
            # Process the file line by line
            current_pos = 0
            while current_pos < mm.size():
                # Find the next newline
                next_newline = mm.find(b'\n', current_pos)
                if next_newline == -1:
                    # No more newlines, read to the end
                    line = mm[current_pos:].decode('ISO-8859-1')
                    current_pos = mm.size()
                else:
                    # Read up to the newline
                    line = mm[current_pos:next_newline].decode('ISO-8859-1')
                    current_pos = next_newline + 1
                
                # Skip empty lines
                if not line.strip():
                    continue
                
                # Split the line into fields
                fields = line.strip().split('|')
                
                # Skip records with wrong number of fields
                if len(fields) < 2:  # At least record_type and unique_system_identifier
                    continue
                
                # For HD table, check if we're filtering for active records
                if active_only and table == "HD":
                    # license_status is the 6th field (index 5) in HD table
                    if len(fields) > 5 and fields[5] != "A":
                        continue
                
                # For related tables, check if the record belongs to an active license
                if active_only and table != "HD" and active_records is not None:
                    # unique_system_identifier is the 2nd field (index 1)
                    if len(fields) > 1:
                        try:
                            unique_id = int(fields[1])
                            if unique_id not in active_records:
                                continue
                        except (ValueError, IndexError):
                            # If we can't parse the ID, include the record to be safe
                            pass
                
                yield fields
                
            mm.close()
        except (ValueError, OSError, MemoryError) as e:
            # Fall back to regular file reading if memory mapping fails
            logging.warning(f"Memory mapping failed for {file_path}, falling back to regular file reading: {e}")
            f.seek(0)
            
            for line in f:
                # Skip empty lines
                if not line.strip():
                    continue
                
                # Split the line into fields
                fields = line.strip().split('|')
                
                # Skip records with wrong number of fields
                if len(fields) < 2:  # At least record_type and unique_system_identifier
                    continue
                
                # For HD table, check if we're filtering for active records
                if active_only and table == "HD":
                    # license_status is the 6th field (index 5) in HD table
                    if len(fields) > 5 and fields[5] != "A":
                        continue
                
                # For related tables, check if the record belongs to an active license
                if active_only and table != "HD" and active_records is not None:
                    # unique_system_identifier is the 2nd field (index 1)
                    if len(fields) > 1:
                        try:
                            unique_id = int(fields[1])
                            if unique_id not in active_records:
                                continue
                        except (ValueError, IndexError):
                            # If we can't parse the ID, include the record to be safe
                            pass
                
                yield fields

def pad_record(record, expected_length):
    """
    Pad the record to ensure it has the expected length.
    """
    return record + [''] * (expected_length - len(record))

def create_optimized_connection(db_path):
    """
    Create an optimized SQLite connection with performance settings.
    """
    global is_shutting_down
    
    if is_shutting_down:
        raise Exception("Application is shutting down")
    
    conn = sqlite3.connect(db_path)
    
    # Register this connection for cleanup
    register_connection(conn)
    
    # Set pragmas for optimal performance
    conn.execute("PRAGMA journal_mode = MEMORY")
    conn.execute("PRAGMA synchronous = OFF")
    conn.execute("PRAGMA cache_size = 1000000")  # ~1GB cache
    conn.execute("PRAGMA temp_store = MEMORY")
    conn.execute("PRAGMA locking_mode = EXCLUSIVE")
    conn.execute("PRAGMA foreign_keys = OFF")
    
    return conn

def disable_all_indexes(conn, table):
    """
    Disable all indexes for a table to speed up loading.
    """
    logging.info(f"Disabling indexes for {table} during data load")
    for index_sql in index_schemas.get(table, []):
        match = re.search(r'CREATE INDEX IF NOT EXISTS (.*?) ON', index_sql)
        if match:
            index_name = match.group(1)
            conn.execute(f"DROP INDEX IF EXISTS {index_name}")

def rebuild_all_indexes(conn, table):
    """
    Rebuild all indexes for a table after loading.
    """
    logging.info(f"Rebuilding indexes for {table}")
    for index_sql in index_schemas.get(table, []):
        conn.execute(index_sql)

def load_data(db, file_path, table, total_records, is_new_db=False, active_only=False, active_records=None):
    """
    Load data directly into the target table with optimized batch processing.
    Drop and recreate table for updates instead of checking existing records.
    
    Args:
        db: Database object
        file_path: Path to the data file
        table: Table name
        total_records: Total number of records in the file
        is_new_db: Whether this is a new database
        active_only: Whether to only include active license records
                    (corresponds to --active-only command-line parameter)
        active_records: Set of unique_system_identifier values for active records (used for related tables)
    """
    global is_shutting_down
    
    start_time = time.time()
    records = []
    processed_records = 0
    expected_length = db.get_column_count(table)

    # Use direct connection for better performance
    conn = None
    try:
        conn = create_optimized_connection(db.db_path)
        
        # For updates, drop and recreate the table
        if not is_new_db:
            logging.info(f"Dropping and recreating table {table}")
            conn.execute(f"DROP TABLE IF EXISTS {table}")
            create_sql = table_schemas.get(table)
            if create_sql:
                conn.execute(create_sql)
            else:
                raise ValueError(f"No schema found for table {table}")
        
        conn.execute("BEGIN TRANSACTION")

        # Create custom progress bar
        pbar = create_record_progress_bar(
            total_records=total_records,
            desc=f"Loading {table} data",
            unit="records"
        )

        # Prepare the insert statement once
        placeholders = ','.join(['?'] * expected_length)
        insert_sql = f"INSERT INTO {table} VALUES ({placeholders})"
        cursor = conn.cursor()
        
        # Direct insert for all records
        for record in parse_file(file_path, expected_length, table, active_only, active_records):
            if is_shutting_down:
                break
            
            if len(record) == expected_length:
                records.append(record)
                processed_records += 1
            else:
                if len(record) < expected_length:
                    record = pad_record(record, expected_length)
                    records.append(record)
                    processed_records += 1
            
            if len(records) >= BATCH_SIZE:
                cursor.executemany(insert_sql, records)
                records = []
                pbar.update(BATCH_SIZE)

        # Insert any remaining records
        if records and not is_shutting_down:
            cursor.executemany(insert_sql, records)
            pbar.update(len(records))

        pbar.close()
        
        if is_shutting_down:
            logging.info("Rolling back transaction due to interrupt")
            conn.rollback()
        else:
            conn.execute("COMMIT")
            # Rebuild indexes after loading
            rebuild_all_indexes(conn, table)
            
            elapsed_time = time.time() - start_time
            logging.info(f"Loaded {processed_records} records into {table} in {elapsed_time:.2f} seconds ({processed_records/elapsed_time:.2f} records/sec)")
        
        return processed_records
    except sqlite3.Error as e:
        logging.error(f"SQLite error during load of {table}: {e}")
        if conn:
            try:
                conn.rollback()
            except:
                pass
        raise
    except KeyboardInterrupt:
        logging.info(f"Interrupted during {table} load. Cleaning up...")
        if conn:
            try:
                conn.rollback()
            except:
                pass
        raise
    finally:
        if conn:
            try:
                conn.close()
                unregister_connection(conn)
            except:
                pass

def parse_counts_file(counts_file_path):
    """
    Parse the counts file to get the expected number of records for each table.
    If the file doesn't exist, return an empty dictionary.
    """
    counts = {}
    try:
        with open(counts_file_path, 'r') as file:
            for line in file:
                parts = line.strip().split()
                if len(parts) == 2:
                    count, path = parts
                    table_name = os.path.basename(path).split('.')[0]
                    counts[table_name] = int(count)
        return counts
    except FileNotFoundError:
        logging.warning(f"Counts file not found at {counts_file_path}. Will proceed without record counts.")
        return counts

def load_all_data(db, extract_path, use_multithreading, tables_to_process, active_only=False):
    """
    Load all data from the extracted files into the database.
    Uses in-memory journaling to avoid disk-based journal files.
    
    Args:
        db: Database object
        extract_path: Path to the extracted files
        use_multithreading: Whether to use multithreading for data loading
        tables_to_process: List of tables to process
        active_only: Whether to only include active license records
                    (corresponds to --active-only command-line parameter)
    """
    global is_shutting_down
    
    start_time = time.time()
    counts_file_path = os.path.join(extract_path, "counts")
    counts = parse_counts_file(counts_file_path)
    
    # Check if this is a new database or an update
    is_new_db = not db.database_exists()
    
    if is_new_db:
        logging.info("Creating new database - using optimized loading strategy with indexes disabled")
        
        # For new databases, use memory journaling for better performance
        conn = None
        try:
            conn = create_optimized_connection(db.db_path)
            conn.close()
            unregister_connection(conn)
            conn = None
        except Exception as e:
            logging.error(f"Error initializing database: {e}")
            if conn:
                try:
                    conn.close()
                    unregister_connection(conn)
                except:
                    pass
    else:
        logging.info("Updating existing database with indexes disabled during load")
        
        # For updates, optimize the database connection with in-memory journaling
        conn = None
        try:
            conn = create_optimized_connection(db.db_path)
            conn.close()
            unregister_connection(conn)
            conn = None
        except Exception as e:
            logging.error(f"Error initializing database: {e}")
            if conn:
                try:
                    conn.close()
                    unregister_connection(conn)
                except:
                    pass
    
    # Pre-create all tables at once for a new database
    if is_new_db:
        db.create_tables(tables_to_process)
    
    # Process tables in order of importance
    # HD and EN tables are most important for lookups
    priority_tables = ["HD", "EN"]
    remaining_tables = [t for t in tables_to_process if t not in priority_tables]
    ordered_tables = priority_tables + remaining_tables
    
    # If active_only is True, we need to process HD table first to get the list of active records
    active_records = None
    if active_only:
        logging.info("Active-only mode: Processing HD table first to identify active records")
        
        # Process HD table first to get the list of active records
        hd_file_path = os.path.join(extract_path, "HD.dat")
        if os.path.exists(hd_file_path):
            # Create a temporary connection to collect active record IDs
            temp_conn = None
            try:
                # Create a temporary table to store active record IDs
                temp_conn = create_optimized_connection(db.db_path)
                temp_conn.execute("CREATE TEMPORARY TABLE IF NOT EXISTS temp_active_records (unique_system_identifier INTEGER PRIMARY KEY)")
                
                # Process HD file to collect active record IDs
                active_count = 0
                batch = []
                
                for record in parse_file(hd_file_path, db.get_column_count("HD"), "HD", True):
                    if len(record) > 1:  # At least record_type and unique_system_identifier
                        try:
                            unique_id = int(record[1])
                            batch.append((unique_id,))
                            active_count += 1
                            
                            if len(batch) >= 10000:
                                temp_conn.executemany("INSERT OR IGNORE INTO temp_active_records VALUES (?)", batch)
                                batch = []
                        except (ValueError, IndexError):
                            pass
                
                # Insert any remaining records
                if batch:
                    temp_conn.executemany("INSERT OR IGNORE INTO temp_active_records VALUES (?)", batch)
                
                # Get the set of active record IDs
                cursor = temp_conn.execute("SELECT unique_system_identifier FROM temp_active_records")
                active_records = set(row[0] for row in cursor.fetchall())
                
                logging.info(f"Identified {len(active_records)} active records")
                
                # Clean up
                temp_conn.execute("DROP TABLE IF EXISTS temp_active_records")
                temp_conn.close()
                unregister_connection(temp_conn)
                temp_conn = None
            except Exception as e:
                logging.error(f"Error collecting active record IDs: {e}")
                if temp_conn:
                    try:
                        temp_conn.close()
                        unregister_connection(temp_conn)
                    except:
                        pass
    
    # Process each table
    for table in ordered_tables:
        if is_shutting_down:
            logging.info("Shutdown requested. Stopping table processing.")
            break
            
        if table not in tables_to_process:
            continue
            
        file_path = os.path.join(extract_path, f"{table}.dat")
        if os.path.exists(file_path):
            # If we don't have a count, estimate it from file size
            if table not in counts or counts[table] == 0:
                file_size = os.path.getsize(file_path)
                # Rough estimate: assume average record is 100 bytes
                estimated_records = max(1, file_size // 100)
                counts[table] = estimated_records
                logging.info(f"Estimated {estimated_records} records for {table} based on file size.")
            
            total_records = counts.get(table, 0)
            
            # Add retry logic for database locks
            max_retries = 3
            retry_count = 0
            while retry_count < max_retries and not is_shutting_down:
                try:
                    load_data(db, file_path, table, total_records, is_new_db, active_only, active_records)
                    break  # Success, exit the retry loop
                except sqlite3.OperationalError as e:
                    if "database is locked" in str(e) and retry_count < max_retries - 1:
                        retry_count += 1
                        logging.warning(f"Database lock detected for {table}, retrying ({retry_count}/{max_retries})...")
                        time.sleep(5)  # Wait 5 seconds before retrying
                    else:
                        logging.error(f"Failed to load {table} after {retry_count} retries: {e}")
                        raise
                except KeyboardInterrupt:
                    logging.info("Keyboard interrupt received. Stopping processing.")
                    is_shutting_down = True
                    break
                except Exception as e:
                    logging.error(f"Error loading {table}: {e}")
                    raise
        else:
            logging.warning(f"{file_path} not found in the extracted files.")
    
    # Final optimization for new databases
    if is_new_db and not is_shutting_down:
        logging.info("Performing final database optimizations...")
        conn = None
        try:
            conn = create_optimized_connection(db.db_path)
            
            # Final optimizations
            conn.execute("PRAGMA optimize")
            conn.execute("ANALYZE")
            conn.execute("VACUUM")
            conn.close()
            unregister_connection(conn)
            conn = None
        except Exception as e:
            logging.error(f"Error during final optimizations: {e}")
            if conn:
                try:
                    conn.close()
                    unregister_connection(conn)
                except:
                    pass
    
    total_time = time.time() - start_time
    logging.info(f"Total loading time: {total_time:.2f} seconds")
