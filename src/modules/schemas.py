"""
FCC ULS Downloader and Loader
Author: Tiran Dagan
Contact: tiran@tirandagan.com

Description: Configuration for table schemas, index statements, and column counts.
"""

table_schemas = {
    "AM": """
    CREATE TABLE IF NOT EXISTS AM (
        record_type TEXT,
        unique_system_identifier INTEGER,
        uls_file_number TEXT,
        ebf_number TEXT,
        call_sign TEXT,
        operator_class TEXT,
        group_code TEXT,
        region_code INTEGER,
        trustee_call_sign TEXT,
        trustee_indicator TEXT,
        physician_certification TEXT,
        ve_signature TEXT,
        systematic_call_sign_change TEXT,
        vanity_call_sign_change TEXT,
        vanity_relationship TEXT,
        previous_call_sign TEXT,
        previous_operator_class TEXT,
        trustee_name TEXT
    );
    """,
    "CO": """
    CREATE TABLE IF NOT EXISTS CO (
        record_type TEXT,
        unique_system_identifier INTEGER,
        uls_file_number TEXT,
        call_sign TEXT,
        comment_date TEXT,
        description TEXT,
        status_code TEXT,
        status_date TEXT
    );
    """,
    "EN": """
    CREATE TABLE IF NOT EXISTS EN (
        record_type TEXT,
        unique_system_identifier INTEGER,
        uls_file_number TEXT,
        ebf_number TEXT,
        call_sign TEXT,
        entity_type TEXT,
        licensee_id TEXT,
        entity_name TEXT,
        first_name TEXT,
        mi TEXT,
        last_name TEXT,
        suffix TEXT,
        phone TEXT,
        fax TEXT,
        email TEXT,
        street_address TEXT,
        city TEXT,
        state TEXT,
        zip_code TEXT,
        po_box TEXT,
        attention_line TEXT,
        sgin TEXT,
        fcc_registration_number TEXT,
        applicant_type_code TEXT,
        applicant_type_code_other TEXT,
        status_code TEXT,
        status_date TEXT,
        _37ghz_license_type TEXT,
        linked_unique_sys_id INTEGER,
        linked_call_sign TEXT
    );
    """,
    "HD": """
    CREATE TABLE IF NOT EXISTS HD (
        record_type TEXT,
        unique_system_identifier INTEGER,
        uls_file_number TEXT,
        ebf_number TEXT,
        call_sign TEXT,
        license_status TEXT,
        radio_service_code TEXT,
        grant_date TEXT,
        expired_date TEXT,
        cancellation_date TEXT,
        eligibility_rule_num TEXT,
        applicant_type_code_reserved TEXT,
        alien TEXT,
        alien_government TEXT,
        alien_corporation TEXT,
        alien_officer TEXT,
        alien_control TEXT,
        revoked TEXT,
        convicted TEXT,
        adjudged TEXT,
        involved_reserved TEXT,
        common_carrier TEXT,
        non_common_carrier TEXT,
        private_comm TEXT,
        fixed TEXT,
        mobile TEXT,
        radiolocation TEXT,
        satellite TEXT,
        developmental_or_sta TEXT,
        interconnected_service TEXT,
        certifier_first_name TEXT,
        certifier_mi TEXT,
        certifier_last_name TEXT,
        certifier_suffix TEXT,
        certifier_title TEXT,
        gender TEXT,
        african_american TEXT,
        native_american TEXT,
        hawaiian TEXT,
        asian TEXT,
        white TEXT,
        ethnicity TEXT,
        effective_date TEXT,
        last_action_date TEXT,
        auction_id INTEGER,
        reg_stat_broad_serv TEXT,
        band_manager TEXT,
        type_serv_broad_serv TEXT,
        alien_ruling TEXT,
        licensee_name_change TEXT,
        whitespace_ind TEXT,
        additional_cert_choice TEXT,
        additional_cert_answer TEXT,
        discontinuation_ind TEXT,
        regulatory_compliance_ind TEXT,
        eligibility_cert_900 TEXT,
        transition_plan_cert_900 TEXT,
        return_spectrum_cert_900 TEXT,
        payment_cert_900 TEXT
    );
    """,
    "HS": """
    CREATE TABLE IF NOT EXISTS HS (
        record_type TEXT,
        unique_system_identifier INTEGER,
        uls_file_number TEXT,
        call_sign TEXT,
        log_date TEXT,
        code TEXT
    );
    """,
    "LA": """
    CREATE TABLE IF NOT EXISTS LA (
        record_type TEXT,
        unique_system_identifier INTEGER,
        call_sign TEXT,
        attachment_code TEXT,
        attachment_description TEXT,
        attachment_date TEXT,
        attachment_file_name TEXT,
        action_performed TEXT
    );
    """,
    "SC": """
    CREATE TABLE IF NOT EXISTS SC (
        record_type TEXT,
        unique_system_identifier INTEGER,
        uls_file_number TEXT,
        ebf_number TEXT,
        call_sign TEXT,
        special_condition_type TEXT,
        special_condition_code INTEGER,
        status_code TEXT,
        status_date TEXT
    );
    """,
    "SF": """
    CREATE TABLE IF NOT EXISTS SF (
        record_type TEXT,
        unique_system_identifier INTEGER,
        uls_file_number TEXT,
        ebf_number TEXT,
        call_sign TEXT,
        license_free_form_type TEXT,
        unique_license_free_form_identifier INTEGER,
        sequence_number INTEGER,
        license_free_form_condition TEXT,
        status_code TEXT,
        status_date TEXT
    );
    """,
    # ------------------------------------------------------------------
    # CA_AM — Canadian (ISED) amateur "Amateur Call Sign List".
    # One flat record per callsign (no relational join, no unique id, no
    # license status/dates). Source: amateur_delim.txt, ";"-delimited, 18
    # fields, in file order. Qualification columns hold the flag letter
    # (A/B/C/D/E) when held, else empty. Optional; only present when the
    # user opts in via --country ca|all.
    # ------------------------------------------------------------------
    "CA_AM": """
    CREATE TABLE IF NOT EXISTS CA_AM (
        call_sign TEXT,
        first_name TEXT,
        surname TEXT,
        street_address TEXT,
        city TEXT,
        province TEXT,
        postal_code TEXT,
        qual_basic TEXT,
        qual_5wpm TEXT,
        qual_12wpm TEXT,
        qual_advanced TEXT,
        qual_honours TEXT,
        club_name TEXT,
        club_name_2 TEXT,
        club_address TEXT,
        club_city TEXT,
        club_province TEXT,
        club_postal_code TEXT
    );
    """
}

