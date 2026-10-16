#!/bin/bash
# Google Cloud Run Deployment Script for AquaVigil Platform

PROJECT_ID=${GOOGLE_CLOUD_PROJECT:-""}
if [ -z "$PROJECT_ID" ]; then
    echo -n "Enter your Google Cloud Project ID: "
    read PROJECT_ID
fi

REGION="us-central1"
SERVICE_NAME="aquavigil-platform"

echo "========================================================"
echo "Deploying AquaVigil to Google Cloud Run"
echo "Project: $PROJECT_ID | Region: $REGION | Service: $SERVICE_NAME"
echo "========================================================"

# 1. Set Google Cloud Project
gcloud config set project "$PROJECT_ID"

# 2. Enable Required Google Cloud APIs
echo -e "\n[1/3] Enabling Google Cloud APIs..."
gcloud services enable \
    run.googleapis.com \
    aiplatform.googleapis.com \
    bigquery.googleapis.com \
    pubsub.googleapis.com \
    storage.googleapis.com

# 3. Build & Deploy Container to Cloud Run
echo -e "\n[2/3] Building container and deploying to Cloud Run..."
gcloud run deploy "$SERVICE_NAME" \
    --source . \
    --region "$REGION" \
    --platform managed \
    --allow-unauthenticated \
    --port 8080 \
    --memory 1Gi \
    --set-env-vars "GOOGLE_CLOUD_PROJECT=$PROJECT_ID,BIGQUERY_DATASET=aquavigil_dataset"

# 4. Deployment Complete
echo -e "\n[3/3] Deployment complete!"
SERVICE_URL=$(gcloud run services describe "$SERVICE_NAME" --platform managed --region "$REGION" --format 'value(status.url)')
echo "Live Cloud Run URL: $SERVICE_URL"
