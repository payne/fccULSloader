# FCC Tool (`fccULSloader`) — Architecture & Design Audit

**Author:** Architecture audit (Task 001) · **Date:** 2026-07-24
**Scope:** Entire codebase — structure, FCC file-load performance, data structure, web layer, and security-sensitive spots.
**Method:** Read-only source review. Every finding cites `file:line`. No production code was changed.
**Working record:** `ai_docs/tasks/001_architecture_design_audit.md`.

---

## 1. Executive Summary

The FCC Tool is a **well-layered small application with a genuinely clean data-access boundary** and an internally-consistent, index-aware schema. The core architecture is sound — there is nothing architecturally broken.

The debt is concentrated in three areas:

1. **Duplication** — four near-identical search methods (~590 LOC) in `database.py`.
2. **A 2,856-line Flask monolith** (`fcc_tool_web.py`) mixing routing, logic, and inline HTML.
3. **A load pipeline that trades crash-safety for speed** — `synchronous=OFF` + per-table drop-and-reload with no cross-table atomicity — plus data-handling gaps (over-length rows silently dropped, dates stored unsortably, a ~4 GB cache mislabeled "1 GB").

A latent cross-cutting bug (web date formatting vs. stored date format) and a few web-security leftovers (unguarded `/debug/session`, 16 `|safe` sites, unsafe `extractall`) complete the picture.

**Verdict:** Healthy foundation, focused debt. Highest-value work: de-duplicate the query layer, harden load integrity, decompose the web module.

**Findings:** 4 High · 8 Medium · 4 Low.

| Severity | IDs |
|----------|-----|
| **High** | F1 (query duplication), F2 (web monolith), I1 (torn-DB on interrupt), W1 (date-format bug) |
| **Medium** | F3 (web secrets/debug), F4 (stale tests), I2 (silent row drop), I3 (unsortable dates), P1 (~4 GB cache), P2 (dead multithreading), W2 (`/debug/session`), W3 (`|safe` XSS surface), E1 (Zip-Slip) |
| **Low** | P3 (misleading docstring), I4 (mmap-fallback dup), W4 (page input validation), E2 (extractor error handling) |

---

## 2. Architecture Overview

### 2.1 Component map

```
   ENTRY POINTS         fcc_tool.py (CLI, 439)      fcc_tool_web.py (Flask, 2856)
                              │                              │
   ORCHESTRATION      updater.py (pipeline hub, 246)         │
                              │                              │
   PIPELINE           downloader(76) → extractor(50) → loader(583)
                              │                    │         │
   DATA LAYER  ────────►  FCCDatabase (database.py, 928)  ◄──┘
                              │
   SHARED KERNEL   schemas.py(273)  config.py(63)  fcc_code_defs.py(75)
                   filesystemtools(183)  logger(88)  progress(179)
```

### 2.2 Dependency facts (verified)
- **No cyclic dependencies.** Leaf utilities (`progress`, `fcc_code_defs`, `schemas`, `extractor`) have no internal imports.
- **`updater.py` is the sole orchestrator** importing `downloader + extractor + loader + config + logger + FCCDatabase` together — a coherent hub, not a god-object.
- **Both front ends depend only on `FCCDatabase`** (+ `Config`, `fcc_code_defs`), never on each other or on the pipeline internals.

### 2.3 Data flow (load path)
```
FCC ULS l_amat.zip  ──download──►  data/l_amat.zip
     ──extract──►  data/extracted/{HD,EN,AM,…}.dat  (pipe-delimited) + counts
     ──loader.load_all_data──►  per table:  disable indexes → parse (mmap) →
                                batch 50k → executemany INSERT → commit → rebuild indexes
     ──►  data/fcc_data.db  (SQLite mirror)   +   data/fcc_metadata.json (last-modified)
```

---

## 3. Strengths (what's done well)

