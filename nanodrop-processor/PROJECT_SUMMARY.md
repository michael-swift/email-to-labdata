# Lab Data Digitization Service - Project Summary

## What It Does

A simple email automation tool that helps researchers digitize their lab equipment readings. Users email photos of any lab instrument screen to `digitizer@seminalcapital.net` and receive back CSV files with the extracted data.

**Process:**
1. Researcher emails photo of lab instrument screen (Nanodrop, plate reader, UV-Vis, etc.)
2. System extracts measurements using GPT-4o vision API
3. Researcher gets CSV reply with structured data and quality assessment

## Who It's For

- Laboratory researchers using any lab instruments with screen displays
- Anyone who needs to digitize tabular data from lab equipment
- Small labs without automated data management systems
- Research facilities looking to streamline data collection workflows

## Current Capabilities

- **Universal instrument support** - Handles any lab equipment with tabular data
- **Multi-image processing** - Handle multiple photos in one email
- **Intelligent format detection** - Automatically identifies instrument type and data structure
- **Reply-all functionality** - Send results to multiple recipients via To/CC fields
- **Quality assessment** - Smart validation and quality indicators
- **Security** - Rate limiting (3/hour, 10/day), input validation, and loop prevention
- **ASCII-safe output** - Clean CSV format without encoding issues

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

Simply email a photo of your lab instrument screen to `digitizer@seminalcapital.net` and receive a CSV file with your measurements within seconds.

**Supported Instruments:**
- Nanodrop spectrophotometers (DNA/RNA concentration)
- 96-well plate readers (complete plate data)
- UV-Vis spectrometers (absorbance measurements)
- Any lab instrument with tabular data display

**Alternative Email Addresses:**
- `digitizer@seminalcapital.net` (primary)
- `nanodrop@seminalcapital.net` (legacy, still works)