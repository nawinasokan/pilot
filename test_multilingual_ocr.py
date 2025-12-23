"""
Test script for multilingual OCR support
Tests English, Chinese, Japanese, and Korean invoice recognition
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.gemini.ocr_engine import extract_text_from_url


test_invoices = {
    "English": "https://resources.tallysolutions.com/mena/wp-content/uploads/2022/01/tax-invoice-format-2-tallyprime.jpg",
}

print("=" * 60)
print("MULTILINGUAL OCR TEST")
print("=" * 60)

for language, url in test_invoices.items():
    print(f"\n📝 Testing {language} invoice...")
    print(f"URL: {url}")
    print("-" * 60)
    
    try:
        text = extract_text_from_url(url)
        
        if text:
            print(f"✅ SUCCESS - Extracted {len(text)} characters")
            print("\nFirst 200 characters:")
            print(text[:200])
            print("...")
        else:
            print("❌ FAILED - No text extracted")
            
    except Exception as e:
        print(f"❌ ERROR: {e}")
    
    print("-" * 60)

print("\n" + "=" * 60)
print("TEST COMPLETE")
print("=" * 60)
print("\n💡 Tips:")
print("- If English works, multilingual model is loaded correctly")
print("- First run downloads Chinese model (~100MB)")
print("- Replace sample URLs with actual Asian language invoices to test")
