# Feature Branch: Claude Code Integration for Agentic Lab Data Analysis

## Overview
Enhance the current nanodrop-processor Lambda function to use Claude Code SDK instead of OpenAI Vision API, enabling more sophisticated, agentic data analysis.

## Current State
- Uses OpenAI Vision API with static prompts
- Basic image-to-JSON extraction
- Limited error handling and retry logic
- No iterative analysis or self-correction

## Proposed Enhancement

### 1. Core Integration Architecture

```python
# claude_code_analyzer.py
import asyncio
from claude_code_sdk import query, ClaudeCodeOptions

class ClaudeCodeAnalyzer:
    def __init__(self, api_key, environment='prod'):
        self.api_key = api_key
        self.environment = environment
        self.base_options = ClaudeCodeOptions(
            max_turns=5,
            output_format='json',
            allowed_tools=['Read', 'Write', 'Bash']
        )
    
    async def analyze_lab_image(self, image_bytes, previous_context=None):
        """
        Agentic analysis of lab instrument images
        Returns enhanced extraction with confidence scores
        """
        # Save image temporarily for Claude Code to analyze
        temp_path = f"/tmp/lab_image_{uuid.uuid4()}.jpg"
        with open(temp_path, 'wb') as f:
            f.write(image_bytes)
        
        prompt = self._build_analysis_prompt(previous_context)
        
        messages = []
        async for message in query(
            prompt=prompt,
            options=self.base_options
        ):
            messages.append(message)
        
        # Extract final result
        result = self._parse_claude_response(messages)
        
        # Cleanup
        os.remove(temp_path)
        
        return result
    
    def _build_analysis_prompt(self, context):
        base_prompt = f"""
        Analyze the lab instrument image at /tmp/lab_image_*.jpg
        
        Your task:
        1. Identify the instrument type and measurement format
        2. Extract ALL visible data with high precision
        3. Validate data consistency and flag anomalies
        4. Suggest quality issues or measurement concerns
        5. Return structured JSON with extraction confidence
        
        {f"Previous context: {context}" if context else ""}
        
        Use multiple approaches if needed. Self-verify your extraction.
        """
        return base_prompt
```

### 2. Enhanced Lambda Integration

```python
# Updated lambda_function.py sections

async def extract_nanodrop_data_agentic(image_bytes, analyzer):
    """Enhanced extraction using Claude Code's agentic capabilities"""
    try:
        # First pass - basic extraction
        result = await analyzer.analyze_lab_image(image_bytes)
        
        # If low confidence, try enhanced analysis
        if result.get('confidence', 0) < 0.8:
            enhanced_prompt_context = {
                "first_attempt": result,
                "instruction": "Re-analyze with focus on unclear values"
            }
            result = await analyzer.analyze_lab_image(
                image_bytes, 
                previous_context=enhanced_prompt_context
            )
        
        return result
        
    except Exception as e:
        logger.error(f"Claude Code analysis failed: {e}")
        # Fallback to OpenAI
        return extract_nanodrop_data(image_bytes)
```

### 3. Agentic Features to Implement

#### A. Multi-Step Verification
```python
async def verify_extraction(analyzer, extraction_result, image_bytes):
    """Use Claude Code to verify and enhance extraction"""
    verification_prompt = f"""
    I extracted this data: {json.dumps(extraction_result)}
    
    Please verify:
    1. Check if ratios make scientific sense
    2. Validate concentration ranges for the assay type
    3. Flag any anomalies or concerns
    4. Suggest dilution factors if needed
    
    Re-check the image if necessary.
    """
    
    verification = await analyzer.query_simple(verification_prompt)
    return verification
```

#### B. Intelligent Error Recovery
```python
async def recover_from_extraction_error(analyzer, error_info, image_bytes):
    """Agentic error recovery with different strategies"""
    strategies = [
        "Try edge detection to find table boundaries",
        "Look for alternative data formats (graphs, charts)",
        "Extract partial data and note missing sections",
        "Identify image quality issues and suggest fixes"
    ]
    
    for strategy in strategies:
        result = await analyzer.analyze_lab_image(
            image_bytes,
            previous_context={"error": error_info, "strategy": strategy}
        )
        
        if result.get('success'):
            return result
    
    return None
```

