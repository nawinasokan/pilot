# app/gemini/builder.py

from app.models import CustomExtractionField
from app.gemini.prompts import SYSTEM_PROMPT, INVOICE_EXTRACTION_MASTER_PROMPT

# ============================================================
# Typed defaults (CRITICAL – DO NOT CHANGE)
# ============================================================

DEFAULT_VALUE = {
    "string": "-",
    "number": 0,
    "date": None,
    "boolean": False,
}


def _json_default(value):
    """
    Convert Python default into strict JSON literal.
    """
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    return f'"{value}"'


# ============================================================
# Prompt Builder
# ============================================================

def build_invoice_prompt(ocr_text: str) -> str:
    fields = CustomExtractionField.objects.filter(is_required=True)
    if not fields.exists():
        raise ValueError("No custom extraction fields configured")

    field_instructions = []
    json_schema = []

    for f in fields:
        field_instructions.append(
            f'- "{f.name}" (type: {f.field_type}, default: {DEFAULT_VALUE[f.field_type]})'
        )
        json_schema.append(
            f'"{f.name}": {_json_default(DEFAULT_VALUE[f.field_type])}'
        )

    return f"""
{SYSTEM_PROMPT}

{INVOICE_EXTRACTION_MASTER_PROMPT}

==================== CRITICAL FILTER RULES ====================

- Extract values ONLY if they clearly belong to a TAX INVOICE.
- Ignore emails, letters, brochures, logos, seals, signatures, footers.
- If the document is NOT an invoice:
  → RETURN THE FULL JSON SCHEMA WITH DEFAULT VALUES ONLY.

==================== FIELD ISOLATION RULES ====================

- Each field must be extracted independently.
- DO NOT infer one field from another.
- DO NOT reuse values across fields.
- If a value is not explicitly present, return the default ONLY.

==================== TRANSLATION & NORMALIZATION GUARD ====================

- DO NOT translate, paraphrase, or romanize any text.
- DO NOT rewrite names, addresses, or identifiers.
- Allowed normalization ONLY applies to:
  • Dates (formatting only, same meaning)
  • Numeric values (remove commas only)
  • Currency → ISO code (INR, USD, CNY, JPY, etc.)
- All other text MUST be returned EXACTLY AS SEEN in OCR.

==================== REQUIRED FIELDS ====================

The output JSON MUST contain EXACTLY these fields.
DO NOT add, remove, or rename fields.

{chr(10).join(field_instructions)}

==================== RAW OCR TEXT ====================

--- RAW OCR TEXT START ---
{ocr_text}
--- RAW OCR TEXT END ---

==================== OUTPUT FORMAT ====================

Return STRICTLY VALID JSON.
NO markdown.
NO comments.
NO explanations.

{{
{", ".join(json_schema)}
}}
""".strip()
