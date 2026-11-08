# MORS AEGIS scientific prototype (Python)

This local FastAPI application has a persistent scientific-data archive, NASA NTRS citation harvesting, NASA FIRMS thermal-anomaly observations, and date-specific NASA GIBS imagery. It is separate from the Node-based MORS AEGIS GitHub repository.

## Run on Windows

1. Install and start Docker Desktop.
2. Keep `.env` local. Set a strong `AEGIS_ACCESS_TOKEN`; add `NASA_FIRMS_MAP_KEY` for FIRMS requests. NASA NTRS and GIBS public endpoints do not need that FIRMS key.
3. Run `docker compose up -d --build` from this directory.
4. Open `http://127.0.0.1:<AEGIS_PORT>` and authenticate with the configured access token.

Docker Compose binds only to loopback. The named `aegis-data` volume persists `/app/data/aegis.db`, user uploads, and content-addressed provider responses in `/app/data/raw`. Do not mount this SQLite database into multiple application replicas.

## Scientific archive

- `raw_assets` is the immutable content-addressed inventory: exact source bytes, SHA-256, content type, provider, request metadata, validation status and record count.
- `raw_ingestions` records every acquisition event even when duplicate response bytes reuse the same content object.
- `fire_observations` stores normalized FIRMS point detections with UTC acquisition time, coordinates, source product, satellite/instrument, quality fields, FRP and source-row JSON. MODIS and VIIRS product identity is retained.
- `research_records` stores NASA NTRS identifiers, titles, abstracts, dates, categories, source links and associated raw-response hashes.
- `scientific_observations` supports measurements with UTC, coordinates, optional altitude / x-y-z and coordinate frame, value/unit, uncertainty, evidence class, method and provenance.
- `fire_cause_records` only represents independently sourced investigations. FIRMS hotspots and imagery do not establish fire causes.
- `prevention_guidance` includes source and geographic scope. Current entries are California guidance and should not be treated as universal instructions.

Raw source objects are stored separately from normalized/indexed rows. Time-series analysis uses UTC observation records; Earth coordinates use EPSG:4326; 3D coordinates require a declared frame and units. Space-time analysis provides daily detection counts and reports FRP against brightness temperature in their source units. Equations and denominators are shown in the Space-Time Explorer. No physical combustion measurements are generated from satellite hotspots.

Use **Raw Data Vault** to request and archive up to 50 NASA NTRS citation/abstract records per search, search local records, and download exact provider responses. Use **Earth Fire Observatory** to retrieve a bounded FIRMS area (requires a valid MAP_KEY) and request an actual date/region NASA GIBS corrected-reflectance snapshot. Use **Space-Time Explorer** to query only archived FIRMS records, plot computed daily counts and available FRP/brightness pairs, inspect rows and export the current page.

## Data and scientific limits

- The application starts with a small curated NTRS catalog and prevention notes. It does **not** ship with a large NASA raw microgravity measurement collection. NTRS harvesting adds catalog metadata and abstracts, not original measurements or PDFs.
- GIBS images are date-specific NASA visualization imagery (corrected reflectance), not raw satellite granules. FIRMS points are thermal anomalies, not confirmed fire boundaries or ground-confirmed causes.
- FIRMS requests are bounded to one product and a small area/date window; source record, confidence, quality, FRP and timestamps remain associated with each detection.
- Uploaded CSV data is user-supplied and unverified. RGB segmentation is exploratory and cannot measure temperature or physical size without calibration.
- The AI provider is Ollama when configured. AI responses do not replace deterministic calculations or establish findings.

## Storage and production deployment

Current storage is SQLite in WAL mode plus files in a persistent Docker volume. This is appropriate for a single local process and moderate append-only archive growth, not a shared multi-worker production service. SQLite and a local filesystem do not provide safe concurrent writes from multiple replicas, high-availability failover, or shared object access. Before exposing a real server, migrate metadata/observations to PostgreSQL (PostGIS for spatial queries), move raw objects to durable object storage, configure backups and retention, add server-side rate limits and authentication, and load-test realistic data volumes. No production server capacity or durability target has been measured.

## Verification

`docker compose build` and `docker compose up -d` build and start the local service. `GET /api/health` is a public readiness endpoint; data and management APIs require the local owner session/token. The repository test suite is in `tests/` and can be run with the documented test image target if desired.

See [docs/SCIENTIFIC_DATA_PLATFORM.md](docs/SCIENTIFIC_DATA_PLATFORM.md) for the schema, time/space representation, data ingestion contract, scientific boundaries and deployment risks.
