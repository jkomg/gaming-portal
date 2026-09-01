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

# ─────────────────────────────────────────────────────────────────────────────
# Deploy-target verification.
#
# Three services in this estate spent weeks deploying into a project that no
# domain pointed at. Each deploy succeeded, so nothing ever failed — the only
# symptom was a public site that quietly stopped changing. amber-wiki did it for
# six days, athens-chronicles-web for a month, heirloom-kitchen shipped a build
# with a broken database that nobody saw because the domain served the old one.
#
# This asks the one question none of those deploys asked: does the domain that
# serves this service actually live in the project we just deployed to?
#
# Deliberately does not take the domain as input — the amber version did, and a
# script that names its own domain can still be wrong about it. This searches
# every project you can see for a mapping pointing at this service name.
# ─────────────────────────────────────────────────────────────────────────────
verify_deploy_target() {
  local project="$1" region="$2" service="$3"
  local token here="" elsewhere=""

  token=$(gcloud auth print-access-token 2>/dev/null) || {
    echo "  (skipped domain check: no gcloud access token)"; return 0; }

  echo ""
  echo "=== Verifying deploy target for $service ==="

  local p hits
  for p in $(gcloud projects list --format='value(projectId)' 2>/dev/null); do
    hits=$(curl -s -m 15 -H "Authorization: Bearer $token" \
      "https://${region}-run.googleapis.com/apis/domains.cloudrun.com/v1/namespaces/${p}/domainmappings" \
      2>/dev/null | python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
except Exception:
    raise SystemExit
if 'error' in d:
    raise SystemExit
for i in d.get('items', []):
    if i.get('spec', {}).get('routeName') == '$service':
        print(i['metadata']['name'])
" 2>/dev/null)
    [ -z "$hits" ] && continue
    if [ "$p" = "$project" ]; then
      here="$hits"
    else
      elsewhere="${elsewhere}${elsewhere:+ }${p}=$(echo "$hits" | tr '\n' ',')"
    fi
  done

  if [ -n "$elsewhere" ]; then
    echo "  ERROR: a domain for '$service' is mapped in a DIFFERENT project." >&2
    echo "    deployed to: $project" >&2
    echo "    mapped in:   $elsewhere" >&2
    [ -n "$here" ] && echo "    also mapped here: $(echo "$here" | tr '\n' ' ')" >&2
    echo "  Traffic goes to the mapped project, not this one. Either deploy" >&2
    echo "  there, or move the mapping. This deploy is probably invisible." >&2
    return 1
  fi

  if [ -n "$here" ]; then
    echo "  OK: $(echo "$here" | tr '\n' ' ') -> $service in $project"
  else
    echo "  Note: no custom domain maps to $service in any visible project."
    echo "  Fine for an internal service; wrong if this is meant to be public."
  fi
  return 0
}

verify_deploy_target "${PROJECT_ID}" "${REGION}" "${SERVICE}"
