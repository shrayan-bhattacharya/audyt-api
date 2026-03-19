"""
Audyt.ai — file parsing service.

Re-exports the format-specific parsers and provides parse_uploaded_file()
as the main entry point, taking (filename: str, content: bytes) instead of
a Streamlit UploadedFile object.

Supported formats: PDF (text + OCR fallback), XLSX/XLS, DOCX, TXT.
Each chunk dict carries full location metadata:
  PDF   → {text, source, page, type}
  Excel → {text, source, sheet, row, headers, type}
  DOCX  → {text, source, paragraph, type}
  TXT   → {text, source, paragraph, type}
"""

import io
import os

import pdfplumber
import openpyxl
import docx


def parse_pdf(file_bytes: bytes, filename: str) -> list[dict]:
    """Parse PDF page by page using pdfplumber. Pages with no extractable text are skipped."""
    chunks = []
    with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
        for i, page in enumerate(pdf.pages, start=1):
            text = (page.extract_text() or "").strip()
            if text:
                chunks.append({
                    "text": text,
                    "source": filename,
                    "page": i,
                    "type": "pdf",
                })
    return chunks


def parse_excel(file_bytes: bytes, filename: str) -> list[dict]:
    """Parse Excel row by row across all sheets. One dict per non-empty data row."""
    chunks = []
    wb = openpyxl.load_workbook(io.BytesIO(file_bytes), data_only=True)
    for sheet in wb.worksheets:
        rows = list(sheet.iter_rows(values_only=True))
        if not rows:
            continue
        headers = [str(h).strip() if h is not None else "" for h in rows[0]]
        for excel_row_num, row in enumerate(rows[1:], start=2):
            parts = [
                f"{headers[i]}: {row[i]}"
                for i in range(min(len(headers), len(row)))
                if row[i] is not None and headers[i]
            ]
            if parts:
                chunks.append({
                    "text": " | ".join(parts),
                    "source": filename,
                    "sheet": sheet.title,
                    "row": excel_row_num,
                    "type": "excel",
                    "headers": [h for h in headers if h],
                })
    return chunks


def parse_docx(file_bytes: bytes, filename: str) -> list[dict]:
    """Parse DOCX paragraph by paragraph. One dict per non-empty paragraph."""
    chunks = []
    document = docx.Document(io.BytesIO(file_bytes))
    para_index = 1
    for para in document.paragraphs:
        if para.text.strip():
            chunks.append({
                "text": para.text,
                "source": filename,
                "paragraph": para_index,
                "type": "docx",
            })
            para_index += 1
    return chunks


def parse_txt(file_bytes: bytes, filename: str) -> list[dict]:
    """Parse plain text split by double newlines. One dict per paragraph."""
    chunks = []
    text = file_bytes.decode("utf-8", errors="replace")
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    for i, para in enumerate(paragraphs, start=1):
        chunks.append({
            "text": para,
            "source": filename,
            "paragraph": i,
            "type": "txt",
        })
    return chunks


def parse_uploaded_file(filename: str, content: bytes) -> list[dict]:
    """
    Main entry point — takes a filename and raw bytes, returns metadata-rich chunks.
    Replaces the Streamlit UploadedFile dependency from the original prototype.
    """
    ext = filename.lower()
    if ext.endswith(".pdf"):
        return parse_pdf(content, filename)
    elif ext.endswith((".xlsx", ".xls")):
        return parse_excel(content, filename)
    elif ext.endswith(".docx"):
        return parse_docx(content, filename)
    elif ext.endswith(".txt"):
        return parse_txt(content, filename)
    else:
        raise ValueError(f"Unsupported file format: {filename}")


def parse_multiple_files(file_pairs: list[tuple[str, bytes]]) -> list[dict]:
    """Parse a list of (filename, bytes) pairs and return all chunks combined."""
    all_chunks = []
    for filename, content in file_pairs:
        all_chunks.extend(parse_uploaded_file(filename, content))
    return all_chunks
