#!/usr/bin/env bash
#
# Fully automated deploy: Hormuz Premium Tracker -> Google Cloud Run
#
# This script does EVERYTHING:
#   1. Enables GCP APIs
#   2. Creates Firestore database
#   3. Builds & deploys to Cloud Run
#   4. Creates Cloud Scheduler job for automated scraping (every 4 hours)
#   5. Triggers initial seed + first scrape automatically
#
# Prerequisites:
#   - gcloud CLI installed and authenticated
#   - A GCP project with billing enabled
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
CRON_SECRET="${CRON_SECRET:-$(openssl rand -hex 16)}"
SCHEDULER_JOB="${SERVICE_NAME}-scrape"

echo "============================================="
echo " Hormuz Premium Tracker - Automated Deploy"
echo "============================================="
echo "Project:      $PROJECT_ID"
echo "Region:       $REGION"
echo "Service:      $SERVICE_NAME"
echo "Cron secret:  $CRON_SECRET"
echo ""

# Set project
gcloud config set project "$PROJECT_ID"

# Enable required APIs
echo "[1/7] Enabling required GCP APIs..."
gcloud services enable \
    run.googleapis.com \
    cloudbuild.googleapis.com \
    firestore.googleapis.com \
    artifactregistry.googleapis.com \
    cloudscheduler.googleapis.com \
    --quiet

# Create Firestore database if it doesn't exist
echo "[2/7] Ensuring Firestore database exists..."
gcloud firestore databases describe --project="$PROJECT_ID" 2>/dev/null || \
    gcloud firestore databases create \
        --project="$PROJECT_ID" \
        --location="$REGION" \
        --type=firestore-native \
        --quiet

# Build and deploy to Cloud Run
echo "[3/7] Building and deploying to Cloud Run..."
gcloud run deploy "$SERVICE_NAME" \
    --source . \
    --region "$REGION" \
    --platform managed \
    --allow-unauthenticated \
    --set-env-vars "GCP_PROJECT_ID=$PROJECT_ID,ADMIN_PASSWORD=$ADMIN_PASSWORD,CRON_SECRET=$CRON_SECRET" \
    --memory 512Mi \
    --cpu 1 \
    --min-instances 0 \
    --max-instances 3 \
    --timeout 300 \
    --quiet

# Get the service URL
echo "[4/7] Getting service URL..."
SERVICE_URL=$(gcloud run services describe "$SERVICE_NAME" \
    --region "$REGION" \
    --format "value(status.url)")
echo "Service URL: $SERVICE_URL"

# Create Cloud Scheduler job for automated scraping every 4 hours
echo "[5/7] Setting up Cloud Scheduler (every 4 hours)..."
if gcloud scheduler jobs describe "$SCHEDULER_JOB" --location="$REGION" 2>/dev/null; then
    echo "Updating existing scheduler job..."
    gcloud scheduler jobs update http "$SCHEDULER_JOB" \
        --location="$REGION" \
        --schedule="0 */4 * * *" \
        --uri="${SERVICE_URL}/cron/scrape" \
        --http-method=POST \
        --headers="X-Cron-Secret=$CRON_SECRET" \
        --attempt-deadline=300s \
        --quiet
else
    echo "Creating new scheduler job..."
    gcloud scheduler jobs create http "$SCHEDULER_JOB" \
        --location="$REGION" \
        --schedule="0 */4 * * *" \
        --uri="${SERVICE_URL}/cron/scrape" \
        --http-method=POST \
        --headers="X-Cron-Secret=$CRON_SECRET" \
        --attempt-deadline=300s \
        --quiet
fi

# Trigger seed (app auto-seeds on first startup, but this ensures it)
echo "[6/7] Triggering initial data seed..."
curl -s -X POST "${SERVICE_URL}/cron/seed" \
    -H "X-Cron-Secret: $CRON_SECRET" | python3 -m json.tool 2>/dev/null || true

# Trigger first automated scrape
echo "[7/7] Running first automated scrape..."
curl -s -X POST "${SERVICE_URL}/cron/scrape" \
    -H "X-Cron-Secret: $CRON_SECRET" | python3 -m json.tool 2>/dev/null || true

echo ""
echo "============================================="
echo " Deployment complete! Fully automated."
echo "============================================="
echo ""
echo " Dashboard:    $SERVICE_URL"
echo " Bakery Game:  $SERVICE_URL/bakery"
echo " Admin panel:  $SERVICE_URL/admin"
echo ""
echo " Admin password:  $ADMIN_PASSWORD"
echo " Cron secret:     $CRON_SECRET"
echo ""
echo " Automation:"
echo "   - Cloud Scheduler runs every 4 hours"
echo "   - Auto-scrapes Google News RSS + 11 maritime sources"
echo "   - Auto-extracts premium rates from article text"
echo "   - Auto-computes risk level from news sentiment"
echo "   - Auto-seeded historical data (Sept 2023 - Mar 2026)"
echo ""
echo " No manual intervention needed."
echo ""
