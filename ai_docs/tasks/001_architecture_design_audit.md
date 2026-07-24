# Task 001 — Architecture & Design Audit of the FCC ULS Loader (`fccULSloader`)

> Template: `ai_docs/dev_templates/task_template.md` (adapted from the BePrepared Next.js template to fit this Python CLI + Flask project — Next.js/Trigger.dev/Drizzle/Supabase sections are intentionally omitted as not applicable).
> Type: **Assessment / audit** — produces findings and recommendations. No production code changes are made as part of this task (any fixes are spun out into follow-up tasks).

---

## 1. Task Overview

### Task Title
**Title:** Assess and audit the architecture and design of the FCC Tool (`fccULSloader`)

### Goal Statement
**Goal:** Produce a rigorous, evidence-based assessment of the current architecture and design of the FCC Tool — a Python CLI (`fcc_tool.py`) plus Flask web app (`fcc_tool_web.py`) that downloads the FCC ULS amateur-radio dataset and maintains a local SQLite mirror for offline lookups. The audit will map the actual module structure, identify architectural strengths, risks, and design smells (coupling, layering, error handling, security, testability, maintainability), and deliver a prioritized set of recommendations so the maintainer can decide what to refactor or harden next. Success is a clear, actionable audit report — not speculative rewrites.

---

## 2. Strategic Analysis — Scope of the Audit

This is an **assessment task**, so the "solution options" are really *how deep and how broad* the audit should go. Three scopes:

#### Option A: Focused structural audit (Recommended)
**Approach:** Audit module boundaries, layering, and coupling across `src/modules/*` and the two entry points; review error handling, configuration, and the SQLite data layer; flag security-relevant spots (SQL construction, file/network handling, Flask session/secret handling). Deliver a written report with severity-ranked findings and a recommended remediation backlog.

**Pros:**
- ✅ Highest signal-to-effort ratio — targets the parts that most affect maintainability and correctness.
- ✅ Fully evidence-based (every finding cites `file:line`).
- ✅ Produces a directly actionable backlog of follow-up tasks.

**Cons:**
- ❌ Does not include deep runtime profiling or a full security pen-test.
- ❌ Does not rewrite anything (by design).

**Complexity:** Low–Medium · **Risk:** Low (read-only analysis)

#### Option B: Structural audit + performance & data-integrity deep dive
**Approach:** Everything in Option A, plus profiling the bulk-load path (`loader.py`, `database.py`), SQLite schema/index review, transaction/commit strategy, and memory behavior on large ULS files.

**Pros:**
- ✅ Surfaces throughput and large-file scaling issues, which matter for a full-DB loader.
- ✅ Validates data-integrity guarantees (partial loads, restarts, idempotency).

**Cons:**
- ❌ Needs representative data and time to run loads.
- ❌ Larger effort before the maintainer sees any output.

**Complexity:** Medium–High · **Risk:** Low

#### Option C: Full audit + threat model (CLI + Flask web surface)
**Approach:** Everything in Option B, plus a security threat model of the Flask app — session/secret management, route auth, input handling, file-download/extraction (zip/path traversal), and dependency CVE review.

**Pros:**
- ✅ Most complete; treats the web interface as an attack surface.
- ✅ Best if the web app will ever be network-exposed.

**Cons:**
- ❌ Largest scope; overkill if the web UI is only ever run on localhost.

**Complexity:** High · **Risk:** Low

### Recommendation & Rationale

**🎯 RECOMMENDED: Option A — Focused structural audit**, with the security-sensitive items from Option C folded in as a lightweight pass (SQL construction, Flask secret/session config, and zip extraction safety are cheap to check and high-value). Performance profiling (Option B) is best as a *follow-up* task once the structural picture is clear.

**Why:** It gives you a complete, actionable read on the codebase's health fastest, keeps every finding grounded in the actual source, and defers expensive profiling/pen-testing until you've decided they're worth it.

### Decision — RESOLVED (2026-07-24)

