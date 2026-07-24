# Task Review Checklist

> **Project:** beprepared.ai — Next.js 15+, React 19, TypeScript 5+, Drizzle ORM, Supabase Auth, Trigger.dev v4, Shadcn UI, Tailwind CSS v4.

Use this checklist to verify implementation quality before marking a task complete. Run through each section systematically.

---

## 1. Type Safety

### 1.1 No `any` Types
```bash
# Search for any types in changed files
npm run lint
```

**Check for:**
- [ ] No explicit `any` type annotations (except where suppressed with `eslint-disable` comment — which itself is discouraged)
- [ ] No implicit `any` from missing types
- [ ] Proper generics used where needed
- [ ] No `@ts-expect-error` or `eslint-disable` comments

### 1.2 Explicit Return Types
```typescript
// ❌ Bad
async function getUser(id: string) {
  return await db.query.profiles.findFirst({ where: eq(profiles.id, id) });
}

// ✅ Good
async function getUser(id: string): Promise<Profile | undefined> {
  return await db.query.profiles.findFirst({ where: eq(profiles.id, id) });
}
```

**Check for:**
- [ ] All functions have explicit return types
- [ ] Async functions return `Promise<T>`
- [ ] Void functions explicitly return `void` or `Promise<void>`

### 1.3 No Type Assertions Without Justification
```typescript
// ❌ Bad - hiding potential issues
const user = data as User;

// ✅ Good - validate first
if (isUser(data)) {
  const user = data;
}
```

---

## 2. Drizzle ORM

### 2.1 Type-Safe Operators (No Raw SQL for Basic Ops)
```typescript
// ❌ Bad
where: sql`user_id = ${userId}`;

// ✅ Good - Type-safe operators
import { eq, inArray, and, or } from 'drizzle-orm';
where: eq(profiles.id, userId);
where: inArray(posts.status, ['draft', 'published']);
```

**Available operators:** `eq`, `ne`, `gt`, `gte`, `lt`, `lte`, `inArray`, `notInArray`, `and`, `or`, `isNull`, `isNotNull`, `like`, `ilike`, `between`

**Exception:** Raw SQL is acceptable for database-specific functions like `sql<string>\`to_tsvector(...)\``, PostGIS operations, and staging table DDL.

### 2.2 Always Use `npm run db:*` Scripts
```bash
# ❌ Bad - bypasses env config
npx drizzle-kit generate
npx drizzle-kit migrate

# ✅ Good - uses correct env file for environment
npm run db:generate          # local/prod
npm run db:generate:staging  # staging
npm run db:migrate           # local/prod
npm run db:migrate:staging   # staging
```

### 2.3 NEVER Use `supabase.from()`
```typescript
// ❌ Bad - bypasses Drizzle type safety
const { data } = await supabase.from('profiles').select('*');

// ✅ Good - Drizzle ORM
const data = await db.query.profiles.findMany();
// or
const data = await db.select().from(profiles);
```

### 2.4 Proper Transaction Usage
```typescript
// ✅ Good - atomic operations
await db.transaction(async (tx) => {
  await tx.insert(orders).values(orderData);
  await tx.update(inventory).set({ quantity: sql`quantity - 1` });
});
```

### 2.5 Schema File Organization
- [ ] New tables go in `src/db/schema/` as separate files
- [ ] All schema files are exported from `src/db/schema/index.ts`
- [ ] Import schema as `@/db/schema`, database as `@/db`

---

## 3. Next.js 15 Patterns

### 3.1 Async Params/SearchParams (Breaking Change)
```typescript
// ✅ Server Components - await the promises
interface PageProps {
  params: Promise<{ id: string }>;
  searchParams: Promise<{ query?: string }>;
}

export default async function Page({ params, searchParams }: PageProps): Promise<React.ReactElement> {
  const { id } = await params;
  const { query } = await searchParams;
}

// ✅ Client Components - use React's use() hook
'use client';
import { use } from 'react';

export default function ClientPage({ params }: { params: Promise<{ id: string }> }): React.ReactElement {
  const { id } = use(params);
}
```

