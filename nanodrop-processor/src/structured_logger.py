#!/usr/bin/env python3
"""
Structured logging for Lambda function.
Outputs JSON-formatted logs for better CloudWatch parsing and analysis.
"""

import json
import time
import traceback
from datetime import datetime, timezone
from typing import Any, Dict, Optional
import os


class StructuredLogger:
    """Structured JSON logger for Lambda functions."""
    
    def __init__(self, service_name: str = "nanodrop-processor"):
        self.service_name = service_name
        self.context = {}
        self.request_start_time = None
        
    def set_request_context(self, request_id: str, event: Dict[str, Any]):
        """Set context for the current request."""
        self.context = {
            "request_id": request_id,
            "service": self.service_name,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        self.request_start_time = time.time()
        
        # Extract relevant info from S3 event
        if "Records" in event and event["Records"]:
            record = event["Records"][0]
            if "s3" in record:
                self.context["s3_bucket"] = record["s3"]["bucket"]["name"]
                self.context["s3_key"] = record["s3"]["object"]["key"]
                self.context["s3_size_bytes"] = record["s3"]["object"]["size"]
    
    def set_user_context(self, email: str, subject: str = None):
        """Set user-specific context."""
        self.context["user_email"] = email
        if subject:
            self.context["email_subject"] = subject
    
    def _log(self, level: str, message: str, **kwargs):
        """Core logging method."""
        log_entry = {
            **self.context,
            "level": level,
            "message": message,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
        # Add any additional fields
        for key, value in kwargs.items():
            if value is not None:
                log_entry[key] = value
        
        # Add duration if we have a start time
        if self.request_start_time:
            log_entry["duration_ms"] = int((time.time() - self.request_start_time) * 1000)
        
        # Output as JSON
        print(json.dumps(log_entry, default=str))
    
    def info(self, message: str, **kwargs):
        """Log info level message."""
        self._log("INFO", message, **kwargs)
    
    def warning(self, message: str, **kwargs):
        """Log warning level message."""
        self._log("WARNING", message, **kwargs)
    
    def error(self, message: str, exception: Exception = None, **kwargs):
        """Log error level message."""
        if exception:
            kwargs["error_type"] = type(exception).__name__
            kwargs["error_message"] = str(exception)
            kwargs["stack_trace"] = traceback.format_exc()
        self._log("ERROR", message, **kwargs)
    
    def metric(self, metric_name: str, value: Any, unit: str = None, **kwargs):
        """Log a metric value."""
        metric_data = {
            "metric_name": metric_name,
            "metric_value": value
        }
        if unit:
            metric_data["metric_unit"] = unit
        
        self._log("METRIC", f"Metric: {metric_name}", **{**metric_data, **kwargs})
    
    def image_processed(self, image_number: int, total_images: int, 
                       success: bool, error_message: str = None,
                       samples_extracted: int = None):
        """Log image processing result."""
        self.info("Image processing completed", 
                 image_number=image_number,
                 total_images=total_images,
                 success=success,
                 error_message=error_message,
                 samples_extracted=samples_extracted)
    
    def openai_request(self, model: str, prompt_tokens: int = None, 
                      completion_tokens: int = None, total_tokens: int = None,
                      duration_ms: int = None, cost_usd: float = None):
        """Log OpenAI API request details."""
        self.info("OpenAI API request completed",
                 openai_model=model,
                 prompt_tokens=prompt_tokens,
                 completion_tokens=completion_tokens,
                 total_tokens=total_tokens,
                 openai_duration_ms=duration_ms,
                 openai_cost_usd=cost_usd)
    
    def request_completed(self, success: bool, images_processed: int = None,
                         samples_extracted: int = None, csv_generated: bool = False,
                         error_type: str = None):
        """Log request completion."""
        duration_ms = int((time.time() - self.request_start_time) * 1000) if self.request_start_time else None
        
        self.info("Request completed",
                 success=success,
                 images_processed=images_processed,
                 samples_extracted=samples_extracted,
                 csv_generated=csv_generated,
                 error_type=error_type,
                 total_duration_ms=duration_ms)


# Global logger instance
logger = StructuredLogger()