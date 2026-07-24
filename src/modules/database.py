"""
FCC Database Module - FCC Amateur Radio License Database Operations
==================================================================

Author: Tiran Dagan (Backstop Radio)
Contact: tiran@tirandagan.com
License: MIT License

Description:
-----------
This module provides a comprehensive interface for interacting with the FCC Amateur Radio
License database. It encapsulates all database operations including creation, querying,
optimization, and maintenance.

Classes:
-------
FCCDatabase: Main class that handles all database operations

    Methods:
    -------
    Database Setup and Maintenance:
    - __init__(db_path): Initialize with database path
    - ensure_db_directory(): Ensure database directory exists
    - create_connection(): Create a connection to the SQLite database
    - create_tables(tables_to_process): Create database tables
    - create_indexes(tables_to_process): Create indexes for tables
    - disable_indexes(tables_to_process): Disable indexes for tables
    - enable_indexes(tables_to_process): Enable indexes for tables
    - get_column_count(table): Get the number of columns in a table
    - database_exists(): Check if the database file exists
    
    Database Optimization:
    - compact_database(): Compact the database to reduce file size
    - optimize_database(): Remove unused tables and columns
    - rebuild_indexes(): Rebuild all indexes to improve search performance
    
    Data Queries:
    - get_record_by_call_sign(call_sign): Get record by call sign
    - search_records_by_name(name): Search records by name
    - search_records_by_state(state): Search records by state
    - search_records_by_name_and_state(name, state): Search by name and state
    
    Display Functions:
    - display_record(record): Display a record in a formatted way (static method)
    - display_verbose_record(record): Display all fields of a record

Usage:
-----
1. Create an instance of FCCDatabase with the path to the database file:
   db = FCCDatabase('/path/to/database.db')

2. Use the methods to interact with the database:
   - Query data: db.get_record_by_call_sign('W1AW')
   - Optimize: db.optimize_database()
   - Rebuild indexes: db.rebuild_indexes()

Dependencies:
------------
- sqlite3: SQLite database interface
- modules.schemas: Table schemas, index definitions, and column counts
- modules.fcc_code_defs: FCC code definitions for display
- modules.filesystemtools: File system operations
"""

import sqlite3
import re
import os
import logging
from modules.schemas import (
    table_schemas, index_schemas, column_counts, view_schemas, view_required_tables
)
from modules import fcc_code_defs
from modules.filesystemtools import ensure_directory, file_exists

