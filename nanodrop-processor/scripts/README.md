# Lab Data Digitization Testing Scripts

## Quick Start

### Send a single test email:
```bash
# To primary digitizer address
python scripts/send_test_email.py --digitizer --image images/test_plate_reader.png

# Test CC/reply-all functionality
python scripts/send_test_email.py --digitizer --cc colleague@example.com --image images/test_plate_reader.png

# Test multiple To recipients (phone-friendly)
python scripts/send_test_email.py --digitizer --to colleague@example.com --image images/test_plate_reader.png

# To development environment
python scripts/send_test_email.py --dev --image images/nanodrop_screenshot.png

# Auto-detect test image
python scripts/send_test_email.py --digitizer
```

### Run full test pipeline:
```bash
# Test all images in dev
python scripts/test_email_pipeline.py

# Quick test with one image
python scripts/test_email_pipeline.py --quick

# Test production (be careful!)
python scripts/test_email_pipeline.py --env prod

# Test specific images
python scripts/test_email_pipeline.py --images images/plate1.png images/plate2.png
```

## Scripts

### `send_test_email.py`
Sends individual test emails to the lab data digitization service.

**Environment Options:**
- `--digitizer` - Send to primary service (digitizer@seminalcapital.net)
- `--dev` - Send to development environment (nanodrop-dev@seminalcapital.net)
- `--prod` - Send to legacy production (nanodrop@seminalcapital.net)

**CC/Reply-All Options:**
- `--to EMAIL` - Add additional To recipient (can be used multiple times)
- `--cc EMAIL` - Add CC recipient (can be used multiple times)

**Email Options:**
- `--image PATH` - Attach specific image
- `--from EMAIL` - Set from address (default: test@seminalcapital.net)
- `--subject TEXT` - Custom subject
- `--body TEXT` - Custom body text

### `test_email_pipeline.py`
Runs comprehensive tests across multiple images with automated log checking.

**Options:**
- `--env {dev,prod}` - Environment to test (default: dev)
- `--images IMG1 IMG2` - Test specific images
- `--quick` - Quick test with just one image
- `--delay SECONDS` - Delay between emails (default: 5)

**Features:**
- Automatically finds test images in `images/` directory
- Sends batch of test emails
- Waits for Lambda processing
- Checks CloudWatch logs for errors
- Provides summary report

## Examples

```bash
# Test CC functionality
python scripts/send_test_email.py --digitizer --cc colleague@example.com --to supervisor@example.com

# Development testing workflow
python scripts/test_email_pipeline.py --env dev

# Production smoke test
python scripts/test_email_pipeline.py --env prod --quick

# Test specific problematic image
python scripts/send_test_email.py --dev --image images/uv_vis_problem.png

# Test loop prevention (should filter out service address)
python scripts/send_test_email.py --digitizer --cc digitizer@seminalcapital.net --to colleague@example.com

# Full production validation (careful!)
python scripts/test_email_pipeline.py --env prod --delay 10
```

## Notes

- The scripts use AWS SES to send emails
- Requires AWS credentials configured (`aws configure`)
- Test images should be in `images/` directory
- Primary service: `digitizer@seminalcapital.net`
- Development emails go to `nanodrop-dev@seminalcapital.net`
- Legacy production: `nanodrop@seminalcapital.net`
- CC/reply-all functionality automatically filters out service addresses to prevent loops