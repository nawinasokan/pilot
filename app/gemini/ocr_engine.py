# ============================================================
# PaddleOCR (Multilingual Asian) + TrOCR (Handwriting fallback)
# PaddleOCR 2.7.x SAFE VERSION – PRODUCTION READY
# ============================================================

import os
import platform
import threading
import requests
from io import BytesIO

import cv2
import numpy as np
from PIL import Image
from paddleocr import PaddleOCR

# ============================================================
# ENV SAFETY (CRITICAL)
# ============================================================

os.environ["FLAGS_use_gpu"] = "0"
os.environ["OMP_NUM_THREADS"] = "1"
os.environ["DISABLE_MODEL_SOURCE_CHECK"] = "True"

# Windows safety
if platform.system() == "Windows":
    os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"
    os.environ["PYTORCH_NO_SHM"] = "1"   # 🔥 FIXES shm.dll crash

# ============================================================
# THREAD-LOCAL PaddleOCR (DJANGO SAFE)
# ============================================================

_thread_local = threading.local()


def _init_paddle_ocr() -> PaddleOCR:
    print("📦 Initializing PaddleOCR (multilingual Asian)")
    return PaddleOCR(
        lang="ch",   # Multilingual CJK + Asian printed text (best free model)
        use_angle_cls=True,
        show_log=False,
    )


def get_paddle_ocr() -> PaddleOCR:
    if not hasattr(_thread_local, "ocr"):
        _thread_local.ocr = _init_paddle_ocr()
    return _thread_local.ocr


# ============================================================
# OPTIONAL TrOCR (HANDWRITING) — LAZY + CPU SAFE
# ============================================================

_trocr_cache = {}


def load_trocr():
    if "model" in _trocr_cache:
        return _trocr_cache["processor"], _trocr_cache["model"]

    try:
        import torch
        from transformers import TrOCRProcessor, VisionEncoderDecoderModel

        # ---- HARD CPU SAFETY ----
        torch.set_num_threads(1)
        torch.set_num_interop_threads(1)

        print("✍️ Initializing TrOCR (handwriting fallback)")

        processor = TrOCRProcessor.from_pretrained(
            "microsoft/trocr-base-handwritten"
        )
        model = VisionEncoderDecoderModel.from_pretrained(
            "microsoft/trocr-base-handwritten"
        )

        model.to("cpu")
        model.eval()

        _trocr_cache["processor"] = processor
        _trocr_cache["model"] = model
        return processor, model

    except Exception as e:
        print("⚠️ TrOCR unavailable:", e)
        return None, None


# ============================================================
# IMAGE PREPROCESSING
# ============================================================

def preprocess(img: np.ndarray) -> np.ndarray:
    h, w = img.shape[:2]
    max_dim = 2000

    if max(h, w) > max_dim:
        scale = max_dim / max(h, w)
        img = cv2.resize(img, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)

    if img.ndim == 3:
        gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
        img = cv2.cvtColor(gray, cv2.COLOR_GRAY2RGB)

    return img


# ============================================================
# PaddleOCR 2.7 RESULT PARSER (FIXED)
# ============================================================

def parse_paddle_result(result) -> str:
    texts = []

    if not result or not isinstance(result, list):
        return ""

    for page in result:
        for line in page:
            if not line or len(line) < 2:
                continue

            text_conf = line[1]
            if not isinstance(text_conf, (list, tuple)) or len(text_conf) != 2:
                continue

            text, confidence = text_conf

            try:
                conf = float(confidence)
            except Exception:
                continue

            if conf >= 0.4 and text and text.strip():
                texts.append(text.strip())

    return "\n".join(texts)


# ============================================================
# HANDWRITING OCR
# ============================================================

def trocr_handwritten_text(img: Image.Image) -> str:
    processor, model = load_trocr()
    if not processor or not model:
        return ""

    try:
        import torch

        pixel_values = processor(images=img, return_tensors="pt").pixel_values
        with torch.no_grad():
            ids = model.generate(pixel_values, max_length=64)

        return processor.batch_decode(ids, skip_special_tokens=True)[0].strip()

    except Exception as e:
        print("⚠️ TrOCR failed:", e)
        return ""


# ============================================================
# PUBLIC API
# ============================================================

def extract_text_from_url(url: str) -> str:
    try:
        response = requests.get(url, timeout=20)
        response.raise_for_status()

        img = Image.open(BytesIO(response.content)).convert("RGB")
        img_np = preprocess(np.array(img))

        result = get_paddle_ocr().ocr(img_np)
        text = parse_paddle_result(result)

        if len(text) < 30 and sum(c.isdigit() for c in text) < 5:
            handwritten = trocr_handwritten_text(img)
            if handwritten:
                text = f"{text}\n{handwritten}".strip()

        return text

    except Exception as e:
        print("❌ OCR URL error:", e)
        return ""