- **Disciplined data-access layering.** Raw `sqlite3` appears only in `database.py` (57 execute/cursor sites) and `loader.py` (20, load-path only). The CLI and web entry points issue **zero** direct SQL — verified. This is the single best structural property of the codebase.
- **`schemas.py` is a clean single source of truth.** For all **8** tables, `column_counts[t]` == `CREATE TABLE` column count == `len(field_names[t])` (verified programmatically). Padding/validation is anchored to a coherent schema; no scattered DDL.
- **Query-aware index design.** EN carries `entity_name`, `first_name`, `last_name`, `state`, and composites `name_search` / `state_unique_sys_id`; HD carries composite `call_sign,license_status`. Indexes match the actual join/filter patterns.
- **Correct high-throughput load pattern.** Indexes disabled before bulk insert and rebuilt after; priority tables (`HD`, `EN`) first; prepared statement reused; `executemany` batched at 50k; `ANALYZE`/`VACUUM`/`PRAGMA optimize` finalize a new DB.
- **Parameterized SQL throughout** — user-supplied values use `?` placeholders (e.g. `database.py:400-403`); no SQL-injection exposure found in the query layer.
- **Interrupt scaffolding.** SIGINT/SIGTERM handlers + an `active_connections` registry roll back and clean up on Ctrl-C within a table (`loader.py:41-92`).
- **Thread-safe web data access.** `FCCDatabase` methods open a fresh connection per call (`create_connection`, `database.py:84`); the module-level `db` object holds only a path, so Flask's threaded dev server is not sharing a connection across threads.

---

## 4. Findings (detailed)

Severity key: **High** = correctness/integrity/security impact or major maintainability drag · **Medium** = real issue, bounded impact · **Low** = polish / latent edge case.

### F1 — [High] Four search methods duplicate ~590 LOC of query logic
`database.py`: `search_records_by_name` (:377), `search_records_by_state` (:472), `search_records_by_name_and_state` (:550), and the unified `search_records` (:874) all re-implement the same `FROM EN JOIN HD LEFT JOIN AM … ORDER BY HD.call_sign` join and the same 4-way `LOWER(...) LIKE LOWER(?)` name match (shared SQL at `:245,397,421,508,570,605`). The CLI calls the three `_by_*` variants; the web calls only `search_records`. Any schema or ranking change must be made in four places.
**Recommendation:** Extract one parametrized query builder; have the CLI helpers delegate to the unified `search_records()`.

### F2 — [High] `fcc_tool_web.py` is a 2,856-line monolith
Routing, business logic, and presentation are all in one file, with ~7 large HTML/CSS/JS string constants rendered via `render_template_string` and **no `templates/` directory**: `ERROR_TEMPLATE` (:75), `BOOTSTRAP_CDN` (:123), `COMMON_JS` (:134), `COMMON_CSS` (:489), `SEARCH_FORM` (:690), `RESULTS_TEMPLATE` (:1406), `PROFILE_TEMPLATE` (:1990).
**Recommendation:** Move markup into Jinja `templates/*.html`; split routes into Flask blueprints. Do this after tests exist (F4).

### I1 — [High] Interrupted `--update` can leave a torn or corrupt database
`create_optimized_connection` sets `PRAGMA synchronous = OFF` and `journal_mode = MEMORY` (`loader.py:228-229`). For updates, each table is `DROP TABLE`-then-recreate-then-reload in its **own** transaction (`loader.py:284-289,293,337`). There is no cross-table atomicity: an interrupt/crash after HD reloads but before EN leaves a **new HD + old EN** mix, and with `synchronous=OFF` a hard crash can corrupt the file — not merely lose the update. There is no guard or recovery.
**Impact:** silent inconsistency after a failed update; user has no signal to `--force-download`.
**Recommendation:** Load updates into temp tables and atomically swap (or wrap all tables in one transaction). At minimum, detect a partial load and refuse to serve / prompt for full rebuild.

### W1 — [High] Web date formatting is dead code due to a storage-format mismatch
`profile()` runs `datetime.strptime(rec[date_field], '%Y-%m-%d')` to reformat grant/expired/last-action dates (`fcc_tool_web.py:2824-2830`), expecting ISO. But the loader stores dates **raw as FCC `MM/DD/YYYY`** — `convert_date()` (`loader.py:32`) is never called (see I3). So the `strptime` **always raises `ValueError`**, which is silently `pass`ed, and dates render unformatted/inconsistent.
**Recommendation:** Fix I3 (store ISO) so this code works, or parse the actual stored format; either way, stop swallowing the error unconditionally.

