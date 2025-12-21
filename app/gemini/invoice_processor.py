# app/gemini/invoice_processor.py

import sys
import json
import hashlib
from decimal import Decimal
from concurrent.futures import ThreadPoolExecutor, as_completed
from django.db.models import F
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.db import transaction, IntegrityError
from app.models import ExtractionBatch, InvoiceExtraction, CustomExtractionField
from app.gemini.ocr_engine import extract_text_from_url
from app.gemini.builder import build_invoice_prompt
from app.gemini.client import client

MAX_WORKERS = 10  


# ============ DATA NORMALIZATION ============

def _str(v):
    return None if not v or v == "-" else str(v).strip()

def _decimal(v):
    try:
        return Decimal(str(v).replace(",", "")) if v not in ("-", "0") else None
    except Exception:
        return None

def _date(v):
    return parse_date(v) if v and v != "-" else None

def normalize_core_invoice_fields(data: dict) -> dict:
    """Normalize the 4 canonical invoice fields for duplicate detection."""
    return {
        "invoice_no": _str(data.get("Invoice No")),
        "gstin": _str(data.get("Supplier GSTIN")),
        "invoice_date": _date(data.get("Invoice Date")),
        "invoice_amount": _decimal(data.get("Total Amount")),
    }


# ============ INVOICE STORAGE ============

def _fingerprint(no, gstin, dt, amt):
    return hashlib.sha256(f"{no}|{gstin}|{dt}|{amt}".encode()).hexdigest()

def store_invoice_extraction(*, batch_master, url, extracted_data, user_id):
    """Store extracted invoice data with duplicate detection."""
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


# ============ OCR & GEMINI VALIDATION ============


def validate_ocr_quality(raw_text):

    if not raw_text:
        return False, "Empty OCR text"
    
    clean_text = ' '.join(raw_text.split())
    
    if len(clean_text) < 50:
        return False, f"OCR text too short ({len(clean_text)} chars, minimum 50 required)"
    
    words = [w for w in clean_text.split() if len(w) >= 3 and any(c.isalpha() for c in w)]
    if len(words) < 10:
        return False, f"Too few meaningful words ({len(words)}, minimum 10 required)"
    
    invoice_keywords = [
        'invoice', 'bill', 'receipt', 'tax', 'amount', 'total', 'date',
        'gstin', 'gst', 'vat', 'supplier', 'buyer', 'customer', 'payment',
        'quantity', 'price', 'subtotal', 'grand total', 'net amount'
    ]
    
    text_lower = clean_text.lower()
    has_invoice_keyword = any(keyword in text_lower for keyword in invoice_keywords)
    
    if not has_invoice_keyword:
        return False, "No invoice-related keywords found (likely empty template or non-invoice image)"
    
    short_words = [w for w in words if len(w) <= 3]
    if len(short_words) / len(words) > 0.7:
        return False, "Text appears to be mostly gibberish/OCR errors"
    
    return True, "Valid invoice text"


def validate_gemini_response(data):
    if not data or not isinstance(data, dict):
        return False
    
    placeholders = {'-', '0', '0.0', '0.00', '0.000', 'n/a', 'na', 'null', 'none', '', 
                  'not available', 'not found', 'nil', 'blank'}
    
    all_values = [str(val).strip().lower() for val in data.values()]
    
    if not all_values:
        return False
    
    placeholder_count = sum(1 for v in all_values if v in placeholders)
    
    if placeholder_count / len(all_values) >= 0.7:
        print(f"⚠️ Placeholder ratio: {placeholder_count}/{len(all_values)} = {placeholder_count/len(all_values)*100:.1f}%")
        return False
    
    return True


