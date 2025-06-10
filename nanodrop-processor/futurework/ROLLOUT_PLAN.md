# Rollout Plan - Future Improvements

Based on the "tiny-SaaS-inside-the-lab" rollout playbook. Last updated: June 2025

## Summary of Completed Work
The Phase 3 security hardening has been successfully implemented (commit a505d26):
- ✅ Domain validation for reputable institutions
- ✅ Magic number validation for image security  
- ✅ Enhanced file validation with size/dimension checks
- ✅ User-friendly error messages with troubleshooting tips
- ✅ Comprehensive test suite for all security features

## Phase 3 Hardening (High Priority)

### Authentication & Security
- [x] **Domain verification** - Accept emails from reputable domains
  - ✅ Implemented validation for .edu, .com, .org, .gov, .ai and research institutions
  - ✅ Blocks temporary/spam domains
  - ✅ Allows legitimate research users while preventing abuse
  - Priority: HIGH (security) - COMPLETED

- [x] **Enhanced file validation** 
  - ✅ Magic number check (verify file is actually an image - JPEG, PNG, GIF)
  - ✅ Size cap enforcement (10 MB per image, 25 MB total)
  - ✅ Image dimension validation (200x200 min, 5000x5000 max)
  - ✅ Aspect ratio validation for equipment screens
  - Priority: HIGH (security) - COMPLETED

### Error Handling & User Experience
- [x] **Friendlier error emails**
  - ✅ User-friendly error messages implemented (e.g., "ensure entire screen is visible")
  - ✅ Clear troubleshooting tips for common issues
  - ✅ Sanitized error messages to prevent information leakage
  - [ ] Retry logic: attempt 3 times before giving up (not yet implemented)
  - Priority: MEDIUM (user experience) - PARTIALLY COMPLETED

### Observability & Monitoring
- [ ] **Structured JSON logging**
  - Replace print statements with structured logs
  - Include: request ID, user email, GPT token count, processing time
  - Track OpenAI model name & version for debugging
  - Priority: MEDIUM (debugging)

### DevOps & Deployment
- [ ] **CI/CD Pipeline**
  - GitHub Actions workflow for automated deployment
  - Separate dev and prod environments
  - Tagged releases with version management
  - Automated testing before deployment
  - Priority: LOW (convenience)

## Phase 4+ Future Enhancements (Nice-to-Have)

### Multi-Channel Support
- [ ] **SMS/MMS endpoint**
  - Twilio number for texting photos when email is clunky
  - Useful for mobile-first workflows

### Lab Integration
- [ ] **LIMS/ELN webhook integration**
  - POST CSV data to Benchling, LabArchives, etc.
  - Auto-populate experiment records

### Expanded Instrument Support
- [ ] **Multi-instrument vision**
  - Generalize prompts for Qubit, plate readers
  - Different parsing logic per instrument type

### Quality Control
- [ ] **Human-in-the-loop correction UI**
  - Simple web interface for CSV editing
  - Show parsed CSV next to original image
  - Only needed if error rate > 1-2%

### Community & Documentation
- [ ] **Open source preparation**
  - Clean up code for public release
  - Write technical blog post or preprint
  - Document deployment process for other labs

## Implementation Notes

### Current Status vs. Playbook
- **Phase 0**: ✅ Complete (cold-start, permissions, CSV correctness)
- **Phase 1**: ✅ In progress (system deployed and functional)
- **Phase 2**: ✅ Ready for pilot (security hardening implemented)
- **Phase 3**: ✅ Security hardening COMPLETED, other improvements in progress

### Priority Order (Updated)
1. ✅ **Domain verification** - COMPLETED
2. ✅ **File validation** - COMPLETED
3. **Structured logging** - Next priority for debugging
4. ✅ **Error handling** - PARTIALLY COMPLETED (missing retry logic)
5. **CI/CD** - Developer convenience

### Current State: Production Ready
The system has completed critical security hardening and is production-ready:
- ✅ Domain validation prevents abuse while allowing legitimate research users
- ✅ Magic number validation ensures only real images are processed
- ✅ Comprehensive file validation with user-friendly error messages
- ✅ Rate limiting and cost protection implemented
- 🚀 Ready for wider pilot testing with research community