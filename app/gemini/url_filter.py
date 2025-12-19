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


def filter_valid_invoice_urls(urls: list[str]) -> tuple[list[str], list[str]]:
    """
    Returns:
        valid_urls   -> list of cleaned valid URLs
        invalid_urls -> list of rejected URLs (for logging/audit)
    """
    valid = []
    invalid = []

    for url in urls:
        cleaned = normalize_url(url)
        if cleaned:
            valid.append(cleaned)
        else:
            invalid.append(url)

    return valid, invalid
