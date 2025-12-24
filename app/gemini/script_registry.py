from typing import Set

SCRIPT_RANGES = {
    "HANZI_KANJI": [(0x4E00, 0x9FFF)],
    "HIRAGANA": [(0x3040, 0x309F)],
    "KATAKANA": [(0x30A0, 0x30FF)],
    "HANGUL": [(0xAC00, 0xD7AF)],

    "THAI": [(0x0E00, 0x0E7F)],
    "LAO": [(0x0E80, 0x0EFF)],
    "KHMER": [(0x1780, 0x17FF)],
    "BURMESE": [(0x1000, 0x109F)],

    "BENGALI_ASSAMESE": [(0x0980, 0x09FF)],
    "DEVANAGARI": [(0x0900, 0x097F)],
    "GUJARATI": [(0x0A80, 0x0AFF)],
    "GURMUKHI": [(0x0A00, 0x0A7F)],
    "ODIA": [(0x0B00, 0x0B7F)],
    "TAMIL": [(0x0B80, 0x0BFF)],
    "TELUGU": [(0x0C00, 0x0C7F)],
    "KANNADA": [(0x0C80, 0x0CFF)],
    "MALAYALAM": [(0x0D00, 0x0D7F)],
    "SINHALA": [(0x0D80, 0x0DFF)],

    "TIBETAN_DZONGKHA": [(0x0F00, 0x0FFF)],

    "ARABIC": [(0x0600, 0x06FF)],
    "HEBREW": [(0x0590, 0x05FF)],
    "SYRIAC": [(0x0700, 0x074F)],

    "ARMENIAN": [(0x0530, 0x058F)],
    "GEORGIAN": [(0x10A0, 0x10FF)],
    "CYRILLIC": [(0x0400, 0x04FF)],

    "THAANA": [(0x0780, 0x07BF)],
    "CHAM": [(0xAA00, 0xAA5F)],
    "TAI_VIET": [(0xAA80, 0xAADF)],
    "LEPCHA": [(0x1C00, 0x1C4F)],
    "LIMBU": [(0x1900, 0x194F)],
    "MEETEI_MAYEK": [(0xABC0, 0xABFF)],
    "OL_CHIKI": [(0x1C50, 0x1C7F)],
    "CHAKMA": [(0x11100, 0x1114F)],
}


def detect_scripts(text: str) -> Set[str]:
    detected = set()

    for ch in text:
        code = ord(ch)
        for script, ranges in SCRIPT_RANGES.items():
            if any(start <= code <= end for start, end in ranges):
                detected.add(script)

    return detected