**✅ Scope selected: Option B — Structural audit + performance & data-integrity deep dive**, covering the **entire codebase**, with the cheap security checks from Option A folded in.

Per the maintainer: *"audit should look at the entire codebase including performance of fcc file loads and data structure."*

This means the audit explicitly includes, on top of the structural review:
- **FCC file-load performance** — the `updater → downloader → extractor → loader → database` pipeline: `parse_file()` (mmap parsing), bulk-insert batching/commit strategy, the index-disable/rebuild dance, the optional `ProcessPoolExecutor` path (`Config.USE_MULTITHREADING`), PRAGMA/connection tuning (`create_optimized_connection`), and behavior/scaling on large `.dat` files.
- **Data structure** — the SQLite schema and its source-of-truth dicts in `schemas.py` (`table_schemas`, `index_schemas`, `column_counts`, `field_names`): table design, index coverage vs. actual query patterns in `database.py`, record padding/validation, and integrity under interrupted loads (`--active-only`, SIGINT cleanup).

---

## 3. Project Analysis & Current State

### Technology & Architecture (from actual source inspection)
- **Language:** Python 3
- **Entry points:**
  - `src/fcc_tool.py` (439 LOC) — command-line interface
  - `src/fcc_tool_web.py` (2856 LOC) — Flask web interface *(largest file by far — a likely audit focus)*
- **Modules (`src/modules/`):**
  - `database.py` (928 LOC) — SQLite data layer *(second largest)*
  - `loader.py` (583 LOC) — bulk load of ULS records
  - `schemas.py` (273 LOC) — table/record schema definitions
  - `updater.py` (246 LOC) — incremental/daily update logic
  - `filesystemtools.py` (183 LOC), `progress.py` (179 LOC), `logger.py` (88 LOC), `downloader.py` (76 LOC), `fcc_code_defs.py` (75 LOC), `config.py` (63 LOC), `extractor.py` (50 LOC)
- **Key dependencies (`src/requirements.txt`):** `requests`, `tqdm`, `colorama`, `Flask`, `Flask-Session`, `Werkzeug`, `click`, `pyinstaller` (packaging via `create_build/`)
- **Data store:** local **SQLite** mirror of the FCC ULS amateur-radio database
- **Packaging:** `create_build/` builds standalone executables (PyInstaller) for macOS/Windows/Linux
- **Tests:** `tests/` and `src/tests/` — `test_database`, `test_loader`, `test_updater`, `test_extractor`, `test_downloader`, `test_logger` *(note: tests appear duplicated in two locations — itself an audit finding to confirm)*
- **Reference docs:** `README.md`, `FCC_DATABASE_DOC.md`, `CHANGELOG.md`

### Current State (to be confirmed during audit)
The tool is functional and shipped (MIT-licensed, by Tiran Dagan / Backstop Radio). Two observations already visible from structure alone, to be verified:
1. **`fcc_tool_web.py` at 2856 LOC** is a monolith relative to the rest of the codebase — a candidate for decomposition.
2. **Tests exist in two parallel locations** (`tests/` and `src/tests/`) — possible drift/duplication.

### Analysis Checklist (what this audit will actually examine)
- [ ] **Module boundaries & layering** — Is there a clean separation between CLI, web, business logic, and data access? Do modules depend downward only, or are there cycles?
- [ ] **Entry-point duplication** — How much logic is shared vs. duplicated between `fcc_tool.py` and `fcc_tool_web.py`?
- [ ] **Data layer (`database.py`, `loader.py`, `schemas.py`)** — SQL construction (parameterized vs. string-built), transaction/commit strategy, index design, idempotency of loads/updates.
- [ ] **Download & extract path (`downloader.py`, `extractor.py`, `updater.py`)** — Network error handling, retry/resume, zip extraction safety (path traversal), disk-space/temp-file handling.
- [ ] **Configuration (`config.py`)** — Where config lives, secrets handling, defaults, validation.
- [ ] **Flask web app (`fcc_tool_web.py`)** — Route organization, session/secret management (`Flask-Session`), input validation, error surfaces, template/output escaping, monolith decomposition opportunities.
- [ ] **Error handling & logging (`logger.py`)** — Consistency, user-facing vs. diagnostic separation, silent failures.
- [ ] **Testing** — Coverage of critical paths, the two-location duplication, test quality.
- [ ] **Packaging (`create_build/`)** — Build reproducibility and dependency pinning.

