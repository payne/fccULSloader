# Task 002 — Optional Canadian (ISED) Amateur Radio Support → Unified US+CA Database

> Template: `ai_docs/dev_templates/task_template.md`.
> Type: **Load-pipeline + Schema + Query/CLI + Web UI** feature (touches every layer). This is the broadest task type — see §1 checklist.
> Golden rule: every claim/plan step cites concrete `file:line` from the real source.

---

## 0. Context — how this fits the existing architecture

Today the tool mirrors **only** the FCC ULS dataset (`l_amat.zip`) into `data/fcc_data.db` and serves it via CLI (`src/fcc_tool.py`) and Flask (`src/fcc_tool_web.py`). This task adds an **optional** second data source — Canada's ISED "Amateur Call Sign List" — into the **same** SQLite file, exposed through a unified query surface, without changing default (US-only) behavior.

Pipeline recap (see `updater.update_data()` `modules/updater.py:152`):
```
updater → downloader.download_file → extractor.extract_data → loader.load_all_data → FCCDatabase
```
The downloader (`modules/downloader.py:15`) and extractor (`modules/extractor.py:14`) are **already source-agnostic** (take arbitrary `url`/`dest_path`/`zip_file_path`) — they can be reused for ISED as-is. The FCC-specific coupling lives in `updater.py`, `loader.parse_file()`, `schemas.py`, and every `FCCDatabase` query method.

### The core structural difference (drives every decision below)

| | FCC ULS | ISED `amateur_delim` |
|---|---|---|
| Structure | 3 normalized tables joined on `unique_system_identifier` (AM/EN/HD) | **1 flat record** per callsign |
| Delimiter | pipe `\|` (`loader.py:143,181`) | semicolon `;` |
| Encoding | ISO-8859-1 (`loader.py:119`) | **UTF-8** (verified: accented QC names e.g. `Mylène`, `Sauvé`) |
| Header row | none (`.dat` files) | **yes** — first line is column names |
| Line endings | `\n` | `\r\n` (CRLF — `line.strip()` already handles) |
| Primary key | `unique_system_identifier` (int) | **none** — callsign is the key |
| License status | `HD.license_status` (`A`/`E`/…) | **none** — only assigned calls published ⇒ treat all as active |
| Operator class | single `AM.operator_class` code | **derived** from 5 boolean qualification flags |
| Dates | grant/expiry/effective | **none** |
| Records | ~1.5M+ | ~91,926 (verified) |

**ISED file layout** (from `readme_amat_delim.txt`, semicolon-separated, 18 fields):
```
1  callsign            10 qual_12wpm  (C)
2  given_names         11 qual_advanced (D)
3  surname             12 qual_honours (E, "Basic with Honours")
4  street_address      13 club_name
5  city                14 club_name_2
6  province            15 club_address
7  postal_code         16 club_city
8  qual_basic  (A)     17 club_province
9  qual_5wpm   (B)     18 club_postal_code
```
Qualification fields hold the flag letter (`A`/`B`/`C`/`D`/`E`) when held, else empty. Sample rows:
```
VA1AA;Bill;McFadden;188 MILLWOOD DRIVE;MIDDLE SACKVILLE;NS;B4E2X8;A;;C;D;;;;;;;
VA1ADV;James Russel;Hannon;279 PUMPING STATION ROAD;AMHERST;NS;B4H3Y3;A;;C;D;;Advocate Fire Department;;PO BOX 126;ADVOCATE HARBOUR;NS;B0M1A0
```
Download URL: `https://apc-cap.ic.gc.ca/datafiles/amateur_delim.zip` (~2.3 MB zip). No documented update cadence — treat like FCC (compare HTTP `Last-Modified`).

### Architectural rules to honor (from Task 001 audit)

1. **Run from `src/`** — bare `modules.*` imports.
2. **SQL only in `database.py` / `loader.py`** — CLI and web issue zero raw SQL. The unified query is a **new `FCCDatabase` method**, never inline in a route.
3. **`schemas.py` four dicts stay in lockstep** — `table_schemas`, `index_schemas`, `column_counts`, `field_names`. New CA table ⇒ edit all four; `column_counts[t]` must equal both the DDL column count and `len(field_names[t])`.
4. **Paths/URLs/knobs live in `Config`** (`modules/config.py`).
5. **The DB is disposable/rebuildable** — a schema/view change means a full rebuild, no migration framework.

---

## 1. Task Overview

### Task Title
**Optional ISED (Canada) amateur-radio import into a unified US+CA SQLite database, opt-in via `--country`.**

### Goal Statement
**Goal:** Let an offline operator look up **Canadian** amateur licenses (callsign, name, address, province, qualification level) from the same tool, same DB, and same UI they already use for US callsigns — while a default run behaves **exactly** as today (US only). Canada is opt-in via `--country ca|all`; the existing FCC importer is untouched.

### Task Type — this touches all of:
- [x] **Load-pipeline / performance** → new ISED download+parse+load path (§5, §7)
- [x] **Schema / data-structure change** → new `CA_AM` table + unified `licenses` view (§7)
- [x] **Query / CLI feature** → country-aware query method + `--country` flag (§5)
- [x] **Web UI feature** → country selector, province filter, CA class labels (§5, §4)