#### C. Batch Learning and Adaptation
```python
class AdaptiveAnalyzer(ClaudeCodeAnalyzer):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.learned_patterns = {}
    
    async def learn_from_success(self, instrument_type, successful_extraction):
        """Store successful patterns for future use"""
        self.learned_patterns[instrument_type] = {
            "columns": successful_extraction.get('columns'),
            "format_hints": successful_extraction.get('format_hints'),
            "timestamp": datetime.now()
        }
    
    def _build_analysis_prompt(self, context):
        prompt = super()._build_analysis_prompt(context)
        
        # Add learned patterns
        if self.learned_patterns:
            prompt += f"\n\nKnown patterns: {json.dumps(self.learned_patterns)}"
        
        return prompt
```

### 4. Implementation Phases

#### Phase 1: Basic Integration (Week 1)
- [ ] Set up Claude Code SDK in Lambda environment
- [ ] Create `claude_code_analyzer.py` module
- [ ] Implement basic image analysis function
- [ ] Add fallback to OpenAI for compatibility

#### Phase 2: Agentic Features (Week 2)
- [ ] Implement multi-step verification
- [ ] Add intelligent error recovery
- [ ] Create confidence scoring system
- [ ] Build anomaly detection logic

#### Phase 3: Advanced Analytics (Week 3)
- [ ] Add batch learning capabilities
- [ ] Implement quality recommendations
- [ ] Create detailed analysis reports
- [ ] Add instrument-specific optimizations

#### Phase 4: Production Deployment (Week 4)
- [ ] Performance optimization
- [ ] Cost analysis and monitoring
- [ ] A/B testing framework
- [ ] Documentation and training

### 5. Benefits of Claude Code Integration

1. **Improved Accuracy**
   - Self-verification reduces errors
   - Multiple extraction attempts
   - Context-aware analysis

2. **Better Error Handling**
   - Intelligent recovery strategies
   - Detailed error diagnostics
   - User-friendly guidance

3. **Enhanced Features**
   - Data validation and QC
   - Anomaly detection
   - Format auto-detection
   - Scientific insights

4. **Cost Optimization**
   - Reduced re-processing
   - Better first-pass success
   - Efficient token usage

### 6. Monitoring and Analytics

```python
# Enhanced DynamoDB schema for Claude Code metrics
claude_metrics = {
    "analyzer_version": "claude-code-v1",
    "turns_used": 3,
    "confidence_score": 0.95,
    "strategies_attempted": ["direct", "enhanced"],
    "tokens_used": 1500,
    "processing_stages": {
        "extraction": 800,
        "verification": 400,
        "enrichment": 300
    }
}
```

### 7. Example Agentic Conversation Flow

```
Turn 1: "I see a NanoDrop 2000 display. Let me extract the concentration table..."
Turn 2: "I notice some A260/A280 ratios are below 1.8. Let me verify these aren't contamination..."
Turn 3: "Sample 5 shows negative concentration. This is likely a blank. Marking for manual review..."
Turn 4: "Based on the RNA assay type and concentrations, I recommend 1:10 dilution for samples 1-3..."
Result: Complete extraction with QC annotations and recommendations
```

### 8. Security and Compliance

- Claude Code runs in isolated environment
- No persistent file storage beyond processing
- API keys stored in AWS Secrets Manager
- Audit logging for all operations
- HIPAA-compliant data handling

### 9. Rollback Plan

- Feature flag: `USE_CLAUDE_CODE_ANALYZER`
- Dual-path processing during transition
- Performance comparison metrics
- Automatic fallback on errors
- Gradual rollout by user group

### 10. Success Metrics

- Extraction accuracy: >95% (from current ~85%)
- Processing time: <10s per image
- User satisfaction: Reduced error emails by 50%
- Cost per extraction: Comparable to OpenAI
- New features adopted: 80% users use QC insights