---

## 4. Context & Problem Definition

### Problem Statement
The codebase has grown organically (notably a ~2,900-line Flask module) and the maintainer wants an objective, structured read on its architecture and design health before investing in further features or refactors. Without an audit, refactoring risk is guesswork; with one, effort can be aimed at the highest-impact, highest-risk areas first.

### Success Criteria
- [ ] Every module in `src/modules/` and both entry points are reviewed and mapped.
- [ ] A dependency/coupling map (who imports/depends on whom) is produced.
- [ ] Findings are severity-ranked (Critical / High / Medium / Low) and each cites concrete `file:line` evidence.
- [ ] Security-sensitive spots (SQL construction, Flask secret/session config, zip extraction) are explicitly assessed.
- [ ] A prioritized remediation backlog is delivered, ready to become follow-up tasks (`002_…`, `003_…`).
- [ ] No production source files are modified by this task.

---

## 5. Development Mode Context
- Read-only audit — **no source changes** in this task.
- Findings that warrant action become separate numbered follow-up tasks.
- Deliverable is a report section appended to this document (§10) plus the backlog (§11).

---

## 6. Requirements

### Functional (of the audit itself)
- Map actual structure and dependencies from source (not assumptions).
- Identify architectural strengths, risks, smells, and design debt.
- Rank findings by severity and cite evidence.

### Non-Functional
- **Traceability:** Every finding references `file:line`.
- **Actionability:** Each finding has a concrete recommended remediation and rough effort.
- **Objectivity:** No stylistic nitpicks dressed up as architecture; focus on maintainability, correctness, and security impact.

### Constraints
- Python 3 / SQLite / Flask stack as-is; recommendations must respect the offline-first, single-user, packaged-executable design goals.
- Do not introduce a decision to rewrite; propose incremental, justified changes.

---

## 7. Data & Database Changes
**None.** This is an assessment. The SQLite schema is *reviewed* (in `schemas.py` / `database.py`) but not modified.

---

## 8. Code Changes Overview
**No code changes required.** This is a pure assessment/planning task. The deliverables are:
1. An architecture & design audit report (findings, severity, evidence) — appended to §10.
2. A prioritized remediation backlog — §11.

Any actual fixes are scoped as separate follow-up tasks after the maintainer reviews the findings.

---

## 9. Audit Methodology (Implementation Plan)

### Phase 1: Structural mapping ✅ COMPLETE (2026-07-24)
- [x] **1.1** Read both entry points and all `src/modules/*` files.
- [x] **1.2** Build a module dependency/import map; flag cycles and God-modules. → §10.2 (no cycles; clean SQL boundary; `updater` = orchestrator, not god-object).
- [x] **1.3** Quantify duplication between CLI and web entry points. → F1 (~590 LOC duplicated search SQL), F2 (web monolith).

### Phase 2: Data & I/O layer review ✅ COMPLETE (2026-07-24)
- [x] **2.1** Audit `database.py` — parameterized SQL (safe), index design (query-aware), connection handling. → §10.2, §10.5.
- [x] **2.2** Audit `loader.py` / `updater.py` — batching/commit, index disable/rebuild, PRAGMA tuning, integrity under interruption. → I1–I4, P1–P3, §10.5.
- [ ] **2.3** Audit `downloader.py` / `extractor.py` — network error handling, zip extraction safety, temp/disk handling. *(carry into Phase 3 pass)*

