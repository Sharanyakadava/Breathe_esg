# DECISIONS

Every meaningful ambiguity I resolved, and what I'd ask the PM.

---

## SAP: Which export format?

**Chose:** Flat file / ALE IDoc-style tab/semicolon-delimited export.

**Why not OData:** OData requires SAP NetWeaver Gateway to be configured and exposed — most enterprise clients need an IT project to enable this. Flat file export is self-service from any SAP GUI with SE16/ME2M/MB51.

**Why not BAPI/RFC:** Requires ABAP developer access and a custom program. Not self-service for a sustainability team.

**Why not IDOC XML:** The binary/XML IDoc format adds parsing complexity for no benefit when the flat file variant carries the same data.

**What subset I handled:**
- Movement types 201 (goods issue to cost center) and 261 (goods issue to production order) → treated as fuel consumption
- Procurement: material groups with prefix PROC/RAW/PACK/CHEM → treated as Scope 3 purchased goods
- Ignored: vendor invoices (MIRO), asset transactions (ANLA), CO/PA profitability segments

**What I ignored:**
- German vs English column headers: handled via a translation dict (`bewegungsart` → `BWART`). Doesn't cover every SAP language setting.
- Plant hierarchy: SAP has plant → storage location → bin. I only resolve at plant (WERKS) level via `FacilityLookup`.
- Multi-company-code scenarios: BUKRS (company code) is captured in `source_extra` but not used for routing.

**What I'd ask the PM:**
1. Do clients have IT support to configure a proper SAP OData service? If yes, OData is far cleaner.
2. What movement types matter to their Scope 1 boundary? 201/261 is a reasonable default but some companies use custom ZMVTs.
3. Do they have a material master export we can use for a proper fuel-type lookup, rather than guessing from MAKTX descriptions?

---

## SAP: Fuel type detection

**Chose:** Heuristic string matching on material description (MAKTX) and material group (MATKL).

Real SAP instances don't have a "fuel type" field — you infer it from material descriptions like "Diesel fuel for generators" or material groups like "FUEL_STAT". The matching dict covers the most common variants in German and English.

**Limitation:** If a material is described as "Energieträger 001" (generic energy carrier), the fuel type is unknown and the record is flagged as suspicious. The analyst must resolve it.

**What I'd ask:** Do clients have a material master extract (MM60) that maps material numbers to fuel types? That would make this deterministic rather than heuristic.

---

## Utility: Portal CSV vs PDF vs API

**Chose:** Portal CSV export.

**Why not PDF:** PDF parsing is fragile. Every utility formats bills differently. Even with Camelot/pdfplumber, tables across page breaks fail, and scanned PDFs require OCR. Not production-reliable.

**Why not Green Button API:** Green Button is the NAESB standard (used by US utilities). But:
- UK and EU utilities don't support it
- Requires OAuth per-utility (each utility has its own OAuth app registration)
- Many US utilities only support Green Button Connect (push notifications), not Green Button Download (on-demand)
Portal CSV is universally available from every utility's self-service portal.

**What I ignored:**
- Demand charges (kW, not kWh) — in the export but not emission-relevant; skipped rows that appear to be demand charges.
- Power factor correction data
- Reactive power (kVAR) — similarly not consumed energy
- Time-of-use tariff breakdowns (on-peak/off-peak split) — I only care about total kWh

**What I'd ask:**
1. Do any facilities have renewable energy contracts (PPAs)? If so, market-based Scope 2 needs supplier-specific emission factors, not grid averages.
2. Which utilities do the clients use? If it's mostly US, Green Button is worth implementing properly. If EU, PDF parsing may be unavoidable for some utilities.

---

## Travel: Concur vs Navan vs expense system

**Chose:** Generic CSV export compatible with Concur, Navan, and most T&E platforms.

All major corporate travel platforms offer CSV exports in their reporting section. Concur's Standard Accounting Extract is the most common format; Navan has a similar structure. Rather than writing a Concur-specific parser, I wrote auto-detection of column names — both platforms use similar headers with slightly different capitalisation.

**What I handled:**
- Flights: IATA code → haversine distance → DEFRA 2023 factors by haul class and cabin
- Hotels: room-nights × regional factor
- Ground: car rental, taxi, rideshare, train/bus where distance or cost available

**What I ignored:**
- Rail emissions for international trains (Eurostar uses a different EF than domestic rail)
- Layovers / connecting flights treated as one segment (origin → final destination distance)
- Chauffeur/limo services
- Ferries

**Distance calculation:** If airport codes are in my IATA table, I use haversine (great-circle). If not, the record is flagged suspicious and a medium-haul estimate is used. In production, the full IATA database (~9,000 airports) would replace my sample of ~50.

**Radiative forcing:** I apply DEFRA's recommended uplift factor of 1.891 to account for high-altitude warming effects. Some frameworks (like TCFD) don't require this — I'd ask the PM whether the client's reporting framework mandates it.

**What I'd ask:**
1. Does the client have a Concur/Navan API key? Direct API pull would be cleaner than manual CSV exports.
2. What reporting framework are they using? GHG Protocol, TCFD, CDP? This affects whether radiative forcing and market-based Scope 2 are required.
3. Do they have employee headcounts by office for commute estimation (Scope 3 Category 7)? Out of scope for this sprint but a common follow-on request.

---

## Review workflow: approve/reject/flag vs multi-stage

**Chose:** Single-stage review. Analyst can approve, reject, or flag. Approved records are visible to auditors. Locked state is available but not yet automated.

A proper multi-stage workflow (analyst → senior analyst → external auditor sign-off) is the right answer for a production system. I chose not to build it in 4 days because it requires role-based permission checks, notification emails, and a proper state machine — all of which take time to do well. The current model supports the fields needed to implement it; it's a UI and permission layer problem, not a data model problem.

---

## Deployment target

**Chose:** Render (free tier for prototype). Django backend as a web service; React built as static files served by the Django static file server via WhiteNoise. SQLite database on the Render disk.

**Why not separate frontend deployment (Vercel + Railway backend):** Simpler for a prototype — one URL, no CORS gymnastics, one service to monitor.

**Why not PostgreSQL:** SQLite is fine for a prototype with one analyst and <100k records. The ORM abstraction means switching is a one-line settings change.
