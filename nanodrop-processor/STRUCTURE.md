# Project Structure

## 🚀 Production Files
- `lambda_function.py` - Main Lambda handler (PRODUCTION)
- `Dockerfile` - Production Docker container  
- `lambda_requirements.txt` - Minimal dependencies (openai, boto3)
- `deploy_lambda.sh` - Deployment script
- `llm_extractor.py` - Standalone LLM extraction module

## 📚 Documentation
- `README.md` - Project overview and deployment guide
- `PRODUCTION_STATUS.md` - Current system status and metrics
- `DEBUGGING_GUIDE.md` - Troubleshooting guide
- `STRUCTURE.md` - This file

## 🧪 Testing & Local Development
- `test_lambda_local.py` - Local Lambda testing
- `tests/` - Comprehensive test framework
- `run_tests.sh` - Test runner
- `Makefile` - Build and test commands

## 🛠 Development Tools
- `tools/` - Development and debugging utilities
  - `debug_lambda.py` - Deployment diagnostics
  - `debug_s3_trigger.sh` - S3 trigger debugging
  - `cleanup.sh` - Repository cleanup script
- `dev/` - Standalone development scripts
  - `demo_llm_system.py` - LLM demonstration
  - `extract_nanodrop_data.py` - Extraction utilities
  - `test_llm_offline.py` - Offline LLM testing
  - `validate_extraction.py` - Data validation

## 📊 Data & Configuration
- `images/` - Sample Nanodrop images
- `extracted_data/` - CSV outputs from testing
- `.env` - Environment variables (OPENAI_API_KEY)
- `.env.example` - Environment template
- `pyproject.toml` - Project configuration
- `requirements.txt` - Full development dependencies

## 🏗 Future Expansion
- `src/` - Full application structure (planned)
- `config/` - Configuration management
- `.archive/` - Historical files and old implementations

## 📦 Docker Files
- `Dockerfile` - Production container (recommended)
- `Dockerfile.minimal` - Minimal fallback container
