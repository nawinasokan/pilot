# app/gemini/builder.py

from app.models import CustomExtractionField
from app.gemini.prompts import SYSTEM_PROMPT, INVOICE_EXTRACTION_MASTER_PROMPT

# Typed defaults (CRITICAL)
DEFAULT_VALUE = {
    "string": "-",
    "number": 0,
    "date": None,
    "boolean": False,
}

def _json_default(value):
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    return f'"{value}"'


def build_invoice_prompt(ocr_text: str) -> str:
    fields = CustomExtractionField.objects.filter(is_required=True)
    if not fields.exists():
        raise ValueError("No custom extraction fields configured")

    instructions = []
    schema = []

    for f in fields:
        instructions.append(
            f'- "{f.name}" (type: {f.field_type}, default: {DEFAULT_VALUE[f.field_type]})'
        )
        schema.append(
            f'"{f.name}": {_json_default(DEFAULT_VALUE[f.field_type])}'
        )

    return f"""
{SYSTEM_PROMPT}

{INVOICE_EXTRACTION_MASTER_PROMPT}

### DATA INPUT: MULTILINGUAL OCR TEXT
The following text was extracted from an invoice using a multilingual OCR engine.

IMPORTANT:
- The OCR text may contain Asian scripts mixed with English.
- DO NOT translate any text.
- Preserve original language exactly as seen.
- Extract values ONLY if explicitly present.

CRITICAL CONSTRAINTS:
- Do NOT guess values.
- Do NOT infer missing information.
- Do NOT fabricate invoice.
- If a value is missing, return the default value ONLY.

--- RAW OCR TEXT START ---
{ocr_text}
--- RAW OCR TEXT END ---

### TARGET JSON SCHEMA (STRICT)
Return VALID JSON only. No explanation.

{{
{", ".join(schema)}
}}
""".strip()
