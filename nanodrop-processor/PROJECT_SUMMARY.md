# Nanodrop Email Processing System - Project Summary

## What It Does

A simple email automation tool that helps researchers digitize their lab equipment readings. Users email photos of Nanodrop spectrophotometer screens to `nanodrop@seminalcapital.net` and receive back CSV files with the extracted data.

**Process:**
1. Researcher emails photo of Nanodrop screen
2. System extracts measurements using GPT-4 vision
3. Researcher gets CSV reply with concentration, purity ratios, and quality assessment

## Who It's For

- Laboratory researchers using Nanodrop spectrophotometers
- Anyone who needs to digitize DNA/RNA concentration measurements
- Small labs without automated data management systems

## Current Capabilities

- **Multi-image processing** - Handle multiple photos in one email
- **Assay type detection** - Automatically identifies RNA vs DNA
- **Quality assessment** - Flags contamination and measurement issues
- **Security** - Rate limiting (3/hour, 10/day) and input validation
- **Encoding fix** - Uses "uL" instead of "μL" to prevent CSV issues

## Technical Status

- ✅ **Production ready** - AWS Lambda deployment with security hardening
- ✅ **Cost efficient** - ~$0.03 per image processed
- ✅ **Fast** - ~9 second response time
- ✅ **Reliable** - Comprehensive test suite and error handling

## Repository Structure

Clean, organized codebase following standard practices:
- `src/` - Lambda source code
- `deploy/` - Deployment scripts and configs
- `tests/` - Test suite
- `docs/` - Documentation

## Purpose

Not a commercial product - just a practical tool to automate a tedious manual task that many researchers face. Saves time transcribing numbers from equipment screens into spreadsheets.

## Usage

Simply email a photo of your Nanodrop screen to `nanodrop@seminalcapital.net` and receive a CSV file with your measurements within seconds.