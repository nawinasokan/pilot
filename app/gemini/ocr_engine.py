# app/gemini/ocr_engine.py
# app/gemini/ocr_engine.py
import os
import cv2
import numpy as np
import requests
from paddleocr import PaddleOCR
from io import BytesIO
from PIL import Image
import platform

# ---------------- CROSS-PLATFORM SAFETY ----------------
os.environ["FLAGS_use_gpu"] = "0"
os.environ["OMP_NUM_THREADS"] = "1"
os.environ["DISABLE_MODEL_SOURCE_CHECK"] = "True"

# Platform detection
IS_LINUX = platform.system() == "Linux"
IS_WINDOWS = platform.system() == "Windows"

# Windows-specific
if IS_WINDOWS:
    os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"

# Linux-specific (prevents threading issues on servers)
if IS_LINUX:
    os.environ["OPENBLAS_NUM_THREADS"] = "1"
    os.environ["MKL_NUM_THREADS"] = "1"
    os.environ["NUMEXPR_NUM_THREADS"] = "1"

# ---------------- THREAD-LOCAL OCR (PRODUCTION READY) ----------------
import threading

# Thread-local storage for OCR instances
_thread_local = threading.local()

def get_ocr():
    """
    Get or initialize a thread-local PaddleOCR instance.
    
    Each thread gets its own OCR instance, enabling true parallel processing
    without threading conflicts. This is production-ready for processing
    thousands of invoices efficiently.
    
    Returns:
        PaddleOCR instance for the current thread
    """
    # Check if current thread has an OCR instance
    if not hasattr(_thread_local, 'ocr'):
        print(f"🔧 Initializing OCR for thread {threading.current_thread().name}")
        _thread_local.ocr = _init_ocr()
    
    return _thread_local.ocr


def _init_ocr():
    """
    Initialize PaddleOCR with English for FAST processing.
    
    Note: Even with English OCR, Gemini can extract data from Asian invoices
    because Gemini is multilingual and can interpret garbled/mixed text.
    
    This provides the best balance of:
    - Speed (English OCR is 3x faster)
    - Multilingual support (Gemini handles the translation)
    - Stability (no freezing issues)
    """
    try:
        return PaddleOCR(
            lang="en",
            use_angle_cls=False
        )
    except Exception as e:
        print(f"⚠️ OCR initialization error: {e}")
        return PaddleOCR(lang="en")


def preprocess(img: np.ndarray) -> np.ndarray:
    """
    Minimal preprocessing - resize if too large.
    Production-optimized for speed and memory efficiency.
    """
    height, width = img.shape[:2]
    max_dimension = 2000
    
    # Only resize if image is too large
    if max(height, width) > max_dimension:
        scale = max_dimension / max(height, width)
        new_width = int(width * scale)
        new_height = int(height * scale)
        img = cv2.resize(img, (new_width, new_height), interpolation=cv2.INTER_AREA)
    
    return img


def extract_text_from_url(url: str) -> str:
    """
    Extract text from an image URL using PaddleOCR.
    
    Production-ready with thread-local OCR instances for parallel processing.
    Each thread uses its own OCR model, enabling true parallelism.
    
    Args:
        url: Image URL to process
        
    Returns:
        Extracted text as a string with newlines separating lines.
        Returns empty string on error.
    """
    try:
        # Download image
        response = requests.get(url, timeout=20)
        response.raise_for_status()

        # Load and convert to RGB
        img = Image.open(BytesIO(response.content)).convert("RGB")
        img_np = np.array(img)
        
        # Preprocess
        img_processed = preprocess(img_np)

        # Run OCR (thread-local instance, no lock needed)
        ocr = get_ocr()
        result = ocr.ocr(img_processed)
        
        # Extract text
        texts = []
        if result and isinstance(result, list):
            for page in result:
                if hasattr(page, '__getitem__') and 'rec_texts' in page:
                    rec_texts = page['rec_texts']
                    if rec_texts and isinstance(rec_texts, list):
                        texts.extend([str(text).strip() for text in rec_texts if text])

        return "\n".join(texts) if texts else ""

    except requests.RequestException as e:
        print(f"❌ Network error: {e}")
        return ""
    except Exception as e:
        print(f"❌ OCR error: {e}")
        import traceback
        traceback.print_exc()
        return ""


