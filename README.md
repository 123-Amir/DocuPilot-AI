# DocuPilot AI

**AI-powered invoice processing, purchase order matching, and discrepancy detection.**

DocuPilot AI helps finance and operations teams review invoices against purchase orders, identify potential mismatches, and understand why a case needs attention.

## Problem

Manually checking invoices against purchase orders is repetitive and error-prone. Missing fields, amount differences, and inconsistent document details can slow down invoice processing.

## Solution

DocuPilot AI provides a dashboard to review invoice cases, inspect extracted document data, identify discrepancies, and ask questions about flagged cases.

## Features

- Invoice data extraction using a configurable open-model gateway.
- Invoice and purchase-order matching with deterministic validation rules.
- Discrepancy detection and case review workflows.
- Dashboard with seeded synthetic invoice cases.
- Case-level chat with evidence-grounded explanations and references.
- Document upload and PDF processing, subject to configured limits.
- Optional Alan workflow escalation integration.
- SQLite-backed local application data.
- Automated backend tests.

## Tech Stack

### Backend
- Python
- FastAPI
- SQLite
- Pytest

### Frontend
- React
- TypeScript
- Vite
- Tailwind CSS

### AI integration
- Alan model gateway
- Configurable open models
- Optional Alan workflow escalation

## Project Structure

```text
docupilot-ai/
├── backend/
│   ├── app/
│   ├── samples/
│   ├── scripts/
│   ├── tests/
│   ├── pyproject.toml
│   └── requirements.txt
└── frontend/
    ├── src/
    ├── index.html
    ├── package.json
    └── vite.config.ts
```

## Prerequisites

- Python installed
- Node.js and npm installed
- Git, if cloning the repository

## Local Setup

### 1. Backend

Open PowerShell:

```powershell
cd backend
```

Create and activate a virtual environment if one does not already exist:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

Install dependencies:

```powershell
pip install -r requirements.txt
```

Configure the environment variables according to `.env.example` and the application's configuration. Keep real API keys and tokens in a local, gitignored `.env` file. Never commit credentials.

Start the API server from the `backend` directory:

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Backend URL: http://127.0.0.1:8000

Interactive API documentation: http://127.0.0.1:8000/docs

### 2. Frontend

Open a second PowerShell terminal:

```powershell
cd frontend
npm install
npm run dev
```

Open the local URL printed by Vite in the terminal.

The frontend development server must be able to reach the backend API. Configure the API base URL using the frontend's supported Vite configuration when necessary.

## Environment Configuration

Use `.env.example` as the reference for supported settings.

| Variable | Purpose |
|---|---|
| `ALAN_MODEL_BASE_URL` | Open-model gateway URL |
| `ALAN_MODEL_API_KEY` | Server-side gateway credential |
| `ALAN_MODEL_NAME` | Primary model for extraction and explanations |
| `ALAN_MODEL_FALLBACKS` | Fallback model configuration |
| `ALAN_MODEL_TIMEOUT_SECONDS` | Model request timeout |
| `ALAN_MODEL_MAX_TOKENS` | Maximum model response tokens |
| `ALAN_CONVERSATION_ID` | Optional gateway conversation identifier |
| `ALAN_WORKFLOW_ID` | Alan workflow identifier for escalation |
| `ALAN_TIMEOUT_SECONDS` | Workflow execution timeout |
| `ALAN_POLL_SECONDS` | Workflow status polling interval |
| `DOCUPILOT_AUTO_SEED` | Seed synthetic demo cases on first start |
| `DOCUPILOT_MAX_UPLOAD_MB` | Maximum configured upload size |
| `DOCUPILOT_MAX_PDF_PAGES` | Maximum configured PDF page count |
| `DOCUPILOT_DISABLE_MODEL` | Disable model calls and use deterministic fixtures |

Never expose API keys in frontend code, screenshots, public issues, or committed environment files.

## API Endpoints

The backend exposes API routes for health checks, dashboard data, purchase orders, cases, documents, review actions, case chat, and optional Alan investigations.

Useful starting points:

- `GET /api/health`
- `GET /api/dashboard`
- `GET /api/purchase-orders`
- `GET /api/cases`
- `GET /api/cases/{case_id}`
- `POST /api/documents`
- `POST /api/cases/{case_id}/review`
- `GET /api/cases/{case_id}/messages`
- `POST /api/cases/{case_id}/chat`

For the exact request and response schemas, run the backend and visit `/docs`.

## Testing

Run backend tests from the `backend` directory:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

Build the frontend from the `frontend` directory:

```powershell
npm run build
```

## Demo Data and Privacy

The bundled sample documents are synthetic demo data. Use synthetic or otherwise authorized documents for demonstrations. Do not upload confidential invoices, customer information, or proprietary company documents to a public demo.

## Alan Workflow Status

The model gateway integration has been tested at the service level. Model availability and latency depend on the upstream provider.

**Alan workflow escalation requires separate workflow configuration.** Set `ALAN_WORKFLOW_ID` and the required integration credentials only after configuring the corresponding workflow. Until a successful end-to-end execution is verified, this capability should be treated as optional and not demonstrated as a confirmed working workflow.

## Current Limitations

- Upstream model failures may cause extraction requests to fall back to a configured model or fixture behavior.
- Real model responses can be slower than deterministic fixture processing.
- Alan workflow escalation is not considered operational until configured and verified end to end.
- Local development instructions do not imply that the application has been deployed publicly.

## Roadmap

- Complete and verify the Alan workflow escalation path.
- Improve resilience to upstream model failures.
- Add further invoice validation and review scenarios.
- Prepare a public demo deployment with safe synthetic data.

## License

Add the intended open-source license before public release. Do not claim a license until the repository contains the corresponding license file.
