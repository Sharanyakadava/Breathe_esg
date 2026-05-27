# SOURCES

For each of the three data sources: what real-world format I researched, what I learned, what my sample data looks like and why, and what would break in a real deployment.

---

## 1. SAP Fuel and Procurement Data

### What I researched

SAP stores goods movements in table `MSEG` (material document segment), joined with `MKPF` (material document header). The most useful export for sustainability is transaction `MB51` (material document list), which produces a flat report of all goods movements by plant, material, and date.

Key fields:
- **BWART** (Bewegungsart) — movement type. 201 = goods issue to cost center (stationary use), 261 = goods issue to production order (typically mobile/process). 561 = initial stock posting (not relevant). 101 = goods receipt (also not relevant to combustion).
- **WERKS** — plant code. An arbitrary 4-character code that means nothing without the facility master.
- **MENGE / MEINS** — quantity and unit of measure. SAP uses its own UOM codes: L (litres), M3 (cubic metres), KG (kilograms), T (metric tonnes), GAL (US gallons).
- **BUDAT** — posting date in YYYYMMDD format (SAP internal format, not ISO 8601).
- **MAKTX** — material description text (free text, inconsistent).
- **MATKL** — material group. Clients often use this to classify fuel vs. non-fuel materials.
- **DMBTR / WAERS** — document amount and currency, used for spend-based Scope 3 estimation.

In practice, exports can have German headers if the SAP system language is DE: `Bewegungsart` instead of `BWART`, `Buchungsdatum` instead of `BUDAT`, `Mengeneinheit` instead of `MEINS`. I handle this via a translation dictionary in the parser.

Delimiter varies: some exports use tab, some semicolon, some comma (when exported via Excel). My parser auto-detects.

### What I learned

The hardest problem isn't parsing — it's semantic resolution:
1. **Fuel type** is not a SAP standard field. You have to infer it from `MAKTX` ("Diesel fuel for generators") or `MATKL` (client-defined material groups). This is inherently fragile.
2. **Plant codes** are meaningless without the facility master. "P001" could be Chicago or Pune depending on the client. The `FacilityLookup` table maps these, but it must be pre-populated.
3. **Scope classification by movement type**: 201 (cost center issue) is typically stationary combustion; 261 (production order issue) is often mobile or process combustion. But a client who stores both diesel generator fuel and delivery van fuel as 201 to the same cost center will make this distinction wrong.

### Sample data rationale

My `sap_fuel_procurement.txt` includes:
- Both tab-separated columns and realistic SAP column names (uppercase)
- Movement types 201 (stationary) and 261 (mobile)
- Multiple plant codes (P001=Chicago US, P002=London UK, P003=Munich DE, WERK1=Hamburg DE)
- Mixed currencies (USD, GBP, EUR)
- German material descriptions ("Erdgas Heizkessel", "Benzin Firmenfahrzeuge") alongside English ones
- LPG, natural gas, diesel, petrol, and heavy fuel oil entries (to exercise different emission factors)
- One PROC material group entry (Scope 3 procurement)
- One "UNKNOWN" material (exercises the suspicious-flag path for unrecognised fuel types)
- Quantities in both L and M3 (exercises unit conversion)

### What would break in a real deployment

1. **Plant code lookup gaps**: If a plant code appears in the export but not in `FacilityLookup`, the record has no facility and can't be grid-region-matched for Scope 2. I flag it but still ingest.
2. **Custom movement types**: Some companies use Z-prefix custom movement types (Z01, Z201). My parser only handles standard SAP movement types.
3. **Multi-client SAP (4-digit company code)**: Large enterprises run multiple company codes in one SAP instance. The parser captures BUKRS in `source_extra` but doesn't use it for routing — a client with 20 company codes would need this.
4. **IDoc XML format**: Some integrations use the true IDoc XML format rather than flat file. Completely different parsing required.
5. **Material descriptions in other languages**: My translation dict covers DE/EN. A plant in Japan with JA material descriptions would need extending.

---

## 2. Utility Portal CSV (Electricity)

### What I researched

Major utility portals and their export formats:
- **UK: National Grid, EDF, British Gas Business** — export CSVs from their online portals. Columns vary per portal but typically include account number, meter serial, billing period (start/end), consumption (kWh), read type (actual/estimated), and tariff code.
- **US: PG&E, Con Edison, ComEd** — Green Button CSV download (NAESB REQ.21 standard) or proprietary portal exports. Green Button is an XML standard primarily, but some utilities offer CSV variants.
- **Aggregators: Urjanet, Arcadia** — normalise data from multiple utilities into a standard CSV schema. More consistent but require a paid subscription.

Key challenges I researched:
- **Billing periods don't align to calendar months.** Meters are read on a cycle that shifts by a few days each month. A "January bill" might run 17 Dec → 19 Jan. My sample data includes this explicitly.
- **Estimated reads.** If a meter reader can't access the property, the utility estimates consumption from historical patterns. These should be flagged for analyst attention.
- **Sub-meters.** Large facilities have multiple meters: a main site meter and sub-meters for HVAC, lighting, production equipment. Aggregating all meters for a facility is an analyst task.
- **Units.** Almost always kWh, but some industrial meters report in MWh. Demand charges are reported in kW (not kWh) — my parser skips these.

### Emission factors

I use:
- **UK**: DEFRA 2023 grid intensity: 0.20493 kgCO₂e/kWh (published annually by DEFRA)
- **US regions**: EPA eGRID 2022 (ERCOT: 0.423, WECC: 0.271, RFC: 0.382, SERC: 0.400)
- **EU average**: IEA 2022 (0.276)
- **India**: IEA 2022 (0.708) — included because sample data has a Singapore office (nearby grid context)