# View schemas — created AFTER the underlying tables load (a view over a
# missing table errors at query time). `create_views()` in database.py
# ensures the referenced tables exist (empty is fine) before creating these.
view_schemas = {
    # Unified, presentation-compatible read model over both data sources.
    # Column names deliberately match the keys the CLI/web display code already
    # reads (call_sign, formatted_name, state, license_class, license_status),
    # so a Canadian province surfaces in `state` and a derived CA qualification
    # code surfaces in `license_class`. `country` is the only new field.
    "licenses": """
    CREATE VIEW IF NOT EXISTS licenses AS
        SELECT
            'US' AS country,
            HD.call_sign AS call_sign,
            CASE
                WHEN EN.entity_name IS NOT NULL AND EN.entity_name != ''
                THEN EN.entity_name
                ELSE TRIM(
                    COALESCE(EN.first_name, '') || ' ' ||
                    COALESCE(EN.mi, '') || ' ' ||
                    COALESCE(EN.last_name, '')
                )
            END AS formatted_name,
            EN.first_name AS first_name,
            EN.last_name AS last_name,
            EN.street_address AS street_address,
            EN.city AS city,
            EN.state AS state,
            EN.zip_code AS postal_code,
            AM.operator_class AS license_class,
            HD.license_status AS license_status
        FROM EN
        JOIN HD ON EN.unique_system_identifier = HD.unique_system_identifier
        LEFT JOIN AM ON EN.unique_system_identifier = AM.unique_system_identifier
        UNION ALL
        SELECT
            'CA' AS country,
            CA_AM.call_sign AS call_sign,
            TRIM(COALESCE(CA_AM.first_name, '') || ' ' || COALESCE(CA_AM.surname, '')) AS formatted_name,
            CA_AM.first_name AS first_name,
            CA_AM.surname AS last_name,
            CA_AM.street_address AS street_address,
            CA_AM.city AS city,
            CA_AM.province AS state,
            CA_AM.postal_code AS postal_code,
            CASE
                WHEN CA_AM.qual_advanced = 'D' THEN 'CA_ADV'
                WHEN CA_AM.qual_honours  = 'E' THEN 'CA_HON'
                WHEN CA_AM.qual_basic    = 'A' THEN 'CA_BAS'
                ELSE ''
            END AS license_class,
            'A' AS license_status
        FROM CA_AM;
    """
}

