# app/gemini_services/invoice_storage.py

import hashlib
from django.db import transaction, IntegrityError
from app.models import InvoiceExtraction, CustomExtractionField
from app.gemini.normalizer import normalize_core_invoice_fields


def _fingerprint_from_core_fields(invoice_no, gstin, invoice_date, invoice_amount):
    """
    Stable duplicate fingerprint based ONLY on the 4 core invoice fields.
    """
    raw = f"{invoice_no}|{gstin}|{invoice_date}|{invoice_amount}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def store_invoice_extraction(*, batch, source_file_name, source_file_url, extracted_data):
    """
    Stores invoice extraction with:
    - STRICT custom field enforcement
    - FIXED duplicate logic (4 core invoice fields)
    - SAFE DB-level deduplication
    """

    # ---------------------------------------------------
    # 1️⃣ Enforce Custom Field Allowlist (HARD FILTER)
    # ---------------------------------------------------
    allowed_fields = set(
        CustomExtractionField.objects
        .filter(is_required=True)
        .values_list("name", flat=True)
    )

    # If no custom fields exist → block extraction
    if not allowed_fields:
        raise ValueError("No custom extraction fields configured")

    # Drop any extra keys returned by Gemini
    filtered_data = {
        key: value
        for key, value in extracted_data.items()
        if key in allowed_fields
    }

    # ---------------------------------------------------
    # 2️⃣ Normalize ONLY the 4 CORE invoice fields
    # ---------------------------------------------------
    core = normalize_core_invoice_fields(filtered_data)

    # ---------------------------------------------------
    # 3️⃣ Build duplicate fingerprint (CORE FIELDS ONLY)
    # ---------------------------------------------------
    fingerprint = _fingerprint_from_core_fields(
        core["invoice_no"],
        core["gstin"],
        core["invoice_date"],
        core["invoice_amount"],
    )

    # ---------------------------------------------------
    # 4️⃣ Store in DB (with duplicate protection)
    # ---------------------------------------------------
    try:
        with transaction.atomic():
            return InvoiceExtraction.objects.create(
                batch=batch,
                source_file_name=source_file_name,
                source_file_url=source_file_url,

                # Canonical fields (for search & reporting)
                invoice_no=core["invoice_no"],
                invoice_supplier_gstin_number=core["gstin"],
                invoice_date=core["invoice_date"],
                invoice_amount=core["invoice_amount"],

                duplicate_fingerprint=fingerprint,

                # Only allowed custom fields are stored
                extracted_data=filtered_data,

                status="SUCCESS",
            )

    except IntegrityError:
        # Duplicate detected by DB unique constraint
        existing = InvoiceExtraction.objects.get(
            duplicate_fingerprint=fingerprint
        )
        existing.status = "DUPLICATE"
        existing.save(update_fields=["status"])
        return existing