For market-based Scope 2, if the CSV contains a renewable percentage column (from a REGO/REC certificate), I scale the emission factor accordingly.

### Sample data rationale

My `utility_electricity.csv` includes:
- Multiple sites (Chicago, London, Munich, Singapore, Hamburg, Amsterdam) matching the SAP plant codes
- Real billing period misalignment: London meter runs 17-Jan to 19-Feb, not calendar months
- One estimated read (Chicago HVAC sub-meter, January) — exercises the suspicion flag
- A TOTAL row at the end — my parser skips it with a keyword check
- Mixed meter IDs and site names (to test column auto-detection)
- Consumption across a realistic range: 18,500 kWh (lighting sub-meter) to 510,000 kWh (main manufacturing)

### What would break in a real deployment

1. **PDF bills**: Some small utilities only send PDF bills. Not handled. Would require a PDF parsing pipeline (Camelot/pdfplumber + layout heuristics), which is fragile.
2. **Portal login automation**: Manually downloading CSVs monthly from 20 utility portals is painful. The right solution is Urjanet/Arcadia integration (automated data collection) or Green Button Connect (push notification when new bill available). Both require infrastructure investment.
3. **Market-based factors with supplier certificates**: If a client has a PPA with a specific renewable generator, the emission factor is not just "0 for green" — it depends on the certificate's additionality and location. REGO/REC accounting is complex and my parser uses a simplified approximation.
4. **Check meters / AMR meters**: Advanced metering infrastructure can produce 15-minute interval data (thousands of rows per meter per year). My parser handles it row-by-row but the volume could be large.
5. **Reactive power and demand charges mixed in CSV**: Some portal exports intermix kWh (consumption) rows with kW (demand) rows. My parser attempts to skip non-consumption rows but could misclassify edge cases.

---

## 3. Corporate Travel (Concur/Navan style CSV)

### What I researched

**Concur Travel** (SAP Concur): The Standard Accounting Extract (SAE) is the most common programmatic export. It's a fixed-format CSV with ~80 columns covering expense report details, trip segments, cost allocations, and approval status. Concur also offers a TripLink feed for bookings made outside Concur.

**Navan (formerly TripActions)**: Reporting tab → Trips provides a CSV with columns including traveler, trip dates, origin, destination, cabin class, cost, and policy compliance flags. More modern and consistent than Concur.

**What I found:**
- Neither platform provides distance — you must calculate it from origin/destination city or airport codes.
- Cabin class is present but encoded differently: Concur uses airline fare codes (Y, B, J, F), Navan uses text ("Economy", "Business"). Both are handled in my normalisation function.
- Hotel rows have check-in and check-out dates, number of nights, and property name. Country is sometimes present, sometimes must be inferred from city.
- Ground transport (car rental, taxi, rideshare) often has neither distance nor meaningful location — only cost and vendor name.
- Some exports mix all trip types in one file; others export flights, hotels, and ground separately. My parser handles both via heuristic type detection.

**Emission factors used:**
- **Flights**: DEFRA 2023, with radiative forcing uplift factor (1.891). Factors differ by haul class (short <1500km, medium 1500-3500km, long >3500km) and cabin class (economy, business 2.6×, first 4.0×).
- **Hotels**: DEFRA 2023, per room-night by region (UK £17, US $14, EU €10, default €12).
- **Ground**: DEFRA 2023 per km. Car rental 0.168, taxi/rideshare 0.149, train 0.035.

**Distance calculation:**
I embedded coordinates for ~50 major airports. Production would use the full IATA database or a geocoding API (like OpenCage or Google Maps). When airport codes are unknown, I flag the record as suspicious and use a medium-haul default (1,500 km).

### Sample data rationale

My `travel_data.csv` includes:
- Flights from recognisable hub airports (ORD, LHR, JFK, CDG) that are in my IATA table — these will calculate correctly
- One flight from XYZ → ABC (unknown codes) — exercises the suspicious flag and distance fallback
- Both economy and business class flights — exercises cabin class multiplier
- Long-haul flights (ORD→LHR, LHR→SIN, ORD→NRT) and short-haul (LHR→CDG, CDG→AMS)
- Hotel entries with check-in/check-out dates and multiple countries (US, GB, FR, SG, JP)
- Car rentals with explicit distance in km
- Taxi entries without distance — exercises cost-based distance estimation
- Train entry with explicit distance (Amsterdam, 180km)

### What would break in a real deployment

1. **IATA airport coverage**: My table has ~50 airports. There are ~9,000 in the IATA database. Flights to/from regional airports (e.g. Manchester MAN, Bangalore BLR, Dallas Love Field DAL) would all fall back to the distance default and be flagged suspicious.
2. **Concur fare class codes**: Concur uses airline fare class letters (Y = economy, C/J = business, F = first). These codes overlap and some airlines use the same letter for different cabins. My normalisation covers the most common patterns but would miss edge cases.
3. **Multi-segment trips**: A trip LHR → CDG → SIN is two segments. If the export shows only origin (LHR) and final destination (SIN), my parser computes the direct great-circle distance — which undercounts the actual distance flown. Concur's segment-level export is better but requires a different data shape.
4. **Personal vs business travel mixing**: If an employee extends a business trip with personal days, the hotel nights should be pro-rated. Concur has flags for this (personal days), but the logic to apply them is business-rule-dependent.
5. **Cost-based distance estimation for taxis**: When no distance is available, I estimate `distance_km = cost × 1.0` (rough $1/km average). This is wrong for premium markets (London black cabs ~£3/km) and cheap markets (Delhi rickshaws ~₹10/km). All such records are flagged suspicious.
