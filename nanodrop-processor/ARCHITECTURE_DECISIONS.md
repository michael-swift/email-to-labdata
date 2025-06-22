# Architecture Decisions

## Image Preprocessing Investigation (June 2025)

### Decision: No Image Preprocessing
**Status**: Decided against implementation

### Background
We investigated whether image preprocessing could improve extraction accuracy for lab instrument photos, particularly for degraded images (blur, poor lighting, rotation, etc.).

### Investigation Process
1. Created comprehensive preprocessing pipeline with PIL/OpenCV
2. Implemented various enhancement techniques:
   - Auto-rotation and perspective correction
   - Glare removal and contrast enhancement  
   - Noise reduction and sharpening
   - LCD/LED screen-specific optimizations
3. Built test harness with synthetic image degradations
4. Tested on plate reader images with various quality issues

### Key Findings
- **GPT-4V is remarkably robust** to image quality issues
- Raw blurred images: 96/96 samples extracted correctly
- Preprocessed blurred images: 94/96 samples extracted (regression)
- Preprocessing added 1.4s overhead with no benefit
- Vision models appear trained on real-world photos, making traditional preprocessing counterproductive

### Conclusion
Modern vision APIs (GPT-4V, Claude Vision) handle degraded images better than expected. Preprocessing removes information the AI models use for context, actually hurting performance.

**Recommendation**: Send raw images directly to vision APIs. Focus optimization efforts on prompt engineering and API response time instead.

### References
- Test results in git history (feature/preprocessing-investigation branch)
- Single test showed 2-sample regression with preprocessing on blurred images
- Processing time: ~40s for vision API vs 1.4s for preprocessing overhead

---

## Claude Code Integration Investigation (June 2025)

### Decision: Deferred - Continue with OpenAI Vision API
**Status**: Investigated but not implemented

### Background  
Evaluated Claude Code SDK for more "agentic" data analysis capabilities versus current OpenAI Vision API approach.

### Proposed Benefits
- Multi-turn reasoning and self-verification
- Tool usage for data validation
- Intelligent error recovery strategies
- Context persistence across analysis steps

### Decision Rationale
1. **Current solution works well** - 85%+ accuracy with simple approach
2. **Complexity vs benefit** - Claude Code adds significant architectural complexity
3. **Cost implications** - Multiple turns would increase per-extraction cost
4. **Lambda constraints** - Node.js + Python runtime requirements
5. **Actual needs** - Most errors are image quality, not AI reasoning limitations

### Recommendation
Continue with current OpenAI Vision API approach. Consider Claude Code for:
- Multi-modal analysis tasks (images + documents + data)
- Research/exploration workflows
- Interactive user refinement scenarios

Simple, direct approaches often outperform complex ones for production data extraction tasks.