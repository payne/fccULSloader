# Staging → Production Deployment and Testing Protocol

This document is the canonical reference for how every BeReady v2 task (528 and onward) deploys from staging to production. Each task file's *"Deployment + testing"* section names task-specific items (which migrations, which trigger tasks, which prompts, which system_settings keys) and references this protocol for the procedural steps.

The protocol exists to enforce: (a) no production deploy without staging verification; (b) no schema change without down-migration; (c) no AI prompt change without replication across environments; (d) automated test coverage where tractable; (e) explicit rollback at every step.

---

## A. Branch and environment workflow

| Branch | Environment | Database | Trigger.dev project | Env file |
|---|---|---|---|---|
| `staging` | staging.bepreparedsolutions.co | Staging Postgres | Staging Trigger.dev | `.env.staging` |
| `main` | be-prepared-web-app-prod.onrender.com | Production Postgres | Production Trigger.dev | `.env.prod` |

**Strict rule:** every change ships to `staging` first, gets UAT-confirmed by Tiran on staging, then merges to `main`. Never push directly to `main`. Never run production migrations from a developer machine without staging-verified equivalence first.

---

## B. Schema migrations (Drizzle)

For any task that adds or modifies a table/column:

### B1. Generate the migration
```bash
# Operating on staging branch
npm run db:generate:staging
```
Review the generated SQL in `drizzle/migrations/` for safety (additive only when possible; no destructive operations without explicit user confirmation).

### B2. Create the down-migration (MANDATORY)
Per CLAUDE.md "Down Migration Safety Protocol":
```bash
mkdir drizzle/migrations/<timestamp_name>
# Create down.sql following ai_docs/dev_templates/drizzle_down_migration.md
```
The `down.sql` MUST use `IF EXISTS` clauses and include comments naming what's being rolled back.

### B3. Apply to staging
```bash
npm run db:migrate:staging
```
Verify success:
```bash
# Inspect the new table/column shape
npm run db:studio:staging
# Or via psql
psql "$(grep DATABASE_URL .env.staging | cut -d= -f2- | tr -d '"')" -c "\d <new_table_name>"
```

### B4. Stage verification
- Confirm the migration applied (table exists, columns match schema definition)
- Confirm no existing data was corrupted (sample 5 rows from related tables)
- Confirm `down.sql` would roll back cleanly — dry-run by replaying it on a staging snapshot if production-critical (rarely required for additive changes; mandatory for destructive)
- Run the task's automated test suite (`npm run test` or task-specific vitest invocation) and confirm green

### B5. Production deploy
After staging UAT signed off by Tiran:
```bash
git checkout main
git merge staging --no-ff
git push origin main
# Render auto-deploys main branch to be-prepared-web-app-prod.onrender.com
npm run db:migrate
# Production migration runs against production DB
```
Verify production migration:
- Inspect production schema via `npm run db:studio` (uses `.env.prod`)
- Smoke-test the affected feature on production with a known-good account
- Watch Render logs (`mcp__render__list_logs` with `resource: ["srv-d7dh1h77f7vs73cj3lo0"]`) for 5 minutes post-deploy

### B6. Rollback procedure
If production deploy breaks:
1. Revert the merge commit on `main`: `git revert -m 1 <merge-sha>` and push
2. Run the down-migration on production: `npm run db:migrate` after editing `drizzle/migrations/meta/_journal.json` to remove the rolled-back entry (see CLAUDE.md "PostgreSQL Functions" note for caveats)
3. Confirm via `npm run db:studio` that the schema rolled back
4. File a post-incident note in `ai_docs/incidents/` (create directory if needed)

---

## C. Trigger.dev tasks

For any task that adds or modifies `src/trigger/tasks/`:

### C1. Local development
```bash
# Operating on staging branch
npm run trigger:dev:staging
# Runs the Trigger.dev dev server against staging keys
```
Test the task by invoking it via the dev console or programmatically.

### C2. Deploy to staging
```bash
npm run trigger:deploy:staging
```
The deploy uploads the task definitions to the staging Trigger.dev project. Verify in the Trigger.dev dashboard that the task appears with the expected schedule/handler.

### C3. Staging verification
- For `schedules.task` (cron): manually trigger via Trigger.dev dashboard's "Test run" button OR wait for the next scheduled fire
- For `task()` (event-driven): trigger from a server action and confirm the run completes successfully
- Inspect run logs in the Trigger.dev dashboard for errors
- Confirm any ledger/state writes landed (e.g. `bpr_quarterly_email_sends` row inserted)

