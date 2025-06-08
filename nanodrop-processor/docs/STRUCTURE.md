# Project Structure

## 🏗 Directory Organization

```
nanodrop-processor/
├── src/                     # Lambda source code
│   ├── lambda_function.py   # Main Lambda handler
│   └── security_config.py   # Security configuration
├── deploy/                  # Deployment files
│   ├── Dockerfile          # Docker container for Lambda
│   ├── deploy_lambda.sh    # Deployment script
│   ├── requirements.txt    # Lambda dependencies (minimal)
│   └── iam_policy.json     # IAM policy with least privilege
├── tests/                   # All test files
│   ├── test_lambda_local.py    # Local testing script
│   ├── test_lambda_security.py # Security testing
│   ├── unit/               # Unit tests
│   ├── fixtures/           # Test fixtures
│   └── conftest.py         # Pytest configuration
├── docs/                    # Documentation
│   ├── DEBUGGING_GUIDE.md  # Troubleshooting guide
│   ├── PRODUCTION_STATUS.md # System status and metrics
│   └── STRUCTURE.md        # This file
├── images/                  # Sample Nanodrop images
├── README.md               # Project overview
├── Makefile                # Build and test automation
├── requirements-dev.txt     # Development dependencies
├── run_tests.sh            # Test runner script
└── pyproject.toml          # Project configuration
```

## 🚀 Production Files

**Core Lambda Files (src/):**
- `lambda_function.py` - Main Lambda handler with email processing logic
- `security_config.py` - Security layer with rate limiting and validation

**Deployment Files (deploy/):**
- `Dockerfile` - Production Docker container configuration
- `deploy_lambda.sh` - Automated deployment script
- `requirements.txt` - Minimal Lambda dependencies (boto3, openai, Pillow)
- `iam_policy.json` - Secure IAM policy with principle of least privilege

## 🧪 Testing Framework

**Test Files (tests/):**
- `test_lambda_local.py` - Quick local Lambda testing
- `test_lambda_security.py` - Security feature validation
- `unit/` - Unit tests for individual components
- `fixtures/` - Test data and image generators
- `conftest.py` - Shared pytest configuration

## 📚 Documentation (docs/)

- `DEBUGGING_GUIDE.md` - Common issues and solutions
- `PRODUCTION_STATUS.md` - Current deployment status
- `STRUCTURE.md` - This project structure guide

## 🔧 Development Tools

- `Makefile` - Commands for install, test, lint, format
- `run_tests.sh` - Flexible test runner with coverage
- `requirements-dev.txt` - Full development dependencies
- `pyproject.toml` - Project metadata and tool configuration

## 📊 Data & Configuration

- `images/` - Sample Nanodrop images for testing
- `.env` - Environment variables (not in git)
- `.env.example` - Template for environment setup
- `.env.test` - Test environment configuration

## 🔐 Security Features

The system includes comprehensive security:
- Rate limiting (3/hour, 10/day per user)
- Input validation (file size, type, content)
- DynamoDB tracking for rate limits
- Error sanitization to prevent info leakage
- Secure IAM policy with minimal permissions