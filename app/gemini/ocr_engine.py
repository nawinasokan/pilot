# app/gemini/ocr_engine.py
# ============================================================
# PaddleOCR (Multilingual Asian) + TrOCR (Handwriting fallback)
# PaddleOCR 2.7.x SAFE VERSION
# ============================================================

import os
import platform
import threading
import requests
from io import BytesIO
from typing import Optional

import cv2
import numpy as np
from PIL import Image
from paddleocr import PaddleOCR

# ============================================================
# ENV SAFETY
# ============================================================

os.environ["FLAGS_use_gpu"] = "0"
os.environ["OMP_NUM_THREADS"] = "1"
os.environ["DISABLE_MODEL_SOURCE_CHECK"] = "True"

if platform.system() == "Windows":
    os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"

# ============================================================
# THREAD-LOCAL OCR
# ============================================================

_thread_local = threading.local()


def _init_paddle_ocr() -> PaddleOCR:
    print("📦 Initializing PaddleOCR (multilingual Asian)")
    return PaddleOCR(
        lang="ch",              # Chinese / Japanese / Korean / English
        use_angle_cls=True,
        show_log=False,
    )


def get_paddle_ocr() -> PaddleOCR:
    if not hasattr(_thread_local, "ocr"):
        _thread_local.ocr = _init_paddle_ocr()
    return _thread_local.ocr


# ============================================================
# OPTIONAL TrOCR (HANDWRITING) — LAZY LOAD
# ============================================================

_trocr_cache = {}


def load_trocr():
    if "model" in _trocr_cache:
        return _trocr_cache["processor"], _trocr_cache["model"]

    try:
        import torch
        from transformers import TrOCRProcessor, VisionEncoderDecoderModel

        print("✍️ Initializing TrOCR (handwriting fallback)")

        processor = TrOCRProcessor.from_pretrained(
            "microsoft/trocr-base-handwritten"
        )
        model = VisionEncoderDecoderModel.from_pretrained(
            "microsoft/trocr-base-handwritten"
        )
        model.eval()

        _trocr_cache["processor"] = processor
        _trocr_cache["model"] = model
        return processor, model

    except Exception as e:
        print("⚠️ TrOCR unavailable:", e)
        return None, None


# ============================================================
# IMAGE PREPROCESS
# ============================================================

def preprocess(img: np.ndarray) -> np.ndarray:
    h, w = img.shape[:2]
    max_dim = 2000

    if max(h, w) > max_dim:
        scale = max_dim / max(h, w)
        img = cv2.resize(img, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)

    return img


# ============================================================
# PARSE PaddleOCR 2.7 OUTPUT (FIXED)
# ============================================================

def parse_paddle_result(result) -> str:
    texts = []

    if not result or not isinstance(result, list):
        return ""

    # PaddleOCR 2.7 returns result per page
    for page in result:
        for line in page:
            if not line or len(line) < 2:
                continue

            text, confidence = line[1]

            if isinstance(confidence, (float, int)) and confidence >= 0.4:
                if text and text.strip():
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

        text = processor.batch_decode(ids, skip_special_tokens=True)[0]
        return text.strip()

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

        ocr = get_paddle_ocr()
        result = ocr.ocr(img_np)
        text = parse_paddle_result(result)

        # Handwriting fallback
        if len(text.strip()) < 30:
            handwritten = trocr_handwritten_text(img)
            if handwritten:
                text = f"{text}\n{handwritten}".strip()

        return text

    except Exception as e:
        print("❌ OCR URL error:", e)
        return ""


def extract_text_from_file(file_path: str) -> str:
    try:
        img = Image.open(file_path).convert("RGB")
        img_np = preprocess(np.array(img))

        ocr = get_paddle_ocr()
        result = ocr.ocr(img_np)
        text = parse_paddle_result(result)

        if len(text.strip()) < 30:
            handwritten = trocr_handwritten_text(img)
            if handwritten:
                text = f"{text}\n{handwritten}".strip()

        return text

    except Exception as e:
        print("❌ OCR FILE error:", e)
        return ""
