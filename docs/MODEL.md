# DATA MODEL

## Overview

The model has five primary tables. Everything flows from `Tenant` → `IngestionBatch` → `EmissionRecord`. The `FacilityLookup` resolves SAP plant codes. `EmissionRecordEdit` is an append-only audit log.

```
Tenant
  ├── TenantMembership (User × Tenant × Role)
  ├── FacilityLookup (SAP plant code → real location)
  └── IngestionBatch (one upload event)
        └── EmissionRecord (one normalised row)
              └── EmissionRecordEdit (append-only change log)
```

---

## Multi-Tenancy

Every row in `EmissionRecord`, `IngestionBatch`, and `FacilityLookup` carries a `tenant` FK. All queryset filters gate on `tenant`. Tenants are isolated at the ORM layer; there is no row-level security in the DB because SQLite is used for the prototype, but the tenant filter is applied on every view — it would be straightforward to replace this with Postgres row-level security policies in production.

`TenantMembership` carries a `role` field (`analyst`, `admin`, `auditor`). The prototype doesn't yet gate individual actions behind role checks — that's called out in TRADEOFFS.md.

---

## Scope 1/2/3 Categorisation

`EmissionRecord.scope` is an enum:

| Value      | Meaning                                    |
|------------|--------------------------------------------|
| `scope1`   | Direct combustion (fuel burned on-site/fleet) |
| `scope2_lb`| Purchased electricity, location-based      |
| `scope2_mb`| Purchased electricity, market-based        |
| `scope3`   | Value chain (travel, procurement)          |

`scope` is set by the parser at ingestion time, based on the emission factor and data source. It is never null.

`category` further classifies:

| Category                | Scope | Source |
|-------------------------|-------|--------|
| `fuel_stationary`       | 1     | SAP (movement type 201, cost center issue) |
| `fuel_mobile`           | 1     | SAP (movement type 261, production order)  |
| `electricity`           | 2     | Utility CSV                                |
| `business_travel_air`   | 3     | Travel CSV (flights)                       |
| `business_travel_hotel` | 3     | Travel CSV (hotels)                        |
| `business_travel_ground`| 3     | Travel CSV (car rental, taxi, train)       |
| `procurement`           | 3     | SAP (material groups with PROC/CHEM/RAW/PACK prefix) |

---

## Unit Normalisation

All `EmissionRecord.quantity_kg_co2e` values are stored in **kg CO2e**. Unit conversion happens inside parsers before the record is written. The raw pre-conversion values are preserved in:

- `source_quantity` — original numeric value
- `source_unit` — original unit string (e.g. `L`, `M3`, `kWh`, `room-night`, `km`)

This means you can always audit the calculation: `source_quantity × emission_factor_value = quantity_kg_co2e`.

SAP UOM → standard unit conversions handled:

| SAP MEINS | Conversion                   |
|-----------|------------------------------|
| L / LT / LTR | → litre (1:1)           |
| M3        | → m3 (1:1)                   |
| KG        | → kg (1:1)                   |
| G         | → kg (÷ 1000)                |
| T         | → kg (× 1000)                |
| GAL       | → litre (× 3.78541)          |

---

## Source-of-Truth Tracking

Every `EmissionRecord` stores:

| Field | Purpose |
|-------|---------|
| `batch` | Which ingestion run produced this row |
| `source_row_id` | Position/identifier in the source file |
| `source_date_raw` | Original date string (before parsing) |
| `source_quantity` | Original numeric value (before unit conversion) |
| `source_unit` | Original unit string |
| `source_extra` | JSON dict of additional source columns not mapped to schema |
| `emission_factor_value` | The factor applied |
| `emission_factor_unit` | Units of the factor |
| `emission_factor_source` | Citation (e.g. "DEFRA 2023") |

`source_extra` captures fields from the source that don't have a canonical mapping — e.g. SAP cost center (`KOSTL`), tariff code from utility export, employee name from travel data. These are preserved for audit without cluttering the main schema.

---

## Audit Trail

`EmissionRecordEdit` is an **immutable append-only table**. Every time a field on `EmissionRecord` is changed through the API, a row is inserted recording:

- `edited_by` (FK to User)
- `edited_at` (auto timestamp)
- `field_name` — which field changed
- `old_value` / `new_value` — as strings
- `reason` — analyst's stated reason

The `EmissionRecord.is_edited` boolean is set to `True` on first edit, so auditors can quickly identify records that were changed post-ingestion.

Review actions (`approved`, `rejected`) record `reviewed_by` and `reviewed_at` directly on the record. `status = 'locked'` is a terminal state that prevents further edits; it's set manually by an admin before handoff to auditors (not yet exposed in the UI — see TRADEOFFS.md).

---

## Design Decisions

**Why not separate tables per source type?** Normalisation. An auditor reviewing Scope 1+2+3 together doesn't want to JOIN across three tables. The `source_extra` JSON field handles source-specific columns without polluting the main schema with nullable columns.

**Why DecimalField not FloatField for CO2e?** Floating-point rounding errors accumulate when summing thousands of emission records. Decimal arithmetic is exact. This matters for audit-grade numbers.

**Why store emission factor on each record?** Factors change annually (DEFRA publishes new conversion factors each year). Storing the factor used at ingestion time means we can reproduce the exact CO2e figure even after factors are updated. If we only stored the factor name/version, a future recalculation would give different numbers.

**Billing period alignment:** `period_start` and `period_end` are stored as dates (not timestamps). Utility billing periods often don't align to calendar months (e.g. 17 Oct → 19 Nov). We store the actual billing period, not a normalised calendar month. Downstream reporting can aggregate by calendar period if needed.
