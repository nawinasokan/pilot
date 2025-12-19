# app/gemini/builder.py
from app.models import CustomExtractionField
from app.gemini.prompts import SYSTEM_PROMPT, INVOICE_EXTRACTION_MASTER_PROMPT


DEFAULT_VALUE = {
    "string": "-",
    "number": "0",
    "date": "-",
    "boolean": "false",
}


def build_invoice_prompt():
    fields = CustomExtractionField.objects.filter(is_required=True)

    if not fields.exists():
        raise ValueError("No custom extraction fields configured")

    instructions = []
    schema = []

    for f in fields:
        instructions.append(
            f'- "{f.name}" (type: {f.field_type}, default: "{DEFAULT_VALUE[f.field_type]}")'
        )
        schema.append(f'"{f.name}": "{DEFAULT_VALUE[f.field_type]}"')

    return f"""
{SYSTEM_PROMPT}

{INVOICE_EXTRACTION_MASTER_PROMPT}

### STRICT EXTRACTION RULES (MANDATORY)
1. You MUST extract ONLY the fields listed below.
2. DO NOT add any extra keys.
3. DO NOT rename fields.
4. If a field value is not clearly visible, return its default value.
5. If ANY doubt exists, return the default value.
6. Output MUST be a valid JSON object with EXACTLY these keys and NOTHING else.

### ALLOWED FIELDS (ALLOWLIST)
{chr(10).join(instructions)}

### OUTPUT JSON SCHEMA (STRICT)
{{
{", ".join(schema)}
}}
""".strip()
