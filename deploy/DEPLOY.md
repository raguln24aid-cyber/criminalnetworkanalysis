# Deploying NEXUS-X to GCP

Architecture: **one Compute Engine VM** runs everything — the FastAPI backend
(systemd), Neo4j (Docker, bound to localhost only), and Caddy serving the
built frontend + reverse-proxying `/api` to the backend on the same origin
(so there's no cross-origin CORS to configure). This mirrors what already
runs locally, and avoids depending on a free-tier managed service that can
disappear (as the Aura instance did).

Estimated cost: an `e2-medium` VM is ~$25/mo on-demand, but a new GCP account
gets $300 in free credit for 90 days — comfortably covers a hackathon
deployment.

## 0. Prerequisites

- A GCP account and a project created (console.cloud.google.com)
- Use **Cloud Shell** (the `>_` icon in the GCP Console) — `gcloud` is
  pre-installed and pre-authenticated there, no local setup needed.

## 1. Create the VM

```bash
gcloud config set project YOUR_PROJECT_ID

# Reserve a static IP so it never changes on restart
gcloud compute addresses create nexus-x-ip --region=us-central1

# Get the reserved IP address (you'll need it below)
gcloud compute addresses describe nexus-x-ip --region=us-central1 --format="get(address)"

# Create the VM
gcloud compute instances create nexus-x-vm \
  --zone=us-central1-a \
  --machine-type=e2-medium \
  --image-family=ubuntu-2204-lts \
  --image-project=ubuntu-os-cloud \
  --address=nexus-x-ip \
  --boot-disk-size=30GB \
  --tags=http-server,https-server

# Open the firewall for web traffic (SSH is open by default)
gcloud compute firewall-rules create allow-http-https \
  --allow=tcp:80,tcp:443 \
  --target-tags=http-server,https-server
```

## 2. Copy the project onto the VM

From your local machine (not Cloud Shell, unless you upload the project to
Cloud Shell's storage first):

```bash
gcloud compute scp --recurse "nexus-x" nexus-x-vm:/tmp/nexus-x --zone=us-central1-a
```

Then SSH in and move it into place:

```bash
gcloud compute ssh nexus-x-vm --zone=us-central1-a
sudo mkdir -p /opt/nexus-x
sudo mv /tmp/nexus-x/* /opt/nexus-x/
sudo chown -R $USER:$USER /opt/nexus-x
```

(For ongoing updates later, push this project to a private GitHub repo and
`git pull` on the VM instead of re-copying every time.)

## 3. Run the setup scripts (on the VM, over SSH)

```bash
cd /opt/nexus-x
chmod +x deploy/*.sh
./deploy/setup_vm.sh          # installs Docker, Python 3.11, Node 20, Caddy
# log out and back in once (so your user picks up the docker group), then:
cp backend/.env.example backend/.env
nano backend/.env             # fill in SECRET_KEY, GROQ_API_KEY, CORS_ORIGINS=https://<your domain>
./deploy/setup_app.sh         # starts Neo4j, sets up venv, builds frontend
```

`setup_app.sh` will print a generated Neo4j password the first time — put it
in `backend/.env` as `NEO4J_PASSWORD`, then re-run `./deploy/setup_app.sh`.

**Before building the frontend**, set the real public URL it should call:

```bash
echo "VITE_API_URL=https://YOUR_DOMAIN_OR_SSLIP_HOST" > frontend/.env.production
```
(Vite bakes this in at build time — `setup_app.sh`'s `npm run build` step
needs this file to already exist.)

## 4. Start the backend as a real service

```bash
sudo cp backend/nexus-backend.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now nexus-backend
sudo systemctl status nexus-backend     # should show "active (running)"
```

## 5. Create the admin account

```bash
cd /opt/nexus-x/backend
./venv/bin/python scripts/create_admin.py
```
This is a real SSH terminal, so the hidden-password prompt works normally
(unlike in a sandboxed non-interactive shell).

## 6. Point Caddy at your domain and go live

If you have a domain: create an `A` record pointing it at the static IP from
step 1. If not, use `sslip.io` — no DNS setup needed, e.g. for IP
`34.123.45.67` your host is `34-123-45-67.sslip.io`.

```bash
sudo nano /etc/caddy/Caddyfile     # paste deploy/Caddyfile, replace the placeholder host
sudo systemctl reload caddy
```

Rebuild the frontend once more now that you know the real host (if you used
sslip.io and didn't know the IP yet in step 3):

```bash
cd /opt/nexus-x/frontend && npm run build
```

Visit `https://YOUR_DOMAIN_OR_SSLIP_HOST` — Caddy issues a real Let's
Encrypt certificate automatically on first request.

## 7. Verify

```bash
curl -s https://YOUR_DOMAIN_OR_SSLIP_HOST/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"<your admin>","password":"<your password>"}'
```
Should return a token. Then open the site in a browser and log in for real.

## Updating after code changes

```bash
# on the VM
cd /opt/nexus-x
git pull                                   # or re-scp
cd backend && ./venv/bin/pip install -r requirements.txt
sudo systemctl restart nexus-backend
cd ../frontend && npm install && npm run build
```

## Notes / limitations of this setup

- **SQLite** (`nexus.db`) lives on the VM's disk — fine for a single-VM
  hackathon deployment, but it won't survive if you ever move to multiple
  backend instances. If this becomes a real multi-instance deployment later,
  migrate `DATABASE_URL` to a managed Postgres (Cloud SQL) — the app already
  goes through SQLAlchemy, so this is a config change plus installing
  `psycopg2-binary`, not a rewrite.
- **Back up the VM disk** (`gcloud compute disks snapshot`) before major
  changes — that's your evidence chain and case data.
- Neo4j and the backend are bound to `127.0.0.1` only; Caddy is the only
  process exposed to the internet. Don't open ports 7474/7687/8000 in the
  firewall.
- Stopping the VM (`gcloud compute instances stop`) when not actively
  demoing avoids ongoing charges outside your free credit window.
