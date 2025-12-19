# app/gemini/url_filter.py
from urllib.parse import urlparse
import os
import logging

logger = logging.getLogger(__name__)

ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".pdf", ".jfif"}


def normalize_url(url: str) -> str | None:
    if not url:
        return None

    url = url.strip()

    # Must be http / https
    if not url.startswith(("http://", "https://")):
        return None

    # Remove trailing slash
    url = url.rstrip("/")

    parsed = urlparse(url)
    if not parsed.scheme or not parsed.netloc:
        return None

    _, ext = os.path.splitext(parsed.path.lower())
    if ext not in ALLOWED_EXTENSIONS:
        return None

    return url


def filter_valid_invoice_urls(urls, dedupe=True):
    valid = []
    invalid = []
    seen = set()

    for url in urls:
        cleaned = normalize_url(url)

        if not cleaned:
            invalid.append(url)
            continue

        if dedupe:
            if cleaned in seen:
                continue
            seen.add(cleaned)

        valid.append(cleaned)

    return valid, invalid

