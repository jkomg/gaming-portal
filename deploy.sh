#!/bin/bash
set -e

PROJECT_ID="jkomg-gaming"
REGION="us-central1"
SERVICE="gaming-portal"
IMAGE="us-central1-docker.pkg.dev/$PROJECT_ID/gaming-repo/$SERVICE"

echo "=== jkomg Gaming Portal — Deploy ==="

# Ensure APIs
gcloud services enable artifactregistry.googleapis.com run.googleapis.com --project=$PROJECT_ID

# Ensure Artifact Registry repo
gcloud artifacts repositories describe gaming-repo --location=$REGION --project=$PROJECT_ID &>/dev/null || \
  gcloud artifacts repositories create gaming-repo --repository-format=docker --location=$REGION --project=$PROJECT_ID

docker build --platform linux/amd64 -t "$IMAGE" .
docker push "$IMAGE"

gcloud run deploy "$SERVICE" \
  --image "$IMAGE" \
  --platform managed \
  --region "$REGION" \
  --project "$PROJECT_ID" \
  --allow-unauthenticated \
  --memory 128Mi \
  --cpu 1 \
  --min-instances 0 \
  --max-instances 2

echo ""
echo "=== Deploy complete ==="
gcloud run services describe $SERVICE --region=$REGION --project=$PROJECT_ID --format='value(status.url)'