### C4. Production deploy
After staging confirmed:
```bash
# On main branch
npm run trigger:deploy:prod
```
Verify in production Trigger.dev dashboard. Watch the first scheduled run (or first invocation) end-to-end.

### C5. Rollback procedure
If a deployed Trigger.dev task is broken:
1. Re-deploy the prior version: check out the prior commit, run `npm run trigger:deploy:prod`
2. If the task is causing data corruption, disable it via the Trigger.dev dashboard "Pause schedule" toggle while fixing
3. Use the kill-switch pattern if the task respects one (e.g. `system_settings.beready_*_enabled` flag set to `false`)

---

## D. System settings (canonical keys)

For any task that adds a key to `system_settings`:

### D1. Add to canonical default
Per CLAUDE.md "System Settings Sync Protocol":
1. Add the key to `DEFAULT_SYSTEM_SETTINGS` array in `src/db/schema/system-settings.ts` with default value, valueType, description, category
2. Confirm `scripts/seed-system-settings.ts` imports `DEFAULT_SYSTEM_SETTINGS` and walks it automatically (no separate `ALL_SETTINGS` array to update in this codebase)

### D2. Seed on staging
```bash
npm run seed:settings:staging
```
Confirms the key exists in staging DB with the default value. Idempotent — safe to re-run.

### D3. Verify in admin UI on staging
Navigate to `/admin/system` → Settings → relevant category. Confirm the key appears, default value is correct, can be edited and saved.

### D4. Seed on production
After staging verified:
```bash
npm run seed:settings
# (Note: prod variant typically doesn't have :staging suffix; verify package.json)
```
Confirm in production admin UI.

### D5. Auto-heal note
The admin layout calls `ensureSystemSettingsSeeded()` on every load, which inserts any missing keys from `DEFAULT_SYSTEM_SETTINGS`. This is the safety net — if the seed script is skipped, the next admin page view inserts the missing keys. But the explicit seed step is still required because (a) it confirms the key landed before users interact, and (b) it logs the seed event for audit.

---

## E. DB-stored AI prompts (replicated across environments)

For any task that creates or modifies a DB-stored prompt (e.g. `beready_v2_pipeline_drafter`, `beready_v2_pipeline_editor_tab1`, etc.):

### E1. Author the prompt in admin UI on staging
1. Navigate to `/admin/system` → AI Prompts (or relevant section) on staging
2. Create or edit the prompt — paste content, save
3. The save invalidates `loadDbPrompt()` cache automatically (5-min TTL)
4. Verify the prompt loads correctly by triggering the LLM call that consumes it (e.g. regenerate a test plan on staging)

### E2. Capture the prompt for production
1. Copy the staging prompt's full content to a working doc or to the task's PR description
2. Note any non-obvious decisions (token budget, expected output shape, voice constraints)

### E3. Apply identical prompt on production
1. Navigate to `/admin/system` → AI Prompts on production
2. Create or edit with **byte-identical** content from staging
3. Save and verify cache invalidation

### E4. Verification — both environments produce equivalent output
Run a known-input regression on both environments:
- Staging: trigger the LLM-backed feature with a canned fixture, capture output
- Production: same canned fixture, same feature, capture output
- Diff the outputs. They should be substantially equivalent (LLM determinism aside — voice rules, structure, vocabulary should match)

### E5. Rollback procedure
The DB-stored prompt has a `previous_value` audit trail (verify if not, add as a follow-up). Rollback = paste the prior value back into the admin UI and save. If `previous_value` is not tracked, the prompt must be re-derived from git history or PR description.

### E6. Inviolable rule — never let staging and production drift
Every prompt change ships to staging FIRST, gets verified, gets approved by Tiran, then is copied byte-identical to production. Production prompt edits without prior staging equivalent are a P0 incident — they make the staging environment meaningless as a test bed.

---

## F. Automated testing

Every task should include vitest coverage to the extent tractable. The default ask:

### F1. Pure functions
Any pure function (deterministic resolver, schema validator, formatter, predicate) has a vitest unit test covering happy path + ≥2 edge cases.

### F2. Server actions
Server actions are tested via vitest with a mocked DB layer OR via integration tests against the staging DB (preferred when the action is small and side-effects are easy to clean up).

### F3. Component tests (UI)
Where the task introduces a non-trivial component (state machine, complex interactions), a `@testing-library/react` test covers user-visible behavior. Snapshot tests are acceptable for stable visual surfaces.

### F4. End-to-end tests on staging
For user-visible flows (new routes, multi-step interactions), a staging E2E test covers the happy path. Document as a manual UAT script in the task file's testing section.

