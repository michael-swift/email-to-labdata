#!/usr/bin/env python3
"""CSV generation and quality assessment helpers."""

import csv
from io import StringIO
from typing import Any, Dict, List


def _safe_float(value):
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        cleaned = (
            value.replace(',', '')
            .replace('ng/uL', '')
            .replace('ng/μL', '')
            .replace('ng/u', '')
            .replace('>', '')
            .replace('<', '')
            .strip()
        )
        try:
            return float(cleaned)
        except ValueError:
            return None
    return None


def assess_quality(a260_a280, a260_a230, concentration):
    ratio_260_280 = _safe_float(a260_a280)
    ratio_260_230 = _safe_float(a260_a230)
    concentration_val = _safe_float(concentration)

    issues: List[str] = []

    if concentration_val is None:
        issues.append("Concentration unavailable")
    else:
        if concentration_val < 0:
            issues.append("Invalid negative concentration")
        elif concentration_val == 0:
            issues.append("Zero concentration")
        elif concentration_val < 5:
            issues.append("Very low concentration (<5 ng/uL)")

    if ratio_260_280 is not None:
        if ratio_260_280 < 1.6:
            issues.append("Possible protein contamination (low 260/280)")
        elif ratio_260_280 > 2.2:
            issues.append("Possible measurement issue (high 260/280)")
    else:
        issues.append("260/280 ratio missing")

    if ratio_260_230 is not None:
        if ratio_260_230 < 1.8:
            issues.append("Possible organic contamination (low 260/230)")
        elif ratio_260_230 > 2.6:
            issues.append("Possible salt carryover (high 260/230)")
    else:
        issues.append("260/230 ratio missing")

    if ratio_260_280 is not None:
        issues = [msg for msg in issues if msg != "260/280 ratio missing"]
    if ratio_260_230 is not None:
        issues = [msg for msg in issues if msg != "260/230 ratio missing"]

    return " ; ".join(issues) if issues else "Good quality"


def _looks_like_nanodrop_sample(sample: Dict[str, Any]) -> bool:
    if not isinstance(sample, dict):
        return False
    has_sample_number = any(key in sample for key in ['sample_number', '#'])
    has_concentration = any(key in sample for key in ['concentration', 'ng/uL', 'ng/μL', 'ng/無'])
    has_ratios = any(key in sample for key in ['A260/A280', 'a260_a280'])
    return has_sample_number and has_concentration and has_ratios


def annotate_sample_quality(data: Dict[str, Any]) -> Dict[str, Any]:
    samples = data.get('samples')
    if not isinstance(data, dict) or not isinstance(samples, list) or not samples:
        return data

    first_sample = next((s for s in samples if isinstance(s, dict)), None)
    if not isinstance(first_sample, dict):
        return data

    if 'well' in first_sample and 'value' in first_sample:
        return data  # plate format

    if not any(_looks_like_nanodrop_sample(sample) for sample in samples if isinstance(sample, dict)):
        return data

    for sample in samples:
        if not isinstance(sample, dict):
            continue
        a260_a280 = sample.get('A260/A280', sample.get('a260_a280'))
        a260_a230 = sample.get('A260/A230', sample.get('a260_a230'))
        concentration = sample.get('ng/uL', sample.get('ng/μL', sample.get('ng/無', sample.get('concentration'))))
        quality = sample.get('Quality Assessment') or sample.get('quality') or assess_quality(
            a260_a280, a260_a230, concentration
        )
        sample['Quality Assessment'] = quality
        sample['quality'] = quality
    return data


def _infer_dynamic_headers(samples):
    headers = []
    for sample in samples:
        if not isinstance(sample, dict):
            continue
        for key in sample.keys():
            normalized_key = key.strip()
            if normalized_key.lower() == 'quality' or normalized_key == 'Quality Assessment':
                continue
            if normalized_key not in headers:
                headers.append(normalized_key)
    return headers


def _sanitize_csv_row(row):
    """Prevent CSV formula injection by escaping dangerous cell prefixes."""
    sanitized_row = []
    for value in row:
        if value is None:
            sanitized_row.append('')
            continue
        if isinstance(value, (int, float)):
            sanitized_row.append(value)
            continue
        value_str = str(value)
        stripped = value_str.lstrip()
        if stripped.startswith(('=', '+', '-', '@')) or stripped.startswith(('\t', '\r')):
            sanitized_row.append("'" + value_str)
        else:
            sanitized_row.append(value_str)
    return sanitized_row


