# Code Style and Conventions

## Language
- **Implementation Language**: Python 3.11
- **Documentation Language**: Japanese (comments, README, etc.)
- **Development Communication**: Think in English, respond in Japanese

## Code Structure
- Services are separated into dedicated modules (google_drive_service, firestore_service, sheets_service)
- Main entry point handles HTTP request/response and orchestration
- Playwright automation is isolated in its own module

## Logging
- Uses Cloud Logging integration (`google.cloud.logging`)
- Log level: INFO
- Logger name: "carewell-automation"

## Error Handling
- Functions should handle errors gracefully
- Return structured JSON responses with status and error details
- Clean up temporary files even on errors

## Security
- Never store credentials in environment variables
- Always use Secret Manager for sensitive data
- Use Workload Identity Federation for CI/CD (no service account keys)
- Minimal permissions principle for service accounts

## File Naming
- Snake case for Python files: `google_drive_service.py`
- Descriptive names that indicate purpose

## Dependencies
- All dependencies listed in `requirements.txt`
- Pin specific versions for reproducibility

## Container
- Base image: `python:3.11-bookworm` (not slim - Playwright needs full dependencies)
- Multi-stage build not required for current implementation