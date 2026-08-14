#!/usr/bin/env bash
# =============================================================================
# deploy.sh — Build, push, and deploy AI Policy Compliance Checker to GCP Cloud Run
# =============================================================================
# Usage:
#   chmod +x deploy.sh
#   ./deploy.sh
#
# Prerequisites:
#   - gcloud CLI installed and authenticated (gcloud auth login)
#   - Docker installed
#   - OPENAI_API_KEY set in your environment or .env file
# =============================================================================

set -euo pipefail

# ---------------------------------------------------------------------------
# Configuration — edit these variables for your GCP project
# ---------------------------------------------------------------------------
PROJECT_ID="${GCP_PROJECT_ID:-your-gcp-project-id}"
REGION="europe-west1"
SERVICE_NAME="ai-compliance-checker"
ARTIFACT_REGISTRY_REPO="ai-compliance-checker"
IMAGE_NAME="${REGION}-docker.pkg.dev/${PROJECT_ID}/${ARTIFACT_REGISTRY_REPO}/${SERVICE_NAME}"
IMAGE_TAG="${IMAGE_TAG:-latest}"
FULL_IMAGE="${IMAGE_NAME}:${IMAGE_TAG}"

# Load OPENAI_API_KEY from .env if not already set
if [ -f ".env" ]; then
  export "$(grep -v '^#' .env | xargs)"
fi

if [ -z "${OPENAI_API_KEY:-}" ]; then
  echo "ERROR: OPENAI_API_KEY is not set. Export it or add it to your .env file."
  exit 1
fi

echo "======================================================================"
echo " AI Policy Compliance Checker — GCP Cloud Run Deployment"
echo "======================================================================"
echo " Project:    ${PROJECT_ID}"
echo " Region:     ${REGION}"
echo " Service:    ${SERVICE_NAME}"
echo " Image:      ${FULL_IMAGE}"
echo "======================================================================"

# ---------------------------------------------------------------------------
# Step 1: Configure Docker to authenticate with Artifact Registry
# ---------------------------------------------------------------------------
echo ""
echo "[1/5] Configuring Docker for Artifact Registry..."
gcloud auth configure-docker "${REGION}-docker.pkg.dev" --quiet

# ---------------------------------------------------------------------------
# Step 2: Ensure Artifact Registry repository exists
# ---------------------------------------------------------------------------
echo ""
echo "[2/5] Ensuring Artifact Registry repository exists..."
gcloud artifacts repositories describe "${ARTIFACT_REGISTRY_REPO}" \
  --location="${REGION}" \
  --project="${PROJECT_ID}" \
  --quiet 2>/dev/null || \
gcloud artifacts repositories create "${ARTIFACT_REGISTRY_REPO}" \
  --repository-format=docker \
  --location="${REGION}" \
  --project="${PROJECT_ID}" \
  --description="AI Policy Compliance Checker Docker images" \
  --quiet

# ---------------------------------------------------------------------------
# Step 3: Build Docker image
# ---------------------------------------------------------------------------
echo ""
echo "[3/5] Building Docker image..."
docker build \
  --platform linux/amd64 \
  --tag "${FULL_IMAGE}" \
  --file Dockerfile \
  .

# ---------------------------------------------------------------------------
# Step 4: Push image to Artifact Registry
# ---------------------------------------------------------------------------
echo ""
echo "[4/5] Pushing image to Artifact Registry..."
docker push "${FULL_IMAGE}"

# ---------------------------------------------------------------------------
# Step 5: Deploy to Cloud Run
# ---------------------------------------------------------------------------
echo ""
echo "[5/5] Deploying to Cloud Run..."
gcloud run deploy "${SERVICE_NAME}" \
  --image="${FULL_IMAGE}" \
  --platform=managed \
  --region="${REGION}" \
  --project="${PROJECT_ID}" \
  --allow-unauthenticated \
  --set-env-vars="OPENAI_API_KEY=${OPENAI_API_KEY},OPENAI_MODEL=${OPENAI_MODEL:-gpt-4o-mini}" \
  --memory=512Mi \
  --cpu=1 \
  --concurrency=80 \
  --min-instances=0 \
  --max-instances=10 \
  --timeout=60 \
  --port=8000 \
  --quiet

# ---------------------------------------------------------------------------
# Done — print the service URL
# ---------------------------------------------------------------------------
SERVICE_URL=$(gcloud run services describe "${SERVICE_NAME}" \
  --region="${REGION}" \
  --project="${PROJECT_ID}" \
  --format="value(status.url)")

echo ""
echo "======================================================================"
echo " Deployment complete!"
echo " Service URL: ${SERVICE_URL}"
echo ""
echo " Quick test:"
echo "   curl -X POST ${SERVICE_URL}/compliance-check \\"
echo "     -H 'Content-Type: application/json' \\"
echo "     -d '{\"content\": \"Our AI denies loans without human review.\", \"context\": \"Fintech\"}'"
echo "======================================================================"
