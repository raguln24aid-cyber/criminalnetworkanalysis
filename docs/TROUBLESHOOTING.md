# Troubleshooting

## Backend won't start
- Confirm Python 3.11 is active (`python --version`), matching `backend/.python-version`.
- Make sure dependencies are installed: `pip install -r backend/requirements.txt`.
- Check that `backend/.env` exists and is filled in (copy from `backend/.env.example`).

## "GROQ_API_KEY not set" or copilot queries fail
- Set `GROQ_API_KEY` in `backend/.env`. Get a key from the Groq console.
- Confirm `GROQ_MODEL` matches a model your key has access to.

## Frontend fails to reach the backend
- Confirm the backend is running on `http://localhost:8000`.
- Check `frontend/src/api/client.js` for the configured base URL.
- Look for CORS errors in the browser console — the backend must allow the frontend's origin.

## Empty graph / no demo data
- Run the synthetic data generator: `python backend/data/synthetic/generate_data.py` (or `make seed`).

## `npm install` fails
- Confirm Node 20 is active (`node --version`), matching `frontend/.nvmrc`.
- Delete `frontend/node_modules` and `package-lock.json` conflicts, then retry `npm install`.