def generate_csv(data: Dict[str, Any]) -> str:
    output = StringIO()
    writer = csv.writer(output)

    if 'samples' in data and isinstance(data['samples'], list):
        samples = data['samples']
        assay_type = data.get('assay_type', data.get('instrument', 'Unknown'))
    elif 'long_form_data' in data:
        samples = data['long_form_data'].get('samples', [])
        assay_type = data.get('assay_type_guess', 'Unknown')
    else:
        samples, assay_type = [], 'Unknown'

    if not samples:
        writer.writerow(['Sample', 'Data', 'Note'])
        writer.writerow(['No data', 'extracted', 'Please check image quality'])
        return output.getvalue()

    first_sample = samples[0]
    columns = data.get('columns')
    is_plate_format = ('well' in first_sample and 'value' in first_sample) or \
        (data.get('is_plate_format', False)) or \
        (columns and all(str(col).isdigit() for col in columns[:5]))
    nanodrop_like = all(_looks_like_nanodrop_sample(sample) for sample in samples if isinstance(sample, dict))

    dynamic_headers = []
    column_headers = []
    append_quality = False
    append_assay = False

    if is_plate_format:
        headers = ['Well', 'Value', 'Quality Assessment', 'Assay Type']
        mode = 'plate'
    elif columns:
        column_headers = list(columns)
        append_quality = 'Quality Assessment' not in column_headers
        append_assay = 'Assay Type' not in column_headers
        headers = column_headers[:]
        if append_quality:
            headers.append('Quality Assessment')
        if append_assay:
            headers.append('Assay Type')
        mode = 'columns'
    elif 'long_form_data' in data:
        headers = ['Sample ID']
        std_vals = first_sample.get('standardized_values', {})
        if 'concentration_ng_ul' in std_vals:
            headers.append('Concentration (ng/uL)')
        if 'a260_a280' in std_vals:
            headers.append('A260/A280')
        if 'a260_a230' in std_vals:
            headers.append('A260/A230')
        headers.extend(['Quality Assessment', 'Assay Type'])
        mode = 'long_form'
    elif nanodrop_like:
        headers = ['Sample Number', 'Concentration (ng/uL)', 'A260/A280', 'A260/A230', 'Quality Assessment', 'Assay Type']
        mode = 'nanodrop'
    else:
        dynamic_headers = _infer_dynamic_headers(samples)
        headers = dynamic_headers[:]
        if 'Quality Assessment' not in headers:
            headers.append('Quality Assessment')
        if 'Assay Type' not in headers:
            headers.append('Assay Type')
        mode = 'dynamic'

    writer.writerow(headers)

    def _write_row(row):
        if len(row) > len(headers):
            row = row[:len(headers)]
        writer.writerow(_sanitize_csv_row(row))

    if mode == 'plate':
        extracted_data = {}
        for sample in samples:
            if 'well' in sample and 'value' in sample:
                extracted_data[sample['well']] = sample['value']
        for row_letter in 'ABCDEFGH':
            for col_number in range(1, 13):
                well = f"{row_letter}{col_number}"
                value = extracted_data.get(well, 'not extracted')
                quality = 'Check manually' if well in extracted_data else 'Manual entry required'
                _write_row([well, value, quality, assay_type])
        return output.getvalue()

    for sample in samples:
        row = []
        if mode == 'columns':
            for header in column_headers:
                row.append(sample.get(header, ''))
            if append_quality:
                row.append(sample.get('Quality Assessment', sample.get('quality', 'Check manually')))
            if append_assay:
                row.append(assay_type)
        elif mode == 'long_form':
            std_vals = sample.get('standardized_values', {})
            row.append(std_vals.get('sample_id', sample.get('row_id', 'Unknown')))
            if 'Concentration (ng/uL)' in headers:
                row.append(std_vals.get('concentration_ng_ul', ''))
            if 'A260/A280' in headers:
                row.append(std_vals.get('a260_a280', ''))
            if 'A260/A230' in headers:
                row.append(std_vals.get('a260_a230', ''))
            row.append(sample.get('quality', sample.get('Quality Assessment', 'Check manually')))
            row.append(assay_type)
        elif mode == 'nanodrop':
            sample_number = sample.get('sample_number', sample.get('#', ''))
            concentration = sample.get('ng/uL', sample.get('ng/μL', sample.get('ng/無', sample.get('concentration', ''))))
            a260_a280 = sample.get('A260/A280', sample.get('a260_a280', ''))
            a260_a230 = sample.get('A260/A230', sample.get('a260_a230', ''))
            quality = sample.get('quality', sample.get('Quality Assessment')) or assess_quality(
                a260_a280, a260_a230, concentration
            )
            row = [sample_number, concentration, a260_a280, a260_a230, quality, assay_type]
        else:  # dynamic
            for header in dynamic_headers:
                row.append(sample.get(header, sample.get(header.replace(' ', '_'), '')))
            quality = sample.get('Quality Assessment', sample.get('quality', 'Not assessed'))
            row.append(quality)
            row.append(assay_type)
        _write_row(row)

    return output.getvalue()
