# Task Completion Checklist

## When Code Changes Are Made

### 1. Code Quality
- [ ] Code follows project conventions (see code_style_and_conventions.md)
- [ ] Japanese comments/documentation updated if needed
- [ ] Error handling is appropriate
- [ ] Temporary files are cleaned up

### 2. Testing
**Note**: Currently no automated tests in `tests/` directory.
- [ ] Manual testing via `./test_request.sh` if applicable
- [ ] Test with actual Carewell data if making automation changes

### 3. Deployment
- [ ] Changes committed to git
- [ ] Push to main branch triggers automatic deployment via GitHub Actions
- [ ] Monitor GitHub Actions workflow for successful deployment
- [ ] Verify Cloud Run service is updated

### 4. Verification (Post-Deploy)
- [ ] Check Cloud Run logs: `gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=carewell-file-collector" --limit 50`
- [ ] Test endpoint with `./test_request.sh`
- [ ] Verify files uploaded to Google Drive
- [ ] Verify records in Google Sheets
- [ ] Verify Firestore duplicate detection

### 5. Documentation
- [ ] Update README.md if functionality changes
- [ ] Update GCP_SETUP.md if infrastructure changes
- [ ] Update DEPLOYMENT_CHECKLIST.md if deployment process changes

## For Infrastructure Changes
- [ ] Update `.github/workflows/deploy.yml` if CI/CD changes
- [ ] Update Dockerfile if container setup changes
- [ ] Update requirements.txt if dependencies change
- [ ] Test Playwright browser compatibility if upgrading
- [ ] Verify Secret Manager secrets are correctly configured