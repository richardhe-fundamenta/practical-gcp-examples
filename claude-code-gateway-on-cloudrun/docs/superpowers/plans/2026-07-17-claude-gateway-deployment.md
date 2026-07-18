# Claude Code Gateway on Cloud Run Implementation Plan (PSC Mode)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deploy a secure, private-network Claude Apps Gateway to Google Cloud Run and route traffic privately from a GCP Cloud Workstation using Private Service Connect (PSC) for Google APIs.

**Architecture:** The gateway container runs the Bun-compiled native `claude gateway` service inside Google Cloud Run with ingress set to `internal`. Session state is persisted in a private-IP Cloud SQL PostgreSQL instance using Direct VPC Egress. The GCP Cloud Workstation connects to the gateway privately by routing the `*.run.app` domain name through a Private Service Connect (PSC) endpoint IP (`10.0.0.100`) mapped in `/etc/hosts`.

**Tech Stack:** Google Cloud Run, Cloud SQL for PostgreSQL, Google Secret Manager, Private Service Connect (PSC), VPC Peering, Claude Code CLI (gateway subcommand), Google Workspace OIDC.

## Global Constraints

- GCP Project ID: `rocketech-de-pgcp-sandbox`
- GCP Compute Region: `us-east5` (Model Garden regional publisher for Claude models)
- Docker Build Platform: `linux/amd64` (forced architecture constraint for Cloud Run runtime)
- Cloud Run Ingress Mode: `internal` (restrict ingress strictly to the VPC network)
- PSC Endpoint IP: `10.0.0.100` (reserved private IP in the VPC subnet)

---

### Task 1: Setup Local Config and Environment Variables

**Files:**
- Create: `env.sh`
- Create: `gateway.yaml` (from template)
- Modify: `.gitignore`

**Interfaces:**
- Consumes: `gateway.yaml.example`
- Produces: `env.sh` (shell config for deployments), `gateway.yaml` (gateway config settings)

- [ ] **Step 1: Check gitignore for secret safety**
Ensure local secret configs are ignored so they are never committed.
Run:
```bash
grep -q "gateway.yaml" .gitignore || echo "gateway.yaml" >> .gitignore
grep -q "env.sh" .gitignore || echo "env.sh" >> .gitignore
```
Expected: `gateway.yaml` and `env.sh` are appended to `.gitignore`.

- [ ] **Step 2: Create env.sh configuration script**
Create the environment configuration file `env.sh` containing the deployment settings.
Write `env.sh`:
```bash
#!/usr/bin/env bash
export PROJECT_ID="rocketech-de-pgcp-sandbox"
export REGION="us-east5"
export DEPLOY="0" # First pass only provisions infrastructure
export INGRESS="internal"
export GATEWAY_YAML="./gateway.yaml"
```
Run:
```bash
chmod +x env.sh
```

- [ ] **Step 3: Copy configuration template**
Create your active config file from the template.
Run:
```bash
cp gateway.yaml.example gateway.yaml
```

- [ ] **Step 4: Verify files exist**
Verify both local configurations exist.
Run:
```bash
ls -la env.sh gateway.yaml
```
Expected: Both files are present.

- [ ] **Step 5: Commit changes**
Commit `.gitignore` updates.
Run:
```bash
git add .gitignore
git commit -m "chore: ignore local secret settings"
```

---

### Task 2: Configure Workspace OIDC and OAuth Credentials

**Files:**
- Modify: `gateway.yaml`

**Interfaces:**
- Consumes: Google Workspace OAuth credentials
- Produces: Configured `gateway.yaml` with Project ID, Client ID, and Allowed Domains

- [ ] **Step 1: Configure gateway.yaml upstreams and OIDC**
Edit `gateway.yaml` to fill in Google Workspace client configurations and upstreams.
Use a text replace tool or editor to modify `gateway.yaml` lines:
- Replace `client_id: REPLACE_ME` with your actual Google Workspace OAuth Client ID.
- Replace `allowed_email_domains: [REPLACE_ME]` with your email domain, e.g., `[rocketech.co.uk]`.
- Replace `project_id: REPLACE_ME` under `upstreams` with `rocketech-de-pgcp-sandbox`.
- Replace `region: us-east5` under `upstreams` with `us-east5`.