class FCCDatabase:
    def __init__(self, db_path):
        self.db_path = db_path
        self.ensure_db_directory()

    @staticmethod
    def _name_match_clause(name, columns):
        """
        Build an order-agnostic, case-insensitive name-match SQL fragment.

        The query is split into whitespace/comma-separated tokens; EACH token
        must appear (as a substring) in AT LEAST ONE of the given columns, and
        tokens may match in any order. So "Brian Burk" matches a record stored
        as entity_name "Burk, Brian" as well as one split into
        first_name="Brian", last_name="Burk". A single token behaves as a plain
        wildcard search.

        Args:
            name (str): The raw user-entered name.
            columns (list[str]): Column expressions to search (e.g. EN.first_name).

        Returns:
            tuple[str, list]: (clause_sql, params) — clause is safe to drop into
            a WHERE (already parenthesized per token); params are '%token%'
            wildcards to bind positionally. Returns ("1=0", []) if no tokens.
        """
        tokens = [t for t in re.split(r'[,\s]+', name.strip()) if t]
        if not tokens:
            return "1=0", []
        clauses = []
        params = []
        for tok in tokens:
            ors = " OR ".join(f"LOWER({c}) LIKE LOWER(?)" for c in columns)
            clauses.append(f"({ors})")
            params.extend([f"%{tok}%"] * len(columns))
        return " AND ".join(clauses), params

    def create_views(self):
        """
        (Re)create the unified `licenses` view over both data sources.

        Ensures every table the view references exists first (an empty table is
        fine) so both UNION arms are always valid regardless of which country
        was loaded, then drops and recreates each view.
        """
        conn = self.create_connection()
        if not conn:
            return
        try:
            c = conn.cursor()
            for t in view_required_tables:
                c.execute(table_schemas[t])
            for view_name, view_sql in view_schemas.items():
                c.execute(f"DROP VIEW IF EXISTS {view_name}")
                c.execute(view_sql)
            conn.commit()
            logging.info(f"Created/refreshed views: {', '.join(view_schemas.keys())}")
        except sqlite3.Error as e:
            logging.error(f"Error creating views: {e}")
            print(f"Error creating views: {e}")
        finally:
            conn.close()

    def ensure_db_directory(self):
        """
        Ensure the database directory exists.
        """
        ensure_directory('db', self.db_path)

    def create_connection(self):
        try:
            conn = sqlite3.connect(self.db_path, uri=False)
            return conn
        except sqlite3.Error as e:
            print(f"Error creating connection to SQLite: {e}")
            return None

    def create_tables(self, tables_to_process):
        conn = self.create_connection()
        if conn:
            try:
                c = conn.cursor()
                for table in tables_to_process:
                    c.execute(table_schemas[table])
                conn.commit()
            except sqlite3.Error as e:
                print(f"Error creating table: {e}")
            finally:
                conn.close()

    def insert_batch_records(self, table, records):
        """
        Insert batch records into the database, handling duplicates by first deleting
        records with the same unique_system_identifier.
        
        Args:
            table (str): The table to insert records into
            records (list): A list of records to insert
        """
        if not records:
            return
        
        conn = self.create_connection()
        if conn:
            try:
                c = conn.cursor()
                
                # For tables with unique_system_identifier, handle duplicates
                if table in ["AM", "CO", "EN", "HD", "HS", "SC", "SF"]:
                    # Extract unique_system_identifiers from the records
                    # The position of unique_system_identifier is 1 in all tables
                    unique_ids = [record[1] for record in records if len(record) > 1]
                    
                    # Create chunks of 500 IDs to avoid SQLite parameter limit
                    chunk_size = 500
                    for i in range(0, len(unique_ids), chunk_size):
                        chunk = unique_ids[i:i + chunk_size]
                        placeholders = ','.join(['?'] * len(chunk))
                        if placeholders:  # Only execute if we have IDs
                            delete_sql = f"DELETE FROM {table} WHERE unique_system_identifier IN ({placeholders})"
                            c.execute(delete_sql, chunk)
                
                # Now insert the new records
                insert_sql = f"INSERT INTO {table} VALUES ({','.join(['?'] * self.get_column_count(table))})"
                c.executemany(insert_sql, records)
                conn.commit()
                
            except sqlite3.Error as e:
                print(f"Error inserting records into {table}: {e}")
            finally:
                conn.close()

    def create_indexes(self, tables_to_process):
        conn = self.create_connection()
        if conn:
            try:
                c = conn.cursor()
                for table in tables_to_process:
                    for index_sql in index_schemas[table]:
                        c.execute(index_sql)
                conn.commit()
            except sqlite3.Error as e:
                print(f"Error creating index: {e}")
            finally:
                conn.close()

    def disable_indexes(self, tables_to_process):
        """
        Disable indexes for the specified tables to improve data loading performance.
        
        Args:
            tables_to_process: List of tables to disable indexes for
        """
        conn = self.create_connection()
        if conn:
            try:
                c = conn.cursor()
                # Count total indexes to drop
                total_indexes = sum(len(index_schemas[table]) for table in tables_to_process)
                logging.info(f"Disabling {total_indexes} indexes for {len(tables_to_process)} tables to improve loading performance...")
                
                for table in tables_to_process:
                    for index_sql in index_schemas[table]:
                        match = re.search(r'CREATE INDEX IF NOT EXISTS (.*?) ON', index_sql)
                        if match:
                            index_name = match.group(1)
                            c.execute(f"DROP INDEX IF EXISTS {index_name};")
                conn.commit()
                logging.info("All indexes disabled successfully.")
            except sqlite3.Error as e:
                logging.error(f"Error disabling indexes: {e}")
            finally:
                conn.close()

    def enable_indexes(self, tables_to_process):
        """
        Enable indexes for the specified tables.
        
        Args:
            tables_to_process: List of tables to enable indexes for
        """
        conn = self.create_connection()
        if conn:
            try:
                c = conn.cursor()
                # Count total indexes to create
                total_indexes = sum(len(index_schemas[table]) for table in tables_to_process)
                logging.info(f"Creating {total_indexes} indexes for {len(tables_to_process)} tables...")
                
                for table in tables_to_process:
                    for index_sql in index_schemas[table]:
                        c.execute(index_sql)
                conn.commit()
                logging.info("All indexes created successfully.")
            except sqlite3.Error as e:
                logging.error(f"Error enabling indexes: {e}")
            finally:
                conn.close()

    def get_column_count(self, table):
        return column_counts.get(table, 0)

    def get_record_by_call_sign(self, call_sign):
        """
        Retrieves the record from the EN table using the given call sign.
        
        Args:
            call_sign (str): The call sign to look up.
        
        Returns:
            dict: The record from the EN table if found, otherwise None.
        """
        query = """
        SELECT 
            EN.*,
            HD.call_sign,
            HD.license_status,
            HD.grant_date,
            HD.expired_date,
            HD.last_action_date,
            AM.operator_class as license_class,
            CASE 
                WHEN EN.entity_name IS NOT NULL AND EN.entity_name != '' 
                THEN EN.entity_name
                ELSE TRIM(
                    COALESCE(EN.first_name, '') || ' ' || 
                    COALESCE(EN.mi, '') || ' ' || 
                    COALESCE(EN.last_name, '')
                )
            END as formatted_name
        FROM EN 
        JOIN HD ON EN.unique_system_identifier = HD.unique_system_identifier
        LEFT JOIN AM ON EN.unique_system_identifier = AM.unique_system_identifier
        WHERE HD.call_sign = ?
        """
        
        try:
            conn = self.create_connection()
            if not conn:
                return None
                
            cursor = conn.cursor()
            cursor.execute(query, (call_sign,))
            record = cursor.fetchone()
            if record:
                field_names = [description[0] for description in cursor.description]
                result_dict = dict(zip(field_names, record))
            else:
                result_dict = None
            conn.close()
            return result_dict
        except sqlite3.Error as e:
            print(f"Error retrieving record: {e}")
            return None

    def compact_database(self):
        """
        Compacts the SQLite database to reduce its file size.
        
        Returns:
            bool: True if compaction was successful, False otherwise.
        """
        try:
            conn = self.create_connection()
            if not conn:
                return False
                
            cursor = conn.cursor()
            
            # Run VACUUM command to rebuild the database file
            cursor.execute("VACUUM")
            
            conn.commit()
            conn.close()
            print(f"Database compacted successfully: {self.db_path}")
            return True
        except sqlite3.Error as e:
            print(f"Error compacting database: {e}")
            return False

    def optimize_database(self):
        """
        Optimizes the database by:
        1. Removing tables that are not used in the query operations
        2. Removing unused columns from the active tables
        
        Only keeps the essential columns in EN and HD tables which are used for call sign lookups.
        
        Returns:
            bool: True if optimization was successful, False otherwise.
        """
        try:
            conn = self.create_connection()
            if not conn:
                return False
                
            cursor = conn.cursor()
            
            # Get all tables in the database
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
            all_tables = [table[0] for table in cursor.fetchall()]

            # Tables used in our queries and the unified `licenses` view.
            # AM (operator class) and CA_AM (Canadian data) MUST be retained or
            # the view breaks; EN/HD power US lookups.
            used_tables = ['EN', 'HD', 'AM', 'CA_AM']
            
            # Tables to be removed
            tables_to_remove = [table for table in all_tables if table not in used_tables and not table.startswith('sqlite_')]
            
            # Remove unused tables
            for table in tables_to_remove:
                cursor.execute(f"DROP TABLE IF EXISTS {table}")
                print(f"Removed unused table: {table}")
            
            # Define essential columns for each table
            essential_columns = {
                'HD': ['unique_system_identifier', 'call_sign', 'license_status'],
                'EN': ['*']  # Keep all columns in EN as we're selecting all of them in the query
            }
            
            # Optimize columns in each used table
            for table in used_tables:
                if table in essential_columns:
                    # Get current table schema
                    cursor.execute(f"PRAGMA table_info({table})")
                    all_columns = [col[1] for col in cursor.fetchall()]
                    
                    # If we're keeping all columns, skip this table
                    if essential_columns[table] == ['*']:
                        print(f"Keeping all columns in table {table}")
                        continue
                    
                    # Determine which columns to keep
                    columns_to_keep = [col for col in all_columns if col in essential_columns[table]]
                    
                    if len(columns_to_keep) < len(all_columns):
                        # Create a new table with only the essential columns
                        columns_str = ', '.join(columns_to_keep)
                        cursor.execute(f"CREATE TABLE {table}_new AS SELECT {columns_str} FROM {table}")
                        
                        # Drop the old table and rename the new one
                        cursor.execute(f"DROP TABLE {table}")
                        cursor.execute(f"ALTER TABLE {table}_new RENAME TO {table}")
                        
                        removed_columns = len(all_columns) - len(columns_to_keep)
                        print(f"Optimized table {table}: removed {removed_columns} unused columns")
            
            conn.commit()

            # Compact the database after optimization
            cursor.execute("VACUUM")

            conn.close()

            # Recreate the unified view (a dropped/rebuilt table can invalidate it).
            self.create_views()
            print(f"Database optimized successfully: {self.db_path}")
            if not tables_to_remove:
                print("No unused tables found to remove.")
            else:
                print(f"Removed {len(tables_to_remove)} unused tables.")
            return True
        except sqlite3.Error as e:
            print(f"Error optimizing database: {e}")
            return False

    def search_records_by_name(self, name):
        """
        Searches for records in the EN table where the entity name contains the given name.
        Performs a case-insensitive wildcard search to match partial names in any position.
        
        Args:
            name (str): The name to search for.
        
        Returns:
            list: A list of dictionaries containing the matching records.
        """
        try:
            # Order-agnostic, multi-token name match (see _name_match_clause):
            # "Brian Burk" matches entity_name "Burk, Brian" and first/last splits.
            name_clause, name_params = self._name_match_clause(
                name, ["EN.entity_name", "EN.first_name", "EN.mi", "EN.last_name"]
            )

            # Optimize the query to use indexes more effectively
            # First, get the unique_system_identifier values that match our criteria
            query = f"""
            WITH matching_ids AS (
                SELECT DISTINCT EN.unique_system_identifier
                FROM EN
                JOIN HD ON EN.unique_system_identifier = HD.unique_system_identifier
                WHERE ({name_clause})
                AND HD.license_status = 'A'
            )
            SELECT
                EN.*,
                HD.call_sign,
                HD.license_status,
                AM.operator_class as license_class,
                CASE
                    WHEN EN.entity_name IS NOT NULL AND EN.entity_name != ''
                    THEN EN.entity_name
                    ELSE TRIM(
                        COALESCE(EN.first_name, '') || ' ' ||
                        COALESCE(EN.mi, '') || ' ' ||
                        COALESCE(EN.last_name, '')
                    )
                END as formatted_name
            FROM EN
            JOIN HD ON EN.unique_system_identifier = HD.unique_system_identifier
            LEFT JOIN AM ON EN.unique_system_identifier = AM.unique_system_identifier
            JOIN matching_ids ON EN.unique_system_identifier = matching_ids.unique_system_identifier
            ORDER BY HD.call_sign
            """

            conn = self.create_connection()
            if not conn:
                print("Error: Could not create database connection")
                return []

            # Enable query optimization
            conn.execute("PRAGMA optimize")
            cursor = conn.cursor()

            try:
                cursor.execute(query, name_params)
                records = cursor.fetchall()
            except sqlite3.Error as e:
                print(f"SQL Error in search_records_by_name: {e}")
                print(f"Query: {query}")
                print(f"Parameters: {name_params}")
                return []
            
            result_list = []
            if records:
                field_names = [description[0] for description in cursor.description]
                
                # Use a set to track unique combinations of unique_system_identifier and call_sign
                seen_records = set()
                
                for record in records:
                    result_dict = dict(zip(field_names, record))
                    
                    # Create a unique key for this record
                    unique_key = (result_dict['unique_system_identifier'], result_dict['call_sign'])
                    
                    # Only add this record if we haven't seen it before
                    if unique_key not in seen_records:
                        seen_records.add(unique_key)
                        result_list.append(result_dict)
            
            conn.close()
            return result_list
        except Exception as e:
            print(f"Unexpected error in search_records_by_name: {e}")
            import traceback
            traceback.print_exc()
            return []

    def search_records_by_state(self, state):
        """
        Searches for records in the EN table where the state matches the given state code.
        
        Args:
            state (str): The two-letter state code to search for.
        
        Returns:
            list: A list of dictionaries containing the matching records.
        """
        # Convert state to uppercase for consistency
        state = state.upper()
        
        # Optimize the query to use indexes more effectively
        query = """
        WITH matching_ids AS (
            SELECT DISTINCT EN.unique_system_identifier
            FROM EN 
            JOIN HD ON EN.unique_system_identifier = HD.unique_system_identifier
            WHERE UPPER(EN.state) = ?
            AND HD.license_status = 'A'
        )
        SELECT 
            EN.*,
            HD.call_sign,
            HD.license_status,
            AM.operator_class as license_class,
            CASE 
                WHEN EN.entity_name IS NOT NULL AND EN.entity_name != '' 
                THEN EN.entity_name
                ELSE TRIM(
                    COALESCE(EN.first_name, '') || ' ' || 
                    COALESCE(EN.mi, '') || ' ' || 
                    COALESCE(EN.last_name, '')
                )
            END as formatted_name
        FROM EN 
        JOIN HD ON EN.unique_system_identifier = HD.unique_system_identifier
        LEFT JOIN AM ON EN.unique_system_identifier = AM.unique_system_identifier
        JOIN matching_ids ON EN.unique_system_identifier = matching_ids.unique_system_identifier
        ORDER BY HD.call_sign
        """
        
        try:
            conn = self.create_connection()
            if not conn:
                return []
                
            # Enable query optimization
            conn.execute("PRAGMA optimize")
            cursor = conn.cursor()
            cursor.execute(query, (state,))
            records = cursor.fetchall()
            
            result_list = []
            if records:
                field_names = [description[0] for description in cursor.description]
                
                # Use a set to track unique combinations of unique_system_identifier and call_sign
                seen_records = set()
                
                for record in records:
                    result_dict = dict(zip(field_names, record))
                    
                    # Create a unique key for this record
                    unique_key = (result_dict['unique_system_identifier'], result_dict['call_sign'])
                    
                    # Only add this record if we haven't seen it before
                    if unique_key not in seen_records:
                        seen_records.add(unique_key)
                        result_list.append(result_dict)
            
            conn.close()
            return result_list
        except sqlite3.Error as e:
            print(f"Error searching records by state: {e}")
            return []

    def search_records_by_name_and_state(self, name, state=None):
        """
        Searches for records in the EN table where the entity name contains the given name
        and optionally filters by state.
        Performs a case-insensitive wildcard search to match partial names in any position.
        
        Args:
            name (str): The name to search for.
            state (str, optional): The two-letter state code to filter by.
        
        Returns:
            list: A list of dictionaries containing the matching records.
        """
        # Order-agnostic, multi-token name match (see _name_match_clause).
        name_clause, name_params = self._name_match_clause(
            name, ["EN.entity_name", "EN.first_name", "EN.mi", "EN.last_name"]
        )

        # Base query for name search - optimize with CTE
        query = f"""
        WITH matching_ids AS (
            SELECT DISTINCT EN.unique_system_identifier
            FROM EN
            JOIN HD ON EN.unique_system_identifier = HD.unique_system_identifier
            WHERE ({name_clause})
        """

        # Add state filter if provided
        params = list(name_params)
        if state:
            state = state.upper()
            query += "AND UPPER(EN.state) = ? "
            params.append(state)
        
        # Add license status filter and close the CTE
        query += """
            AND HD.license_status = 'A'
        )
        SELECT 
            EN.*,
            HD.call_sign,
            HD.license_status,
            AM.operator_class as license_class,
            CASE 
                WHEN EN.entity_name IS NOT NULL AND EN.entity_name != '' 
                THEN EN.entity_name
                ELSE TRIM(
                    COALESCE(EN.first_name, '') || ' ' || 
                    COALESCE(EN.mi, '') || ' ' || 
                    COALESCE(EN.last_name, '')
                )
            END as formatted_name
        FROM EN 
        JOIN HD ON EN.unique_system_identifier = HD.unique_system_identifier
        LEFT JOIN AM ON EN.unique_system_identifier = AM.unique_system_identifier
        JOIN matching_ids ON EN.unique_system_identifier = matching_ids.unique_system_identifier
        ORDER BY HD.call_sign
        """
        
        try:
            conn = self.create_connection()
            if not conn:
                return []
                
            # Enable query optimization
            conn.execute("PRAGMA optimize")
            cursor = conn.cursor()
            cursor.execute(query, params)
            records = cursor.fetchall()
            
            result_list = []
            if records:
                field_names = [description[0] for description in cursor.description]
                
                # Use a set to track unique combinations of unique_system_identifier and call_sign
                seen_records = set()
                
                for record in records:
                    result_dict = dict(zip(field_names, record))
                    
                    # Create a unique key for this record
                    unique_key = (result_dict['unique_system_identifier'], result_dict['call_sign'])
                    
                    # Only add this record if we haven't seen it before
                    if unique_key not in seen_records:
                        seen_records.add(unique_key)
                        result_list.append(result_dict)
            
            conn.close()
            return result_list
        except sqlite3.Error as e:
            print(f"Error searching records by name and state: {e}")
            return []

    # ------------------------------------------------------------------
    # Canadian (ISED) queries — read through the unified `licenses` view.
    # CA_AM is small (~92k rows) so a view scan is trivially fast; the
    # optimized indexed EN/HD/AM path stays reserved for the large US tables.
    # CA result dicts expose the same keys the US path/display code uses
    # (call_sign, formatted_name, city, state, zip_code, license_class,
    # license_status) plus a 'country' tag.
    # ------------------------------------------------------------------
    _CA_SELECT = """
        SELECT country, call_sign, formatted_name, first_name, last_name,
               street_address, city, state, postal_code AS zip_code,
               license_class, license_status
        FROM licenses
        WHERE country = 'CA'
    """

    def _run_ca_query(self, where_extra, params):
        """Execute a CA view query and return a list of result dicts."""
        query = self._CA_SELECT + where_extra
        try:
            conn = self.create_connection()
            if not conn:
                return []
            cursor = conn.cursor()
            cursor.execute(query, params)
            rows = cursor.fetchall()
            field_names = [d[0] for d in cursor.description]
            results = [dict(zip(field_names, row)) for row in rows]
            conn.close()
            return results
        except sqlite3.Error as e:
            logging.error(f"Error querying Canadian records: {e}")
            return []

    def get_ca_records_by_call_sign(self, call_sign):
        """Return Canadian records for a callsign (list; normally 0 or 1)."""
        return self._run_ca_query(" AND call_sign = ? ORDER BY call_sign", (call_sign,))

    def search_ca_records(self, name=None, province=None):
        """
        Search Canadian records by name and/or province.

        Name matching is order-agnostic across formatted_name/first_name/
        last_name (see _name_match_clause). Province reuses the 'state' column.
        """
        where = ""
        params = []
        if name:
            clause, name_params = self._name_match_clause(
                name, ["formatted_name", "first_name", "last_name"]
            )
            where += f" AND ({clause})"
            params.extend(name_params)
        if province:
            where += " AND UPPER(state) = ?"
            params.append(province.upper())
        where += " ORDER BY call_sign"
        return self._run_ca_query(where, params)

    def rebuild_indexes(self):
        """
        Rebuilds all indexes in the database to improve search performance.
        
        Returns:
            bool: True if rebuilding indexes was successful, False otherwise.
        """
        try:
            conn = self.create_connection()
            if not conn:
                return False
                
            cursor = conn.cursor()
            
            # First, analyze the database
            cursor.execute("ANALYZE")
            
            # Rebuild indexes for EN table
            print("Rebuilding indexes for EN table...")
            cursor.execute("REINDEX idx_EN_unique_sys_id")
            cursor.execute("REINDEX idx_EN_entity_name")
            cursor.execute("REINDEX idx_EN_first_name")
            cursor.execute("REINDEX idx_EN_last_name")
            cursor.execute("REINDEX idx_EN_state")
            
            # Try to create new optimized indexes if they don't exist
            try:
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_EN_state_unique_sys_id ON EN (state, unique_system_identifier)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_EN_name_search ON EN (entity_name, first_name, last_name)")
                print("Created new optimized indexes for name and state searches.")
            except sqlite3.Error as e:
                print(f"Note: Could not create new indexes: {e}")
            
            # Rebuild indexes for HD table
            print("Rebuilding indexes for HD table...")
            cursor.execute("REINDEX idx_HD_call_sign")
            cursor.execute("REINDEX idx_HD_unique_sys_id")
            
            # Try to create new optimized index if it doesn't exist
            try:
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_HD_license_status ON HD (license_status)")
                print("Created new optimized index for license status.")
            except sqlite3.Error as e:
                print(f"Note: Could not create license status index: {e}")
            
            # Optimize the database
            cursor.execute("PRAGMA optimize")
            
            conn.commit()
            conn.close()
            print(f"Indexes rebuilt successfully: {self.db_path}")
            return True
        except sqlite3.Error as e:
            print(f"Error rebuilding indexes: {e}")
            return False

    def database_exists(self):
        """
        Check if the database file exists.
        
        Returns:
            bool: True if the database file exists, False otherwise
        """
        return file_exists(self.db_path)
    
    def remove_inactive_records(self, args):
        """
        Remove all inactive license records from the database.
        
        This removes records from the HD table where license_status is not 'A',
        and also removes related records from other tables.
        
        The user is prompted to confirm before records are deleted.
        """
        conn = self.create_connection()
        if conn:
            try:
                cursor = conn.cursor()
                
                # First, identify all inactive records in the HD table
                logging.info("Identifying inactive records...")
                cursor.execute("CREATE TEMPORARY TABLE temp_inactive_records AS SELECT unique_system_identifier, call_sign FROM HD WHERE license_status != 'A'")
                
                # Get count of inactive records
                cursor.execute("SELECT COUNT(*) FROM temp_inactive_records")
                inactive_count = cursor.fetchone()[0]
                
                if inactive_count == 0:
                    logging.info("No inactive records found in the database")
                    print("No inactive records found in the database. Nothing to delete.")
                    cursor.execute("DROP TABLE temp_inactive_records")
                    return
                
                # Get a sample of call signs to show the user
                cursor.execute("SELECT call_sign FROM temp_inactive_records LIMIT 10")
                sample_calls = [row[0] for row in cursor.fetchall() if row[0]]
                sample_text = ", ".join(sample_calls) if sample_calls else "N/A"
                
                # Ask for confirmation
                print(f"\nWARNING: This will delete {inactive_count} inactive license records from the database.")
                print(f"Sample of call signs to be deleted: {sample_text}")
                print("\nThis action cannot be undone. Related records in other tables will also be deleted.")
                
                if args.non_interactive:
                    confirmation = "yes"
                else:
                    confirmation = input("\nAre you sure you want to continue? (yes/no): ").strip().lower()
                
                if confirmation != "yes":
                    print("Operation cancelled. No records were deleted.")
                    cursor.execute("DROP TABLE temp_inactive_records")
                    return
                
                # Start a transaction
                conn.execute("BEGIN TRANSACTION")
                
                # Delete related records from other tables
                for table in ["AM", "CO", "EN", "HS", "LA", "SC", "SF"]:
                    try:
                        # Check if the table exists
                        cursor.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table}'")
                        if cursor.fetchone():
                            logging.info(f"Removing inactive records from {table} table...")
                            cursor.execute(f"""
                                DELETE FROM {table} 
                                WHERE unique_system_identifier IN (
                                    SELECT unique_system_identifier FROM temp_inactive_records
                                )
                            """)
                            deleted = cursor.rowcount
                            logging.info(f"Removed {deleted} records from {table} table")
                            print(f"Removed {deleted} records from {table} table")
                    except sqlite3.Error as e:
                        logging.error(f"Error removing inactive records from {table}: {e}")
                
                # Delete inactive records from HD table
                logging.info("Removing inactive records from HD table...")
                cursor.execute("""
                    DELETE FROM HD 
                    WHERE unique_system_identifier IN (
                        SELECT unique_system_identifier FROM temp_inactive_records
                    )
                """)
                deleted = cursor.rowcount
                logging.info(f"Removed {deleted} records from HD table")
                print(f"Removed {deleted} records from HD table")
                
                # Drop the temporary table
                cursor.execute("DROP TABLE temp_inactive_records")
                
                # Commit the transaction
                conn.commit()
                
                # Vacuum the database to reclaim space
                logging.info("Vacuuming database to reclaim space...")
                print("Vacuuming database to reclaim space...")
                conn.execute("VACUUM")
                
                logging.info("Inactive records removal completed")
                print("\nInactive records have been successfully removed from the database.")
                
            except sqlite3.Error as e:
                logging.error(f"Database error during inactive records removal: {e}")
                conn.rollback()
                print(f"Error: {e}")
            finally:
                conn.close()
        else:
            logging.error("Could not connect to the database")
            print("Error: Could not connect to the database")

    @staticmethod
    def display_record(record):
        """
        Displays a record in a formatted way.
        
        Args:
            record (dict): The record to display.
        """
        # Display call sign first if available
        if 'call_sign' in record:
            print(f"Call Sign: {record['call_sign']}")
        
        # Display name information
        if record.get('entity_name'):
            print(f"Entity Name: {record['entity_name']}")
        else:
            name_parts = []
            if record.get('first_name'):
                name_parts.append(record['first_name'])
            if record.get('mi'):
                name_parts.append(record['mi'])
            if record.get('last_name'):
                name_parts.append(record['last_name'])
            if name_parts:
                print(f"Name: {' '.join(name_parts)}")
        
        # Display other important fields
        important_fields = ['unique_system_identifier', 'entity_type', 'applicant_type_code', 'city', 'state', 'zip_code']
        for field in important_fields:
            if field in record and record[field]:
                if field == 'entity_type' and record[field] in fcc_code_defs.entity_type:
                    print(f"Entity Type: {fcc_code_defs.entity_type[record[field]]} ({record[field]})")
                elif field == 'applicant_type_code' and record[field] in fcc_code_defs.applicant_type_code:
                    print(f"Applicant Type: {fcc_code_defs.applicant_type_code[record[field]]} ({record[field]})")
                else:
                    print(f"{field.replace('_', ' ').title()}: {record[field]}")
        
        print("-" * 40)  # Separator between records

    def display_verbose_record(self, record):
        """
        Displays all fields of a record.
        
        Args:
            record (dict): The record to display.
        """
        for f in record:
            if record[f]:
                if f == 'entity_type' and record[f] in fcc_code_defs.entity_type:
                    print(f"{f}: {fcc_code_defs.entity_type[record[f]]} ({record[f]})")
                elif f == 'applicant_type_code' and record[f] in fcc_code_defs.applicant_type_code:
                    print(f"{f}: {fcc_code_defs.applicant_type_code[record[f]]} ({record[f]})")
                else:
                    print(f"{f}: {record[f]}")
        print("-" * 40)  # Separator between records

    def search_records(self, callsign=None, name=None, state=None, sort=None, status=None,
                        license_class=None, country="us", page=1, per_page=20):
        """
        Search for records based on various criteria, across one or both countries.

        Args:
            callsign (str): Call sign to search for
            name (str): Name to search for
            state (str): State/province to filter by
            sort (str): Field to sort by
            status (str): License status to filter by
            license_class (str): License class to filter by
            country (str): 'us' (FCC only), 'ca' (ISED only), or 'all' (both).
                           Defaults to 'us' so existing callers are unchanged.
            page (int): Page number (1-based)
            per_page (int): Number of results per page

        Returns:
            dict: Dictionary containing records (each tagged with 'country') and total count
        """
        try:
            country = (country or "us").lower()
            want_us = country in ("us", "all")
            want_ca = country in ("ca", "all")
            results = []

            if callsign:
                if want_us:
                    rec = self.get_record_by_call_sign(callsign)
                    if rec:
                        rec['call_sign'] = callsign
                        rec['country'] = 'US'
                        results.append(rec)
                if want_ca:
                    results.extend(self.get_ca_records_by_call_sign(callsign))
            else:
                if want_us:
                    if name and state:
                        us = self.search_records_by_name_and_state(name, state)
                    elif name:
                        us = self.search_records_by_name(name)
                    elif state:
                        us = self.search_records_by_state(state)
                    else:
                        us = []
                    for r in us:
                        r['country'] = 'US'
                    results.extend(us)
                if want_ca and (name or state):
                    # For CA the 'state' filter is a province code.
                    results.extend(self.search_ca_records(name=name, province=state))

            # Filter by status if requested
            if status:
                results = [r for r in results if r.get('license_status', '').upper() == status.upper()]

            # Filter by license class if requested
            if license_class:
                results = [r for r in results if r.get('license_class', '').upper() == license_class.upper()]

            # Sort if requested
            if sort:
                results = sorted(results, key=lambda r: (r.get(sort, '') or '').upper())

            total_results = len(results)
            start = (page - 1) * per_page
            end = start + per_page

            return {
                'records': results[start:end],
                'total': total_results
            }

        except Exception as e:
            logging.error(f"Error searching records: {e}")
            return {'records': [], 'total': 0}