### Phase 3: Web layer & cross-cutting concerns ✅ COMPLETE (2026-07-24)
- [x] **3.1** Audit `fcc_tool_web.py` — routes (`/`,`/search`,`/profile`,`/debug/session`), session/secret config, input validation, `|safe`/escaping, date-format bug. → W1–W4, F3.
- [x] **3.2** Audit `extractor.py` (Zip-Slip), connection handling (per-call `create_connection`, thread-safe). → E1; connection handling deemed acceptable.
- [x] **3.3** Reviewed tests (both locations, stale) and packaging. → F4.

### Phase 4: Synthesis ✅ COMPLETE (2026-07-24)
- [x] **4.1** Consolidated findings, severity-ranked, `file:line`-cited. → §10.3.
- [x] **4.2** Audit written into §10 + standalone report `fccLoader_architecture_audit.md`.
- [x] **4.3** Remediation backlog produced. → §11.
- [x] **4.4** Chat summary + recommended next tasks delivered.

---

## 10. Audit Findings
*(To be filled in during Phase 4. Structure below.)*

### 10.1 Executive Summary
The FCC Tool is a **well-layered small application with a genuinely clean data-access boundary** and an internally-consistent, index-aware schema — the core architecture is sound. Its debt is concentrated in three places: (1) **duplication** — four near-identical search methods (~590 LOC) in `database.py`; (2) a **2,856-line Flask monolith** that mixes routing, logic, and inline HTML; and (3) a load pipeline that **trades crash-safety for speed** (`synchronous=OFF`, per-table drop+reload with no cross-table atomicity), plus data-handling gaps (over-length rows silently dropped, dates stored unsortably, a ~4 GB cache mislabeled "1 GB"). A latent cross-cutting bug (web date formatting vs. stored date format) and a handful of web-security leftovers (unguarded `/debug/session`, 16 `|safe` sites, unsafe `extractall`) round out the list. **Nothing is architecturally broken**; the highest-value work is de-duplicating the query layer, hardening load integrity, and decomposing the web module. Full detail: standalone report `fccLoader_architecture_audit.md`.

**Finding counts:** High = 4 (F1, F2, I1, W1) · Medium = 8 (F3, F4, I2, I3, P1, P2, W2, W3, E1) · Low = 4 (P3, I4, W4, E2).

### 10.2 Architecture Map — Phase 1 (Structural Mapping) ✅

**Dependency graph (internal imports; arrows = "depends on"):**

```
                       ┌─────────────────┐         ┌──────────────────┐
   ENTRY POINTS        │  fcc_tool.py    │         │ fcc_tool_web.py  │
                       │  (CLI, 439)     │         │ (Flask, 2856)    │
                       └───────┬─────────┘         └────────┬─────────┘
                               │                            │
        ┌──────────┬───────────┼─────────────┐             │
        ▼          ▼           ▼             ▼             ▼
    updater ── config    fcc_code_defs    logger      ┌─────────────┐
      │  │  \                                          │             │
      │  │   └── downloader ── progress                ▼             ▼
      │  │        extractor                        FCCDatabase   config.Config
      │  │        loader ────────────────┐        (database.py, 928)
      │  └────────────────┐              │              │
      ▼                   ▼              ▼              ▼
  FCCDatabase ◄────────── schemas.py ◄───┘        schemas.py + fcc_code_defs
      │                (data structure SoT)             │
      ▼                                                 ▼
  filesystemtools ── config                     filesystemtools
```

**Layering assessment:**
- **Clean data-access boundary (strength):** Raw `sqlite3` lives in exactly two modules — `database.py` (57 execute/cursor sites) and `loader.py` (20, load-path only). Neither entry point issues SQL directly (`fcc_tool.py`: 0, `fcc_tool_web.py`: 0). Both front ends go through `FCCDatabase`. Layering is genuinely respected.
- **`schemas.py` is a proper shared kernel:** `table_schemas` / `index_schemas` / `column_counts` / `field_names` are consumed by both `database.py` and `loader.py` — single source of truth for the data structure, no duplicated DDL. Index coverage is deliberate (EN has `entity_name`, `first_name`, `last_name`, `state`, and composite `name_search` / `state_unique_sys_id`; HD has composite `call_sign,license_status`).
- **`updater.py` is the pipeline hub:** the only module importing `downloader + extractor + loader + config + logger + FCCDatabase` together — a coherent orchestrator, not a god-object.
- **No dependency cycles** among modules. Leaf utilities (`progress`, `fcc_code_defs`, `schemas`, `extractor`) have no internal deps.

