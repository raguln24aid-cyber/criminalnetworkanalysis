# Changelog

All notable changes to NEXUS-X are documented in this file.

## [Unreleased]
### Added
- Project governance docs: LICENSE (MIT), CONTRIBUTING.md, CODE_OF_CONDUCT.md, SECURITY.md.
- GitHub issue templates (bug report, feature request) and a pull request template.
- Basic CI workflow (backend syntax check, frontend build).
- `docs/ARCHITECTURE.md` and `docs/API.md`.
- Pinned tool versions (`.python-version`, `.nvmrc`) and a `Makefile` for common dev commands.
- README badges, Project Structure, and Roadmap sections.

## [0.1.0] - 2026-09-12
### Added
- Initial release: FastAPI backend with temporal graph reconstruction, evidence ledger, intelligence engine, and investigation copilot.
- React + Vite + TailwindCSS frontend: command center, network explorer, evidence explorer, intelligence, copilot, data ingestion, and audit log pages.
- Synthetic data generator for demo investigations.
- Deployment configs: Docker Compose, Caddy reverse proxy, systemd service unit, VM setup scripts.
