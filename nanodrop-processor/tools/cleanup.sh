#!/bin/bash

# Cleanup script for nanodrop-processor development cruft

echo "🧹 Cleaning up development cruft..."

# Create archive directory for old files
mkdir -p .archive/policies
mkdir -p .archive/test-results

# Archive old policy files
echo "📦 Archiving old policy files..."
mv lambda-delete-policy.json ecr-lambda-policy.json required_permissions.json updated_policy.json .archive/policies/ 2>/dev/null || true

# Archive test results
echo "📦 Archiving test results..."
mv llm_test_results.json .archive/test-results/ 2>/dev/null || true

# Clean Python cache files
echo "🗑️  Removing Python cache files..."
find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
find . -type f -name "*.pyc" -delete 2>/dev/null || true
find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true

# Remove the large lambda_package directory (86MB!)
echo "🗑️  Removing bloated lambda_package directory..."
rm -rf lambda_package/

# Clean up lambda_layer if empty
if [ -z "$(ls -A lambda_layer/python 2>/dev/null)" ]; then
    echo "🗑️  Removing empty lambda_layer..."
    rm -rf lambda_layer/
fi

# Remove any zip files
echo "🗑️  Removing old zip files..."
rm -f *.zip

# Clean up duplicate or old deployment scripts
echo "📦 Consolidating deployment scripts..."
if [ -f deploy_lambda_improved.sh ]; then
    # Archive the old one
    mv deploy_lambda.sh .archive/ 2>/dev/null || true
    # Rename improved to main
    mv deploy_lambda_improved.sh deploy_lambda.sh
fi

# Remove simple_deploy.py as we'll use Docker approach
mv simple_deploy.py .archive/ 2>/dev/null || true

# Clean up any test artifacts
echo "🗑️  Cleaning test artifacts..."
rm -f response.json test-event.json notification.json trust-policy.json lambda-policy.json

# Create a clean directory structure summary
echo "📁 Creating clean directory structure..."
cat > STRUCTURE.md << 'EOF'
# Project Structure

## Core Lambda Files
- `lambda_function.py` - Main Lambda handler
- `Dockerfile` - Production Docker container
- `Dockerfile.minimal` - Minimal Docker container (fallback)
- `lambda_requirements.txt` - Lambda-specific dependencies (openai, boto3)
- `deploy_lambda.sh` - Main deployment script

## Testing & Development
- `test_lambda_local.py` - Local Lambda testing
- `test_llm_offline.py` - LLM extraction testing
- `llm_extractor.py` - Standalone LLM extraction module
- `debug_lambda.py` - Deployment diagnostics tool
- `validate_extraction.py` - Data validation utilities

## Documentation
- `README.md` - Project overview and deployment guide
- `DEBUGGING_GUIDE.md` - Troubleshooting guide
- `STRUCTURE.md` - This file

## Test Suite
- `tests/` - Comprehensive test framework
- `run_tests.sh` - Test runner
- `Makefile` - Build and test commands
- `pyproject.toml` - Project configuration
- `requirements.txt` - Full development dependencies

## Data & Images
- `images/` - Sample Nanodrop images
- `extracted_data/` - CSV outputs from testing

## Configuration
- `.env` - Environment variables (OPENAI_API_KEY)
- `.gitignore` - Git ignore rules

## Future Application Structure
- `src/` - Full application code (to be implemented)
  - `api/` - Web API endpoints
  - `models/` - Data models
  - `processors/` - Processing logic
  - `services/` - External services
  - `utils/` - Utilities
  - `workers/` - Background workers

## Archived Files
- `.archive/` - Old policies, scripts, and test results
EOF

echo "✅ Cleanup complete!"
echo ""
echo "📊 Space saved:"
du -sh .archive/ 2>/dev/null || echo "Archive: 0K"
echo ""
echo "Next steps:"
echo "1. Review STRUCTURE.md for clean project layout"
echo "2. Run './debug_lambda.py' to check deployment readiness"
echo "3. Use './deploy_lambda.sh' for deployment"
echo "4. Check DEBUGGING_GUIDE.md for S3 trigger troubleshooting"