### 3.2 revalidatePath Requires Type
```typescript
// ❌ Bad - missing type parameter for dynamic route
revalidatePath('/reports/[reportId]');

// ✅ Good - include type parameter
revalidatePath('/reports/[reportId]', 'page');
```

### 3.3 No Async Client Components
```typescript
// ❌ Bad
'use client';
export default async function Component() { ... }

// ✅ Good - use hooks
'use client';
import { useEffect, useState } from 'react';
export default function Component(): React.ReactElement {
  const [data, setData] = useState(null);
  useEffect(() => { fetchData().then(setData); }, []);
}
```

### 3.4 `'use client'` Only When Necessary
- [ ] Server components are the default — don't add `'use client'` unless the component uses hooks, event handlers, or browser APIs
- [ ] Keep `'use client'` boundaries as low as possible in the component tree

---

## 4. Supabase Auth

### 4.1 Server-Side Only
```typescript
// ✅ Always async — server-side only
import { createClient } from '@/lib/supabase/server';
const supabase = await createClient();

// ❌ NEVER use NEXT_PUBLIC_SUPABASE_* variables
// ❌ NEVER create client-side Supabase instances
```

### 4.2 Auth Operations via Server Actions Only
```typescript
// ✅ All auth operations go through server actions in src/app/actions/auth.ts
import { getCurrentUser, signOut } from '@/app/actions/auth';

// ❌ NEVER call supabase.auth directly from client components
```

### 4.3 Admin Check
```typescript
// ✅ Check admin role via Drizzle
const profile = await db.query.profiles.findFirst({
  where: eq(profiles.id, user.id),
  columns: { role: true },
});
const isAdmin = profile?.role === 'admin';
```

### 4.4 Protected API Routes
```typescript
// ✅ Every protected route must check auth
export async function POST(request: Request): Promise<Response> {
  const supabase = await createClient();
  const { data: { user }, error } = await supabase.auth.getUser();

  if (error || !user) {
    return Response.json({ error: 'Unauthorized' }, { status: 401 });
  }
  // ...
}
```

---

## 5. Server/Client Separation

### 5.1 Server-Only Imports
```typescript
// These imports are SERVER-ONLY — never import in 'use client' files:
import { createClient } from '@/lib/supabase/server';
import { db } from '@/db';
import { headers, cookies } from 'next/headers';
```

### 5.2 No Secrets in Client Code
```typescript
// ❌ Bad - exposing secrets
const apiKey = process.env.OPENROUTER_API_KEY; // In client component

// ✅ Good - only NEXT_PUBLIC_ vars in client
const googleKey = process.env.NEXT_PUBLIC_GOOGLE_SERVICES_API_KEY;
```

**Check for:**
- [ ] No `process.env.` (without `NEXT_PUBLIC_`) accessed in `'use client'` files
- [ ] Supabase env vars are server-only (no `NEXT_PUBLIC_SUPABASE_*`)

---

## 6. Shadcn UI & Styling

### 6.1 Component Installation
```bash
# ✅ Always use this exact command
npx shadcn@latest add <component>

# ❌ NEVER use these
npx shadcn-ui add ...
pnpm dlx shadcn ...
```

### 6.2 cn() Does NOT Use tailwind-merge
```typescript
// ❌ Bad - cn() won't deduplicate conflicting classes
<DialogContent className={cn("max-w-lg", "max-w-7xl")}>

// ✅ Good - inline style for dimension overrides
<DialogContent style={{ maxWidth: '80rem' }}>

// ✅ Good - responsive with inline style
<DialogContent style={{ maxWidth: 'min(80rem, calc(100vw - 4rem))' }}>
```

**Check for:**
- [ ] No conflicting Tailwind dimension classes passed via `cn()` or `className`
- [ ] Shadcn component dimension overrides use inline `style`
- [ ] No inline styles for things other than dimension overrides (use Tailwind)

### 6.3 No Inline Styles (Except Dimension Overrides)
```typescript
// ❌ Bad
<div style={{ color: 'blue', padding: '1rem' }}>

// ✅ Good
<div className="text-primary p-4">
```

