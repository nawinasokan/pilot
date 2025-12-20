from django.db import close_old_connections, transaction
from .models import UploadManagement
import pandas as pd
import re
from urllib.parse import urlparse
import os

ALLOWED_URL_EXTENSIONS = {".jpg", ".jpeg", ".png", ".pdf", ".jfif"}

import hashlib

def calculate_file_hash(uploaded_file):
    hasher = hashlib.sha256()
    for chunk in uploaded_file.chunks():
        hasher.update(chunk)
    uploaded_file.seek(0) 
    return hasher.hexdigest()

def normalize_url(url: str) -> str:
    """
    Normalize URL coming from Excel / CSV
    """
    if not url:
        return ""

    return (
        str(url)
        .replace("\xa0", "")   # non-breaking space
        .replace("\n", "")
        .replace("\r", "")
        .strip()
    )


def is_valid_image_url(url: str) -> bool:
    """
    URL is VALID only if:
    - scheme is http or https
    - ends with allowed extension
    """
    try:
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https"):
            return False

        ext = os.path.splitext(parsed.path)[1].lower()
        return ext in ALLOWED_URL_EXTENSIONS
    except Exception:
        return False

def process_uploaded_file(upload_id):
    close_old_connections()

    base = UploadManagement.objects.get(id=upload_id)

    column_name = base.file_url      # header name
    file_path = base.storage_path
    batch_id = base.batch_id

    ext = os.path.splitext(file_path)[1].lower()

    # ---------- LOAD FILE ----------
    if ext == ".csv":
        df = pd.read_csv(file_path, dtype=str)
    elif ext in [".xlsx", ".xls"]:
        df = pd.read_excel(file_path, dtype=str, engine="openpyxl")
    else:
        base.status = "FAILED"
        base.save(update_fields=["status"])
        return

    if column_name not in df.columns:
        base.status = "FAILED"
        base.save(update_fields=["status"])
        return

    raw_values = (
        df[column_name]
        .dropna()
        .astype(str)
        .tolist()
    )

    seen = set()

    with transaction.atomic():

        # ---------- FIRST ROW (parent update) ----------
        first_url = normalize_url(raw_values[0])

        base.file_url = first_url
        base.link_status = "VALID" if is_valid_image_url(first_url) else "INVALID"
        base.status = "COMPLETED"
        base.save(update_fields=["file_url", "link_status", "status"])

        seen.add(first_url)

        # ---------- CHILD ROWS ----------
        bulk_rows = []

        for raw in raw_values[1:]:
            url = normalize_url(raw)

            if url in seen:
                status = "DUPLICATE"
            else:
                status = "VALID" if is_valid_image_url(url) else "INVALID"

            seen.add(url)

            bulk_rows.append(
                UploadManagement(
                    batch_id=batch_id,
                    file_name=base.file_name,
                    file_url=url,
                    storage_path=file_path,
                    status="COMPLETED",
                    link_status=status,
                    created_by=base.created_by,
                    file_hash=None   # 🔥 CRITICAL FIX
                )
            )

        if bulk_rows:
            UploadManagement.objects.bulk_create(bulk_rows)