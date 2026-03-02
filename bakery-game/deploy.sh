#!/usr/bin/env bash
#
# Deploy: Bakery Management Game -> Google Cloud Run
#
# Prerequisites:
#   - gcloud CLI installed and authenticated
#   - A GCP project with billing enabled
#
# Usage:
#   ./deploy.sh <PROJECT_ID> [REGION] [SERVICE_NAME]
#
# Example:
#   ./deploy.sh my-gcp-project us-central1 bakery-game

set -euo pipefail

PROJECT_ID="${1:?Usage: ./deploy.sh <PROJECT_ID> [REGION] [SERVICE_NAME]}"
REGION="${2:-us-central1}"
SERVICE_NAME="${3:-bakery-game}"

echo "============================================="
echo " Bakery Management Game - Deploy to Cloud Run"
echo "============================================="
echo "Project:  $PROJECT_ID"
echo "Region:   $REGION"
echo "Service:  $SERVICE_NAME"
echo ""

# Set project
gcloud config set project "$PROJECT_ID"

# Enable required APIs
echo "[1/3] Enabling required GCP APIs..."
gcloud services enable \
    run.googleapis.com \
    cloudbuild.googleapis.com \
    artifactregistry.googleapis.com \
    --quiet

# Build and deploy to Cloud Run
echo "[2/3] Building and deploying to Cloud Run..."
gcloud run deploy "$SERVICE_NAME" \
    --source . \
    --region "$REGION" \
    --platform managed \
    --allow-unauthenticated \
    --memory 256Mi \
    --cpu 1 \
    --min-instances 0 \
    --max-instances 2 \
    --timeout 60 \
    --quiet

# Get the service URL
echo "[3/3] Getting service URL..."
SERVICE_URL=$(gcloud run services describe "$SERVICE_NAME" \
    --region "$REGION" \
    --format "value(status.url)")

echo ""
echo "============================================="
echo " Deployment complete!"
echo "============================================="
echo ""
echo " Bakery Game: $SERVICE_URL"
echo ""
