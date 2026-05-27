# Breathe ESG — Emissions Ingestion Prototype

Django REST + React app for ingesting, normalising, and reviewing Scope 1/2/3 emissions data from SAP, utility portals, and corporate travel platforms.

## Credentials (demo)

| Role    | Username  | Password   |
|---------|-----------|------------|
| Analyst | `analyst` | `demo1234` |
| Admin   | `admin`   | `admin1234`|

---

## Local setup

### Backend

```bash
cd backend
python -m venv venv
source venv/bin/activate         # Windows: venv\Scripts\activate
pip install -r requirements.txt
python manage.py migrate
python seed.py                   # Creates demo users, tenant, and facilities
python manage.py runserver
```

Backend runs at http://localhost:8000

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Frontend runs at http://localhost:5173 (proxies /api → :8000)

---

## Testing ingestion

Sample files are in `backend/sample_data/`. Upload them via the **Ingest Data** page in the UI, or via curl:

```bash
# SAP flat file
curl -X POST http://localhost:8000/api/ingestion/upload/ \
  -H "Authorization: Token <your-token>" \
  -F "file=@backend/sample_data/sap_fuel_procurement.txt" \
  -F "source_type=sap_flat_file" \
  -F "tenant=<tenant-uuid>"

# Utility CSV
curl -X POST http://localhost:8000/api/ingestion/upload/ \
  -H "Authorization: Token <your-token>" \
  -F "file=@backend/sample_data/utility_electricity.csv" \
  -F "source_type=utility_csv" \
  -F "grid_region=UK" \
  -F "tenant=<tenant-uuid>"

# Travel CSV
curl -X POST http://localhost:8000/api/ingestion/upload/ \
  -H "Authorization: Token <your-token>" \
  -F "file=@backend/sample_data/travel_data.csv" \
  -F "source_type=travel_csv" \
  -F "tenant=<tenant-uuid>"
```

Get your token from `POST /api/auth/login/` with `{"username": "analyst", "password": "demo1234"}`.

---

## Key API endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/auth/login/` | Get auth token |
| GET  | `/api/auth/me/` | Current user + tenants |
| POST | `/api/ingestion/upload/` | Upload source file |
| GET  | `/api/emissions/records/` | List emission records (filterable) |
| POST | `/api/emissions/records/{id}/review/` | Approve/reject/flag a record |
| POST | `/api/emissions/records/bulk_approve/` | Bulk approve selected records |
| GET  | `/api/emissions/records/summary/` | Aggregated dashboard data |
| GET  | `/api/emissions/batches/` | Ingestion batch history |
| GET/POST/PUT | `/api/emissions/facilities/` | SAP plant code → facility lookup |

---

## Project structure

```
breathe_esg/
├── backend/
│   ├── breathe_esg/         Django project settings, URLs, WSGI
│   ├── emissions/           Core models: EmissionRecord, IngestionBatch, Tenant
│   ├── ingestion/           Upload endpoint + parsers
│   │   └── parsers/
│   │       ├── sap_parser.py
│   │       ├── utility_parser.py
│   │       └── travel_parser.py
│   ├── users/               Auth views (login, me)
│   ├── audit/               Placeholder (future audit export)
│   ├── sample_data/         Test files for all three sources
│   └── seed.py              Demo data setup script
├── frontend/
│   └── src/
│       ├── pages/           Dashboard, Review, Upload, Batches
│       ├── components/      Layout (sidebar nav)
│       ├── hooks/           useAuth (React Context)
│       └── api/             Axios client
└── docs/
    ├── MODEL.md             Data model + design decisions
    ├── DECISIONS.md         Ambiguity resolution
    ├── TRADEOFFS.md         Deliberate omissions
    └── SOURCES.md           Per-source research and sample data rationale
```

---

## Deployment (Render)

1. Push repo to GitHub (can be private — share with saurav@, rahul@, shivang@ at breatheesg.com)
2. Create a new **Web Service** on Render
3. Set build command: `cd backend && pip install -r requirements.txt && python manage.py collectstatic --noinput && python manage.py migrate && python seed.py`
4. Set start command: `cd backend && gunicorn breathe_esg.wsgi:application --bind 0.0.0.0:$PORT`
5. Add env vars: `SECRET_KEY` (generate), `DEBUG=False`, `ALLOWED_HOSTS=.onrender.com`

The frontend is built into Django's static files via WhiteNoise — no separate Vercel deployment needed.

To include the React build in Django static files, first run:
```bash
cd frontend && npm run build
# Then copy dist/ to backend/static/frontend/ and configure Django to serve index.html for non-/api/ routes
```

---

## Documentation

- **MODEL.md** — Data model design, multi-tenancy, audit trail, unit normalisation
- **DECISIONS.md** — Every ambiguity resolved (SAP format choice, utility CSV vs PDF, etc.)
- **TRADEOFFS.md** — RBAC, async processing, emission factor versioning
- **SOURCES.md** — Per-source research, sample data rationale, production failure modes