def process_single_invoice(url, batch_master_id, user_id, index, total):
    result = {
        'url': url,
        'index': index,
        'status': 'failed',
        'error': None
    }
    
    try:
        print(f"📝 Processing {index}/{total}: {url}")
        sys.stdout.flush()
        
        # OCR Extraction
        raw_text = extract_text_from_url(url)
        
        print("========== OCR OUTPUT ==========")
        print(raw_text[:500])
        print("================================")
        sys.stdout.flush()
        
        # Validate OCR quality
        is_valid, validation_reason = validate_ocr_quality(raw_text)
        
        if not is_valid:
            print(f"⚠️ SKIPPING: {validation_reason}")
            print(f"💰 Saved API tokens by not sending to Gemini")
            sys.stdout.flush()
            
            batch_master = ExtractionBatch.objects.get(id=batch_master_id)
            InvoiceExtraction.objects.create(
                batch_master=batch_master,
                source_file_name=batch_master.file_name,
                source_file_url=url,
                invoice_no=None,
                invoice_supplier_gstin_number=None,
                invoice_date=None,
                invoice_amount=None,
                duplicate_fingerprint=hashlib.sha256(f"{url}_{timezone.now().isoformat()}".encode()).hexdigest(),
                extracted_data={"error": validation_reason},
                status="FAILED",
                created_by_id=user_id
            )
            
            raise ValueError(f"Invalid OCR quality: {validation_reason}")
        
        print(f"✅ OCR validation passed: {validation_reason}")
        sys.stdout.flush()
        
        # Gemini ExtractionW
        print("🧠 Sending text to Gemini")
        sys.stdout.flush()
        
        prompt = build_invoice_prompt(raw_text)
        
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=[prompt]
        )
        
        output = response.text or ""
        if "{" not in output:
            raise ValueError("Gemini did not return JSON")
        
        json_str = output[output.find("{"):output.rfind("}") + 1]
        extracted_data = json.loads(json_str)
        
        print(f"🔍 Gemini extracted data: {extracted_data}")
        sys.stdout.flush()
        
        # Validate Gemini response
        if not validate_gemini_response(extracted_data):
            print("⚠️ REJECTING: Gemini returned only default values (empty template detected)")
            print(f"💰 Prevented storing invalid invoice data")
            sys.stdout.flush()
            
            batch_master = ExtractionBatch.objects.get(id=batch_master_id)
            InvoiceExtraction.objects.create(
                batch_master=batch_master,
                source_file_name=batch_master.file_name,
                source_file_url=url,
                invoice_no=None,
                invoice_supplier_gstin_number=None,
                invoice_date=None,
                invoice_amount=None,
                duplicate_fingerprint=hashlib.sha256(f"{url}_{timezone.now().isoformat()}".encode()).hexdigest(),
                extracted_data={"error": "Empty template - Gemini returned only default values", "raw_response": extracted_data},
                status="FAILED",
                created_by_id=user_id
            )
            
            raise ValueError("Empty template detected: Gemini returned only default values")
        
        print(f"✅ Gemini validation passed: Contains valid invoice data")
        sys.stdout.flush()
        
        # Store in database
        batch_master = ExtractionBatch.objects.get(id=batch_master_id)
        store_invoice_extraction(
            batch_master=batch_master,
            url=url,
            extracted_data=extracted_data,
            user_id=user_id
        )
        
        print("✅ Invoice extracted")
        result['status'] = 'success'
        
    except Exception as e:
        print(f"❌ Invoice failed: {e}")
        result['error'] = str(e)
        
        if "Invalid OCR quality" not in str(e) and "Empty template" not in str(e):
            try:
                batch_master = ExtractionBatch.objects.get(id=batch_master_id)
                if not InvoiceExtraction.objects.filter(source_file_url=url, batch_master=batch_master).exists():
                    InvoiceExtraction.objects.create(
                        batch_master=batch_master,
                        source_file_name=batch_master.file_name,
                        source_file_url=url,
                        invoice_no=None,
                        invoice_supplier_gstin_number=None,
                        invoice_date=None,
                        invoice_amount=None,
                        duplicate_fingerprint=hashlib.sha256(f"{url}_{timezone.now().isoformat()}".encode()).hexdigest(),
                        extracted_data={"error": str(e)},
                        status="FAILED",
                        created_by_id=user_id
                    )
            except Exception as store_error:
                print(f"⚠️ Could not store failed record: {store_error}")
    
    finally:
        try:
            with transaction.atomic():
                ExtractionBatch.objects.filter(id=batch_master_id).update(
                    processed_count=F("processed_count") + 1
                )
        except Exception as e:
            print(f"⚠️ Progress update failed: {e}")
    
    return result


def process_invoices_parallel(batch_master_id, urls, user_id):
    """
    Process multiple invoices in parallel using ThreadPoolExecutor.
    """
    from django.db import connection
    
    batch_master = ExtractionBatch.objects.get(id=batch_master_id)
    total_urls = len(urls)
    
    print(f"🚀 Started Batch {batch_master_id} with {total_urls} invoices")
    print(f"⚙️ Using {MAX_WORKERS} parallel workers")
    sys.stdout.flush()
    
    try:
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            future_to_url = {
                executor.submit(
                    process_single_invoice,
                    url,
                    batch_master_id,
                    user_id,
                    index,
                    total_urls
                ): url
                for index, url in enumerate(urls, start=1)
            }
            
            success_count = 0
            failed_count = 0
            
            for future in as_completed(future_to_url):
                url = future_to_url[future]
                try:
                    result = future.result()
                    if result['status'] == 'success':
                        success_count += 1
                    else:
                        failed_count += 1
                except Exception as e:
                    print(f"❌ Future exception for {url}: {e}")
                    failed_count += 1
        
        batch_master.refresh_from_db()
        batch_master.status = "COMPLETED"
        batch_master.completed_at = timezone.now()
        batch_master.save(update_fields=["status", "completed_at"])
        
        print(f"🏁 Batch Fully Completed")
        print(f"✅ Success: {success_count} | ❌ Failed: {failed_count} | 📊 Total: {total_urls}")
        sys.stdout.flush()
    
    except Exception as e:
        print(f"🛑 BATCH PROCESSING CRASH: {e}")
        import traceback
        traceback.print_exc()
        
        try:
            batch_master.refresh_from_db()
            batch_master.status = "FAILED"
            batch_master.save(update_fields=["status"])
        except:
            pass
    
    finally:
        connection.close()
