# Security Recommendations for Nanodrop Processor

## Current Security Measures Evaluation

### ✅ Keep These
1. **Rate Limiting** - 10/hour is reasonable
2. **File Size Limits** - Appropriate for image processing
3. **Error Sanitization** - Prevents info leakage
4. **Cost Monitoring** - Essential for API services

### ❌ Remove/Modify These
1. **Domain Validation** - Too restrictive for open service

## Recommended Additional Security Measures

### 1. Content Validation
```python
def validate_image_content(self, image_data: bytes) -> bool:
    """Validate image is actually a nanodrop screen."""
    # Use PIL to verify it's a valid image
    try:
        from PIL import Image
        import io
        img = Image.open(io.BytesIO(image_data))
        
        # Basic validation
        if img.width < 200 or img.height < 200:
            return False
        if img.width > 5000 or img.height > 5000:
            return False
            
        return True
    except:
        return False
```

### 2. Response Rate Limiting
- Limit how many times the same email gets processed (prevent loops)
- Cache results for 1 hour to avoid reprocessing

### 3. Abuse Detection
```python
ABUSE_PATTERNS = [
    # Multiple failed attempts
    'failed_attempts': {'threshold': 5, 'window': 3600},
    # Sending identical images repeatedly  
    'duplicate_images': {'threshold': 3, 'window': 3600},
    # Malformed requests
    'invalid_format': {'threshold': 10, 'window': 3600}
]
```

### 4. Authentication Token (Optional)
For premium users or specific organizations:
```python
# Optional API key in email subject or body
API_KEY_PATTERN = r'API-KEY:\s*([A-Za-z0-9]{32})'
```

### 5. Monitoring & Alerting
- CloudWatch alarms for:
  - Sudden spike in requests (>100/hour)
  - High error rates (>20%)
  - Excessive OpenAI costs (>$50/day)
  
### 6. Data Privacy
- Don't log email content or image data
- Auto-delete S3 objects after 24 hours
- Hash email addresses in logs

## Implementation Priority
1. **High**: Remove domain validation
2. **High**: Add content validation 
3. **Medium**: Add duplicate detection
4. **Low**: Optional authentication for premium features

## Cost Protection
```python
# Daily cost limit
DAILY_OPENAI_LIMIT = 50.00  # USD
DAILY_TOKEN_LIMIT = 1000000  # ~$20-30 for GPT-4

def check_daily_cost_limit(self):
    """Stop processing if daily limit exceeded."""
    # Query CloudWatch for today's usage
    # Return False if over limit
```

## SES Production Considerations
When you get SES production access:
- Implement bounce/complaint handling
- Add unsubscribe mechanism
- Monitor sender reputation