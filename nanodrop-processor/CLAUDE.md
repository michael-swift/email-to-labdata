# Lab Data Digitization Service - Quick Reference

## 🚀 Quick Commands

### Testing CC/Reply-All Functionality
```bash
# Test multiple To recipients (phone-friendly)
python scripts/send_test_email.py --digitizer --to colleague@example.com

# Test traditional CC
python scripts/send_test_email.py --digitizer --cc colleague@example.com

# Test combined To + CC
python scripts/send_test_email.py --digitizer --to supervisor@example.com --cc colleague@example.com

# Test loop prevention (should filter out service address)
python scripts/send_test_email.py --digitizer --cc digitizer@seminalcapital.net --to colleague@example.com
```

### Development Workflow
```bash
# Deploy and test in dev environment
make dev-test

# Deploy to production (with safety checks)
make prod-deploy

# Check recent logs
make logs

# Monitor live logs
make tail-logs

# Quick dev deployment only
./deploy/deploy_lambda_dev.sh
```

### Email Addresses
- **Primary**: `digitizer@seminalcapital.net` (generic lab data service)
- **Legacy**: `nanodrop@seminalcapital.net` (still works)  
- **Development**: `nanodrop-dev@seminalcapital.net`

### Testing & Debugging
```bash
# Run unit tests with coverage
python scripts/check_coverage.py

# Test specific image
python scripts/send_test_email.py --digitizer --image path/to/image.jpg

# Check system status
make status

# Clean temp files
make clean

# Download and analyze latest request
make debug-last
```

### CloudWatch Logs
```bash
# Tail logs directly
aws logs tail /aws/lambda/nanodrop-processor --follow

# Filter for errors
aws logs filter-log-events --log-group-name="/aws/lambda/nanodrop-processor" --filter-pattern="ERROR"

# Check recent CC extractions
aws logs filter-log-events --log-group-name="/aws/lambda/nanodrop-processor" --filter-pattern="recipients extracted" --start-time=$(date -d '1 hour ago' +%s)000
```

## 📧 How It Works

1. **Send**: Email lab instrument photo to `digitizer@seminalcapital.net`
2. **Include**: CC or multiple To recipients as needed
3. **Receive**: All recipients get CSV + original images within ~9 seconds

## 🔒 Security Features

- **Rate limiting**: 3/hour, 10/day per sender
- **Loop prevention**: Service addresses filtered from CC lists
- **Input validation**: File size/type checks
- **No data retention**: Images deleted after processing

## 🛠 Deployment Environments

| Environment | Lambda Function | Email Address | Use Case |
|-------------|----------------|---------------|----------|
| **Production** | `nanodrop-processor` | `digitizer@seminalcapital.net` | Live users |
| **Legacy Prod** | `nanodrop-processor` | `nanodrop@seminalcapital.net` | Backwards compatibility |
| **Development** | `nanodrop-processor-dev` | `nanodrop-dev@seminalcapital.net` | Testing |

## 💡 Common Tasks

**Add new test image:**
```bash
# Copy to tests/fixtures/test_images/
# Then test with:
python scripts/send_test_email.py --digitizer --image tests/fixtures/test_images/your_image.jpg
```

**Test new instrument type:**
```bash
# Send test email and check extraction accuracy
python scripts/send_test_email.py --digitizer --image your_instrument.jpg
# Check logs for processing details
make logs
```

**Deploy bug fix:**
```bash
# Test in dev first
make dev-test
# If passes, deploy to production
make prod-deploy
```