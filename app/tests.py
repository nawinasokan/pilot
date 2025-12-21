# from django.test import TestCase

from app.gemini.ocr_engine import extract_text_from_url

url = "https://resources.tallysolutions.com/mena/wp-content/uploads/2022/01/tax-invoice-format-2-tallyprime.jpg"
text = extract_text_from_url(url)
print(text)