### F3 — [Medium] Web app ships insecure defaults
Hardcoded `app.secret_key = 'dev-secret-key-backstop-radio'` (`fcc_tool_web.py:18`) and `app.run(debug=True, host='0.0.0.0', port=5000)` (`:2857`): predictable session signing, the Werkzeug debugger exposed, bound to all interfaces. Acceptable for localhost single-user use (the stated design), dangerous if ever exposed.
**Recommendation:** Load the secret from env / `os.urandom(24)`; gate `debug` and host behind config; document localhost-only intent.

### F4 — [Medium] Tests are duplicated and stale
`tests/` and `src/tests/` contain the same filenames. Several call outdated signatures — e.g. `self.db.create_tables()` with no argument (`src/tests/test_database.py:18`) though the real signature is `create_tables(self, tables_to_process)` (`database.py:92`), and `insert_record()` (`test_database.py:38`) which no longer exists (it's `insert_batch_records`, `database.py:105`). They give false confidence and won't run clean.
**Recommendation:** Keep one location; fix signatures; add load-path and query regression tests.

### I2 — [Medium] Over-length records are silently dropped
In `load_data`, the row-collection branches are `if len(record) == expected` … `elif len(record) < expected: pad` — with **no `else`** (`loader.py:312-320`). A record with *more* fields than expected matches neither branch and is skipped with no log and no counter.
**Recommendation:** Truncate-or-log over-length rows; maintain and report a skipped-row count.

### I3 — [Medium] Dates stored unsortably (raw `MM/DD/YYYY`)
`convert_date()` exists to normalize to sortable `YYYY-MM-DD` (`loader.py:32`) but has **zero call sites** — the load loop inserts records verbatim (`loader.py:308-329`). Consequently any `ORDER BY` or range filter on date columns is lexicographically wrong (e.g. `12/31/1999` sorts before `01/01/2020`). Also the direct cause of W1.
**Recommendation:** Apply `convert_date` to date fields during load via a per-table date-field map, or store ISO-8601.

### P1 — [Medium] SQLite cache is ~4 GB, not the "~1 GB" claimed
`PRAGMA cache_size = 1000000` (`loader.py:230`) is a **page** count; at the default 4 KB page size that is ≈ **4.1 GB**, not the "~1GB" the inline comment states. On the tool's stated field/emergency low-spec targets this can cause heavy paging or OOM during load.
**Recommendation:** Use a KB-based negative value (e.g. `-262144` ≈ 256 MB) or a realistic page count; fix the comment.

### P2 — [Medium] Vestigial multithreading (dead code + misleading knob)
`ProcessPoolExecutor` is imported (`loader.py:22`) and `Config.USE_MULTITHREADING` (`config.py:59`) threads through `load_all_data(..., use_multithreading, ...)` (`loader.py:388`) from `updater.py:234` — but it is **never branched on**; loads are always sequential.
**Recommendation:** Remove the dead import/param/config, or actually implement it — parallelize *parsing* (SQLite bulk insert is single-writer, so parallel writes won't help).

### W2 — [Medium] Unguarded `/debug/session` endpoint
`/debug/session` returns `dict(session)` as JSON with no auth (`fcc_tool_web.py:2848-2854`) — session/info disclosure, a debug leftover in shipped code.
**Recommendation:** Remove, or gate behind a debug/config flag.

### W3 — [Medium] 16 `|safe` filters disable autoescaping
The inline templates use `|safe` 16 times. `render_template_string` autoescapes by default, so `|safe` re-opens an XSS hole wherever it wraps user-influenced search terms or DB-derived values.
**Recommendation:** Audit each `|safe`; remove it on anything user- or DB-derived. Reflected search terms are the primary risk.

### E1 — [Medium] `extractall()` has no Zip-Slip guard
`zip_ref.extractall(extract_to_path)` (`extractor.py:45`) trusts archive member paths; a crafted zip with `../` entries could write outside the target dir. Real-world risk is low (the archive comes from the trusted FCC HTTPS URL), but it is the canonical unsafe pattern.
**Recommendation:** Validate each member resolves within `extract_to_path` before extraction.

### Low-severity
- **P3** — `parse_file` docstring claims "reads large blocks (10MB chunks)" (`loader.py:96-99`); it actually reads line-by-line via `mmap.find(b'\n')` (`:124-136`). Fix the docstring.
- **I4** — If mmap iteration throws mid-stream after yielding N rows, the fallback re-reads from `seek(0)` and re-yields everything (`loader.py:170-205`) → duplicate inserts. Don't fall back after partial consumption.
- **W4** — `page`/`per_page` come from unvalidated `int(request.args.get(...))` (`fcc_tool_web.py:2751-2752`); non-numeric raises (caught → error page), negative/huge values feed OFFSET/LIMIT unchecked. Validate and clamp.
- **E2** — `extractor` handles `BadZipFile` but on `rmtree` failure only warns and continues (`extractor.py:29-32`), risking mixed old/new extracted files. Fail hard or verify a clean dir.

---

## 5. Performance & data-structure assessment (focus area)

**Load pipeline throughput** is built on the right primitives: indexes are dropped before bulk load and rebuilt after (`loader.py:237-254`), the connection is PRAGMA-tuned for speed, inserts are batched at 50k via a reused prepared statement, and the loader logs `records/sec` (`loader.py:342`) so regressions are observable. Priority ordering (`HD`, `EN` first) front-loads the tables lookups depend on.

**The cost of that speed** is durability: `synchronous=OFF` + `journal_mode=MEMORY` + per-table drop/reload means the pipeline is fast but not crash-safe or cross-table-atomic (I1). For a *fully rebuildable* mirror this is a defensible trade — but only if a partial load is detected and a rebuild is forced, which today it is not.

**Data structure** is a relative strength: the four `schemas.py` dicts are mutually consistent across all 8 tables, indexes align with queries, and record padding is schema-anchored. The two structural defects are behavioral, not shape: over-length rows vanish silently (I2), and dates are stored in a non-sortable string format (I3) that also breaks downstream display (W1). Both are cheap to fix and high-value.

**Memory:** the ~4 GB cache (P1) is the main scaling risk on modest hardware; batch buffers (≤50k Python rows) and the `active_records` set (`--active-only`) are bounded and fine.

---

## 6. Prioritized Remediation Backlog

Each item is scoped to become its own numbered task under `ai_docs/tasks/`.

### P0 — correctness & integrity (do first)
- **`002` Harden load integrity (I1, I2, I4).** Temp-table-and-swap (or single transaction) for updates; count+log malformed/over-length rows; fix mmap-fallback duplication.
- **`003` Fix date storage + display (I3, W1).** Normalize to ISO at load via a per-table date-field map; verify `profile()` formatting; document that this needs a full rebuild.

### P1 — maintainability & security
- **`004` Consolidate the four search methods (F1).** One query builder; CLI delegates to `search_records()`.
- **`005` Web security hardening (F3, W2, W3, E1).** Env secret + config-gated debug/host; remove/guard `/debug/session`; audit `|safe`; Zip-Slip guard.
- **`006` Cache sizing + dead-code removal (P1, P2, P3).** Right-size cache + fix comment; remove or implement multithreading; fix docstring.

### P2 — structure & tests
- **`007` De-dupe & repair tests (F4).** Single location; fix signatures; add load + query regression coverage.
- **`008` Decompose the web monolith (F2).** Extract templates to `templates/`; split routes into blueprints. Largest effort — after tests exist.

### Suggested sequence
`002 → 003` (correctness) → `007` (a safety net) → `004 → 005 → 006` (debt/security) → `008` (the big structural refactor, now covered by tests).

---

## 7. Method & Coverage Notes

- **Covered:** all of `src/modules/*` and both entry points; import/dependency graph; CLI vs. web query paths; the full load pipeline (`updater`/`downloader`/`extractor`/`loader`); schema consistency (programmatically verified across 8 tables); web routes, session/secret handling, input validation, escaping surface; zip extraction; test layout; packaging.
- **Not performed (out of scope / deferred):** live profiling against a full multi-GB FCC dataset (findings are static-analysis-based, grounded in the code's PRAGMA/transaction choices); a full penetration test of the web UI; dependency CVE scanning. These are candidates only if the tool is exposed beyond localhost or throughput becomes a concern.
- **Confidence:** High for structural, data-layer, and load-pipeline findings (direct source evidence). W3 (`|safe`) is flagged as a surface to audit rather than a confirmed live exploit — each of the 16 sites should be checked individually.
