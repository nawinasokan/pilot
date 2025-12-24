# app/gemini/builder.py
from app.models import CustomExtractionField
from app.gemini.prompts import SYSTEM_PROMPT, INVOICE_EXTRACTION_MASTER_PROMPT

DEFAULT_VALUE = {
    "string": "-",
    "number": "0",
    "date": "-",
    "boolean": "false",
}

def build_invoice_prompt(ocr_text):
    fields = CustomExtractionField.objects.filter(is_required=True)
    if not fields.exists():
        raise ValueError("No custom extraction fields configured")

    instructions = []
    schema = []

    for f in fields:
        instructions.append(f'- "{f.name}" (type: {f.field_type}, default: "{DEFAULT_VALUE[f.field_type]}")')
        schema.append(f'"{f.name}": "{DEFAULT_VALUE[f.field_type]}"')

    return f"""
        {SYSTEM_PROMPT}

        {INVOICE_EXTRACTION_MASTER_PROMPT}

        ### DATA INPUT: MULTILINGUAL OCR TEXT
        The following text was extracted from an invoice using a high-precision OCR engine.

        IMPORTANT RULES:
        - The OCR text may contain Indian or Asian languages mixed with English.
        - DO NOT translate names, addresses, item descriptions, or values.
        - Extract values exactly as they appear in the text.
        - If a field value is in a local language, keep it as-is.

        Apply all the forensic rules above to this text.

        --- RAW OCR TEXT START ---
        {ocr_text}
        --- RAW OCR TEXT END ---

        ### TARGET JSON SCHEMA (STRICT)
        {{
        {", ".join(schema)}
        }}
        """.strip()