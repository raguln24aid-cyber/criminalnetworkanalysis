#!/bin/bash
# Run from /opt/nexus-x after the project code has been copied there and
# setup_vm.sh has already run. Idempotent - safe to re-run after a `git pull`.
set -euo pipefail
cd "$(dirname "$0")/.."

echo "=== Starting local Neo4j container (same setup as local dev) ==="
if [ ! "$(docker ps -aq -f name=nexus-neo4j)" ]; then
  read -sp "Set a Neo4j password: " NEO4J_PW
  echo ""
  docker run -d \
    --name nexus-neo4j \
    --restart unless-stopped \
    -p 127.0.0.1:7474:7474 -p 127.0.0.1:7687:7687 \
    -e NEO4J_AUTH="neo4j/${NEO4J_PW}" \
    -v nexus_neo4j_data:/data \
    -v nexus_neo4j_logs:/logs \
    neo4j:5
  echo "NEO4J_PASSWORD=${NEO4J_PW}  <-- put this in backend/.env"
else
  echo "nexus-neo4j container already exists, leaving it as-is."
fi
# Bound to 127.0.0.1 only - Neo4j's bolt/http ports are never exposed to the
# public internet, only reachable from the backend running on the same VM.

echo "=== Setting up backend venv ==="
cd backend
python3.11 -m venv venv
./venv/bin/pip install --upgrade pip
./venv/bin/pip install -r requirements.txt

if [ ! -f .env ]; then
  echo ""
  echo "!!! backend/.env does not exist yet. Copy .env.example to .env and fill in:"
  echo "    SECRET_KEY, GROQ_API_KEY, NEO4J_PASSWORD (from above), CORS_ORIGINS (your real domain)"
  echo "    Then re-run this script, or just continue manually from here."
  exit 1
fi

echo "=== Building frontend for production ==="
cd ../frontend
npm install
npm run build
# dist/ is what Caddy serves - VITE_API_URL must be set (in frontend/.env.production
# or the shell environment) to your real public https://domain BEFORE this build step,
# since Vite bakes it in at build time, not read at runtime.

echo ""
echo "=== Done. Remaining manual steps: ==="
echo "1. sudo cp /opt/nexus-x/backend/nexus-backend.service /etc/systemd/system/"
echo "   sudo systemctl daemon-reload && sudo systemctl enable --now nexus-backend"
echo "2. ./venv/bin/python scripts/create_admin.py   (run from backend/, real TTY so this works fine over SSH)"
echo "3. sudo cp /opt/nexus-x/deploy/Caddyfile /etc/caddy/Caddyfile   (edit the domain first!)"
echo "   sudo systemctl reload caddy"