### F5. CI integration
Vitest runs on every PR via existing CI (verify `package.json` test script). A PR with failing tests blocks merge.

---

## G. Manual test plan (UAT)

Every task file's *"Deployment + testing"* section includes a manual UAT script — the steps Tiran (or a tester) walks through on staging before approving production deploy. The format:

```
1. As a user with [tier], navigate to [route]
2. Confirm [expected visible behavior]
3. Perform [action]
4. Confirm [expected state change in UI + DB]
5. Confirm [no regression in adjacent feature X]
```

The script lives at the bottom of each task file. PR description references it.

---

## H. Rollback procedures (consolidated)

For any task that mutates schema, prompts, or trigger tasks, the task file lists the rollback procedure explicitly. The defaults:

| Change type | Rollback |
|---|---|
| Additive schema (column / table) | Run down-migration; redeploy app |
| Destructive schema | Restore from latest DB snapshot; redeploy app; file incident |
| Trigger.dev task | Re-deploy prior commit; pause schedule via dashboard if causing harm |
| DB-stored prompt | Paste prior value via admin UI; verify cache invalidation |
| System setting | Edit value back via admin UI (`/admin/system`); auto-heal won't overwrite |
| New route | Comment out the route in `src/app/.../page.tsx` and redeploy (returns 404); fix and re-deploy |
| New UI component | Comment out the consumer's import and redeploy |

---

## I. Per-task deployment + testing section template

Each task file ends with a section structured like this. Implementer copies and fills the bracketed items.

```markdown
## Deployment + testing

This task follows the staging → production protocol at `ai_docs/dev_templates/staging_to_prod_protocol.md`.

### Task-specific items

- **Schema migrations:** [list every migration file this task adds, or "none"]
- **Trigger.dev tasks:** [list every new/changed task in `src/trigger/`, or "none"]
- **System settings keys:** [list every key added to `DEFAULT_SYSTEM_SETTINGS`, or "none"]
- **DB-stored AI prompts:** [list every prompt key this task creates/modifies, or "none"]
- **New routes:** [list new pages, or "none"]
- **Cross-env data (e.g. cron schedules, kill switches):** [list anything that needs identical config across staging + prod]

### Automated tests

- [ ] Vitest covers: [list specific test cases]
- [ ] CI runs the test suite on every PR (existing infra)
- [ ] [Any task-specific automated check, e.g. eval suite, audit script]

### Staging deployment sequence

1. Merge task PR to `staging` branch
2. Run `npm run db:generate:staging` if schema changed (review generated SQL; create `down.sql`)
3. Run `npm run db:migrate:staging` to apply migration
4. Run `npm run seed:settings:staging` if system settings keys added
5. Run `npm run trigger:deploy:staging` if Trigger.dev tasks changed
6. Manually replicate any DB-stored prompts via staging `/admin/system` UI
7. Render auto-deploys staging branch to `staging.bepreparedsolutions.co`
8. Confirm Render build succeeds via `mcp__render__list_deploys` for staging service

### Staging UAT

[Numbered manual test script — see §G template above]

### Production deployment sequence

After Tiran signs off on staging UAT:

1. Merge `staging` → `main`
2. Run `npm run db:migrate` against production DB
3. Run `npm run seed:settings` against production DB (verify exact command in package.json)
4. Run `npm run trigger:deploy:prod`
5. Manually replicate DB-stored prompts via production `/admin/system` UI (byte-identical to staging)
6. Render auto-deploys `main` to `be-prepared-web-app-prod.onrender.com`
7. Smoke-test the feature on production with a known account
8. Watch Render production logs for 5 minutes

### Production UAT

[Brief smoke-test script — typically a subset of staging UAT focused on happy path]

### Rollback

[Specific steps per the table in §H of the protocol doc, customized for this task]
```

---

## J. Inviolable rules summary

1. **Staging first, always.** No production change without staging-verified equivalence.
2. **Down-migrations are mandatory for schema changes.** Created before `db:migrate` runs.
3. **AI prompts replicated byte-identical.** Staging and production prompts must match after each release.
4. **System settings seeded on both environments.** `DEFAULT_SYSTEM_SETTINGS` is the source of truth; seed scripts run on staging and prod.
5. **Automated tests cover pure functions and critical paths.** New tests are part of the PR, not deferred.
6. **Every task file ends with a Deployment + testing section.** No exceptions.
7. **Rollback is documented per task.** Mid-incident is not the time to figure it out.

---

*Created: 2026-05-16 — canonical reference for BeReady v2 staging → production deployment.*
*Cited by: Task 528 §15 and every Task 529–545 file's Deployment + testing section.*
