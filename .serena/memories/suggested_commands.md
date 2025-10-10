# Suggested Commands

## Development Setup
```bash
# Install dependencies
pip install -r requirements.txt

# Install Playwright browsers
playwright install chromium
```

## Deployment
Deployment is automated via GitHub Actions on push to main branch:
```bash
git add .
git commit -m "Your commit message"
git push origin main
```

GitHub Actions automatically:
1. Builds Docker image
2. Pushes to Artifact Registry
3. Deploys to Cloud Run Functions

## Testing the Service
Use the test script:
```bash
./test_request.sh
```

Or manual curl:
```bash
curl -X POST https://carewell-file-collector-imczapxkba-an.a.run.app \
  -H "Content-Type: application/json" \
  -d @test_request.json
```

## GCP Commands
```bash
# Check service status
gcloud run services describe carewell-file-collector --region asia-northeast1

# View logs
gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=carewell-file-collector" --limit 50

# List artifact registry images
gcloud artifacts docker images list asia-northeast1-docker.pkg.dev/carewell-automation/carewell-functions
```

## Environment Variables
- `GCP_PROJECT`: GCP project ID (default: carewell-automation)
- `GOOGLE_APPLICATION_CREDENTIALS`: Path to service account credentials (for local testing)
- `GOOGLE_CLOUD_PROJECT`: Alternative to GCP_PROJECT

## System Utilities (macOS - Darwin)
Standard macOS/Unix commands available:
- `ls`, `cd`, `pwd`, `grep`, `find`
- `git` for version control
- `docker` for container operations