**Front-end duplication (CLI vs Web):** The two entry points share **no presentation code** and diverge even at the query layer:
- CLI calls three separate query methods: `search_records_by_name`, `search_records_by_state`, `search_records_by_name_and_state`.
- Web calls one unified `search_records(...)` (paginated/filtered).
- These four methods in `database.py` re-implement the **same** `FROM EN JOIN HD LEFT JOIN AM … ORDER BY HD.call_sign` join and the same 4-way `LOWER(...) LIKE LOWER(?)` name-match block (evidence: `database.py:245,397,421,489,508,570,605`). ≈590 lines of largely parallel SQL — the single biggest structural-debt item found so far.

### 10.3 Findings (severity-ranked) — accumulating; finalized in Phase 4

| # | Severity | Area | Finding | Evidence (`file:line`) | Recommendation |
|---|----------|------|---------|------------------------|----------------|
| F1 | High | Maintainability | Four search methods duplicate the same EN/HD/AM join + `LIKE LOWER` name-match logic (~590 LOC). A schema/query change must be made in 4 places. | `database.py:377,472,550,874` (defs); shared SQL at `:245,397,421,508,570,605` | Extract a single parametrized query builder; have CLI helpers call the unified `search_records()`. |
| F2 | High | Web architecture | `fcc_tool_web.py` is a 2,856-LOC monolith; ~7 giant HTML/CSS/JS string constants (`ERROR_TEMPLATE`, `BOOTSTRAP_CDN`, `COMMON_JS`, `COMMON_CSS`, `SEARCH_FORM`, `RESULTS_TEMPLATE`, `PROFILE_TEMPLATE`) via `render_template_string` — no `templates/` dir. Mixes routing, presentation, and markup. | `fcc_tool_web.py:75,123,134,489,690,1406,1990` | Move markup to Jinja `templates/` files; split routes into blueprints. |
| F3 | Medium | Security | Hardcoded `app.secret_key = 'dev-secret-key-backstop-radio'` and `app.run(debug=True, host='0.0.0.0')`. Predictable session signing + debugger + bound to all interfaces. Acceptable on localhost, dangerous if exposed. | `fcc_tool_web.py:18,2857` | Load secret from env/`os.urandom`; gate `debug`/host behind config; document localhost-only intent. |
| F4 | Medium | Testing | `tests/` and `src/tests/` are duplicates and **stale** — call outdated signatures (`create_tables()` with no arg; removed `insert_record()`). Give false confidence / won't run. | `src/tests/test_database.py:18,38` vs `database.py:92,105` | Delete one copy; fix signatures; add load-path + query regression tests. |
| **I1** | **High** | **Data integrity** | Update path drops+reloads each table in a **separate** transaction under `PRAGMA synchronous=OFF` + `journal_mode=MEMORY`. A crash/interrupt mid-`--update` can leave a **torn DB** (new HD, old EN) or a corrupt file — not just an incomplete load — with no automatic recovery. | `loader.py:228-229,284-289,293,337` | Load updates into temp tables and atomically swap (or wrap all tables in one txn); document that an interrupted `--update` needs `--force-download`. |
| **I2** | Medium | Data loss | Records with **more** fields than expected are silently dropped — the `len==expected`/`len<expected` branches have no `else`, so over-length rows are skipped with no log and no counter. | `loader.py:312-320` | Truncate-or-log over-length rows; count & report skipped records. |
| **I3** | Medium | Data structure | Dates are stored raw as FCC `MM/DD/YYYY` strings. `convert_date()` exists to normalize to sortable `YYYY-MM-DD` but is **never called**, so `ORDER BY`/range filters on grant/expiration dates are lexicographically wrong. | `loader.py:32` (defined, 0 call sites); load loop `:308-329` | Apply `convert_date` to date fields during load (per-table date-field map) or store ISO-8601. |
| **P1** | Medium | Performance | `PRAGMA cache_size = 1000000` is **pages**, ≈ **4 GB** (comment wrongly says "~1GB"). On the tool's stated field/emergency low-spec targets this risks heavy paging or OOM during load. | `loader.py:230` | Use KB-based negative value (e.g. `-262144` ≈ 256 MB) or a realistic page count; fix the comment. |
| **P2** | Medium | Dead code | Multithreading is vestigial: `ProcessPoolExecutor` imported, `Config.USE_MULTITHREADING` + `use_multithreading` param plumbed end-to-end, but never branched on — loads are always sequential. Sets false expectations. | `loader.py:22,388,396`; `updater.py:234`; `config.py:59` | Remove the dead import/param/config, or actually implement (parallelize *parsing*, not the single-writer SQLite insert). |
| P3 | Low | Correctness (docs) | `parse_file` docstring claims "reads large blocks (10MB chunks)"; it actually reads line-by-line via `mmap.find(b'\n')`. Misleading. | `loader.py:96-99` vs `:124-136` | Fix docstring. |
| I4 | Low | Data integrity (edge) | If mmap iteration throws mid-stream after yielding N records, the fallback re-reads from `seek(0)` and re-yields all rows → duplicate inserts. | `loader.py:170-205` | Don't fall back after partial consumption; track position or fail hard. |
| **W1** | **High** | **Web bug (cross-cutting)** | `profile()` formats dates with `strptime(…, '%Y-%m-%d')` expecting ISO, but the loader stores raw `MM/DD/YYYY` (I3). The parse always raises `ValueError`, is silently swallowed, and dates render unformatted. Dead display logic caused by the I3 storage mismatch. | `fcc_tool_web.py:2824-2830` ↔ `loader.py:32` | Fix I3 (store ISO) or parse the actual stored format; don't swallow the error blindly. |
| W2 | Medium | Security | `/debug/session` route is unguarded and returns `dict(session)` as JSON — session/info disclosure, a debug leftover shipped in the app. | `fcc_tool_web.py:2848-2854` | Remove, or gate behind a debug/config flag. |
| W3 | Medium | Security (XSS surface) | 16 `|safe` filters disable Jinja autoescaping in the inline templates. Any that render user-influenced search terms/records are reflected/stored XSS vectors. | `fcc_tool_web.py` (16 `|safe` sites) | Audit each `|safe`; remove on any user/DB-derived value. |
| W4 | Low | Input validation | `page`/`per_page` via unvalidated `int(request.args.get(...))` — non-numeric raises (caught generically → error page); negative/huge values feed OFFSET/LIMIT unchecked. | `fcc_tool_web.py:2751-2752` | Validate/clamp to sane bounds; default on parse failure. |
| E1 | Medium | Security | `zip_ref.extractall()` has no Zip-Slip / path-traversal guard. Low real-world risk (source is the trusted FCC HTTPS URL), but the canonical unsafe pattern. | `extractor.py:45` | Validate member paths stay within `extract_to_path` before extracting. |

