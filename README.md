# Offline Callsign Lookup

A comprehensive utility for managing and querying FCC amateur radio license database files, creating a local SQLite copy of the entire FCC ULS database for offline use. Includes both a command-line interface and a modern web interface.

## 📺 Watch: How to Use

[![Watch the Offline Callsign Lookup walkthrough](docs/how-to-use-poster.jpg)](https://github.com/tirandagan/fccULSloader/blob/main/docs/how-to-use.mp4)

▶️ **[Click the image to watch the walkthrough](https://github.com/tirandagan/fccULSloader/blob/main/docs/how-to-use.mp4)** — installing and using Offline Callsign Lookup (US + Canada lookups, CLI & web).

<!-- Note: GitHub strips <video> tags that reference raw repo files, so a clickable
     poster image is used above (it opens GitHub's built-in video player page).
     To embed a TRUE inline player instead, edit this README on GitHub (pencil icon),
     drag-and-drop docs/how-to-use.mp4 into the editor, and GitHub will insert a
     playable https://github.com/user-attachments/assets/<id> URL — paste that here. -->

## Table of Contents 📑

- [Overview](#overview)
- [Author and License](#author-and-license)
- [Features](#features)
  - [Web Interface](#web-interface)
  - [Database Management](#database-management)
  - [Query Capabilities](#query-capabilities)
- [Installation](#installation)
- [Usage](#usage)
  - [Web Interface](#using-the-web-interface)
  - [Command Line Options](#command-line-options)
  - [Examples](#examples)
- [Project Structure](#project-structure)
- [Configuration](#configuration)
- [Database Documentation](#database-documentation)
- [Troubleshooting](#troubleshooting)
- [Contributing](#contributing)
- [Changelog](#changelog)

## Overview

Offline Callsign Lookup is a command-line and web application that creates and maintains a complete local SQLite copy of the FCC Amateur Radio License database. This allows you to develop applications that can look up any callsign, entity, or license name without requiring internet connectivity. The tool provides functionality to download and update the database from the [FCC's Universal Licensing System (ULS)](https://www.fcc.gov/wireless/universal-licensing-system), look up amateur radio call signs, search for licensees by name or state, and maintain the database for optimal performance.

The offline nature of this tool makes it particularly valuable for amateur radio operators in the field, emergency communications scenarios, or any situation where internet access may be limited or unavailable.

Offline Callsign Lookup can optionally also mirror the **Canadian** amateur database from Innovation, Science and Economic Development Canada (ISED) into the same local database, giving you a unified US + Canada offline lookup. This is entirely opt-in via `--country` (see [Canadian (ISED) Data](#canadian-ised-data-)); by default the tool works with US/FCC data only, exactly as before.


[↑ Back to Table of Contents](#table-of-contents-)

## Author and License

**Author:** Tiran Dagan (Backstop Radio)  
**Contact:** tiran@tirandagan.com  
**License:** MIT License

Copyright (c) 2026 Tiran Dagan

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

[↑ Back to Table of Contents](#table-of-contents-)

## Features

### Web Interface
**[[Features](#features) > Web Interface]**

Offline Callsign Lookup includes a modern, responsive web interface (`callsign_lookup_web.py`) that provides an elegant way to search and view FCC amateur radio license data:

#### Search Interface
- **Clean, Modern Design**: A beautiful, intuitive search interface
- **Multiple Search Options**: 
  - Callsign lookup (e.g., W1AW)
  - Name search (partial or full)
  - State filtering with searchable dropdown
- **Keyboard Shortcuts**: Quick navigation using Alt + C/N/S
- **Search Tips**: Built-in help and search suggestions
- **Recent Searches**: Track and quickly access your recent searches

![Main Search Interface](docs/screenshots/main_search.jpg)
*Clean, modern search interface with keyboard shortcuts and search tips*

#### Search Results
- **Flexible Views**: 
  - Table view for compact listing
  - Card view for detailed information
- **Advanced Filtering**:
  - License status (Active/Inactive)
  - License class (Extra, General, Technician)
  - Sort by various fields
- **Pagination**: Browse through large result sets
- **Quick Actions**: Direct access to detailed profiles

![Search Results](docs/screenshots/search_results.jpg)
*Search results with advanced filtering and sorting options*

#### Profile View
- **Detailed Information**: Comprehensive license details
- **Interactive Map**: View licensee location
- **Personal Information**: Entity details and contact info
- **License Details**: Status, class, dates, and more
- **Dark Mode**: Toggle between light and dark themes
- **Responsive Design**: Works on desktop and mobile

![Profile View](docs/screenshots/profile_view.jpg)
*Detailed profile view with interactive map and comprehensive license information*

The web interface is built with:
- Flask for the backend
- Bootstrap 5 for responsive design
- Leaflet.js for interactive maps
- Modern CSS with animations and transitions
- Session management for recent searches
- Real-time search filtering

[↑ Back to Table of Contents](#table-of-contents-)

### Database Management
**[[Features](#features) > Database Management]**

Offline Callsign Lookup can automatically download and update the FCC amateur radio license database from the [FCC's ULS database downloads page](https://www.fcc.gov/uls/transactions/daily-weekly). The tool checks for updates by comparing the last modified date of the remote file with your local copy, ensuring you only download new data when it's available.

Key features:

- **Automatic update detection**: Checks if a new version is available before downloading
- **Efficient data processing**: Downloads, extracts, and loads data into an SQLite database
- **Optimized data loading**: Uses temporary tables and bulk operations for fast data loading
- **Index creation**: Automatically creates optimized indexes for fast searching
- **Cleanup**: Removes temporary files after processing to save disk space

The tool also provides several options for maintaining and optimizing the database:

- **Compaction**: Reclaims unused space in the database file
- **Optimization**: Removes unused tables and columns to reduce database size
- **Index rebuilding**: Rebuilds database indexes to improve search performance

[↑ Back to Table of Contents](#table-of-contents-)

### Query Capabilities
**[[Features](#features) > Query Capabilities]**

#### Call Sign Lookup

The primary function of Offline Callsign Lookup is to look up FCC license information by call sign. This retrieves all available information for a specific amateur radio call sign from the database.

#### Name Search

You can search for license records by name using a case-insensitive search that matches names in any position. The search is **order-agnostic**: `"Brian Burk"` matches a record stored as `"Burk, Brian"` — each word just has to appear somewhere in the name, in any order. This is useful for finding all licenses associated with a particular person or organization.

#### State / Province Filtering

The tool allows you to search for records by two-letter state code (US) or province code (Canada). This is helpful for finding all licensees in a specific geographic area.

#### Country Scope (US / Canada)

With the optional Canadian data loaded, you can scope any query to the US (FCC), Canada (ISED), or both at once via `--country` (CLI) or the Country selector (web). See [Canadian (ISED) Data](#canadian-ised-data-).

#### Combined Searches

You can combine name and state/province filters to perform more targeted searches, such as finding all licensees with a specific name in a particular state.

[↑ Back to Table of Contents](#table-of-contents-)

## Installation

Offline Callsign Lookup can be run directly from Python source or as a standalone executable. For detailed instructions on building and running the application, see the [Build Documentation](create_build/README.md).

### Quick Start

#### Running from Python Source

```bash
# Install dependencies
pip install -r requirements.txt

# Run the CLI application
python callsign_lookup.py --help

# Run the web interface
python callsign_lookup_web.py
```

The web interface requires additional Python packages:
- Flask
- Flask-Session
- Leaflet.js (included via CDN)

These are all included in requirements.txt.

#### Using Pre-built Executables

Download the latest release from the [Releases page](https://github.com/tirandagan/fccULSloader/releases) for your platform (Windows, Linux, or macOS).

[↑ Back to Table of Contents](#table-of-contents-)

## Usage

### Using the Web Interface
**[[Usage](#usage) > Web Interface]**

To start the web interface:

```bash
python src/callsign_lookup_web.py
```

This will start a Flask web server on port 5000. You can then access the web interface by opening a web browser and navigating to:

```
http://localhost:5000
```

**Choosing a different port:** If port 5000 is already in use, pass `--port` (or set the `PORT` environment variable). This is common on macOS, where the **AirPlay Receiver** listens on port 5000 by default:

```bash
python src/callsign_lookup_web.py --port 8000
# or
PORT=8000 python src/callsign_lookup_web.py
```

You can also override the bind address with `--host` (or the `HOST` env var), which defaults to `0.0.0.0`.

The web interface provides:

1. **Search Options**:
   - Search by callsign (e.g., W1AW)
   - Search by name (partial or full)
   - Filter by state
   
2. **Advanced Filtering**:
   - License status (Active/Inactive)
   - License class (Extra, General, Technician)
   - Sort results by various fields
   
3. **Keyboard Shortcuts**:
   - Alt + C: Focus callsign field
   - Alt + N: Focus name field
   - Alt + S: Focus state field
   - Ctrl + T: Toggle dark/light theme

4. **View Options**:
   - Table view for compact listing
   - Card view for detailed information
   - Interactive map view for location data

### Command Line Options
**[[Usage](#usage) > Command Line Options]**

Offline Callsign Lookup provides a comprehensive set of command-line options for database management and querying:

#### Database Management Options

| Option | Description |
|--------|-------------|
| `--update` | Check for and download updates to the FCC database |
| `--force-download` | Force download even if data is up to date |
| `--skip-download` | Skip download and use existing data files |
| `--check-update` | Check if an update is available without downloading |
| `--keep-files` | Keep downloaded and extracted files after processing |
| `--quiet` | Suppress INFO log messages (only show WARNING and above) |
| `--compact` | Compact the database to reduce file size |
| `--optimize` | Remove unused tables and compact the database |
| `--rebuild-indexes` | Rebuild database indexes to improve search performance |
| `--active-only` | Only keep active license records (license_status="A") in the database. Requires confirmation before deleting records |
| `--country {us,ca,all}` | Which country's data to download/load/query — `us` (FCC, **default**), `ca` (Canada/ISED), or `all` (both). Canadian data loads into the **same** database alongside the FCC data. No effect on `--active-only` (all Canadian records are active). |

#### Query Options

| Option | Description |
|--------|-------------|
| `--callsign CALLSIGN` | Look up a specific amateur radio call sign |
| `--name NAME` | Search for records by name. Case-insensitive and **order-agnostic** — `"Brian Burk"` matches a record stored as `"Burk, Brian"`. Each word must appear somewhere in the name, in any order. |
| `--state STATE` | Filter records by two-letter **state** (US, e.g. CA, NY, TX) or **province** (CA, e.g. ON, QC, BC) code |
| `--verbose` | Display all fields for each record, including related records from other tables |

[↑ Back to Table of Contents](#table-of-contents-)

### Examples
**[[Usage](#usage) > Examples]**

#### Database Management

Update the database with the latest data from the FCC:
```
python callsign_lookup.py --update
```

Force a new download regardless of whether the data is up to date:
```
python callsign_lookup.py --force-download
```

Check if an update is available without downloading:
```
python callsign_lookup.py --check-update
```

Update the database and only keep active license records:
```
python callsign_lookup.py --update --active-only
```

Force a complete database rebuild with only active license records:
```
python callsign_lookup.py --force-download --active-only
```

Filter an existing database to only keep active license records:
```
python callsign_lookup.py --active-only
```

When using the `--active-only` option, the tool will:
1. Display the number of inactive records that will be deleted
2. Show a sample of call signs that will be removed
3. Ask for confirmation before proceeding with the deletion

This safety feature ensures you don't accidentally delete records you might need.

When using `--active-only` with `--force-download`, the database will be completely rebuilt with only active records, skipping the check for inactive records in the existing database.

Optimize the database to reduce its size:
```
python callsign_lookup.py --optimize
```

Rebuild indexes to improve search performance:
```
python callsign_lookup.py --rebuild-indexes
```

#### Queries

Look up a specific call sign:
```
python callsign_lookup.py --callsign W1AW
```

Search for records by name:
```
python callsign_lookup.py --name "Smith"
```

Search for records in a specific state:
```
python callsign_lookup.py --state CA
```

Combine name and state search:
```
python callsign_lookup.py --name "Smith" --state TX
```

Display detailed information for search results:
```
python callsign_lookup.py --name "Smith" --verbose
```

Search by name regardless of stored order (matches "Burk, Brian"):
```
python callsign_lookup.py --name "Brian Burk"
```

#### Canadian (ISED) Data 🇨🇦

Offline Callsign Lookup can optionally mirror the Canadian amateur database from Innovation,
Science and Economic Development Canada (ISED) into the **same** SQLite file,
giving you a unified US + Canada lookup. This is entirely opt-in via
`--country`; without it, the tool behaves exactly as before (US only).

Download and load **both** US and Canadian data:
```
python callsign_lookup.py --update --country all
```

Load **only** the Canadian data:
```
python callsign_lookup.py --update --country ca
```

Look up a Canadian call sign:
```
python callsign_lookup.py --callsign VE3XYZ --country ca
```

Search Canadian records by name and province, and query both countries at once:
```
python callsign_lookup.py --name "Tremblay" --state QC --country ca
python callsign_lookup.py --callsign VA2AA --country all
```

The Canadian source is the ISED "Amateur Call Sign List"
(`amateur_delim.zip`). It provides callsign, name, address, province, and
qualification level (Basic / Basic with Honours / Advanced). ISED publishes
only assigned callsigns, so all Canadian records are treated as active.
Canadian data is licensed under the
[Open Government Licence – Canada](https://open.canada.ca/en/open-government-licence-canada).

[↑ Back to Table of Contents](#table-of-contents-)

## Project Structure

The project is organized as follows:

```
callsign-lookup/
├── src/                  # Source code directory
│   ├── callsign_lookup.py       # Main CLI application script
│   ├── callsign_lookup_web.py   # Web interface application
│   ├── flask_session/    # Flask session storage
│   │   ├── css/         # Stylesheets
│   │   ├── js/          # JavaScript files
│   │   └── img/         # Images and icons
│   ├── modules/          # Application modules
│   └── tests/           # Test files
├── create_build/         # Build scripts and tools
│   ├── build_executable.py  # Main build script
│   ├── simple_build.py   # Simplified build script
│   ├── install.bat       # Windows installation script
│   ├── install.sh        # Linux installation script
│   └── install_macos.sh  # macOS installation script
├── dist/                 # Distribution directory (created during build)
│   ├── callsign-lookup-windows/ # Windows executable
│   ├── callsign-lookup-linux/   # Linux executable
│   └── callsign-lookup-macos/   # macOS executable
├── resources/            # Application resources
├── README.md             # This documentation
├── FCC_DATABASE_DOC.md   # Detailed database documentation
├── run.bat               # Windows run script
├── run.sh                # Linux/macOS run script
└── requirements.txt      # Python dependencies
```

When running the application, additional directories are created:

```
callsign-lookup/
├── data/                 # Data directory (created automatically)
│   ├── callsign_data.db       # SQLite database (holds both US and, if loaded, CA data)
│   ├── fcc_metadata.json # Metadata about the last FCC download
│   ├── ised_metadata.json# Metadata about the last ISED (Canada) download
│   ├── extracted/        # Extracted FCC .dat files
│   └── extracted_ca/     # Extracted ISED (Canada) data file
└── logs/                 # Log directory (created automatically)
    └── callsign_lookup.log      # Application log file
```

Key modules (`src/modules/`) include `config.py` (paths/URLs/knobs),
`schemas.py` (table/index/view definitions — single source of truth for data
structure), `database.py` (all SQL/queries, incl. the unified `licenses`
view), `loader.py` (FCC `.dat` bulk loader), `ised_loader.py` (Canadian ISED
loader), and `updater.py` (download/extract/load orchestration).

[↑ Back to Table of Contents](#table-of-contents-)

## Configuration

The database path and other configuration settings are defined in the `modules/config.py` file. You can modify these settings to customize the tool's behavior:

- `DB_PATH`: Path to the SQLite database file
- `DATA_PATH`: Directory for storing data files
- `ZIP_FILE_URL`: URL for downloading the FCC database
- `TABLES_TO_PROCESS`: List of FCC tables to process during data loading
- `HTTP_TIMEOUT`: `(connect, read)` timeouts (seconds) for all downloads/update checks
- `DEFAULT_COUNTRY`: Default country scope when `--country` is omitted (`us` | `ca` | `all`)
- `ISED_ZIP_FILE_URL`: URL for the Canadian (ISED) "Amateur Call Sign List"
- `ISED_EXTRACT_PATH` / `ISED_METADATA_FILE`: Canadian download/extract locations

[↑ Back to Table of Contents](#table-of-contents-)

## Database Documentation

The FCC database contains multiple tables with information about amateur radio licenses. The primary tables used by Offline Callsign Lookup are:

- `HD`: License header information (call sign, license status, etc.)
- `EN`: Entity information (name, address, etc.)
- `AM`: Amateur license information (operator class, etc.)
- `HS`: License history information
- `CO`: Comments associated with licenses
- `LA`: License attachments
- `SC`: Special conditions
- `SF`: Special free form conditions

When Canadian data is loaded (`--country ca|all`), one additional table and a view are present:

- `CA_AM`: Canadian (ISED) amateur records — one flat row per callsign (callsign, name, address, province, qualification flags, club fields)
- `licenses` (view): a unified, presentation-friendly read model over both sources, exposing `country`, `call_sign`, `formatted_name`, `state` (US state or CA province), `license_class`, `license_status`, and address fields. This is what powers cross-country queries.

> I created a detailed information about the FCC database structure, tables, fields, and their meanings, see the [FCC Database Documentation](FCC_DATABASE_DOC.md).

The FCC data is sourced from the [FCC's ULS database downloads page](https://www.fcc.gov/uls/transactions/daily-weekly), specifically the Amateur Radio Service database file (`l_amat.zip`).

**[📄 View Complete FCC Database Documentation](FCC_DATABASE_DOC.md)**

[↑ Back to Table of Contents](#table-of-contents-)

## Troubleshooting

### Common Issues

- **Database not found**: Run `python callsign_lookup.py --update` to download and create the database.
- **Slow searches**: Run `python callsign_lookup.py --rebuild-indexes` to optimize search performance.
- **Large database size**: Run `python callsign_lookup.py --optimize` to reduce the database size.
- **Download errors**: Check your internet connection and try again with `python callsign_lookup.py --force-download`.

### Logs

The application logs are stored in the `logs/callsign_lookup.log` file. If you encounter issues, check this file for detailed error messages and debugging information.

[↑ Back to Table of Contents](#table-of-contents-)

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request or open an Issue on GitHub.

1. Fork the repository
2. Create a feature branch: `git checkout -b feature-name`
3. Commit your changes: `git commit -am 'Add some feature'`
4. Push to the branch: `git push origin feature-name`
5. Submit a pull request

[↑ Back to Table of Contents](#table-of-contents-)

## Changelog

For a detailed list of changes between versions, please see the [CHANGELOG.md](CHANGELOG.md) file.

The current version is 1.8.0, which adds `--port`/`--host` options to the web interface so it can run on a port other than 5000 (useful when macOS AirPlay Receiver occupies port 5000).

[↑ Back to Table of Contents](#table-of-contents-)