#!/usr/bin/env python3
"""SES email helper functions."""

from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from typing import List, Sequence

from structured_logger import logger


def slugify_label(value, fallback="lab_data"):
    if not value:
        return fallback
    slug = value.replace(" ", "_").replace("/", "_")
    slug = slug.replace("(", "").replace(")", "")
    slug = ''.join(ch for ch in slug if ch.isalnum() or ch in ('_', '-')).lower()
    return slug or fallback


def compress_image_for_email(image_data, max_size_kb=2000):
    from io import BytesIO
    from PIL import Image

    try:
        img = Image.open(BytesIO(image_data))
        if img.mode in ('RGBA', 'P'):
            img = img.convert('RGB')

        quality = 85
        compressed_data = None

        while quality >= 30:
            output = BytesIO()
            img.save(output, format='JPEG', quality=quality, optimize=True)
            compressed_data = output.getvalue()
            if len(compressed_data) <= max_size_kb * 1024:
                break
            quality -= 15

        return compressed_data if compressed_data else image_data
    except Exception:
        return image_data


def _build_standard_body(instrument_label, assay_type, image_count, sample_count, commentary, samples):
    body = f"""Your lab data has been digitized successfully!

Instrument Type: {instrument_label}
Assay Type: {assay_type}
Images Processed: {image_count}
Samples Extracted: {sample_count}

ANALYSIS SUMMARY:
{commentary}

SAMPLE RESULTS:
"""
    for i, sample in enumerate(samples, 1):
        sample_id = sample.get('#', sample.get('sample_number', f'Sample {i}'))
        concentration = sample.get('ng/μL', sample.get('ng/uL', sample.get('ng/無', sample.get('concentration', 'N/A'))))
        a260_280 = sample.get('A260/A280', sample.get('a260_a280'))
        a260_230 = sample.get('A260/A230', sample.get('a260_a230'))
        if isinstance(concentration, (int, float)) and concentration < 0:
            body += f"    {sample_id}: INVALID (negative value: {concentration})\n"
        elif a260_280 and a260_230:
            body += f"    {sample_id}: {concentration} ng/uL (260/280: {a260_280}, 260/230: {a260_230})\n"
        else:
            body += f"    {sample_id}: {concentration}\n"
    return body


def _build_plate_body(instrument_label, sample_count, samples):
    body = f"""Your lab data has been digitized successfully!

Instrument Type: {instrument_label}
Format: 96-well plate
Samples extracted: {sample_count} of 96 wells

The detailed results are attached as a complete 96-well CSV. Wells not extracted by AI are marked as "not extracted" for manual review.

Data Preview (first 5 wells):
"""
    for i, sample in enumerate(samples[:5], 1):
        well = sample.get('well', f'Sample {i}')
        value = sample.get('value', 'N/A')
        body += f"    {well}: {value}\n"
    if sample_count > 5:
        body += f"    ... and {sample_count - 5} more wells (see CSV for complete data)\n"
    return body


def send_success_email(
    ses_client,
    recipients: Sequence[str],
    csv_content: str,
    data,
    original_images: Sequence[bytes],
):
    msg = MIMEMultipart()
    recipients = list(recipients)
    primary_recipient = recipients[0]
    cc_recipients = recipients[1:]

    assay_type = data.get('assay_type', 'Unknown')
    sample_count = len(data['samples'])
    commentary = data.get('commentary', 'No additional analysis provided.')
    image_count = len(original_images) if isinstance(original_images, list) else 1
    instrument_label = data.get('instrument') or assay_type
    instrument_slug = slugify_label(instrument_label)

    msg['Subject'] = f'Lab Data Results - {instrument_label} ({sample_count} samples, {image_count} images)'
    msg['From'] = 'digitizer@seminalcapital.net'
    msg['To'] = primary_recipient
    msg['X-Lab-Data-Processed'] = 'true'
    if cc_recipients:
        msg['CC'] = ', '.join(cc_recipients)

    is_plate_format = data.get('is_plate_format', False) or (
        data['samples'] and 'well' in data['samples'][0]
    )

    logger.info(
        "Email format detection",
        is_plate_format=is_plate_format,
        has_is_plate_format_field=data.get('is_plate_format', False),
        has_well_in_samples=(data['samples'] and 'well' in data['samples'][0]) if data['samples'] else False,
        first_sample_structure=data['samples'][0] if data['samples'] else None,
    )

    if is_plate_format:
        body = _build_plate_body(instrument_label, sample_count, data['samples'])
    else:
        body = _build_standard_body(instrument_label, assay_type, image_count, sample_count, commentary, data['samples'])

    body += """

The detailed results are attached as a CSV file, along with your original image(s) for reference.

--
Lab Data Digitization Service
"""

    msg.attach(MIMEText(body, 'plain'))

    csv_attachment = MIMEBase('text', 'csv')
    csv_attachment.set_payload(csv_content)
    encoders.encode_base64(csv_attachment)
    csv_attachment.add_header(
        'Content-Disposition',
        f'attachment; filename=labdata_{instrument_slug}_{sample_count}_samples.csv'
    )
    msg.attach(csv_attachment)

    if isinstance(original_images, list):
        images = original_images
    else:
        images = [original_images]

    for i, image_data in enumerate(images, 1):
        compressed_image = compress_image_for_email(image_data, max_size_kb=2000)
        img_attachment = MIMEBase('image', 'jpeg')
        img_attachment.set_payload(compressed_image)
        encoders.encode_base64(img_attachment)
        img_attachment.add_header(
            'Content-Disposition',
            f'attachment; filename=labdata_image_{i}.jpg'
        )
        msg.attach(img_attachment)

    ses_client.send_raw_email(
        Source=msg['From'],
        Destinations=recipients,
        RawMessage={'Data': msg.as_string()}
    )


def send_error_email(ses_client, to_email: str, error_message: str):
    ses_client.send_email(
        Source='digitizer@seminalcapital.net',
        Destination={'ToAddresses': [to_email]},
        Message={
            'Subject': {'Data': 'Lab Data Processing Error'},
            'Body': {
                'Text': {
                    'Data': f"""
                    Sorry, we couldn't process your lab instrument image.
                    
                    Error: {error_message}
                    
                    Please ensure:
                    - You attached a clear photo of the instrument screen
                    - The entire screen is visible
                    - The image is in JPEG or PNG format
                    
                    --
                    Lab Data Digitization Service
                    """
                }
            }
        }
    )
