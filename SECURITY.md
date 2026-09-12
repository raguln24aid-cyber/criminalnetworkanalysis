# Security Policy

NEXUS-X handles sensitive investigative data. If you discover a security vulnerability, please report it responsibly.

## Reporting a Vulnerability
- Do **not** open a public GitHub issue for security vulnerabilities.
- Email the maintainer directly with a description of the issue, steps to reproduce, and potential impact.
- Allow a reasonable time for the issue to be assessed and addressed before any public disclosure.

## Scope
- Authentication and authorization bypass
- Evidence ledger tampering or hash-verification bypass
- Injection vulnerabilities (SQL, prompt injection into the LLM copilot, etc.)
- Exposure of secrets (`.env` values, API keys, JWT secrets)

## Supported Versions
Only the `main` branch is actively maintained and receives security fixes.