### Decisions already made with the maintainer (2026-07-24)
1. **Schema = unified normalized `licenses` view.** Both FCC (`EN`+`HD`+`AM`) and ISED (`CA_AM`) map into one view exposing common columns; queries hit the view.
2. **CLI = `--country us|ca|all`, default `us`** (today's behavior unchanged).
3. **Scope = CLI *and* Web UI** both surface Canadian data.
4. **Datasets = main Amateur Call Sign List only** (`amateur_delim.zip`). Special-event calls / examiners are out of scope (future task).

---

## 2. Strategic Analysis & Solution Options

### Problem context
The unified-view decision is set, but two sub-decisions carry real trade-offs and are worth recording: **(a)** how the ISED file is parsed/loaded given `loader.parse_file()` is hardwired to FCC semantics, and **(b)** how the unified view names its columns so the existing presentation layers (CLI `display_record`, web templates) keep working.

### Option A — Dedicated ISED loader + presentation-compatible view *(Recommended)*
**Approach:**
- New `modules/ised_loader.py` with its own `parse_ised_file()` (UTF-8, `;`, skip header) and `load_ised_data()` — do **not** overload `loader.parse_file()` (it hardcodes `|`, ISO-8859-1, and FCC `unique_system_identifier`/`active_only` position logic at `loader.py:143,150-165`).
- Add `CA_AM` to `schemas.py` (all four dicts).
- Add a `licenses` **view** whose output columns **alias to the names the current presentation already expects** — `call_sign`, `formatted_name`, `city`, `state` (province reused here), `license_class` (CA qualification code reused here), `license_status`, plus a **new** `country` column. FCC rows fill these from `EN/HD/AM`; CA rows fill `state`←province, `license_class`←derived CA code, `license_status`←`'A'`.
- One new query method `search_licenses(...)` on `FCCDatabase` reads the view with an optional `country` filter.

**Pros ✅** Existing FCC path byte-for-byte unchanged; CLI/web display code needs **minimal** change because column names match; view keeps SQL in the data layer (rule 2); addresses Task 001 **F1** by giving new searches one query path instead of a 5th duplicate.
**Cons ❌** Reusing `state`/`license_class` columns for province/CA-class is slightly "overloaded" semantically (mitigated by the explicit `country` column + a country-aware label map).
**Complexity:** Medium · **Risk:** Low-Med · **Fit:** strong (respects rules 1–5).

### Option B — Overload `loader.parse_file()` with a delimiter/encoding param
**Approach:** Parameterize the existing parser (`delimiter`, `encoding`, `skip_header`) and route ISED through `load_data()`.
**Pros ✅** Less new code.
**Cons ❌** `parse_file()` and `load_data()` are riddled with FCC assumptions (`fields[1]` = `unique_system_identifier` for dedup `database.py:126`; `active_only`/HD logic `loader.py:150-165`); bolting CA on risks regressing the hot FCC load path. **Higher blast radius on the most performance-sensitive code.**
**Complexity:** Med · **Risk:** **High** (touches FCC hot path) · **Fit:** weaker.

### Option C — Fully normalize ISED into EN/HD-shaped rows
**Approach:** Synthesize fake `unique_system_identifier`s and split ISED into `EN`/`HD` rows so existing queries "just work" unchanged.
**Pros ✅** Zero query changes.
**Cons ❌** Fabricates keys, pollutes FCC tables with non-FCC data, breaks the "EN/HD == FCC" mental model, and complicates `--active-only`'s FCC-specific deletes (`database.py:764`). Rejected.
**Complexity:** High · **Risk:** High · **Fit:** poor.

### 🎯 Recommendation
**Option A.** Isolate ISED in its own loader + table, unify only at a read-only view whose columns are presentation-compatible. Lowest risk to the offline FCC path, cleanest query surface, and it opportunistically consolidates search (F1).

### Decision Request (chat-facing)
*(Already resolved on the four big questions. The only open sub-decision to confirm during implementation — not blocking design:)* whether the province filter reuses the existing "State" dropdown (relabeled "State / Province" with Canadian provinces appended when Canada is in scope) vs. a separate control. Recommend **reuse + relabel** for a single, familiar filter.

---

## 3. Current-State Analysis (cited)

- **Data layer `modules/database.py`** — Query methods to touch/extend:
  - `get_record_by_call_sign()` `database.py:217` — EN⨝HD⟕AM on `unique_system_identifier`, `WHERE HD.call_sign=?`. **US-only**; CA lookups need a view-based sibling.
  - `search_records_by_name/_by_state/_by_name_and_state` `database.py:377,472,550` — all three hardcode the same `EN⨝HD⟕AM … LOWER(...) LIKE` + `HD.license_status='A'` shape (**Task 001 F1**, ~4 near-duplicate blocks).
  - `search_records()` `database.py:874` — the **web/paginated entry point**; dispatches to the above by which args are set, then does status/class/sort/pagination in Python. **This is the natural place to add `country`** and route to the new unified method.
  - `create_tables()` `database.py:92`, `insert_batch_records()` `database.py:105` (dedup keyed on `unique_system_identifier` `:123-135` — CA_AM not in that list ⇒ naturally skips dedup), `get_column_count()` `database.py:214` (reads `column_counts`).
  - ⚠️ `search_records()` references `logger` and `DatabaseError` that are **not imported** in `database.py` (`:927-928`) — latent bug; will surface if that except-branch runs. Fix opportunistically or leave noted (out of strict scope).
- **Schema `modules/schemas.py`** — four dicts, currently 8 FCC tables. Add `CA_AM` to all four + the `licenses` view DDL (new — decide whether views live in `table_schemas` or a new `view_schemas` dict; recommend a new `view_schemas` dict created after load, since a view over `EN/HD/AM/CA_AM` must be created *after* those tables exist).
- **Config `modules/config.py`** — only FCC paths/URL today (`:55-58`). Need ISED URL/zip/extract paths + a default-country knob. `TABLES_TO_PROCESS` `:62` governs FCC scope; CA needs an analogous constant.
- **Load pipeline** — `updater.update_data()` `updater.py:152` is FCC-only (uses `Config.ZIP_FILE_URL`, writes `fcc_metadata.json` `:63`, loads `Config.TABLES_TO_PROCESS` `:227-234`). `check_for_update()` `:106` is hardwired to `Config.ZIP_FILE_URL`. `downloader.download_file()` `:15` and `extractor.extract_data()` `:14` are **generic/reusable**.
- **CLI `fcc_tool.py`** — `argparse` in `main()` `:186`; update/force-download call `updater.update_data(...)` `:288,317`; queries call the `search_*` methods directly `:374-427`. No country concept.
- **Web `fcc_tool_web.py`** (2,870 lines, inline templates — **Task 001 F2**) — routes `/` `:2726`, `/search` `:2742`, `/profile/<callsign>` `:2798`. `search()` reads `state`/`status`/`license_class` args and calls `db.search_records(...)` `:2767`. `STATES` dict (US only) `:2630`, `LICENSE_CLASS_MAP` `:2646` (FCC classes), rendered in `RESULTS_TEMPLATE` `:1406` via `r.get('state')` `:1820`, `r.get('license_class')` + `LICENSE_CLASS_MAP` `:1827`. Profile route uses `get_record_by_call_sign()` `:2801` (US-only path).
- **Code translation `modules/fcc_code_defs.py`** — `entity_type` `:65`, `applicant_type_code` `:46`. No operator-class map here (the web keeps its own `LICENSE_CLASS_MAP`). Add a **Canadian** qualification→label map.

### Current State
Everything is US/FCC-specific but cleanly layered: the download/extract primitives are reusable, SQL is already confined to the data layer, and the web already has a `search_records()` seam with `status`/`license_class` filters. There is **no** country concept anywhere and **no** second data source path.

---

## 4. Known Constraints & Debt to respect (Task 001)

- **F1 (High):** 4 duplicate search methods. **Do not add a 5th** — introduce the unified `search_licenses()` and route `search_records()` through it.
- **F2 (High):** `fcc_tool_web.py` is a 2,870-line inline-HTML monolith. Add the country selector/labels with **minimal** additions; do not balloon it. (Full template extraction is a separate task.)
- **F4 (Med):** `tests/` and `src/tests/` are duplicated & stale. Add **new** ISED tests against real signatures; fix any stale test you rely on.
- **I1 (High, integrity):** interrupted load can leave a torn DB (`synchronous=OFF`, per-table drop+reload). ISED load must follow the same interrupt-safe pattern (`is_shutting_down`, registered connections, rollback) as `loader.py:41-92,308-360`.
- **I2 (Med):** over/under-length records silently dropped/padded (`loader.py:312-320`). For ISED, **count and log** skipped rows (malformed field count) rather than silently dropping.
- **P1 (Med):** `cache_size` comment says ~1GB but is ~4GB — irrelevant to correctness; don't copy the misleading comment.

---

## 5. Code Changes — Where Things Go

### 5.1 `modules/config.py` — new source + knob
```python
# ISED (Canada) — optional second source
ISED_ZIP_FILE_URL  = 'https://apc-cap.ic.gc.ca/datafiles/amateur_delim.zip'
ISED_ZIP_FILE_PATH = os.path.join(DATA_PATH, "amateur_delim.zip")
ISED_EXTRACT_PATH  = os.path.join(DATA_PATH, "extracted_ca")     # keep CA files separate from FCC .dat
ISED_DATA_FILE     = "amateur_delim.txt"
ISED_TABLES_TO_PROCESS = ["CA_AM"]
DEFAULT_COUNTRY    = "us"                                        # us | ca | all
```
Keep `DB_PATH = data/fcc_data.db` (single unified DB; renaming would orphan existing installs — note in README instead).

### 5.2 `modules/schemas.py` — `CA_AM` table (all four dicts) + view
```python
# table_schemas["CA_AM"]
CREATE TABLE IF NOT EXISTS CA_AM (
    call_sign TEXT, first_name TEXT, surname TEXT, street_address TEXT,
    city TEXT, province TEXT, postal_code TEXT,
    qual_basic TEXT, qual_5wpm TEXT, qual_12wpm TEXT, qual_advanced TEXT, qual_honours TEXT,
    club_name TEXT, club_name_2 TEXT, club_address TEXT, club_city TEXT,
    club_province TEXT, club_postal_code TEXT
);
# index_schemas["CA_AM"]: call_sign, surname, first_name, province  (mirror EN/HD indexes for the reused filters)
# column_counts["CA_AM"] = 18   ← must equal DDL cols == len(field_names["CA_AM"])
# field_names["CA_AM"] = [ ...the 18 names above, in file order... ]
```
New `view_schemas` dict (created **after** tables load, in `enable_indexes`/a new `create_views()` step):
```sql
CREATE VIEW IF NOT EXISTS licenses AS
  SELECT 'US' AS country, HD.call_sign AS call_sign,
         <EN formatted_name expr> AS formatted_name,
         EN.street_address AS street_address, EN.city AS city,
         EN.state AS state, EN.zip_code AS postal_code,
         AM.operator_class AS license_class, HD.license_status AS license_status
  FROM EN JOIN HD ON EN.unique_system_identifier=HD.unique_system_identifier
          LEFT JOIN AM ON EN.unique_system_identifier=AM.unique_system_identifier
  UNION ALL
  SELECT 'CA' AS country, call_sign,
         TRIM(COALESCE(first_name,'')||' '||COALESCE(surname,'')) AS formatted_name,
         street_address, city, province AS state, postal_code,
         -- derived CA class code (highest qualification held), see §7
         CASE WHEN qual_advanced='D' THEN 'CA_ADV'
              WHEN qual_honours='E'  THEN 'CA_HON'
              WHEN qual_basic='A'    THEN 'CA_BAS'
              ELSE '' END AS license_class,
         'A' AS license_status
  FROM CA_AM;
```
> Column names deliberately match what the CLI/web already read (`call_sign`, `formatted_name`, `state`, `license_class`, `license_status`) so presentation barely changes; `country` is the only new field.

### 5.3 `modules/ised_loader.py` — NEW (don't touch FCC `loader.py`)
- `parse_ised_file(path)`: open UTF-8; **skip first line** (header); split on `;`; skip rows whose field count != 18 (log a running skipped-count, per I2); yield 18-field lists. Reuse the interrupt-safety pattern from `loader.py` (`is_shutting_down`, `register_connection`, rollback).
- `load_ised_data(db, extract_path)`: drop+recreate `CA_AM`, batch-insert (`BATCH_SIZE`), rebuild `CA_AM` indexes — mirror `loader.load_data()` shape (`loader.py:256-344`) minus the `unique_system_identifier` dedup/`active_only` branches.

### 5.4 `modules/updater.py` — country-aware orchestration
- Generalize update: add `update_ised_data(skip_download, keep_files, force_download, quiet)` mirroring `update_data()` but with ISED URL/paths, `ised_metadata.json`, and `ised_loader.load_ised_data`. Reuse `downloader.download_file` / `extractor.extract_data` unchanged.
- Add a `check_for_update(url=Config.ZIP_FILE_URL, metadata_file=...)` param so the same logic serves both sources (currently hardcoded `:117,184`).
- After both sources load, call `db.create_views()` so `licenses` reflects whatever tables exist.
- A dispatcher (`update_country(country, ...)`) runs FCC and/or ISED based on `us|ca|all`.

### 5.5 `modules/database.py` — one unified query method (addresses F1)
- Add `search_licenses(callsign=None, name=None, region=None, country=None, status=None, license_class=None, sort=None, page=1, per_page=20)` — parameterized (`?`) query over the `licenses` view with optional `WHERE country=?`, `call_sign=?`, name `LIKE`, `state=?` (province/state), status/class filters, `ORDER BY`, pagination. **All user input via placeholders** (keep the codebase's clean record).
- Route `search_records()` `:874` through `search_licenses()` (keep signature; add `country`). Add a view-based `get_license_by_call_sign(callsign, country=None)` for CA/all profile lookups; keep `get_record_by_call_sign()` for the FCC-verbose CLI path.
- Add `create_views()` (creates/refreshes `licenses` from `view_schemas`).

### 5.6 `fcc_tool.py` — `--country` flag
- Add to `db_group`: `--country {us,ca,all}` default `Config.DEFAULT_COUNTRY`; help: "Which country's data to download/load/query (default: us)."
- Update/force-download paths (`:288,317`) → call the country dispatcher.
- Query paths (`:374-427`): pass `country` into the unified search; when country includes CA, `--state` also matches provinces (document that `--state ON` works). `--active-only` is a **no-op for CA** (ISED is all-active) — log that, don't error.
- Refresh the module docstring option list (`:63-91`) and `display_header`/help.

### 5.7 `fcc_tool_web.py` — selector + labels (minimal footprint)
- `search()` `:2742`: read `country = request.args.get('country', Config.DEFAULT_COUNTRY)`; pass to `db.search_records(..., country=country)` `:2767`.
- `SEARCH_FORM` `:690`: add a small Country select (US / Canada / All). Relabel the State control "State / Province"; when CA is in scope, append Canadian provinces to `STATES` (new `PROVINCES` dict, merged for the dropdown).
- `RESULTS_TEMPLATE` `:1406`: add a **Country** column; make the class label country-aware — extend/merge `LICENSE_CLASS_MAP` `:2646` with CA codes (`CA_BAS`→"Basic", `CA_HON`→"Basic w/ Honours", `CA_ADV`→"Advanced"). `r.get('state')` `:1820` now shows province for CA rows automatically.
- `profile()` `:2798`: use the country-aware `get_license_by_call_sign()` so `VE3XYZ` resolves.

### 📂 Key Changes Summary
| What | Why | Files | Impact |
|---|---|---|---|
| New CA source config | opt-in second dataset | `config.py` | additive |
| `CA_AM` table + `licenses` view | unified normalized surface | `schemas.py` | rebuild required |
| Dedicated ISED loader | avoid regressing FCC hot path | `ised_loader.py` (new) | isolated |
| Country-aware update/dispatch | download/load CA optionally | `updater.py` | additive |
| `search_licenses()` + view lookup | one query path (F1) | `database.py` | FCC methods retained |
| `--country` flag | opt-in CLI | `fcc_tool.py` | default unchanged |
| Country selector + CA labels | CA visible in UI | `fcc_tool_web.py` | additive to monolith |

---

## 6. Requirements & Success Criteria

### Functional
- **Order-agnostic name search (applies to US *and* CA).** A multi-word name query must match regardless of stored order or `Last, First` formatting: searching `Brian Burk` returns a record stored as `Burk, Brian` (FCC `entity_name`) or as `first_name=Brian, last_name=Burk`. Implemented by tokenizing the query on whitespace/commas and requiring **each token to match at least one name field** (`entity_name`/`first_name`/`mi`/`last_name` for FCC; `formatted_name`/`first_name`/`last_name` for CA), tokens in any order. Single-word searches behave as before. Retrofit the existing FCC name methods (`database.py:377,550`) via a shared clause builder rather than a new duplicate (Task 001 F1).
- `--country us` (and no flag) → **identical** to today (US only).
- `--country ca` → downloads/loads/queries **only** ISED; `--country all` → both, in one `fcc_data.db`.
- `python fcc_tool.py --callsign VE3XYZ --country all` returns the Canadian record (name, address, province, qualification).
- `--name`/`--state` search works across the selected country/countries; province codes accepted for CA.
- Web `/search?country=ca|all` returns CA rows with a Country column and correct Basic/Advanced labels; `/profile/VE3XYZ` renders.

### Non-Functional
- **Offline-first:** once loaded, all CA queries work with no network.
- **Performance:** FCC load throughput (records/sec in `logs/fcc_tool.log`) **must not regress**; ISED (~92k rows) loads in seconds.
- **Portability:** no new heavy deps (stdlib `zipfile`/`csv` suffice; ISED is UTF-8 so no new codecs). Must still build under PyInstaller (`create_build/`).
- **Cross-platform:** handle CRLF and UTF-8 on Windows/Linux/macOS.

### Success Criteria (measurable)
- [ ] Default run byte-for-byte unchanged (diff a US-only DB build before/after — same FCC table row counts).
- [ ] `CA_AM` loads ~91,926 rows (±, source changes); malformed-row skips **logged with a count**.
- [ ] `schemas.py` parity check passes for `CA_AM` (18 == 18 == 18).
- [ ] `licenses` view returns both `country='US'` and `country='CA'` rows after an `--country all` build.
- [ ] CLI + web CA lookups verified against a known VE/VA/VO callsign.
- [ ] `README.md` (Features / Command-Line Options / Configuration / Project Structure) + `CHANGELOG.md` + version bump updated (CLAUDE.md convention).

---

## 7. Data, Schema & Integrity

### Schema/view plan
- [ ] Add `CA_AM` to **all four** `schemas.py` dicts; verify `column_counts["CA_AM"] == len(field_names["CA_AM"]) ==` DDL column count (= 18).
- [ ] Add `view_schemas["licenses"]`; create it **after** table load (a view over missing tables errors — guard so a CA-only or US-only build still creates a valid view, e.g. only `UNION` the arms whose tables exist, or accept that querying a missing arm is impossible because the tables always exist as empty after `create_tables`). Recommend: always `create_tables` for both `EN/HD/AM` and `CA_AM` so both view arms are valid even when one is empty.
- [ ] Indexes on `CA_AM(call_sign)`, `(surname)`, `(first_name)`, `(province)` to match reused filters.

### Derived Canadian "class"
ISED has no single class code; derive a display code from the flags (highest privilege wins), mapped in the web label map:
- `qual_advanced == 'D'` → `CA_ADV` → "Advanced"
- `qual_honours == 'E'` → `CA_HON` → "Basic with Honours"
- `qual_basic == 'A'` → `CA_BAS` → "Basic"
- (`5wpm`/`12wpm` are Morse endorsements, not a class — optionally surface in the verbose/profile view, not as the class.)
Document this mapping in `fcc_code_defs.py` (new `ca_qualification` dict) so it's discoverable next to the FCC code defs.

### Load / integrity (mirror Task 001 lessons)
- [ ] ISED load uses the interrupt-safe pattern (registered connections, `is_shutting_down`, rollback) — an interrupted CA load must not corrupt FCC tables (they're loaded in a separate step/connection).
- [ ] Malformed rows (field count ≠ 18) **counted and logged**, not silently dropped (fixes I2 behavior for the new path).
- [ ] Header row explicitly skipped (don't insert `callsign;first_name;...` as data).
- [ ] No dates to convert; no `active_only` filtering for CA (all active) — log the no-op.

### Migration / rebuild note
No migration framework — adding `CA_AM` + `licenses` means a **full rebuild** (`python fcc_tool.py --force-download` for US, and a first `--country ca|all` for CA). **Existing `fcc_data.db` files remain valid for US queries**; the `licenses` view is created on next load. State this in README.

---

## 8. Implementation Plan (phased, file-cited)

### Phase 0 — Confirm source layout (fast, done during dev)
- [ ] Re-download `amateur_delim.zip`, re-verify 18 fields / UTF-8 / header / CRLF and current row count before coding the parser. (Already verified once on 2026-07-24.)

### Phase 1 — Schema & config foundation
- [ ] **1.1** Add ISED constants + `DEFAULT_COUNTRY` — `modules/config.py`.
- [ ] **1.2** Add `CA_AM` to all four dicts + `view_schemas["licenses"]` — `modules/schemas.py`; run parity check.

### Phase 2 — ISED load pipeline
- [ ] **2.1** `modules/ised_loader.py`: `parse_ised_file()` + `load_ised_data()` (new; reuse interrupt-safety pattern).
- [ ] **2.2** `updater.py`: parameterize `check_for_update(url, metadata_file)`; add `update_ised_data()` + `update_country()` dispatcher; call `db.create_views()` after load; write `ised_metadata.json`.
- [ ] **2.3** `database.py`: `create_views()`; ensure `create_tables`/`get_column_count` handle `CA_AM`.

### Phase 3 — Unified query layer
- [ ] **3.1** `database.py`: `search_licenses()` over the view (parameterized) + `get_license_by_call_sign()`.
- [ ] **3.2** Route `search_records()` `:874` through `search_licenses()`, adding `country` (keep US default behavior identical).

### Phase 4 — CLI
- [ ] **4.1** Add `--country {us,ca,all}`; wire update/force-download → dispatcher; wire queries → unified search; `--active-only` no-op for CA — `fcc_tool.py`. Refresh docstring/help.

### Phase 5 — Web UI
- [ ] **5.1** Country select + "State/Province" relabel + `PROVINCES` — `SEARCH_FORM`/`STATES` in `fcc_tool_web.py`.
- [ ] **5.2** Country column + CA class labels in `RESULTS_TEMPLATE`/`LICENSE_CLASS_MAP`; pass `country` in `search()` `:2767`; country-aware `profile()`.

### Phase 6 — Docs
- [ ] **6.1** `README.md` (Features / Command-Line Options / Configuration / Project Structure), `CHANGELOG.md` entry, version bump in `fcc_tool.py:105`.

### Phase 7 — Testing & Validation (run from `src/`)
- [ ] **7.1** Unit: `parse_ised_file()` on a 3-row fixture (incl. a club row + an accented name + a malformed row) — asserts field count, header skip, skip-count log.
- [ ] **7.2** Schema parity test for `CA_AM` (new test; don't trust stale `tests/` — F4).
- [ ] **7.3** Real load: `python fcc_tool.py --country ca --force-download` → confirm `CA_AM` count + records/sec in `logs/fcc_tool.log`; then `--country all` and confirm FCC counts unchanged vs. a pre-change US build.
- [ ] **7.4** CLI: `--callsign <known VE call> --country all --verbose`; `--name --state ON`.
- [ ] **7.5** Web: `http://localhost:5000` → country=Canada and All; verify results, class labels, profile.

### 🛑 Checkpoint
Present an **"Implementation Complete!"** summary and **stop for code review** (§9) before declaring done.

---

## 9. Comprehensive Code Review (before "done")
- [ ] Re-read every changed file end-to-end.
- [ ] **Architecture compliance:** no SQL in routes/CLI (new query is a `FCCDatabase` method); `schemas.py` four dicts consistent incl. `CA_AM`; ISED paths/URL in `Config`, not hardcoded; FCC `loader.py` untouched (or, if touched, justified + reperf-tested).
- [ ] **Parameterization:** all user-influenced view queries use `?`.
- [ ] **No new debt (Task 001):** did **not** add a 5th duplicate search method (routed through `search_licenses`); web additions are minimal (F2); new tests added, no reliance on stale ones (F4); ISED load is interrupt-safe (I1) and logs skips (I2).
- [ ] **Regression proof:** US-only build identical to pre-change (row counts + a sample callsign).
- [ ] Docs + CHANGELOG + version bumped.
- [ ] Honest summary: files touched, tests run + real results.

---

## 10. Reliability, Recovery & Edge-Case Gotchas (added on reflection)

> These are the non-obvious failure modes. Several are **pre-existing weaknesses in the shared download/update path** that this task would otherwise inherit and duplicate for ISED — fix them **once, in the shared path**, so FCC benefits too. Grounded against source on 2026-07-24.

### 10.1 Safe recovery from an aborted / partial download ⚠️ (highest priority)
Today's flow is **not** crash-safe, and ISED (a foreign gov server, likely slower / flakier) makes this bite sooner:
- **Failed download is ignored.** `downloader.download_file()` returns `False` on total failure (`downloader.py:66`), but `updater.update_data()` **ignores the return** (`updater.py:196`) and proceeds to `save_download_metadata()` (`:199`) then extract. So a failed/aborted download **still records "downloaded at time X"** → the next `--update` sees "up to date" and **won't retry**. Recovery is broken by design.
- **Metadata written before load.** `save_download_metadata()` runs right after download (`updater.py:199`), *before* extract+load. An interrupt during load leaves metadata claiming success over a torn DB (compounds Task 001 **I1**).
- **Non-atomic write.** Download streams straight to the final path (`downloader.py:47`, `open(dest_path,'wb')`). A truncated `amateur_delim.zip`/`l_amat.zip` sits at the real path looking legitimate; `--skip-download` then feeds it to `extract_data`, which catches `BadZipFile` (`extractor.py:48`) and **returns without raising** → `update_data` prints a generic "extraction dir empty" message. Confusing, not recoverable-by-design.
- **No completeness check.** `Content-Length` is fetched only for the progress bar (`downloader.py:35`) and never compared to bytes written; no `zipfile.is_zipfile()`/`testzip()` validation.

**Design the recovery path (apply to both sources):**
1. Download to a **temp file** (`<dest>.part`), validate, then **atomic `os.replace()`** to the final path — a partial download can never masquerade as complete.
2. **Validate before trusting:** `zipfile.is_zipfile()` + `ZipFile.testzip()` (and, when the server sent one, assert bytes-written == `Content-Length`). On failure, delete the temp file and fail loudly.
3. **Check `download_file`'s return value** in `update_data`; on `False`, **abort without writing metadata** and exit non-zero.
4. **Write metadata only after a successful load** (move `save_download_metadata()` to the end), so an interrupted run never records false success and the next run cleanly retries.
5. **Idempotent re-run:** `--skip-download` must verify the local zip/extract exists and is valid; if not, instruct the user to re-run without `--skip-download` instead of silently proceeding.
6. Leftover `<dest>.part` on startup ⇒ safe to discard/overwrite (never resumed — no HTTP Range support here).

### 10.2 No network timeouts anywhere (confirmed: `grep timeout modules/` → none)
Every `requests.head`/`requests.get` (`downloader.py:34,38`; `updater.py:117,184`) has **no `timeout=`** → a hung connection blocks the process forever. A foreign server hang is exactly the ISED risk. **Add explicit timeouts** (e.g. `timeout=(10, 60)`) to all four calls; treat a timeout as a normal retryable failure in `download_file`'s loop.

### 10.3 `cleanup_temp_files()` is hardcoded to FCC paths
`filesystemtools.cleanup_temp_files()` (`:164-183`) deletes only `Config.ZIP_FILE_PATH` and `Config.EXTRACT_PATH`. It will **never clean the ISED zip/extract dir**, and `--keep-files` won't cover them either. Generalize it to take paths (or clean both sources). Also ensure `ISED_EXTRACT_PATH != EXTRACT_PATH` (it is `extracted_ca` in §5.1) — `extractor.extract_data()` does `shutil.rmtree(extract_to_path)` (`:26`), so overlapping paths would delete the other source's files.

### 10.4 Performance regression risk from routing US searches through the view ⚠️
This is a genuine tension with the "unified view" decision. The current FCC name search is **hand-optimized**: a CTE that filters on indexed columns + `HD.license_status='A'` first (`database.py:394-425`). A view exposes `formatted_name` as a **computed expression** (the `CASE/COALESCE/TRIM`), which is **not indexable** → `SELECT … FROM licenses WHERE formatted_name LIKE '%x%'` becomes a **full scan of ~1.5M FCC rows on every name search**, regressing US latency.
**Mitigation (keep the clean surface without the regression):** make `search_licenses()` **country-aware about *how* it queries**, not just *what* it filters:
- For **US**, keep the existing indexed EN/HD/AM path (call the current optimized methods).
- For **CA** (~92k rows), a simple indexed `CA_AM` query or the view's CA arm is trivially fast either way.
- For **`all`**, run both and merge/paginate in Python (as `search_records()` already assembles results `database.py:892-924`).
The `licenses` view remains the clean **read model for callsign/profile lookups and CA**; it does **not** have to be the engine for high-cardinality US `LIKE` scans. Benchmark a US name search before/after (records/sec, wall-clock) to prove no regression.

### 10.5 `optimize_database()` will drop `CA_AM` **and break the view**
`--optimize` (`database.py:295`) hardcodes `used_tables=['EN','HD']` (`:318`) and **drops every other table** — that already drops `AM` (which `get_record_by_call_sign` LEFT JOINs, `:247`) and would drop `CA_AM`, leaving the `licenses` view referencing a missing table (query-time error). Update `used_tables` to include `AM` and `CA_AM`, drop+recreate views around it, or make `--optimize` view-aware. Likewise `rebuild_indexes()` (`:647`) REINDEXes hardcoded FCC index names only — add CA indexes or note the gap.

### 10.6 `licenses` view requires both arms' tables to exist
A view over `EN/HD/AM/CA_AM` fails to *query* if any referenced table is absent. On a pre-existing US-only DB (built before this feature), `CA_AM` won't exist. **`create_views()` must `create_tables(['CA_AM'])` first** (empty table is fine), and a US-only or CA-only build must still create *all* referenced tables (empty) so both `UNION ALL` arms are valid.

### 10.7 Partial success on `--country all`
If FCC loads but ISED download fails (or vice-versa): sources load via **separate steps/connections**, so a CA failure leaves US tables intact (good). But the run must **report per-source outcome**, write each source's metadata **independently and only on its own success**, refresh the view over whatever loaded, and **exit non-zero** if any requested source failed — never silently claim success.

### 10.8 Parsing robustness (defensive, even though clean today)
Verified on the current file: **0 rows with ≠18 fields**, **0 duplicate callsigns**. But don't hard-assume it stays that way:
- Use `csv.reader(f, delimiter=';')` over naive `str.split(';')` so a future embedded-`;` (unquoted) address is handled by one policy; **skip rows with field-count ≠ 18 and log a running count** (fixes Task 001 **I2** for the new path) rather than corrupting column alignment.
- Read as **`utf-8-sig`** to tolerate a possible BOM on line 1 (the header we skip anyway).
- Explicitly **skip the header row** (`callsign;first_name;…`) — inserting it as data is the classic first-run bug.
- Even though callsigns are unique today, `get_license_by_call_sign()` should `fetchall`/handle >1 gracefully (return all, tagged) rather than assume one.

### 10.9 Presentation edge cases
- **Windows console:** printing accented CA names (`Mylène`, `Sauvé`) to a cp1252 console can raise `UnicodeEncodeError`. Guard CLI output (e.g. `errors='replace'` or reconfigure stdout to UTF-8) — the FCC ISO-8859-1 path never hit chars beyond latin-1.
- **Profile template:** `PROFILE_TEMPLATE` assumes FCC fields (FRN, grant/expiry, entity fields). CA rows lack these — ensure the template uses `.get()`/conditionals so a CA profile renders blanks, not a `KeyError`.
- **Web class filter:** the license-class dropdown lists only FCC `E/G/T` (`fcc_tool_web.py:1783-1785`); CA codes (`CA_BAS/CA_HON/CA_ADV`) won't be filterable unless added when CA is in scope. **Recent-searches** display looks up province via `STATES.get()` (`:2708`) — merge `PROVINCES` or CA rows show raw codes.

### 10.10 Update-check semantics for ISED
`check_for_update()` returns `False` (→ "up to date", skip) on **any** `RequestException` (`updater.py:148-150`) and `True` when the server sends **no `Last-Modified`**. Confirm whether `apc-cap.ic.gc.ca` returns `Last-Modified`/`Content-Length`; if not, `--country ca` without `--force-download` will **re-download every run**. Parameterize `check_for_update(url, metadata_file)` (currently hardcoded to FCC) and give ISED its own `ised_metadata.json`.

### 10.11 Tests must not depend on the live network
Unit tests for `parse_ised_file()` use a **committed tiny fixture** (3 rows: a club row, an accented name, a deliberately malformed row) — never the live download. Keep the real `apc-cap` fetch as a **manual/integration** step (§7.3). Ensure `--skip-download` is wired for ISED so offline dev/test can reload from `data/extracted_ca/`.

### 10.12 Packaging & licensing (low risk, don't forget)
- `ised_loader.py` is a static import ⇒ PyInstaller picks it up; `csv`/`zipfile` are stdlib (bundled). No new pip deps. Verify a build still runs (`create_build/`).
- ISED data is under the **Open Government Licence – Canada**; the tool downloads at runtime (doesn't redistribute the dataset), but add an **attribution note** in `README.md`.

---

## 11. Status / Completion Tracking
- **[2026-07-24]** — Task created. Four design decisions resolved with maintainer (unified `licenses` view · `--country us|ca|all` default us · CLI+Web scope · `amateur_delim.zip` only). ISED layout verified against live download (18 fields, `;`-delimited, UTF-8, header row, CRLF, ~91,926 rows, 0 dupes, 0 malformed). Plan grounded in `file:line` evidence across config/schemas/database/loader/updater/downloader/extractor/CLI/web.
- **[2026-07-24]** — Added §10 Reliability/Recovery/Gotchas on reflection. Confirmed against source: no HTTP timeouts anywhere; `download_file` return value ignored + metadata written pre-load (aborted-download recovery is broken); `cleanup_temp_files()` hardcoded to FCC paths; `optimize_database()` would drop `CA_AM`/`AM` and break the view; unified-view name search is a US-latency regression risk (mitigation: country-aware query strategy, view stays the read model for lookups/CA). These pre-existing weaknesses should be fixed once in the shared path.
- **[2026-07-24]** — Added order-agnostic name-search requirement (§6) at maintainer's request ("Brian Burk" must match "Burk, Brian"). Set target version to **v2.1.0**.
- **[2026-07-24]** — **IMPLEMENTED (all phases).** Branch `feature/canada-ised-support`.
  - **P1 Config/Schema:** `config.py` ISED consts + `HTTP_TIMEOUT` + `DEFAULT_COUNTRY`; `schemas.py` `CA_AM` (4 dicts, parity 18==18==18) + `view_schemas["licenses"]` + `view_required_tables`.
  - **P2 Pipeline:** new `modules/ised_loader.py` (UTF-8/`;`/header-skip, csv.reader, malformed-count logging, interrupt-safe reusing loader helpers); `downloader.py` hardened (atomic `.part`→`os.replace`, zip validation, size check, timeouts, honest return, `desc`); `updater.py` parameterized `check_for_update(url, metadata_file)`, `_remote_last_modified`, metadata-after-load, `update_ised_data()`, `update_country()` dispatcher, per-source outcome + exit; `filesystemtools.cleanup_temp_files(zip, extract)` generalized.
  - **P3 Data layer:** `database.py` `_name_match_clause` (order-agnostic), `create_views()`, `get_ca_records_by_call_sign`, `search_ca_records`, country-aware `search_records()` (fixed latent undefined-`logger`/`DatabaseError` bug), FCC name methods retrofitted to token match, `optimize_database()` retains AM/CA_AM + recreates views.
  - **P4 CLI:** `--country {us,ca,all}` (default us), `gather_query_records()`, update/force-download → `update_country` with non-zero exit on failure, version → **2.1.0**, docstring refreshed.
  - **P5 Web:** Country selector, State/Province relabel + `PROVINCES`/`STATES_AND_PROVINCES`, `search()` country param, results Country column (table + card) + CA class labels, profile CA fallback, `create_views()` at startup.
  - **P6 Docs:** README (Overview, Features, Options, Examples incl. Canada + order-agnostic, Config, Project Structure, DB docs, OGL-Canada attribution), CHANGELOG `[2.1.0]`, version bump.
  - **P7 Tests:** new `src/tests/test_ised.py` — **8 tests, all pass** (schema parity, parse header/malformed skip, UTF-8 accents, unified view both-countries, derived CA class, order-agnostic US search, country=all merge, CA callsign lookup).
  - **Real-data validation:** loaded live `amateur_delim.zip` → **91,926 CA rows in 0.18s (514k rec/s)**, 0 malformed; unified view = **1,678,614 US + 91,926 CA**. Verified via CLI + running Flask app: US unchanged (W1AW), CA callsign (VA2AA→Jacques Sauvé, class Advanced), accented names, province filter, country=all merge, and **order-agnostic search on real FCC data** ("STEPHEN WESSELS" → AA0AI stored "WESSELS, STEPHEN W"). Front-ends issue **0** raw SQL. Pre-existing stale tests (F4) still fail identically on base code — no new regressions.
  - **Note:** the maintainer's real `data/fcc_data.db` now additionally contains the `CA_AM` table + `licenses` view + Canadian data (from validation); harmless and rebuildable.
- **[2026-07-24]** — **Code review (`/code-review`) + all fixes applied.** Static analysis (pyflakes) clean — the only findings are pre-existing (unused imports / f-string on base HEAD). Fixes: (1) 🟡 `update_data`/`update_ised_data` now report success on an up-to-date no-op instead of exiting non-zero when temp files were cleaned; (2) 🟢 ISED parser uses `csv.QUOTE_NONE`; (3) 🟢 download size mismatch is a warning (zip-integrity check is authoritative); (4) 🟢 web `create_views()` moved out of the `db=None` init path. Re-verified: 8/8 tests pass, front-ends 0 raw SQL, default US behavior unchanged.
- **[2026-07-24]** — **Product rename → "Offline Callsign Lookup"** (short/code name `callsignLookup`), per maintainer. `git mv src/fcc_tool.py → src/callsign_lookup.py`, `fcc_tool_web.py → callsign_lookup_web.py`; class `FCCDatabase → CallsignLookupDatabase`; `APP_NAME`/CLI header/web branding ("Offline Callsign Lookup"); log `fcc_tool.log → callsign_lookup.log`; on-disk DB `fcc_data.db → callsign_data.db` (existing 900MB DB renamed in place to preserve it) and `Config.DB_PATH` updated; build/install scripts, README, CHANGELOG, CLAUDE.md updated. **Preserved as data-source terms** (not renamed): "FCC"/"ISED", FCC table names, `l_amat.zip`, `fcc_code_defs.py`, and the source-scoped `fcc_metadata.json` / `ised_metadata.json` (these name the data *sources*, parallel to the source zip filenames — not the app). Verified: 0 residual product-name refs in code/build/docs; compiles; 8/8 tests pass; CLI works against renamed DB (header reads "Offline Callsign Lookup v2.1.0"). ai_docs task docs (this file, 001) left as historical records.
- **[2026-07-24]** — Also embedded the maintainer's how-to video (`docs/how-to-use.mp4`) in README (TOC entry + `<video>` player pointing at the raw URL on `main`, with a relative-link fallback).