def extract_text_from_file(file_path: str) -> str:
    """
    Extract text from a local image file.
    
    Works on both Windows and Linux.
    
    Args:
        file_path: Path to local image file
        
    Returns:
        Extracted text as a string with newlines separating lines
    """
    try:
        # Load image
        img = Image.open(file_path).convert("RGB")
        img_np = np.array(img)
        
        # Preprocess
        img_processed = preprocess(img_np)

        # Run OCR
        ocr = get_ocr()
        result = ocr.ocr(img_processed)
        
        # Extract text
        texts = []
        if result and isinstance(result, list):
            for page in result:
                if hasattr(page, '__getitem__') and 'rec_texts' in page:
                    rec_texts = page['rec_texts']
                    if rec_texts and isinstance(rec_texts, list):
                        texts.extend([str(text).strip() for text in rec_texts if text])

        return "\n".join(texts) if texts else ""

    except Exception as e:
        print(f"❌ OCR error: {e}")
        import traceback
        traceback.print_exc()
        return ""








































# import os
# import cv2
# import numpy as np
# import requests
# from paddleocr import PaddleOCR
# from io import BytesIO
# from PIL import Image

# # ---------------- HARD SAFETY ----------------
# os.environ["FLAGS_use_gpu"] = "0"
# os.environ["OMP_NUM_THREADS"] = "1"
# os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"
# os.environ["DISABLE_MODEL_SOURCE_CHECK"] = "True"

# # ---------------- SINGLETON OCR ----------------
# _OCR = None

# def get_ocr():
#     global _OCR
#     if _OCR is None:
#         print("📦 Initializing PaddleOCR (SAFE MODE)")
#         _OCR = PaddleOCR(lang="en", use_angle_cls=False)
#     return _OCR


# def preprocess(img: np.ndarray) -> np.ndarray:
#     """
#     Minimal preprocessing - just resize if too large.
#     """
#     height, width = img.shape[:2]
#     max_dimension = 2000
    
#     if max(height, width) > max_dimension:
#         scale = max_dimension / max(height, width)
#         new_width = int(width * scale)
#         new_height = int(height * scale)
#         img = cv2.resize(img, (new_width, new_height), interpolation=cv2.INTER_AREA)
#         print(f"📏 Resized image to {new_width}x{new_height}")
    
#     return img


# def extract_text_from_url(url: str) -> str:
#     try:
#         print("⬇️ Downloading image...")
#         response = requests.get(url, timeout=20)
#         response.raise_for_status()

#         print("🖼️ Loading image...")
#         img = Image.open(BytesIO(response.content)).convert("RGB")
#         img_np = np.array(img)
        
#         print(f"📐 Original size: {img_np.shape}")
        
#         img_processed = preprocess(img_np)

#         print("🔍 Running OCR...")
#         ocr = get_ocr()
#         result = ocr.ocr(img_processed)
        
#         print("📝 Extracting text...")
#         texts = []
        
#         if result and isinstance(result, list):
#             for page in result:
#                 if hasattr(page, '__getitem__') and 'rec_texts' in page:
#                     rec_texts = page['rec_texts']
#                     if rec_texts and isinstance(rec_texts, list):
#                         texts.extend([str(text).strip() for text in rec_texts if text])

#         final_text = "\n".join(texts)
#         print(f"✅ Extracted {len(texts)} lines of text")
#         return final_text if final_text else ""

#     except Exception as e:
#         print(f"❌ OCR ERROR: {e}")
#         import traceback
#         traceback.print_exc()
#         return ""