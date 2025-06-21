# Nanodrop Testing Scripts

## Quick Start

### Send a single test email:
```bash
# To development (default)
python scripts/send_test_email.py --image images/test_plate_reader.png

# To production
python scripts/send_test_email.py --prod --image images/nanodrop_screenshot.png

# Auto-detect test image
python scripts/send_test_email.py --dev
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
Sends individual test emails to the Nanodrop processor.

**Options:**
- `--dev` / `--prod` - Choose environment (default: prod)
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
# Development testing workflow
python scripts/test_email_pipeline.py --env dev

# Production smoke test
python scripts/test_email_pipeline.py --env prod --quick

# Test specific problematic image
python scripts/send_test_email.py --dev --image images/uv_vis_problem.png

# Full production validation (careful!)
python scripts/test_email_pipeline.py --env prod --delay 10
```

## Notes

- The scripts use AWS SES to send emails
- Requires AWS credentials configured (`aws configure`)
- Test images should be in `images/` directory
- Development emails go to `nanodrop-dev@seminalcapital.net`
- Production emails go to `nanodrop@seminalcapital.net`