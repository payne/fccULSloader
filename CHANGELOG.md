# Changelog

All notable changes to the Offline Callsign Lookup project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.1.0] - 2026-07-24

### Added
- **Optional Canadian (ISED) amateur data support.** Offline Callsign Lookup can now mirror the
  Canadian "Amateur Call Sign List" from Innovation, Science and Economic
  Development Canada (ISED) into the **same** SQLite database as the FCC data,
  for unified US + Canada lookups.
  - New `--country {us,ca,all}` option (CLI) and Country selector (web). Default
    is `us`, so existing behavior is unchanged unless you opt in.
  - `python callsign_lookup.py --update --country all` downloads and loads both sources;
    `--country ca` loads only Canada.
  - Canadian records carry callsign, name, address, province, and qualification
    level (Basic / Basic with Honours / Advanced). ISED publishes only assigned
    callsigns, so all Canadian records are treated as active.
  - New `CA_AM` table plus a unified `licenses` view (in `schemas.py`) that both
    the FCC (`EN`/`HD`/`AM`) and ISED data map into; queries read the view.
  - New `modules/ised_loader.py` handles the ISED file (semicolon-delimited,
    UTF-8, header row) independently of the FCC `.dat` loader.
  - Web UI: Country selector, a Country column in results, Canadian province
    filtering (State/Province dropdown), Basic/Advanced class labels, and
    Canadian callsign profile pages.
- **Order-agnostic name search.** A multi-word name query now matches regardless
  of stored order or `Last, First` formatting — searching `"Brian Burk"` returns
  a record stored as `"Burk, Brian"`. Applies to both US and Canadian data, in
  the CLI and the web UI.

### Changed
- Downloads are now crash-safe: files are streamed to a temporary `.part` file,
  validated (size vs. `Content-Length` and zip integrity), and only then
  atomically moved into place. Download metadata is written **only after** a
  successful load, so an interrupted or failed run no longer records false
  "up to date" state and cleanly re-downloads on the next run.
- All HTTP requests (downloads and update checks) now use explicit connection/read
  timeouts (`Config.HTTP_TIMEOUT`) so a hung server can't block indefinitely.
- `--optimize` now retains the `AM` and `CA_AM` tables and recreates the
  `licenses` view (previously it dropped tables the queries/view depend on).

### Fixed
- `search_records()` referenced an undefined logger/exception on the error path;
  it now logs via the standard logger and returns an empty result set.

## [1.8.0] - 2026-07-24

### Added
- Web interface now accepts `--port` and `--host` command-line options (with `PORT`/`HOST` environment variable fallbacks) instead of hardcoding port 5000
  - Lets the server run on an alternate port when 5000 is unavailable — common on macOS, where the AirPlay Receiver binds port 5000 by default
  - Example: `python src/callsign_lookup_web.py --port 8000` or `PORT=8000 python src/callsign_lookup_web.py`

## [1.7.0] - 2025-03-08

### Added
- New `--active-only` command-line option to filter out inactive license records
  - When used with `--update`, only active records are loaded into the database
  - When used alone, it removes inactive records from an existing database
  - Shows a sample of call signs to be deleted and requires confirmation
  - Displays detailed feedback about the deletion process
- Safety features for the `--active-only` option:
  - Confirmation prompts before deleting records
  - Display of the number of inactive records that will be deleted
  - Sample of call signs that will be removed
- Special handling when `--active-only` is used with `--force-download`:
  - Database is completely rebuilt with only active records
  - Skips the check for inactive records in the existing database
- Enhanced `--verbose` option to display related records from all available tables

### Changed
- Improved error handling and user feedback during database operations
- Enhanced documentation with detailed examples for the new features
- Cleaned up console output during index creation and removal for a more professional appearance
- Moved requirements.txt to the src folder for better project organization
- Improved display of coded fields to show full text descriptions (e.g., "operator_class: Amateur Extra (E)" instead of just "operator_class: E")
- Completely redesigned verbose output format:
  - Organized fields into logical groups (license, operator, personal, contact, etc.)
  - Combined related fields on the same line (name components, address details)
  - Used shorthand labels for better space efficiency (UID, ULS#, etc.)
  - Eliminated duplication in related records
  - Used table names as section headers with descriptive titles (e.g., "Entity/Licensee (EN) RECORDS")
  - Displayed multiple related records in a compact tabular format
  - Improved field ordering for better readability (e.g., Attention field above address)
  - Omitted redundant call sign information from related records
  - Grouped related records by their primary HD record for better organization
- Simplified application header to a single line with underline for a cleaner look

### Fixed
- Various minor bug fixes and performance improvements
- Fixed argument processing issue when using `--active-only` with `--force-download`
- Fixed issue where using `--force-download` without `--update` didn't trigger any action
- Fixed Linux executable naming to follow the format "callsign-lookup-linux-[version]"

## [1.6.0] - 2025-02-15

### Added
- Initial public release of Offline Callsign Lookup
- Comprehensive database management features
- Query capabilities for amateur radio call signs
- Search functionality by name and state
- Detailed documentation and examples 