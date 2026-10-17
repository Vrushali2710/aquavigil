# Google Cloud Run Deployment Script for AquaVigil Platform
# Hackathon Track: Sustainability & Community Resilience

Set-Location -Path $PSScriptRoot

# 1. Check for file-based credentials (Service Account JSON)
$credFile = $null
$possibleCreds = @("credentials.json", "gcp_credentials.json", "service_account.json", "key.json")
foreach ($f in $possibleCreds) {
    if (Test-Path $f) {
        $credFile = (Resolve-Path $f).Path
        break
    }
}

if ($credFile) {
    Write-Host "========================================================" -ForegroundColor Cyan
    Write-Host "Auto-detected Google Cloud Credentials File: $credFile" -ForegroundColor Green
    Write-Host "Authenticating gcloud using service account key..." -ForegroundColor Cyan
    gcloud auth activate-service-account --key-file="$credFile"
    
    $json = Get-Content $credFile | ConvertFrom-Json
    if ($json.project_id) {
        $PROJECT_ID = $json.project_id
        $env:GOOGLE_CLOUD_PROJECT = $PROJECT_ID
    }
} else {
    $PROJECT_ID = $env:GOOGLE_CLOUD_PROJECT
    if (-not $PROJECT_ID) {
        $PROJECT_ID = Read-Host "Enter your Google Cloud Project ID"
    }
}

$REGION = "us-central1"
$SERVICE_NAME = "aquavigil-platform"

Write-Host "========================================================" -ForegroundColor Cyan
Write-Host "Deploying AquaVigil to Google Cloud Run" -ForegroundColor White
Write-Host "Project: $PROJECT_ID | Region: $REGION | Service: $SERVICE_NAME" -ForegroundColor Yellow
Write-Host "========================================================" -ForegroundColor Cyan

# 2. Set Google Cloud Project
gcloud config set project $PROJECT_ID

# 3. Enable Required Google Cloud APIs
Write-Host "`n[1/3] Enabling Google Cloud APIs..." -ForegroundColor Green
gcloud services enable `
    run.googleapis.com `
    aiplatform.googleapis.com `
    bigquery.googleapis.com `
    pubsub.googleapis.com `
    storage.googleapis.com

# 4. Build & Deploy Container to Cloud Run
Write-Host "`n[2/3] Building container and deploying to Cloud Run..." -ForegroundColor Green
gcloud run deploy $SERVICE_NAME `
    --source . `
    --region $REGION `
    --platform managed `
    --allow-unauthenticated `
    --port 8080 `
    --memory 1Gi `
    --set-env-vars "GOOGLE_CLOUD_PROJECT=$PROJECT_ID,BIGQUERY_DATASET=aquavigil_dataset"

# 5. Deployment Complete
Write-Host "`n[3/3] Deployment complete!" -ForegroundColor Green
$SERVICE_URL = (gcloud run services describe $SERVICE_NAME --platform managed --region $REGION --format 'value(status.url)')
Write-Host "Live Cloud Run URL: $SERVICE_URL" -ForegroundColor Cyan
