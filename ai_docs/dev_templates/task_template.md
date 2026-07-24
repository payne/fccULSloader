# Task Template — FCC Tool (`fccULSloader`)

> **Purpose:** Project-specific template for creating comprehensive task documents for the FCC Tool — a **Python 3** application (CLI `src/fcc_tool.py` + Flask web `src/fcc_tool_web.py`) that builds and maintains a **complete offline SQLite mirror** of the FCC Amateur Radio ULS database (`l_amat.zip`) for offline callsign/name/state lookups.
>
> **Usage:** Copy this file to `ai_docs/tasks/NNN_short_name.md` (auto-numbered by `/task-creator`), then fill it out. Delete sections that don't apply — most query/CLI tasks won't touch the load pipeline, and vice-versa.
>
> **Golden rule:** Every claim, plan step, and finding must cite concrete `file:line` evidence from the actual source — never assumptions.

---

## 0. How This Codebase Is Built (read before planning)

Understanding the architecture is prerequisite to any task. The diagram and rules below are the mental model to plan against.

```
   ENTRY POINTS                fcc_tool.py (CLI)        fcc_tool_web.py (Flask)
                                     │                          │
   ORCHESTRATION           updater.py (pipeline hub)            │
                                     │                          │
   PIPELINE STAGES   downloader → extractor → loader           │
                                     │            │             │
   DATA LAYER  ───────────►  FCCDatabase (database.py) ◄────────┘
                                     │
   SHARED KERNEL   schemas.py (tables/indexes/counts/fields)  ·  config.py (Config)
                   fcc_code_defs.py (code→text)  ·  filesystemtools · logger · progress
```

### Architectural rules — DO NOT VIOLATE (verified in Task 001 audit)

1. **Run from `src/`.** All imports are bare `modules.*`. Every command runs from inside `src/` or Python can't resolve `modules`. Tests too: `cd src && python -m unittest discover -s tests`.

2. **SQL lives in exactly two modules: `database.py` and `loader.py`.** The CLI and web entry points issue **zero** raw SQL — they go through `FCCDatabase` methods. **A new query belongs as a method on `FCCDatabase`, never inline in a route or in `main()`.** (Audit confirmed: `fcc_tool.py`=0, `fcc_tool_web.py`=0 direct `.execute()`.)

3. **`schemas.py` is the single source of truth for data structure.** `table_schemas` (DDL), `index_schemas` (post-load indexes), `column_counts` (field count used to pad/validate rows), `field_names` (ordered names). These four **must stay mutually consistent** — for every table, `column_counts[t]` == columns in `table_schemas[t]` == `len(field_names[t])` (audit verified all 8 agree). Changing a table means editing all four in lockstep.

4. **`config.py` holds all paths/URLs/knobs** as static `Config` attributes. The key knob is `Config.TABLES_TO_PROCESS` — default `["AM","EN","HD"]` (lookup essentials) vs. the full 8-table set (`AM,CO,EN,HD,HS,LA,SC,SF`). Never hardcode a path that belongs in `Config`.

5. **The load pipeline is linear and index-aware.** `updater.update_data()` → `downloader` → `extractor` → `loader.load_all_data()`. Loader disables indexes before bulk insert, rebuilds after, uses an aggressively-tuned SQLite connection (`create_optimized_connection`), batches at `BATCH_SIZE=50000`. Priority tables (`HD`, `EN`) load first.

6. **The SQLite mirror is disposable/rebuildable.** No user data lives only in the DB — it's a cache of FCC's dataset. This licenses aggressive rebuilds, but see the integrity caveats in §7.

7. **Two front ends, one data layer, no shared presentation.** CLI verbose output and the web UI both format records via `fcc_code_defs` mappings but share no view code. Don't try to unify them; do unify the *queries* behind `FCCDatabase`.

8. **Keep docs current (project convention).** Substantial features → update `README.md` (Features / Command-Line Options / Configuration / Project Structure) **and** add a `CHANGELOG.md` entry + version bump in the same change. See `CLAUDE.md` → Conventions.

---

## 1. Task Overview

### Task Title
**Title:** [Brief, specific title]