- [ ] **Step 2: Verify REPLACE_ME values are gone**
Verify that all active `REPLACE_ME` strings have been replaced in `gateway.yaml`.
Run:
```bash
grep -vE '^[[:space:]]*#' gateway.yaml | grep -q 'REPLACE_ME' && echo "FAIL" || echo "PASS"
```
Expected: Output is `PASS`.

- [ ] **Step 3: Commit updates**
Commit the template changes.
Run:
```bash
git add Dockerfile gateway.yaml.example setup.sh
git commit -m "feat: import gateway base setup assets"
```

---

### Task 3: First Pass Provisioning (Infrastructure Only)

**Files:**
- Create: `setup.sh` (executes setup)

**Interfaces:**
- Consumes: `env.sh`, `gateway.yaml`, local Docker/gcloud session
- Produces: VPC network, subnets, PSA Peering, Cloud SQL PostgreSQL database, Secret Manager Secrets, and Built Gateway Docker Image

- [ ] **Step 1: Run setup.sh first-pass**
Run `setup.sh` with `DEPLOY=0` to create base infrastructure and databases. This will skip the Cloud Run deployment until OIDC secrets are loaded.
Run:
```bash
source ./env.sh
./setup.sh
```
Expected: The script provisions APIs, VPC networks, Cloud SQL, Secret Manager, downloads the binary, builds the container, and exits saying: `Skipping Cloud Run deploy (DEPLOY=0)`.

- [ ] **Step 2: Verify PostgreSQL connection secret exists**
Confirm Secret Manager has stored the SQL connection URL.
Run:
```bash
gcloud secrets versions describe latest --secret="gateway-postgres-url" --project="rocketech-de-pgcp-sandbox"
```
Expected: Status is `ENABLED`.

- [ ] **Step 3: Verify Container Image exists in Artifact Registry**
Confirm the gateway Docker image is built and pushed.
Run:
```bash
gcloud artifacts docker images list us-east5-docker.pkg.dev/rocketech-de-pgcp-sandbox/claude-gateway/gateway
```
Expected: Output lists the gateway image with a version tag.

---

### Task 4: Configure Private Service Connect (PSC) for Google APIs

**Files:**
- None (GCP CLI Commands)

**Interfaces:**
- Consumes: Deployed VPC network `cc-gateway-vpc`
- Produces: Global PSC endpoint forwarding rule at `10.0.0.100`

- [ ] **Step 1: Reserve PSC IP Address**
Reserve a private IP address `10.0.0.100` within the VPC for routing Google API requests.
Run:
```bash
gcloud compute addresses create psc-google-apis \
  --global \
  --purpose=PRIVATE_SERVICE_CONNECT \
  --addresses=10.0.0.100 \
  --network=cc-gateway-vpc \
  --project="rocketech-de-pgcp-sandbox"
```
Expected: Address resource `psc-google-apis` is successfully created with IP `10.0.0.100`.

- [ ] **Step 2: Create PSC Forwarding Rule**
Create the forwarding rule to route traffic addressed to `10.0.0.100` directly to Google's internal APIs.
Run:
```bash
gcloud compute forwarding-rules create psc-google-apis-fw \
  --global \
  --network=cc-gateway-vpc \
  --address=psc-google-apis \
  --target-google-apis-bundle=all-apis \
  --project="rocketech-de-pgcp-sandbox"
```
Expected: Forwarding rule `psc-google-apis-fw` is successfully created.

- [ ] **Step 3: Verify Forwarding Rule**
Verify that the forwarding rule is active.
Run:
```bash
gcloud compute forwarding-rules describe psc-google-apis-fw --global --project="rocketech-de-pgcp-sandbox"
```
Expected: Output displays details of the forwarding rule pointing to `all-apis`.

---

### Task 5: Store OAuth Client Secret and Deploy Cloud Run (Second Pass)

