import io
import docx
import pdfplumber
import fitz  # PyMuPDF fallback
from app.common.exceptions import ParsingError

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
        text_parts = []
        meta = {"has_tables": False, "page_count": 0}

        # Primary: pdfplumber
        try:
            with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
                meta["page_count"] = len(pdf.pages)
                for page in pdf.pages:
                    txt = page.extract_text()
                    if txt:
                        text_parts.append(txt)
                    if page.extract_tables():
                        meta["has_tables"] = True
        except Exception:
            text_parts = []  # Fallback trigger

        # Fallback: PyMuPDF (fitz) if pdfplumber extracted nothing or crashed
        if not text_parts:
            try:
                doc = fitz.open(stream=file_bytes, filetype="pdf")
                meta["page_count"] = len(doc)
                for page in doc:
                    txt = page.get_text()
                    if txt:
                        text_parts.append(txt)
            except Exception as e:
                raise ParsingError(f"Failed to read PDF file: {str(e)}")

        return {"raw_text": "\n".join(text_parts), "metadata": meta}

    def _extract_docx(self, file_bytes: bytes) -> dict:
        meta = {"has_tables": False, "has_headers": False, "has_footers": False}
        try:
            doc = docx.Document(io.BytesIO(file_bytes))
            meta["has_tables"] = len(doc.tables) > 0
            for sec in doc.sections:
                if sec.header.text.strip(): meta["has_headers"] = True
                if sec.footer.text.strip(): meta["has_footers"] = True

            paras = [p.text for p in doc.paragraphs if p.text.strip()]
            for table in doc.tables:
                for row in table.rows:
                    row_txt = " | ".join(c.text.strip() for c in row.cells if c.text.strip())
                    if row_txt: paras.append(row_txt)

            return {"raw_text": "\n".join(paras), "metadata": meta}
        except Exception as e:
            raise ParsingError(f"Failed to read DOCX: {str(e)}")