### Goal Statement
**Goal:** [What you're achieving and why it matters to an offline FCC-lookup user.]

### Task Type (pick one — determines which sections matter)
- [ ] **Query / CLI feature** → focus §3, §5 (FCCDatabase methods), §6, §8
- [ ] **Web UI feature** → focus §3, §5 (routes/templates), §6, §8; mind the monolith (§4)
- [ ] **Load-pipeline / performance** → focus §3, §7 (data + integrity), §8
- [ ] **Schema / data-structure change** → focus §7 (schemas.py lockstep), §8
- [ ] **Refactor / tech-debt** → reference Task 001 findings
- [ ] **Docs / assessment only** → no code changes; state deliverable

---

## 2. Strategic Analysis & Solution Options

> Use when multiple viable approaches exist, trade-offs are significant, or the change touches the load pipeline / schema / web monolith. Skip for isolated, one-obvious-way changes.

### Problem Context
[Why this needs consideration — what makes the decision non-trivial in *this* architecture?]

### Options
For each: **Approach**, **Pros ✅**, **Cons ❌**, **Complexity** (Low/Med/High), **Risk**, and its **architectural fit** (does it respect the rules in §0 — SQL confined to the data layer, schema kept consistent, no new SQL in routes?).

### Recommendation & Rationale
**🎯 Recommended: Option [X].** [Why — respecting performance, offline goal, maintainability, and the §0 rules.]

### Decision Request (chat-facing — must be answerable in one pass)
Present the decision to the user in **plain, experience-first language** (what changes for the person doing lookups), recommended option first, marked "(Recommended)". Keep file paths / method names / schema detail in *this document*, not in the chat question. Prefer `AskUserQuestion`.

---

## 3. Current-State Analysis (fill from real source)

**Analysis checklist — check only what's relevant:**
- [ ] **Data layer (`modules/database.py`)** — Which `FCCDatabase` methods are relevant? (`search_records`, `search_records_by_name/state/name_and_state`, `get_record_by_call_sign`, `remove_inactive_records`, `create_tables`, `insert_batch_records`, `create_indexes`, `compact/optimize_database`.) Can you reuse/extend one instead of adding a parallel method? *(Note: the four search methods overlap heavily — Task 001 F1.)*
- [ ] **Schema (`modules/schemas.py`)** — Which tables/columns/indexes are involved? Will you need a lockstep change across all four dicts?
- [ ] **Config (`modules/config.py`)** — New path/URL/knob? Does `TABLES_TO_PROCESS` affect scope?
- [ ] **Load pipeline (`updater/downloader/extractor/loader`)** — Does this touch parsing, batching, indexes, or the update/rebuild flow?
- [ ] **CLI (`fcc_tool.py`)** — New flag? `argparse` in `main()`; remember `--non-interactive` and confirmation prompts for destructive ops.
- [ ] **Web (`fcc_tool_web.py`)** — Which route (`/`, `/search`, `/profile/<callsign>`)? Which inline template constant (`SEARCH_FORM`, `RESULTS_TEMPLATE`, `PROFILE_TEMPLATE`, `COMMON_CSS/JS`)? Session/recent-searches involved?
- [ ] **Code translation (`modules/fcc_code_defs.py`)** — New coded field to render human-readably?

### Current State
[What exists today, cited to files. What works / what's missing.]

---

## 4. Known Architectural Constraints & Debt (from Task 001 audit)

Account for these when planning; don't unknowingly re-introduce or collide with them:

- **F1 (High):** 4 search methods duplicate the same `EN JOIN HD LEFT JOIN AM … LIKE LOWER(?)` SQL (~590 LOC). If your task adds/changes search behavior, prefer consolidating toward one query builder over copying a 5th variant.
- **F2 (High):** `fcc_tool_web.py` is a 2,856-line monolith with inline HTML via `render_template_string` (no `templates/`). New web work should lean toward extracting Jinja templates / blueprints rather than growing the monolith.
- **F3 (Med, security):** hardcoded `secret_key`, `debug=True`, bound `0.0.0.0` — localhost-only assumption.
- **F4 (Med):** `tests/` and `src/tests/` are duplicated **and stale** (outdated signatures). Fix/replace, don't trust.
- **I1 (High, integrity):** interrupted `--update` can leave a torn/partial DB (`synchronous=OFF`, per-table drop+reload, no cross-table atomicity).
- **I2/I3 (Med):** over-length records silently dropped (`loader.py:312-320`); dates stored raw MM/DD/YYYY (unsortable) because `convert_date()` is never called.
- **P1 (Med):** `cache_size` is ~4 GB, not the "~1GB" the comment claims.

---

## 5. Code Changes — Where Things Go

### Queries / mutations → `modules/database.py`
- Add a method on `FCCDatabase`; use **parameterized** SQL (`?` placeholders) — never string-interpolate user input (the codebase already does this correctly; keep it that way).
- Reuse the existing `EN/HD/AM` join shape; consider extending `search_records()` rather than cloning it.

### Schema changes → `modules/schemas.py` (+ `config.py` if a new table)
- Edit **all four** dicts in lockstep (`table_schemas`, `index_schemas`, `column_counts`, `field_names`).
- Add indexes that match your actual query's filter/sort columns (see existing EN name/state composites as the pattern).
- If adding a table to the default set, update `Config.TABLES_TO_PROCESS`.

### CLI → `fcc_tool.py`
- Add the `argparse` flag in `main()`; wire to an `FCCDatabase` call; honor `--quiet`/`--non-interactive`; add a confirmation prompt for any destructive operation (pattern: `remove_inactive_records`).

### Web → `fcc_tool_web.py`
- Add/extend a route; reuse `FCCDatabase` (never inline SQL). Prefer extracting markup to a `templates/` file over enlarging the inline constants.

### Load pipeline → `modules/loader.py` / `updater.py`
- Preserve the index-disable→load→rebuild ordering and batching; if you touch integrity behavior, address I1/I2 rather than around them.

### 📂 Before / After
Show the key before/after snippets with file paths and a **Key Changes Summary** (what, why, files, impact). If none: "No code changes required."

---

## 6. Requirements & Success Criteria

### Functional Requirements
- [Requirement 1 …]

### Non-Functional
- **Offline-first:** must work with no network once the DB exists.
- **Performance:** don't regress load throughput (loader logs records/sec) or query latency; keep indexes aligned to queries.
- **Portability:** must still run from source *and* as a PyInstaller build (`create_build/`); no new heavy deps without cause (`src/requirements.txt`).
- **Cross-platform:** Windows/Linux/macOS.

### Success Criteria (specific, measurable)
- [ ] [Outcome 1]
- [ ] Docs updated (`README.md` + `CHANGELOG.md`) if user-visible.

---

## 7. Data, Schema & Integrity

### Schema change plan (if any)
- [ ] Update all four `schemas.py` dicts consistently (verify with a column-count parity check).
- [ ] Add/adjust `index_schemas` for new query patterns.
- [ ] Confirm `loader` padding/validation still holds (`get_column_count` reads `column_counts`).

### Load / integrity considerations (if touching the pipeline)
- [ ] Does an interrupt leave a consistent DB? (Mind I1 — per-table drop+reload isn't atomic across tables.)
- [ ] Are malformed/over-/under-length records handled and **counted/logged**, not silently dropped? (I2)
- [ ] Are date fields stored sortably? (I3 — apply `convert_date` if you touch date loading.)
- [ ] PRAGMA/cache settings appropriate for low-spec targets? (P1)

### Migration / rebuild note
There is **no migration framework** — the DB is regenerated from FCC source. A schema change generally means a **full rebuild** (`python fcc_tool.py --force-download`). State this explicitly and warn if existing DBs become incompatible.

---

## 8. Implementation Plan (phased, file-cited)

### Phase 1: [Name]
- [ ] **1.1** [Task] — Files: `path`; Details: […]

### Phase 2: [Name]
- [ ] **2.1** …

### Phase N: Testing & Validation
- [ ] Run relevant tests from `src/` (`python -m unittest …`) — **fix stale tests you rely on** (F4).
- [ ] For load changes: run a real `--force-download` (or `--skip-download` against existing `data/extracted/`) and confirm record counts + records/sec in `logs/fcc_tool.log`.
- [ ] For query changes: verify against known callsigns (e.g. `W1AW`) via both CLI and web.
- [ ] For web changes: load `http://localhost:5000`, exercise the affected route.

### 🛑 Checkpoint
After implementation, present an **"Implementation Complete!"** summary and **stop for code review** before declaring done.

---

## 9. Comprehensive Code Review (mandatory before "done")

- [ ] Re-read every changed file end-to-end.
- [ ] **Architecture compliance:** no SQL outside `database.py`/`loader.py`; `schemas.py` four dicts still consistent; nothing hardcoded that belongs in `Config`; ran/considered from `src/`.
- [ ] **Parameterization:** all user-influenced SQL uses `?` placeholders.
- [ ] **No new debt** colliding with Task 001 findings (didn't add a 5th duplicate search method, didn't grow the web monolith unnecessarily).
- [ ] Verified against requirements & success criteria (§6).
- [ ] Docs updated (§0 rule 8).
- [ ] Summarize: what changed, files touched, tests run + results (honestly — if a test failed or was skipped, say so).

---

## 10. Status / Completion Tracking

Update this log in real time. Mark checkboxes `[x]` with the **actual** current date (get today's date; don't assume) and a brief note (files, key changes).

- **[YYYY-MM-DD]** — [Created / decision made / phase completed / outcome]

**Example:**
```
### Phase 1: Add --grid-square lookup
- [x] 1.1 Added `search_records_by_grid()` on FCCDatabase ✓ 2026-07-24
      Files: modules/database.py; parameterized query, reuses EN/HD join
- [x] 1.2 Wired `--grid-square` argparse flag ✓ 2026-07-24
      Files: fcc_tool.py:main(); honors --quiet
```