# Tables the `licenses` view references — must exist (empty is fine) before the
# view can be queried, regardless of which country was actually loaded.
view_required_tables = ["AM", "EN", "HD", "CA_AM"]

index_schemas = {
    "AM": ["CREATE INDEX IF NOT EXISTS idx_AM_call_sign ON AM (call_sign);",
           "CREATE INDEX IF NOT EXISTS idx_AM_unique_sys_id ON AM (unique_system_identifier);"],
    "CO": ["CREATE INDEX IF NOT EXISTS idx_CO_call_sign ON CO (call_sign);"],
    "EN": ["CREATE INDEX IF NOT EXISTS idx_EN_call_sign ON EN (call_sign);",
           "CREATE INDEX IF NOT EXISTS idx_EN_unique_sys_id ON EN (unique_system_identifier);",
           "CREATE INDEX IF NOT EXISTS idx_EN_entity_name ON EN (entity_name);",
           "CREATE INDEX IF NOT EXISTS idx_EN_first_name ON EN (first_name);",
           "CREATE INDEX IF NOT EXISTS idx_EN_last_name ON EN (last_name);",
           "CREATE INDEX IF NOT EXISTS idx_EN_state ON EN (state);",
           "CREATE INDEX IF NOT EXISTS idx_EN_state_unique_sys_id ON EN (state, unique_system_identifier);",
           "CREATE INDEX IF NOT EXISTS idx_EN_name_search ON EN (entity_name, first_name, last_name);"],
    "HD": ["CREATE INDEX IF NOT EXISTS idx_HD_call_sign ON HD (call_sign,license_status);",
           "CREATE INDEX IF NOT EXISTS idx_HD_unique_sys_id ON HD (unique_system_identifier);",
           "CREATE INDEX IF NOT EXISTS idx_HD_license_status ON HD (license_status);"],
    "HS": ["CREATE INDEX IF NOT EXISTS idx_HS_call_sign ON HS (call_sign);"],
    "LA": ["CREATE INDEX IF NOT EXISTS idx_LA_call_sign ON LA (call_sign);"],
    "SC": ["CREATE INDEX IF NOT EXISTS idx_SC_call_sign ON SC (call_sign);"],
    "SF": ["CREATE INDEX IF NOT EXISTS idx_SF_call_sign ON SF (call_sign);"],
    "CA_AM": ["CREATE INDEX IF NOT EXISTS idx_CA_AM_call_sign ON CA_AM (call_sign);",
              "CREATE INDEX IF NOT EXISTS idx_CA_AM_surname ON CA_AM (surname);",
              "CREATE INDEX IF NOT EXISTS idx_CA_AM_first_name ON CA_AM (first_name);",
              "CREATE INDEX IF NOT EXISTS idx_CA_AM_province ON CA_AM (province);"]
}