### 6.4 Animation Guidelines
```typescript
// ✅ User-initiated actions: ease-out
<button className="transition-transform duration-150 ease-out active:scale-95">

// ✅ Staying on-screen changes: ease-in-out
<div className="transition-transform duration-300 ease-in-out">

// ❌ Bad - transition-all causes jank
<div className="transition-all">

// ❌ Bad - ease-in makes UI feel sluggish
<div className="transition-transform ease-in">
```

| Easing | Use For |
|--------|---------|
| `ease-out` | User-initiated (buttons, dropdowns, modals) |
| `ease-in-out` | Elements changing on-screen (morphing, position) |
| `ease` | Subtle hover effects (color, background, opacity) |
| `linear` | Constant animations (progress bars, marquees) |
| `ease-in` | **AVOID** — makes UI feel sluggish |

---

## 7. Server Actions

### 7.1 Proper Structure
```typescript
// File: src/app/actions/example.ts
'use server';

import { createClient } from '@/lib/supabase/server';
import { db } from '@/db';
import { revalidatePath } from 'next/cache';

export async function updateItem(id: string, title: string): Promise<{ error?: string }> {
  const supabase = await createClient();
  const { data: { user }, error: authError } = await supabase.auth.getUser();

  if (authError || !user) {
    return { error: 'Unauthorized' };
  }

  await db.update(items)
    .set({ title, updatedAt: new Date() })
    .where(and(eq(items.id, id), eq(items.userId, user.id)));

  revalidatePath('/items', 'page');
  return {};
}
```

### 7.2 No Toast in Server Actions
```typescript
// ❌ Bad - toast is client-side only
export async function doThing(): Promise<void> {
  toast.success('Done!'); // Will error
}

// ✅ Good - return result, let client show toast
export async function doThing(): Promise<{ error?: string }> {
  return {};
}
```

---

## 8. Trigger.dev Tasks

### 8.1 Import from Correct Package
```typescript
// ✅ Good - v4 SDK
import { task, logger, metadata } from '@trigger.dev/sdk';

// ❌ Bad - v3 suffix or old patterns
import { task } from '@trigger.dev/sdk/v3';
import { client } from '...'; client.defineJob(...);
```

### 8.2 Orchestration Patterns
```typescript
// ✅ Good - sequential orchestration
const result = await childTask.triggerAndWait({ payload });
if (!result.ok) { /* handle error */ }

// ❌ Bad - Promise.all with triggerAndWait is NOT supported
await Promise.all([
  taskA.triggerAndWait(...),
  taskB.triggerAndWait(...),
]);
```

### 8.3 Progress Tracking
```typescript
// ✅ Use metadata for progress
metadata.set('progress', 50);
metadata.set('step', 'Processing data');

// ✅ Use logger for structured logging
logger.info('Task started', { jobId, datasetType });
```

### 8.4 Deploy Commands
```bash
# ✅ Use npm scripts — they load correct env files
npm run trigger:deploy:staging
npm run trigger:deploy:prod

# ❌ Bad - bypasses env config
npx trigger.dev@latest deploy
```

---

## 9. Error Handling

### 9.1 Consistent API Error Responses
```typescript
return Response.json({ error: 'Not found' }, { status: 404 });
return Response.json({ error: 'Validation failed', details: issues }, { status: 400 });
```

### 9.2 Graceful Duplicate Handling
```typescript
// ✅ Server actions should return success on duplicates, not throw
const existing = await db.query.items.findFirst({ where: eq(items.id, id) });
if (existing) return { success: true, data: existing };
```

### 9.3 Try-Catch for External Calls
```typescript
try {
  const response = await stripe.customers.create({ email });
  return Response.json({ customerId: response.id });
} catch (error) {
  console.error('Stripe error:', error);
  return Response.json({ error: 'Payment service unavailable' }, { status: 503 });
}
```

---

## 10. Code Quality

### 10.1 No Debug Artifacts
```bash
# Check for leftover TODOs in changed files
grep -r "TODO\|FIXME\|XXX\|HACK" --include="*.ts" --include="*.tsx" src/
```

- [ ] No `console.log` debugging (use `console.error` for actual error logging)
- [ ] No commented-out code — git has history
- [ ] No `TODO`/`FIXME` in production code

