# app/gemini/client.py
import os
from dotenv import load_dotenv
from pathlib import Path
from google import genai

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

print("Initializing Gemini client... calling google.generativeai")
print('sssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssss')


GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL = os.getenv("GEMINI_MODEL")

print("🔑 GEMINI_API_KEY loaded:", bool(GEMINI_API_KEY))
print("🤖 GEMINI_MODEL:", GEMINI_MODEL)

if not GEMINI_API_KEY:
    raise RuntimeError("GEMINI_API_KEY is missing")

client = genai.Client(api_key=GEMINI_API_KEY)

