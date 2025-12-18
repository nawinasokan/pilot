from django.db import close_old_connections, transaction
from .models import UploadManagement
import pandas as pd


def process_uploaded_file(upload_id):
    close_old_connections()

    base_upload = UploadManagement.objects.get(id=upload_id)

    selected_header = base_upload.file_url  
    file_path = base_upload.storage_path
    batch_id = base_upload.batch_id

    ext = file_path.split(".")[-1].lower()

    if ext == "csv":
        df = pd.read_csv(file_path, dtype=str)
    elif ext in ["xlsx", "xls"]:
        df = pd.read_excel(file_path, dtype=str, engine="openpyxl")
    else:
        base_upload.status = "FAILED"
        base_upload.save(update_fields=["status"])
        return

    if selected_header not in df.columns:
        base_upload.status = "FAILED"
        base_upload.save(update_fields=["status"])
        return

    values = (
        df[selected_header]
        .dropna()
        .astype(str)
        .str.strip()
        .tolist()
    )

    seen = set()

    with transaction.atomic():

        first_value = values[0]
        base_upload.file_url = first_value
        base_upload.status = "COMPLETED"
        base_upload.save(update_fields=["file_url", "status"])
        seen.add(first_value)

        # Create remaining rows
        bulk_rows = []  
        for v in values[1:]:
            link_status = "DUPLICATE" if v in seen else "VALID"
            seen.add(v)

            bulk_rows.append(
                UploadManagement(
                    batch_id=batch_id,
                    file_name=base_upload.file_name,
                    file_url=v,                     
                    storage_path=file_path,
                    status="COMPLETED",
                    link_status=link_status,
                    created_by=base_upload.created_by
                )
            )

        UploadManagement.objects.bulk_create(bulk_rows)