### 10.2 Consistent Naming
- **Files:** kebab-case (`geospatial-import.ts`)
- **Components:** PascalCase (`GeospatialImport`)
- **Functions:** camelCase (`processImport`)
- **Constants:** SCREAMING_SNAKE_CASE (`MAX_FILE_SIZE`)
- **Types/Interfaces:** PascalCase (`ImportPayload`)
- **Database tables:** snake_case with prefix (`bpli_utilities`)
- **Drizzle schema exports:** camelCase (`bpliUtilities`)

### 10.3 Import Paths
```typescript
// ✅ Good - project aliases
import { db } from '@/db';
import { profiles } from '@/db/schema';
import { createClient } from '@/lib/supabase/server';

// ❌ Bad - relative paths that go too far up
import { db } from '../../../../db';
```

---

## 11. Environment Variables

### 11.1 Branch-Aware Commands
| Branch | Dev | Build | DB Commands |
|--------|-----|-------|-------------|
| `main` | `npm run dev` | `npm run build` | `npm run db:*` |
| `staging` | `npm run dev:staging` | `npm run build:staging` | `npm run db:*:staging` |

### 11.2 New Env Vars
When adding new environment variables:
- [ ] Added to `.env.staging` and `.env.prod`
- [ ] Added to `trigger.config.ts` `syncEnvVars` if needed by Trigger.dev tasks
- [ ] Documented in CLAUDE.md Environment Variables section
- [ ] Server-only vars do NOT have `NEXT_PUBLIC_` prefix

---

## 12. Testing Checklist

### 12.1 Automated
```bash
npm run lint              # ESLint
npm run build             # Type checking + build verification
npm run build:staging     # If on staging branch
```

### 12.2 Manual Testing
- [ ] Happy path works as expected
- [ ] Error states handled gracefully
- [ ] Loading states display correctly
- [ ] Auth redirects work properly
- [ ] Light/dark mode correct
- [ ] Mobile responsive (320px+)

### 12.3 Edge Cases
- [ ] Empty states handled
- [ ] Invalid input rejected
- [ ] Unauthorized access blocked
- [ ] Duplicate submissions handled gracefully

---

## 13. Final Verification

Before marking a task complete:

- [ ] `npm run lint` passes with no new errors
- [ ] `npm run build` (or `build:staging`) succeeds
- [ ] No `any` types introduced
- [ ] All functions have explicit return types
- [ ] Server/client separation maintained
- [ ] Auth checks on all protected routes/actions
- [ ] Input validation on user-facing endpoints
- [ ] No debug `console.log` left behind
- [ ] `revalidatePath` includes type parameter for dynamic routes
- [ ] Shadcn dimension overrides use inline `style`, not conflicting classes
- [ ] New env vars documented and added to relevant config
- [ ] Database changes applied to staging first, verified, then production

---

## Quick Reference: Common Mistakes

| Mistake | Fix |
|---------|-----|
| `any` type | Use specific type or generic |
| Missing return type | Add explicit `: ReturnType` |
| `supabase.from('table')` | Use Drizzle: `db.select().from(table)` |
| `npx drizzle-kit generate` | Use `npm run db:generate` |
| Raw SQL for basic query | Use `eq`, `inArray`, etc. |
| `@trigger.dev/sdk/v3` | Use `@trigger.dev/sdk` |
| `Promise.all` with `triggerAndWait` | Sequential calls only |
| Async client component | Use `useEffect` + `useState` |
| Missing auth check | Add `getUser()` check first |
| `revalidatePath('/path/[id]')` | `revalidatePath('/path/[id]', 'page')` |
| `cn("max-w-lg", "max-w-7xl")` | Use `style={{ maxWidth: '...' }}` |
| `NEXT_PUBLIC_SUPABASE_*` | Server-only: `SUPABASE_URL`, `SUPABASE_ANON_KEY` |
| Toast in server action | Return result, client shows toast |
| `transition-all` | Use specific: `transition-shadow`, `transition-transform` |
| `npx drizzle-kit migrate` | Use `npm run db:migrate` |
| `npx shadcn-ui add` | Use `npx shadcn@latest add` |
