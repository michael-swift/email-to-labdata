# Test Images Documentation

## Location
All test images are stored in: `tests/fixtures/test_images/`

## Available Test Images

### 1. `nanodrop_standard.jpg`
- **Type**: Standard Nanodrop spectrophotometer screen
- **Format**: Tabular data with concentration values
- **Use Case**: Testing standard Nanodrop data extraction

### 2. `plate_reader_96well.jpg`
- **Type**: 96-well plate reader display
- **Format**: Grid layout (A1-H12)
- **Use Case**: Testing plate format detection and extraction
- **Expected**: Should extract ~96 wells with proper formatting

### 3. `uv_vis_history.jpg`
- **Type**: UV-Vis spectrophotometer history screen
- **Format**: Tabular data with absorbance values
- **Use Case**: Testing flexible instrument support
- **Note**: Previously caused "Not a Nanodrop image" errors (now fixed)

### 4. `luminescence_plate.jpg`
- **Type**: Luminescence plate reader
- **Format**: 96-well plate with luminescence values
- **Use Case**: Testing alternative plate reader formats

## Testing Commands

### Quick Test (Single Image)
```bash
# Test specific image in dev
python scripts/send_test_email.py --dev --image tests/fixtures/test_images/plate_reader_96well.jpg

# Test specific image in prod
python scripts/send_test_email.py --prod --image tests/fixtures/test_images/nanodrop_standard.jpg
```

### Auto-Detection Test
```bash
# Will automatically find and use first available test image
python scripts/send_test_email.py --dev
```

### Full Test Suite
```bash
# Test all images in development
python scripts/test_email_pipeline.py --env dev

# Test all images in production (careful!)
python scripts/test_email_pipeline.py --env prod
```

## Adding New Test Images

1. Add new test images to: `tests/fixtures/test_images/`
2. Use descriptive names: `instrument_type_description.jpg`
3. Include various formats:
   - Standard tables (Nanodrop, UV-Vis)
   - 96-well plates
   - Different instruments
   - Edge cases

## Expected Behavior

- **Standard Tables**: Extract headers and row data
- **96-Well Plates**: 
  - Detect as plate format
  - Extract well positions (A1, B2, etc.)
  - Generate complete 96-well grid in CSV
  - Show "not extracted" for missing wells
- **Email Response**: 
  - CSV attachment with extracted data
  - Preview of first 5 samples/wells in email body
  - Quality assessment indicators

## Troubleshooting

If a test image fails:
1. Check CloudWatch logs for the specific error
2. Verify the image is readable and clear
3. Check if it's a new instrument type that needs prompt adjustment
4. Test in dev environment first before prod