column_counts = {
    "AM": 18,
    "CO": 8,
    "EN": 30,
    "HD": 59,
    "HS": 6,
    "LA": 8,
    "SC": 9,
    "SF": 11,
    "CA_AM": 18
}

field_names = {
    "AM": [
        "record_type", "unique_system_identifier", "uls_file_number", "ebf_number", "call_sign",
        "operator_class", "group_code", "region_code", "trustee_call_sign", "trustee_indicator",
        "physician_certification", "ve_signature", "systematic_call_sign_change", "vanity_call_sign_change",
        "vanity_relationship", "previous_call_sign", "previous_operator_class", "trustee_name"
    ],
    "CO": [
        "record_type", "unique_system_identifier", "uls_file_number", "call_sign", "comment_date",
        "description", "status_code", "status_date"
    ],
    "EN": [
        "record_type", "unique_system_identifier", "uls_file_number", "ebf_number", "call_sign",
        "entity_type", "licensee_id", "entity_name", "first_name", "mi", "last_name", "suffix", "phone", "fax",
        "email", "street_address", "city", "state", "zip_code", "po_box", "attention_line", "sgin",
        "fcc_registration_number", "applicant_type_code", "applicant_type_code_other", "status_code",
        "status_date", "_37ghz_license_type", "linked_unique_sys_id", "linked_call_sign"
    ],
    "HD": [
        "record_type", "unique_system_identifier", "uls_file_number", "ebf_number", "call_sign",
        "license_status", "radio_service_code", "grant_date", "expired_date", "cancellation_date",
        "eligibility_rule_num", "applicant_type_code_reserved", "alien", "alien_government", "alien_corporation", 
        "alien_officer", "alien_control", "revoked", "convicted", "adjudged", "involved_reserved",
        "common_carrier", "non_common_carrier", "private_comm", "fixed", "mobile", "radiolocation",
        "satellite", "developmental_or_sta", "interconnected_service", "certifier_first_name", "certifier_mi",
        "certifier_last_name", "certifier_suffix", "certifier_title", "gender", "african_american",
        "native_american", "hawaiian", "asian", "white", "ethnicity", "effective_date", "last_action_date",
        "auction_id", "reg_stat_broad_serv", "band_manager", "type_serv_broad_serv", "alien_ruling",
        "licensee_name_change", "whitespace_ind", "additional_cert_choice", "additional_cert_answer",
        "discontinuation_ind", "regulatory_compliance_ind", "eligibility_cert_900", "transition_plan_cert_900",
        "return_spectrum_cert_900", "payment_cert_900"
    ],
    "HS": [
        "record_type", "unique_system_identifier", "uls_file_number", "call_sign", "log_date", "code"
    ],
    "LA": [
        "record_type", "unique_system_identifier", "call_sign", "attachment_code", "attachment_description",
        "attachment_date", "attachment_file_name", "action_performed"
    ],
    "SC": [
        "record_type", "unique_system_identifier", "uls_file_number", "ebf_number", "call_sign",
        "special_condition_type", "special_condition_code", "status_code", "status_date"
    ],
    "SF": [
        "record_type", "unique_system_identifier", "uls_file_number", "ebf_number", "call_sign",
        "license_free_form_type", "unique_license_free_form_identifier", "sequence_number",
        "license_free_form_condition", "status_code", "status_date"
    ],
    "CA_AM": [
        "call_sign", "first_name", "surname", "street_address", "city", "province", "postal_code",
        "qual_basic", "qual_5wpm", "qual_12wpm", "qual_advanced", "qual_honours",
        "club_name", "club_name_2", "club_address", "club_city", "club_province", "club_postal_code"
    ]
}