**Files:**
- Modify: `env.sh`
- Modify: `gateway.yaml`

**Interfaces:**
- Consumes: Google Workspace OAuth client secret
- Produces: Populated Secret Manager secrets, Deployed Cloud Run service

- [ ] **Step 1: Save OAuth Client Secret to Secret Manager**
Store your Workspace Client Secret securely in Secret Manager so the Cloud Run instance can load it.
Run:
```bash
printf '%s' "YOUR_GOOGLE_WORKSPACE_OAUTH_CLIENT_SECRET" | gcloud secrets create gateway-oidc-client-secret \
  --replication-policy=automatic --data-file=- --project="rocketech-de-pgcp-sandbox"
```
Expected: Output shows created secret version details.

- [ ] **Step 2: Update env.sh to deploy**
Enable Cloud Run deployments on subsequent script runs.
Modify `env.sh`:
```bash
#!/usr/bin/env bash
export PROJECT_ID="rocketech-de-pgcp-sandbox"
export REGION="us-east5"
export DEPLOY="1" # Deploy is enabled
export INGRESS="internal"
export GATEWAY_YAML="./gateway.yaml"
```

- [ ] **Step 3: Execute Cloud Run Deployment**
Run the setup script again. Since `DEPLOY=1` and secrets exist, it will trigger `gcloud run deploy`.
Run:
```bash
source ./env.sh
./setup.sh
```
Expected: Output displays Cloud Run service details and provides a `status.url` matching `https://claude-gateway-xxxxxx.a.run.app`.

- [ ] **Step 4: Update gateway.yaml public URL**
Set the `public_url` parameter in `gateway.yaml` to the real Cloud Run URL returned by step 3.
Modify `gateway.yaml`:
```yaml
listen:
  host: 0.0.0.0
  port: 8080
  public_url: https://claude-gateway-xxxxxx.a.run.app   # REPLACE with your real status.url
```

- [ ] **Step 5: Redeploy with updated configuration**
Trigger the final redeploy so the gateway environment publishes the matching config secret.
Run:
```bash
source ./env.sh
./setup.sh
```
Expected: The service updates configuration successfully with matching public URL endpoints.

---

### Task 6: Cloud Workstation Routing & Verification

**Files:**
- Modify: `/etc/hosts` (on Cloud Workstation)

**Interfaces:**
- Consumes: Cloud Run service URL
- Produces: Private DNS resolution of `*.run.app` inside the Workstation environment

- [ ] **Step 1: Map DNS locally on Cloud Workstation**
Open the terminal inside your Cloud Workstation instance and add a static DNS mapping pointing the Cloud Run domain name to the PSC IP.
Run:
```bash
echo "10.0.0.100  claude-gateway-xxxxxx.a.run.app" | sudo tee -a /etc/hosts
```
*(Replace `claude-gateway-xxxxxx.a.run.app` with the actual URL of your service).*

- [ ] **Step 2: Verify Well-Known OAuth Configuration**
Test that the workstation resolves the address privately and successfully hits the private Cloud Run service.
Run on Cloud Workstation:
```bash
curl -iv https://claude-gateway-xxxxxx.a.run.app/.well-known/oauth-authorization-server
```
Expected: Output shows resolution to `10.0.0.100` and HTTP `200 OK` response with JSON metadata.

- [ ] **Step 3: Verify Login Redirect**
Test OIDC login redirection to Google Workspace.
Run on Cloud Workstation:
```bash
curl -iv https://claude-gateway-xxxxxx.a.run.app/login
```
Expected: HTTP `302 Found` response redirecting to `https://accounts.google.com/o/oauth2/v2/auth`.

- [ ] **Step 4: Point Claude Code CLI to Gateway**
Configure the Claude CLI environment in your Cloud Workstation to point to the new gateway.
Run on Cloud Workstation:
```bash
export ANTHROPIC_BASE_URL="https://claude-gateway-xxxxxx.a.run.app/v1"
claude
```
Expected: Claude Code CLI prompts you to sign in via your Workspace OAuth flow.
