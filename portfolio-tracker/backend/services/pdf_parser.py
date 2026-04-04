"""
PDF parsing orchestrator.

Strategy:
1. Try pdfplumber (structured text extraction) — fast, no API cost
2. If pdfplumber yields too little text, fall back to Claude Vision API
"""
from __future__ import annotations

import base64
import io
import os
from pathlib import Path
from typing import Any

import pdfplumber
import fitz  # PyMuPDF — used for page-to-image conversion for Claude Vision

from config import settings
from services.parsers.base import ParsedStatement, BrokerParser
from services.parsers.ibkr import IBKRParser
from services.parsers.futu import FutuParser
from services.parsers.sofi import SoFiParser
from services.parsers.osl import OSLParser

PARSERS: dict[str, BrokerParser] = {
    "ibkr": IBKRParser(),
    "futu": FutuParser(),
    "sofi": SoFiParser(),
    "osl": OSLParser(),
}

MIN_TEXT_LENGTH = 200  # characters; below this we consider the PDF image-based


async def parse_statement(
    pdf_bytes: bytes,
    broker: str,
    filename: str = "statement.pdf",
) -> ParsedStatement:
    """
    Main entry point. Returns a ParsedStatement with positions and transactions.
    broker must be one of: ibkr, futu, sofi, osl
    """
    broker = broker.lower()
    if broker not in PARSERS:
        raise ValueError(f"Unknown broker '{broker}'. Must be one of: {list(PARSERS)}")

    parser = PARSERS[broker]

    # Try pdfplumber first
    text, tables = _extract_with_pdfplumber(pdf_bytes)

    if len(text.strip()) >= MIN_TEXT_LENGTH:
        return parser.parse(text=text, tables=tables, filename=filename)

    # Fall back to Claude Vision
    if settings.anthropic_api_key:
        vision_text = await _extract_with_claude_vision(pdf_bytes, broker)
        return parser.parse(text=vision_text, tables=[], filename=filename)

    raise ValueError(
        "PDF appears to be image-based (scanned) and ANTHROPIC_API_KEY is not set. "
        "Please set the key to enable Claude Vision parsing."
    )


def _extract_with_pdfplumber(pdf_bytes: bytes) -> tuple[str, list[list[list[str | None]]]]:
    """Extract raw text and tables from a text-based PDF."""
    text_parts: list[str] = []
    all_tables: list[list[list[str | None]]] = []

    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text() or ""
            text_parts.append(page_text)

            tables = page.extract_tables() or []
            for table in tables:
                if table:
                    all_tables.append(table)

    return "\n".join(text_parts), all_tables


async def _extract_with_claude_vision(pdf_bytes: bytes, broker: str) -> str:
    """
    Use Claude Vision to extract structured data from a scanned/image-based PDF.
    Sends each page as an image and asks Claude to return the holdings/transactions as structured text.
    """
    import anthropic

    client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)

    # Convert PDF pages to images using PyMuPDF
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    page_images: list[str] = []

    for page_num in range(min(len(doc), 10)):  # Cap at 10 pages
        page = doc[page_num]
        mat = fitz.Matrix(2, 2)  # 2x zoom for better OCR quality
        pix = page.get_pixmap(matrix=mat)
        img_bytes = pix.tobytes("png")
        page_images.append(base64.standard_b64encode(img_bytes).decode())

    doc.close()

    prompt = f"""
You are parsing a {broker.upper()} broker statement PDF. Extract ALL holdings/positions and ALL transactions.

For each POSITION return exactly:
POSITION | symbol | name | quantity | price | currency | market_value

For each TRANSACTION return exactly:
TRANSACTION | date(YYYY-MM-DD) | type(buy/sell/dividend/fee) | symbol | quantity | price | amount | fee | currency

Return ONLY these lines, nothing else. If a field is unknown use ''.
"""

    content: list[Any] = []
    for img_b64 in page_images:
        content.append({
            "type": "image",
            "source": {"type": "base64", "media_type": "image/png", "data": img_b64},
        })
    content.append({"type": "text", "text": prompt})

    response = await client.messages.create(
        model="claude-opus-4-6",
        max_tokens=4096,
        messages=[{"role": "user", "content": content}],
    )

    return response.content[0].text
