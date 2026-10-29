import io
import os
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from uuid import uuid4

from fastapi import HTTPException, UploadFile

from app.resume.service import ResumeService


def make_upload(filename: str, data: bytes = b"%PDF-1.4 sample") -> UploadFile:
    return UploadFile(filename=filename, file=io.BytesIO(data))


class UploadSecurityTests(unittest.TestCase):
    """A6/A7: client filenames are never paths, and limits are enforced."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.settings = SimpleNamespace(
            upload_dir=self.tmp.name,
            max_file_size_mb=1,
            allowed_extensions=[".pdf", ".docx", ".txt"],
        )
        patcher = patch("app.resume.service.get_settings", return_value=self.settings)
        patcher.start()
        self.addCleanup(patcher.stop)

        self.service = ResumeService(MagicMock())
        self.service.extractor = MagicMock()
        self.service.extractor.extract.return_value = {
            "raw_text": "Sample resume text",
            "metadata": {},
        }
        self.service.sec_parser = MagicMock()
        self.service.sec_parser.parse.return_value = {}

    def test_traversal_filename_cannot_escape_upload_dir(self):
        user_id = uuid4()
        resume = self.service.upload(make_upload("../../evil.pdf"), user_id)

        expected_dir = os.path.join(self.tmp.name, str(user_id))
        self.assertEqual(os.path.dirname(resume.file_path), expected_dir)
        self.assertNotIn("..", resume.file_path)
        # display name keeps only the basename; the stored file is random
        self.assertEqual(resume.filename, "evil.pdf")
        self.assertNotEqual(os.path.basename(resume.file_path), resume.filename)
        self.assertTrue(os.path.exists(resume.file_path))
        self.assertFalse(
            os.path.exists(os.path.join(self.tmp.name, "..", "evil.pdf"))
        )

    def test_windows_traversal_is_stripped(self):
        resume = self.service.upload(make_upload("..\\..\\evil.pdf"), uuid4())
        self.assertEqual(resume.filename, "evil.pdf")
        self.assertEqual(os.path.dirname(resume.file_path), os.path.join(
            self.tmp.name, str(resume.user_id)
        ))

    def test_disallowed_extension_is_rejected(self):
        with self.assertRaises(HTTPException) as ctx:
            self.service.upload(make_upload("payload.exe"), uuid4())
        self.assertEqual(ctx.exception.status_code, 400)
        self.assertIn(".pdf", ctx.exception.detail)
        self.service.extractor.extract.assert_not_called()
        self.service.session.add.assert_not_called()

    def test_extensionless_file_is_rejected(self):
        with self.assertRaises(HTTPException) as ctx:
            self.service.upload(make_upload("resume"), uuid4())
        self.assertEqual(ctx.exception.status_code, 400)
        self.service.extractor.extract.assert_not_called()

    def test_oversized_file_is_rejected_before_parsing(self):
        too_big = b"x" * (1024 * 1024 + 1)
        with self.assertRaises(HTTPException) as ctx:
            self.service.upload(make_upload("resume.pdf", too_big), uuid4())
        self.assertEqual(ctx.exception.status_code, 413)
        self.assertIn("1 MB", ctx.exception.detail)
        self.service.extractor.extract.assert_not_called()
        self.service.session.add.assert_not_called()

    def test_file_at_the_limit_is_accepted(self):
        at_limit = b"x" * (1024 * 1024)
        resume = self.service.upload(make_upload("resume.pdf", at_limit), uuid4())
        self.assertEqual(resume.file_type, ".pdf")

    def test_empty_file_is_rejected(self):
        with self.assertRaises(HTTPException) as ctx:
            self.service.upload(make_upload("resume.pdf", b""), uuid4())
        self.assertEqual(ctx.exception.status_code, 400)
        self.service.extractor.extract.assert_not_called()

    def test_missing_filename_is_rejected(self):
        with self.assertRaises(HTTPException) as ctx:
            self.service.upload(make_upload(""), uuid4())
        self.assertEqual(ctx.exception.status_code, 400)

    def test_display_name_is_sanitized(self):
        resume = self.service.upload(
            make_upload('..\\my\x00 <resume>?.pdf'), uuid4()
        )
        self.assertEqual(resume.filename, "my resume.pdf")
        self.assertEqual(resume.file_type, ".pdf")

    def test_same_display_name_gets_distinct_stored_paths(self):
        user_id = uuid4()
        first = self.service.upload(make_upload("resume.pdf"), user_id)
        second = self.service.upload(make_upload("resume.pdf"), user_id)
        self.assertEqual(first.filename, second.filename)
        self.assertNotEqual(first.file_path, second.file_path)
        self.assertTrue(os.path.exists(first.file_path))
        self.assertTrue(os.path.exists(second.file_path))

    def test_extension_is_lowercased(self):
        resume = self.service.upload(make_upload("RESUME.PDF"), uuid4())
        self.assertEqual(resume.file_type, ".pdf")
        self.assertTrue(resume.file_path.endswith(".pdf"))
