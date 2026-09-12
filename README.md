# NEXUS-X

![License](https://img.shields.io/badge/license-MIT-blue.svg)
![Backend](https://img.shields.io/badge/backend-FastAPI-009688.svg)
![Frontend](https://img.shields.io/badge/frontend-React%20%2B%20Vite-61DAFB.svg)

**Neural Evidence & eXplainable Unified Surveillance Intelligence eXchange**

"From fragmented evidence to explainable temporal intelligence."

## Overview
NEXUS-X is an AI-powered Criminal Network Analysis System built for the Ministry of Home Affairs (NCRB). It is an **investigation decision-support system** that ingests fragmented data, builds an evidence-aware temporal graph, and utilizes AI to discover hidden links, behavioral anomalies, and contradictions.

## Features
- **Temporal Graph Reconstuction**: View how the network evolves over time.
- **Evidence Ledger**: Tamper-evident cryptographic SHA-256 hashes for all evidence.
- **Intelligence Engine**: Calculates node importance, hidden links, and network contradictions.
- **Investigation Copilot**: Groq-powered natural language queries against the evidence graph.
- **IIG Ranking**: Investigation Information Gain scoring to prioritize next steps.

## Tech Stack
- Frontend: React, Vite, TailwindCSS, React Flow, Recharts
- Backend: FastAPI, SQLAlchemy, SQLite, NetworkX, Groq SDK

## Project Structure
```
nexus-x/
├── backend/
│   ├── app/
│   │   ├── agents/        # Agent workflow/state machine for ingestion
│   │   ├── api/           # FastAPI route handlers
│   │   ├── evidence/      # Tamper-evident evidence ledger
│   │   ├── models/        # SQLAlchemy ORM models
│   │   ├── prompts/       # LLM prompt templates
│   │   ├── schemas/       # Pydantic request/response schemas
│   │   ├── security/      # Auth and request dependencies
│   │   └── services/      # Graph, intelligence, extraction, and audit services
│   ├── data/synthetic/    # Demo data generator
│   └── scripts/           # Admin/ops scripts
├── frontend/
│   └── src/
│       ├── api/           # API client
│       ├── components/    # Shared UI (layout, sidebar)
│       └── pages/         # Command center, network explorer, copilot, etc.
└── deploy/                # Caddy config, VM/app setup scripts, deployment guide
```

## Setup & Running Locally

### 1. Backend Setup
```bash
cd backend
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python data/synthetic/generate_data.py
uvicorn app.main:app --reload
```
The backend will run on `http://localhost:8000`.

### 2. Frontend Setup
```bash
cd frontend
npm install
npm run dev
```
The frontend will run on `http://localhost:3000`.

### 3. Demo Data
The synthetic data generator (`generate_data.py`)





 automatically populates the SQLite database with 50+ entities, relationships, events, and evidence objects to demonstrate hidden links, contradictions, and structural node importance.

## Environment Variables (.env)
Create a `.env` in the `backend/` folder:
```env
PROJECT_NAME="NEXUS-X"
SECRET_KEY="supersecretkey"
DATABASE_URL="sqlite:///./nexus.db"
GROQ_API_KEY="your_groq_api_key_here"
GROQ_MODEL="llama3-8b-8192"
```

## Testing
```bash
cd backend
pip install -r requirements-dev.txt
pytest
```

## Roadmap
- [ ] Role-based access control for multi-agency investigations
- [ ] Export investigation reports (PDF) with the evidence chain attached
- [ ] Real-time collaborative graph annotation
- [ ] Support for additional LLM providers alongside Groq

## Notice
AI-generated relationships are investigative leads, not proof of criminal activity. Final decisions require authorized human investigation and verification.
