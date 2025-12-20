from django.db import transaction, IntegrityError
from django.utils import timezone
from app.models import InvoiceExtraction, CustomExtractionField
from .normalizer import normalize_core_invoice_fields
import hashlib

def _fingerprint(no, gstin, dt, amt):
    return hashlib.sha256(f"{no}|{gstin}|{dt}|{amt}".encode()).hexdigest()

def store_invoice_extraction(*, batch_master, url, extracted_data, user_id):
    allowed_keys = set(CustomExtractionField.objects.filter(is_required=True).values_list("name", flat=True))
    filtered_data = {k: v for k, v in extracted_data.items() if k in allowed_keys}

    core = normalize_core_invoice_fields(extracted_data)
    f_print = _fingerprint(core["invoice_no"], core["gstin"], core["invoice_date"], core["invoice_amount"])

    try:
        with transaction.atomic():
            InvoiceExtraction.objects.create(
                batch_master=batch_master,
                source_file_name=batch_master.file_name,
                source_file_url=url,
                invoice_no=core["invoice_no"],
                invoice_supplier_gstin_number=core["gstin"],
                invoice_date=core["invoice_date"],
                invoice_amount=core["invoice_amount"],
                duplicate_fingerprint=f_print,
                extracted_data=filtered_data,
                status="SUCCESS",
                created_by_id=user_id
            )
    except IntegrityError:
        InvoiceExtraction.objects.filter(duplicate_fingerprint=f_print).update(status="DUPLICATE")

    batch_master.processed_count += 1
    if batch_master.processed_count >= batch_master.total_count:
        batch_master.status = 'COMPLETED'
        batch_master.completed_at = timezone.now()
    batch_master.save()