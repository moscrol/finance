#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

MIN_TEXT_CHARS = 500
MAX_OCR_HEIGHT = 3200
OVERLAP = 80


def text_layer(pdf: Path) -> str:
    chunks = []
    try:
        from pypdf import PdfReader
        for i, page in enumerate(PdfReader(str(pdf)).pages, 1):
            chunks.append(f"\n\n===== PAGE {i} =====\n\n" + (page.extract_text() or ""))
    except Exception:
        return ""
    return "".join(chunks)


def crop_chunks(image):
    width, height = image.size
    if height <= MAX_OCR_HEIGHT:
        yield image
        return
    top = 0
    while top < height:
        bottom = min(height, top + MAX_OCR_HEIGHT)
        yield image.crop((0, top, width, bottom))
        if bottom == height:
            break
        top = max(0, bottom - OVERLAP)


def ocr_pdf(pdf: Path, dpi: int) -> str:
    from pdf2image import convert_from_path
    import pytesseract

    chunks = []
    pages = convert_from_path(str(pdf), dpi=dpi)
    for page_no, image in enumerate(pages, 1):
        page_parts = []
        for part_no, chunk in enumerate(crop_chunks(image), 1):
            txt = pytesseract.image_to_string(chunk, lang="chi_sim+eng", config="--psm 6")
            page_parts.append(f"\n--- OCR CHUNK {part_no} ---\n{txt}")
        chunks.append(f"\n\n===== PAGE {page_no} =====\n\n" + "\n".join(page_parts))
    return "".join(chunks)


def main() -> int:
    parser = argparse.ArgumentParser(description="Extract hbs PDF text with OCR fallback and tall-image chunking.")
    parser.add_argument("--pdf", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--dpi", default=180, type=int)
    args = parser.parse_args()

    pdf = args.pdf.expanduser().resolve()
    text = text_layer(pdf)
    method = "text_layer"
    if len(text.strip()) < MIN_TEXT_CHARS:
        text = ocr_pdf(pdf, args.dpi)
        method = "ocr_chunked"
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(text, encoding="utf-8")
    print(json.dumps({"pdf": str(pdf), "out": str(args.out), "method": method, "chars": len(text)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