### 10.4 Strengths (confirmed in Phase 1)
- Disciplined data-access layering — SQL confined to `database.py` + `loader.py`; entry points never touch `sqlite3`.
- `schemas.py` as a clean single-source-of-truth kernel for table + index definitions.
- Clear linear pipeline (`updater` → `downloader`/`extractor`/`loader` → `FCCDatabase`) with no cyclic dependencies.
- Deliberate, query-aware index design (composite indexes match the join/filter patterns).
- Interrupt safety scaffolding in the load path (SIGINT handlers, connection tracking).

### 10.5 Phase 2 — Data & I/O Layer (load performance + data integrity) ✅

**Load pipeline (per table):** `parse_file()` (mmap, line-by-line, ISO-8859-1, `|`-split) → in-Python batch list (`BATCH_SIZE=50000`) → `cursor.executemany(INSERT … VALUES)` → per-table `BEGIN/COMMIT` → `rebuild_all_indexes()`. New DB: pre-create tables, indexes rebuilt post-load, then `ANALYZE`+`VACUUM`+`PRAGMA optimize`. Updates: `DROP TABLE`+recreate+reload per table.

**What's done well (strengths):**
- Index-disable-before-load / rebuild-after is the correct high-throughput SQLite pattern; priority ordering (`HD`, `EN` first) matches lookup importance.
- Prepared statement reused; 50k batched `executemany`; final `ANALYZE`/`VACUUM` on new DB.
- **Data structure is internally consistent** — `column_counts` == `CREATE TABLE` column count == `field_names` length for **all 8 tables** (verified). Padding/validation is anchored to a coherent schema.
- SIGINT/SIGTERM handlers + `active_connections` registry give graceful rollback *within a table*.

