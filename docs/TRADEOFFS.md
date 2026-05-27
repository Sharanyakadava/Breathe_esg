# TRADEOFFS

Three things I deliberately did not build, and why.

---

## 1. Role-based permission enforcement

**What I built:** A `role` field on `TenantMembership` (`analyst`, `admin`, `auditor`). The data model is ready.

**What I didn't build:** Actual enforcement. Any authenticated user with access to a tenant can approve records, upload files, or view all data regardless of role.

**Why I stopped here:**

Doing RBAC badly is worse than not doing it. A half-built permission system creates a false sense of security — an auditor account that *looks* read-only but actually isn't. Proper RBAC in Django requires:

1. Custom permission classes per view/action
2. Object-level permissions (can this analyst approve records in this tenant's batch?)
3. Tests proving the boundary holds

That's a solid day of work done carefully. Given 4 days total, I prioritised getting the data model, parsers, and review UX right — things that are hard to retrofit — over permissions, which can be layered on cleanly once the surfaces are defined.

**What I'd do next:** Add a `TenantPermission` class that checks `request.user`'s membership role before allowing write operations. `auditor` role gets read-only. `analyst` can approve/reject but not lock. `admin` can lock and manage facilities.

---

## 2. Async processing / task queue

**What I built:** Synchronous file processing inside the HTTP request. Upload → parse → persist → respond.

**What I didn't build:** Celery/RQ task queue with background processing and websocket status updates.

**Why I stopped here:**

For a prototype with files up to ~10,000 rows and one concurrent user, synchronous processing is fine. A 5,000-row SAP export parses in under 2 seconds. The HTTP timeout isn't a problem.

But in production this breaks immediately:
- A 200,000-row utility export takes 30+ seconds → Nginx/Gunicorn timeout
- Multiple concurrent uploads block the single worker
- If processing crashes mid-way, the user gets a 500 with no way to check status

**What I'd do next:** Move ingestion into a Celery task. The `IngestionBatch` record is created synchronously (gives the user a batch ID immediately), then processing runs in the background. The frontend polls `GET /api/emissions/batches/{id}/` for status updates. This is a clean architectural seam — the batch model already has `status`, `row_count_*`, and `error_log` fields designed for async population.

---

## 3. Emission factor versioning / recalculation

**What I built:** Each `EmissionRecord` stores the factor used at ingestion time. If DEFRA publishes new factors, records ingested before the update are permanently on the old factor.

**What I didn't build:** A versioned `EmissionFactor` table, or a "recalculate all records with updated factors" workflow.

**Why I stopped here:**

This is a real tradeoff, not just scope. Storing the factor on the record is actually the *right* choice for auditability — the 2024 annual report should reflect the factors that were published and valid in 2024, not 2025 factors backdated. But it means the system can't answer "what would our 2024 emissions be if we applied 2025 DEFRA factors?" — a question sustainability teams legitimately want for comparability.

A proper solution has:
1. An `EmissionFactor` table with (`source`, `version`, `valid_from`, `valid_to`, `category`, `value`)
2. FK from `EmissionRecord` to `EmissionFactor` (instead of storing value directly)
3. A recalculation API that creates a new batch of records with updated factors, rather than mutating existing records
4. Reporting that can compare across factor vintages

This is architecture worth designing carefully because it touches every parser and the audit trail logic. I chose to defer it and document the tradeoff rather than bolt on a half-baked version.

**What I'd do next:** Introduce the `EmissionFactor` table and FK, then write a migration that populates it from the hardcoded values currently in the parsers. All factor lookups then go through the DB, and factor versioning is a natural extension.
