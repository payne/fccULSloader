# Git Workflow & Commit Guide

> **Project:** bepreparedsolutions.co — Two-branch workflow (`staging` and `main`) with staging-first database changes.

---

## 1. Branch & Environment Model

| Branch | Purpose | Deploy Target | Env File | DB Commands |
|--------|---------|---------------|----------|-------------|
| `staging` | Active development, testing | Render Staging | `.env.staging` | `npm run db:*:staging` |
| `main` | Production-ready code | Render Production | `.env.prod` | `npm run db:*` |

**Flow:** Feature work happens on `staging`. After verification, merge `staging` into `main` for production deployment.

---

## 2. Commit Message Format

### Structure
```
<type>: <subject line>

<optional body — what and why>

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>
```

### Subject Line Rules
- Under 72 characters
- Imperative mood ("add feature" not "added feature")
- Capitalize first word after type prefix
- No trailing period

### Types
| Type | Use For |
|------|---------|
| `feat` | New features or functionality |
| `fix` | Bug fixes |
| `refactor` | Code restructuring without behavior changes |
| `chore` | Dependencies, tooling, config updates |
| `docs` | Documentation updates |
| `style` | Formatting, whitespace, styling changes |
| `perf` | Performance improvements |

### Examples
```
feat: Add BeInformed admin utilities page with filters and sorting

Port utilities list and detail pages from BPLI with Trust Blue theme,
light/dark mode, and mobile-responsive layouts.

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>
```

```
fix: Resolve DialogContent dimension override on monitoring page

cn() lacks tailwind-merge, so conflicting max-w classes weren't
deduplicating. Use inline style for maxWidth instead.

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>
```

### Commit via HEREDOC (Required for Multi-Line Messages)
```bash
git commit -m "$(cat <<'EOF'
feat: Add geospatial import trigger task

Port BPLI's 6-step geospatial import pipeline into the main app's
trigger config with updated import paths and SDK v4 imports.

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>
EOF
)"
```

---

## 3. Staging Changes

### Prefer Specific Files Over `git add .`
```bash
# ✅ Good — explicit about what's included
git add src/trigger/tasks/beinformed/geospatial-import.ts
git add src/trigger/beinformed-utils/import/file-parser.ts
git add trigger.config.ts

# ⚠️ Risky — can accidentally include .env, credentials, large binaries
git add .
git add -A
```

### Never Commit
- `.env`, `.env.local`, `.env.staging`, `.env.prod`
- `credentials.json`, API keys, secrets
- `node_modules/`, `.next/`
- Large binary files

---

## 4. Pre-Commit Checks

Before committing, verify:

```bash
# Lint passes
npm run lint

# Build succeeds (use correct env for branch)
npm run build           # on main
npm run build:staging   # on staging
```

If a pre-commit hook fails:
- The commit did NOT happen
- Fix the issue, re-stage files, create a NEW commit
- Do NOT use `--amend` (that would modify the previous commit)
- Do NOT use `--no-verify` to bypass hooks

---

## 5. Database Change Workflow

**Always apply database changes to staging first, verify, then production.**

### On `staging` branch:
```bash
# 1. Generate migration
npm run db:generate:staging

# 2. Review the generated SQL in drizzle/migrations/
# 3. Apply to staging database
npm run db:migrate:staging

# 4. Verify in Drizzle Studio
npm run db:studio:staging

# 5. Commit the migration files
git add drizzle/migrations/
git commit -m "chore: Add migration for bpli_utilities table

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

### After merging to `main`:
```bash
# Apply the same migration to production
npm run db:migrate
```

**CRITICAL:** Never run `npx drizzle-kit` directly. Always use `npm run db:*` scripts.

---

## 6. Trigger.dev Deployment

```bash
# Deploy to staging (from staging branch)
npm run trigger:deploy:staging

# Deploy to production (from main branch, after merge)
npm run trigger:deploy:prod
```

---

## 7. Dependency Installation

```bash
# This project requires --legacy-peer-deps for some packages
npm install <package> --legacy-peer-deps
npm install -D <package> --legacy-peer-deps
```

---

## 8. Single vs. Multiple Commits

### Prefer Single Comprehensive Commit When:
- All changes are part of one logical unit of work (e.g., porting a feature)
- Changes span implementation + config + documentation for one feature

### Split Into Multiple Commits When:
- Changes are genuinely unrelated (e.g., a bug fix + a new feature)
- One part is ready but another needs more work
- Separating makes rollback easier for risky changes

---

## 9. Push Safety

```bash
# Check current branch before pushing
git branch --show-current

# Push to remote with tracking
git push -u origin staging

# NEVER force-push to main without explicit approval
# NEVER push directly to main — merge from staging
```

### Before Pushing
- [ ] All commits have meaningful messages
- [ ] `npm run lint` passes
- [ ] `npm run build` (or `build:staging`) succeeds
- [ ] No sensitive data in any committed files
- [ ] Branch is up to date with remote (`git pull` first)

---

## 10. Common Operations

### View Recent Commits (for Style Reference)
```bash
git log --oneline -10
```

### Undo Last Commit (Keep Changes)
```bash
git reset --soft HEAD~1
```

### Check What Will Be Committed
```bash
git status
git diff --staged
```

### Stash Work in Progress
```bash
git stash push -m "WIP: description"
git stash pop
```

---

## 11. Quality Checklist

### Before Every Commit
- [ ] Changes are related and belong together
- [ ] Commit message explains what and why
- [ ] No debug `console.log` statements
- [ ] No `.env` files or secrets included
- [ ] No `@ts-expect-error` or `eslint-disable` added
- [ ] Lint passes
- [ ] Co-Authored-By footer included (when AI-assisted)

### Before Merging staging → main
- [ ] All features tested on staging environment
- [ ] Database migrations verified on staging
- [ ] Trigger.dev tasks deployed and verified on staging
- [ ] Build passes on staging branch
- [ ] No WIP commits in the merge
