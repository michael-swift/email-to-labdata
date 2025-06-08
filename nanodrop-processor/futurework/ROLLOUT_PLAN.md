# Rollout Plan - Future Improvements

Based on the "tiny-SaaS-inside-the-lab" rollout playbook, here are the Phase 3 hardening and polish items we want to implement.

## Phase 3 Hardening (High Priority)

### Authentication & Security
- [ ] **Domain verification** - Only accept emails from verified domains (e.g., `seminalcapital.net`)
  - Implement SES inbound rule to verify sender domain
  - Reject spoofed senders
  - Priority: HIGH (security)

- [ ] **Enhanced file validation** 
  - Magic number check (verify file is actually an image)
  - Size cap enforcement (<6 MB per image)
  - Prevent malicious payload uploads
  - Priority: HIGH (security)

### Error Handling & User Experience
- [ ] **Friendlier error emails**
  - Replace technical error messages with user-friendly explanations
  - Include troubleshooting tips ("ensure entire screen is visible")
  - Retry logic: attempt 3 times before giving up
  - Priority: MEDIUM (user experience)

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
- **Phase 1**: Ready to start (dog-fooding with current system)
- **Phase 2**: Can proceed with 3-5 user pilot using current security
- **Phase 3**: Items above represent the hardening we want

### Priority Order
1. **Domain verification** - Critical for production use
2. **File validation** - Security essential
3. **Structured logging** - Helpful for debugging
4. **Error handling** - Improves user experience
5. **CI/CD** - Developer convenience

### Decision: Start Phase 1 Now
The current system is production-ready enough to begin dog-fooding and small pilot testing. Phase 3 improvements can be implemented in parallel based on feedback from real usage.