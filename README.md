# EUDR Compliance Automation Agent

**EU Deforestation Regulation (Regulation (EU) 2023/1115) Compliance & TRACES-NT DDS Automation Pipeline**

---

## 📌 Architecture Overview

```
EUDR Supply Chain Payload (JSON)
          │
          ▼
┌─────────────────────────────────────────────────────────────┐
│ 1. TraceabilityCollector (SpatialValidator)                 │
│    - WGS84 bounds check & topological validity (Shapely)    │
│    - EUDR Art. 9(1)(d) 4ha Rule: >=4ha strictly Polygon     │
│    - Geodesic ellipsoid area calculation (pyproj Geod)      │
└──────────────────────────────┬──────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────┐
│ 2. SatelliteComplianceChecker (DeforestationAnalyzer)       │
│    - EUDR Cut-off Baseline: 31 December 2020                │
│    - Hansen GFC / JRC Forest Cover / Sentinel NDVI overlay  │
│    - Post-2020 loss detection -> DEFORESTATION_DETECTED     │
└──────────────────────────────┬──────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────┐
│ 3. LegalDocumentAuditor (LegalAuditor)                      │
│    - EUDR Country Risk Benchmarking (Low / Standard / High) │
│    - Origin legality permits (Land Title, Harvest Permit)   │
│    - FPIC consent & document expiry verification            │
└──────────────────────────────┬──────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────┐
│ 4. DDSGenerator (TRACES-NT DDS Statement)                   │
│    - TRACES-NT submission payload generation                │
│    - Cryptographic digital signature (HMAC-SHA256)          │
│    - Immutable audit trail & execution UUID tracking        │
└─────────────────────────────────────────────────────────────┘
```

---

## 🚀 Quick Start

### 1. Installation

```bash
# Create virtual environment
python -m venv .venv
.\.venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Run API Server

```bash
uvicorn app.main:app --reload --port 8000
```
Swagger UI: `http://localhost:8000/docs`

---

## 🧪 Testing

```bash
pytest -v tests/
```

---

## 📋 API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/v1/eudr/health` | Health check & Cut-off date information |
| `POST` | `/api/v1/eudr/validate-spatial` | Standalone GIS coordinate & 4ha polygon validation |
| `POST` | `/api/v1/eudr/evaluate` | Full end-to-end compliance evaluation & TRACES DDS generator |
