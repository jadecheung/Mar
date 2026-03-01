#!/usr/bin/env bash
#
# Deploy Hormuz Premium Tracker to Google Cloud Run
#
# Prerequisites:
#   1. gcloud CLI installed and authenticated
#   2. A GCP project with billing enabled
#   3. Firestore database created (Native mode)
#
# Usage:
#   ./deploy.sh <PROJECT_ID> [REGION] [SERVICE_NAME]
#
# Example:
#   ./deploy.sh my-gcp-project us-central1 hormuz-tracker

set -euo pipefail

PROJECT_ID="${1:?Usage: ./deploy.sh <PROJECT_ID> [REGION] [SERVICE_NAME]}"
REGION="${2:-us-central1}"
SERVICE_NAME="${3:-hormuz-tracker}"
ADMIN_PASSWORD="${ADMIN_PASSWORD:-hormuz2026}"

echo "=========================================="
echo " Hormuz Premium Tracker - Cloud Run Deploy"
echo "=========================================="
echo "Project:  $PROJECT_ID"
echo "Region:   $REGION"
echo "Service:  $SERVICE_NAME"
echo ""

# Set project
gcloud config set project "$PROJECT_ID"

# Enable required APIs
echo "[1/5] Enabling required GCP APIs..."
gcloud services enable \
    run.googleapis.com \
    cloudbuild.googleapis.com \
    firestore.googleapis.com \
    artifactregistry.googleapis.com \
    --quiet

# Create Firestore database if it doesn't exist
echo "[2/5] Ensuring Firestore database exists..."
gcloud firestore databases describe --project="$PROJECT_ID" 2>/dev/null || \
    gcloud firestore databases create \
        --project="$PROJECT_ID" \
        --location="$REGION" \
        --type=firestore-native \
        --quiet

# Build and deploy to Cloud Run
echo "[3/5] Building and deploying to Cloud Run..."
gcloud run deploy "$SERVICE_NAME" \
    --source . \
    --region "$REGION" \
    --platform managed \
    --allow-unauthenticated \
    --set-env-vars "GCP_PROJECT_ID=$PROJECT_ID,ADMIN_PASSWORD=$ADMIN_PASSWORD,SCRAPE_INTERVAL_HOURS=6" \
    --memory 512Mi \
    --cpu 1 \
    --min-instances 0 \
    --max-instances 3 \
    --timeout 300 \
    --quiet

# Get the service URL
echo "[4/5] Getting service URL..."
SERVICE_URL=$(gcloud run services describe "$SERVICE_NAME" \
    --region "$REGION" \
    --format "value(status.url)")

echo ""
echo "[5/5] Seeding initial data..."
echo "Run the following command to seed historical data:"
echo ""
echo "  GCP_PROJECT_ID=$PROJECT_ID python seed_data.py"
echo ""
echo "=========================================="
echo " Deployment complete!"
echo "=========================================="
echo ""
echo " Dashboard:  $SERVICE_URL"
echo " Admin:      $SERVICE_URL/admin"
echo ""
echo " Admin password: $ADMIN_PASSWORD"
echo " (Change via ADMIN_PASSWORD env var)"
echo ""
