from decimal import Decimal
from django.utils.dateparse import parse_date


def normalize_core_invoice_fields(data: dict) -> dict:
    """
    Normalize ONLY the 4 canonical invoice fields
    used for duplicate detection.
    """

    return {
        "invoice_no": _str(data.get("Invoice No")),
        "gstin": _str(data.get("Supplier GSTIN")),
        "invoice_date": _date(data.get("Invoice Date")),
        "invoice_amount": _decimal(data.get("Total Amount")),
    }


def _str(v):
    return None if not v or v == "-" else str(v).strip()


def _decimal(v):
    try:
        return Decimal(str(v).replace(",", "")) if v not in ("-", "0") else None
    except Exception:
        return None


def _date(v):
    return parse_date(v) if v and v != "-" else None
