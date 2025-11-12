# Email-to-LabData

## Nanodrop Email Processor

AWS Lambda function that processes Nanodrop spectrophotometer screenshots sent via email, extracts measurement data using GPT-4o, and sends back CSV files with the results.

<img src="nanodrop-processor/images/minimal-ascii-poster.png" alt="Nanodrop Processor Poster" width="640" />

## Debugging & Operations

### S3 Bucket Info
- **Bucket**: `nanodrop-emails-seminalcapital`
- **Region**: `us-west-2` 
- **Incoming emails**: Stored with prefix `incoming/`

### Recent S3 Objects
```bash
# List recent objects with timestamps
aws s3 ls s3://nanodrop-emails-seminalcapital/incoming/ --recursive

# Get last 3 objects
aws s3api list-objects-v2 --bucket nanodrop-emails-seminalcapital --prefix incoming/ --query 'sort_by(Contents, &LastModified)[-3:].[Key,LastModified,Size]' --output table
```

### Local Testing
```bash
cd nanodrop-processor
# Run debug test on recent S3 emails
~/miniforge3/envs/ELN/bin/python debug_test.py
```

### Project Structure
- `nanodrop-processor/` - Lambda function code
- `nanodrop-processor/src/lambda_function.py` - Main handler
- `nanodrop-processor/debug_test.py` - Local testing script
- `nanodrop-processor/debug_emails/` - Downloaded emails for testing
