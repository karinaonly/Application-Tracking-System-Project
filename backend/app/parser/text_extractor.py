import io
import re

import docx
import pdfplumber
import pymupdf as fitz  # PyMuPDF fallback (the `fitz` alias is deprecated)
from app.common.exceptions import ParsingError

# B9: PDF header/footer detection only matters when contact details are trapped
# there; repeated page numbers should not be flagged.
_CONTACT_LINE_RE = re.compile(r"@|(?:https?://|www\.)|(?<!\w)\+?\d[\d\s().-]{5,}\d(?!\w)", re.I)
_ICON_FONT_HINTS = ("symbol", "wingding", "awesome", "material", "icon")


class TextExtractor:
    def extract(self, file_bytes: bytes, file_type: str) -> dict:
        if file_type == ".pdf":
            return self._extract_pdf(file_bytes)
        elif file_type == ".docx":
            return self._extract_docx(file_bytes)
        elif file_type == ".txt":
            return {"raw_text": file_bytes.decode("utf-8", errors="ignore"), "metadata": {}}
        raise ParsingError(f"Unsupported format: {file_type}")

    def _extract_pdf(self, file_bytes: bytes) -> dict:
        text_parts: list[str] = []
        page_texts: list[str] = []
        fonts: set[str] = set()
        column_pages = 0
        meta = {
            "has_tables": False,
            "page_count": 0,
            "image_count": 0,
            "has_images": False,
            "font_count": 0,
            "has_icon_font": False,
            "has_multi_column": False,
            "has_headers": False,
            "has_footers": False,
        }

        # Primary: pdfplumber
        try:
            with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
                meta["page_count"] = len(pdf.pages)
                for page in pdf.pages:
                    txt = page.extract_text()
                    if txt:
                        text_parts.append(txt)
                        page_texts.append(txt)
                    if page.extract_tables():
                        meta["has_tables"] = True

                    # B9: images/icons, fonts, and column layout.
                    meta["image_count"] += len(getattr(page, "images", []) or [])
                    try:
                        for char in page.chars:
                            name = (char.get("fontname") or "").lower()
                            if name:
                                fonts.add(name)
                    except Exception:
                        pass
                    if self._looks_multi_column(page):
                        column_pages += 1
        except Exception:
            text_parts = []  # Fallback trigger
            page_texts = []

        # Fallback: PyMuPDF (fitz) if pdfplumber extracted nothing or crashed
        if not text_parts:
            try:
                doc = fitz.open(stream=file_bytes, filetype="pdf")
                meta["page_count"] = len(doc)
                for page in doc:
                    txt = page.get_text()
                    if txt:
                        text_parts.append(txt)
                        page_texts.append(txt)
                    meta["image_count"] += len(page.get_images(full=True))
                    for font in page.get_fonts(full=True):
                        name = (font[3] or "").lower()
                        if name:
                            fonts.add(name)
                    if self._looks_multi_column_fitz(page):
                        column_pages += 1
            except Exception as e:
                raise ParsingError(f"Failed to read PDF file: {str(e)}")

        meta["has_images"] = meta["image_count"] > 0
        meta["font_count"] = len(fonts)
        meta["has_icon_font"] = any(hint in font for font in fonts for hint in _ICON_FONT_HINTS)
        meta["has_multi_column"] = column_pages > 0
        if len(page_texts) >= 2:
            meta["has_headers"], meta["has_footers"] = self._repeated_contact_lines(page_texts)

        return {"raw_text": "\n".join(text_parts), "metadata": meta}

    @staticmethod
    def _looks_multi_column(page) -> bool:
        """B9: true when a page has substantial text on both sides of a
        vertical gutter and almost nothing spanning the middle. A single-column
        resume with right-aligned dates does not meet the left/right counts."""
        try:
            words = page.extract_words()
            width = float(page.width or 0)
        except Exception:
            return False
        if len(words) < 30 or width <= 0:
            return False
        left = sum(1 for w in words if w["x1"] <= width * 0.45)
        right = sum(1 for w in words if w["x0"] >= width * 0.55)
        middle = sum(1 for w in words if w["x0"] < width * 0.55 and w["x1"] > width * 0.45)
        return left >= 8 and right >= 8 and middle <= max(3, len(words) * 0.05)

    @staticmethod
    def _looks_multi_column_fitz(page) -> bool:
        """Same heuristic for the PyMuPDF fallback, using word boxes."""
        try:
            width = float(page.rect.width)
            words = page.get_text("words")
        except Exception:
            return False
        if len(words) < 30 or width <= 0:
            return False
        left = sum(1 for w in words if w[2] <= width * 0.45)
        right = sum(1 for w in words if w[0] >= width * 0.55)
        middle = sum(1 for w in words if w[0] < width * 0.55 and w[2] > width * 0.45)
        return left >= 8 and right >= 8 and middle <= max(3, len(words) * 0.05)

    @staticmethod
    def _repeated_contact_lines(page_texts: list[str]) -> tuple[bool, bool]:
        """B9: flag a PDF header/footer only when the same contact-like line is
        repeated across pages — ordinary page numbers are ignored."""
        def normalized(line: str) -> str:
            return re.sub(r"\s+", " ", line).strip().lower()

        tops, bottoms = [], []
        for text in page_texts:
            lines = [line for line in text.splitlines() if line.strip()]
            if lines:
                tops.append(normalized(lines[0]))
                bottoms.append(normalized(lines[-1]))

        threshold = max(2, (len(page_texts) + 1) // 2)

        def repeated(lines: list[str]) -> bool:
            counts: dict[str, int] = {}
            for line in lines:
                counts[line] = counts.get(line, 0) + 1
            return any(
                count >= threshold and _CONTACT_LINE_RE.search(line)
                for line, count in counts.items()
            )

        return repeated(tops), repeated(bottoms)

    def _extract_docx(self, file_bytes: bytes) -> dict:
        meta = {
            "has_tables": False,
            "has_headers": False,
            "has_footers": False,
            "image_count": 0,
            "has_images": False,
            "font_count": 0,
            "has_icon_font": False,
            "has_multi_column": False,
        }
        try:
            doc = docx.Document(io.BytesIO(file_bytes))
            meta["has_tables"] = len(doc.tables) > 0
            for sec in doc.sections:
                # python-docx headers/footers expose paragraphs, not `.text`;
                # the old `.text` access raised and failed every DOCX upload.
                header_text = "\n".join(p.text for p in sec.header.paragraphs).strip()
                footer_text = "\n".join(p.text for p in sec.footer.paragraphs).strip()
                if header_text: meta["has_headers"] = True
                if footer_text: meta["has_footers"] = True

            # B9: images/icons and font variety are visible to ATS too.
            meta["image_count"] = len(doc.inline_shapes)
            meta["has_images"] = meta["image_count"] > 0
            fonts = {
                run.font.name.lower()
                for paragraph in doc.paragraphs
                for run in paragraph.runs
                if run.font.name
            }
            meta["font_count"] = len(fonts)
            meta["has_icon_font"] = any(
                hint in font for font in fonts for hint in _ICON_FONT_HINTS
            )

            paras = [p.text for p in doc.paragraphs if p.text.strip()]
            for table in doc.tables:
                for row in table.rows:
                    row_txt = " | ".join(c.text.strip() for c in row.cells if c.text.strip())
                    if row_txt: paras.append(row_txt)

            return {"raw_text": "\n".join(paras), "metadata": meta}
        except Exception as e:
            raise ParsingError(f"Failed to read DOCX: {str(e)}")
