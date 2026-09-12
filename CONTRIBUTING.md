# Contributing to NEXUS-X

Thanks for your interest in improving NEXUS-X. This guide covers the basics for getting a change in.

## Getting Started
1. Fork the repository and clone your fork.
2. Follow the [Setup & Running Locally](README.md#setup--running-locally) instructions in the README to get the backend and frontend running.
3. Create a feature branch off `main`: `git checkout -b feature/your-change`.

## Development Guidelines
- **Backend** (`backend/`): FastAPI + SQLAlchemy. Keep route handlers thin; put business logic in `app/services/`.
- **Frontend** (`frontend/`): React + Vite + TailwindCSS. New pages go in `src/pages/`, shared UI in `src/components/`.
- Never commit real secrets. Copy `backend/.env.example` to `backend/.env` for local values.
- Keep commits focused — one logical change per commit, with a clear message.

## Submitting Changes
1. Make sure the backend starts (`uvicorn app.main:app --reload`) and the frontend builds (`npm run build`) without errors.
2. Open a pull request against `main` describing what changed and why.
3. Link any related issue in the PR description.

## Reporting Issues
Use the bug report template when filing an issue, and include steps to reproduce where possible.