**Risk profile:** The load path optimizes aggressively for speed (`synchronous=OFF`, `journal_mode=MEMORY`, `locking_mode=EXCLUSIVE`, ~4 GB cache) and trades away crash-safety and cross-table atomicity. Justifiable for a *fully rebuildable* mirror, but currently an interrupted `--update` can silently leave a torn/partial DB with no guardrail — see **I1**. Findings **I1–I4, P1–P3** recorded in §10.3.

---

**Phases 1–2 COMPLETE.** Remaining: Phase 3 (web layer deep dive — routes, session/secret handling, input validation, `render_template_string` decomposition) and Phase 4 (synthesis + remediation backlog §11).

---

## 11. Remediation Backlog (proposed follow-up tasks)

Prioritized; each is sized to become its own numbered task. Full rationale in `fccLoader_architecture_audit.md`.

**P0 — correctness/integrity (do first)**
- [ ] **`002` Harden load integrity (I1, I2, I4).** Temp-table-and-swap for updates so an interrupted `--update` can't leave a torn DB; count+log malformed/over-length rows instead of silent drop; fix the mmap-fallback duplicate-yield.
- [ ] **`003` Fix date storage + display (I3, W1).** Normalize dates to ISO `YYYY-MM-DD` at load (apply `convert_date` via a per-table date-field map), then verify `profile()` formatting works; add a migration note (full rebuild required).

**P1 — maintainability & security**
- [ ] **`004` Consolidate the four search methods (F1).** One parametrized query builder; CLI helpers delegate to unified `search_records()`. ~590 LOC → one place.
- [ ] **`005` Web security hardening (F3, W2, W3, E1).** Env-based secret + config-gated `debug`/host; remove/guard `/debug/session`; audit all 16 `|safe`; add Zip-Slip guard to `extractor`.
- [ ] **`006` Fix cache sizing + remove dead code (P1, P2, P3).** Right-size `cache_size` (KB-negative) + fix comment; remove vestigial multithreading (`ProcessPoolExecutor`/`USE_MULTITHREADING`) or implement parsing parallelism; fix `parse_file` docstring.

**P2 — structure & tests**
- [ ] **`007` De-dupe & repair tests (F4).** Single test location; fix stale signatures; add load-path + query regression coverage.
- [ ] **`008` Decompose the web monolith (F2).** Extract inline templates to `templates/`; split routes into blueprints. Larger effort; do after tests exist.

---

## 12. Status Log
- **2026-07-24** — Task created. `ai_docs/` structure established (`tasks/`, `dev_templates/`).
- **2026-07-24** — Scope **resolved to Option B** (entire codebase + FCC file-load performance + data structure, plus cheap security checks). Ready to begin Phase 1. Two findings already noted from initial scan, to confirm: (a) `fcc_tool_web.py` monolith (~2,856 LOC, inline `render_template_string`, hardcoded `app.secret_key`, `debug=True`); (b) duplicated **and stale** tests in `tests/` and `src/tests/` (call outdated signatures such as `create_tables()` with no arg and a removed `insert_record()`).
