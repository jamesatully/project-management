"""Uploading, opening, replacing and removing the file attached to a document (UI, API and storage)."""
import shutil
import tempfile

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from .. import models
from ..models import Document
from .factories import make_document, make_project

PDF = b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n"


def pdf(name="Notice of Award.pdf", content=PDF):
    return SimpleUploadedFile(name, content, content_type="application/pdf")


class TempMediaMixin:
    """Store uploads in a throwaway MEDIA_ROOT so tests never write into the repo."""

    @classmethod
    def setUpClass(cls):
        cls._media = tempfile.mkdtemp()
        cls._media_override = override_settings(MEDIA_ROOT=cls._media)
        cls._media_override.enable()
        super().setUpClass()

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        cls._media_override.disable()
        shutil.rmtree(cls._media, ignore_errors=True)


class DocumentFileModelTests(TempMediaMixin, TestCase):
    def setUp(self):
        self.document = make_document(make_project())

    def test_file_is_optional(self):
        self.document.full_clean()
        self.assertFalse(self.document.file)

    def test_allowed_types(self):
        for name in ["a.pdf", "b.DOCX", "c.xlsx", "d.msg", "e.jpg"]:
            self.document.file = SimpleUploadedFile(name, b"x")
            self.document.full_clean()

    def test_rejects_other_types(self):
        for name in ["page.html", "script.js", "drawing.svg", "archive.zip", "noextension"]:
            self.document.file = SimpleUploadedFile(name, b"x")
            with self.assertRaises(ValidationError, msg=name) as ctx:
                self.document.full_clean()
            self.assertIn("file", ctx.exception.message_dict)

    def test_rejects_large_files(self):
        self.document.file = SimpleUploadedFile("big.pdf", b"x")
        self.document.file.file.size = models.DOCUMENT_FILE_MAX_MB * 1024 * 1024 + 1
        with self.assertRaisesMessage(ValidationError, "at most"):
            self.document.full_clean()

    def test_stored_under_document_folder_with_original_name(self):
        self.document.file = pdf()
        self.document.save()
        self.assertEqual(self.document.file.name, f"documents/{self.document.pk}/Notice_of_Award.pdf")
        self.assertEqual(self.document.file.filename, "Notice_of_Award.pdf")
        self.assertEqual(self.document.file.extension, "PDF")
        self.assertEqual(self.document.file.url, reverse("pm:document-file", args=[self.document.pk]))

    def test_replaced_and_deleted_files_leave_storage(self):
        self.document.file = pdf("first.pdf")
        self.document.save()
        storage, first = self.document.file.storage, self.document.file.name
        with self.captureOnCommitCallbacks(execute=True):
            self.document.file = pdf("second.pdf")
            self.document.save()
        self.assertFalse(storage.exists(first))
        second = self.document.file.name
        self.assertTrue(storage.exists(second))
        with self.captureOnCommitCallbacks(execute=True):
            self.document.delete()
        self.assertFalse(storage.exists(second))


class DocumentFileViewTests(TempMediaMixin, TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user("tester", password="pw-123456!")
        self.client.force_login(self.user)
        self.project = make_project()
        self.document = make_document(self.project)

    def form_data(self, **extra):
        return {
            "project": self.project.pk, "subject": "Notice of Award", "document_type": "LETTER",
            "document_date": "2026-01-05", "originating_organization": "Utility", "recipient_organization": "Acme",
            **extra,
        }

    def test_form_is_multipart(self):
        response = self.client.get(reverse("pm:document-create"))
        self.assertContains(response, 'enctype="multipart/form-data"')
        self.assertContains(response, 'accept=".pdf,')

    def test_upload_and_open(self):
        response = self.client.post(reverse("pm:document-create"), self.form_data(file=pdf()))
        self.assertEqual(response.status_code, 302)
        document = Document.objects.get(subject="Notice of Award")
        url = reverse("pm:document-file", args=[document.pk])

        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertEqual(response["Content-Disposition"], 'inline; filename="Notice_of_Award.pdf"')
        self.assertEqual(b"".join(response.streaming_content), PDF)

        # Detail, list and edit pages link to it in a new tab.
        for page in [document.get_absolute_url(), reverse("pm:document-list"), reverse("pm:document-update", args=[document.pk])]:
            response = self.client.get(page)
            self.assertContains(response, f'href="{url}" target="_blank"')

    def test_rejected_type_shows_error(self):
        response = self.client.post(
            reverse("pm:document-create"), self.form_data(file=SimpleUploadedFile("evil.html", b"<script>"))
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "File extension")
        self.assertFalse(Document.objects.filter(subject="Notice of Award").exists())

    def test_edit_keeps_replaces_or_removes_file(self):
        self.document.file = pdf("first.pdf")
        self.document.save()
        edit = reverse("pm:document-update", args=[self.document.pk])
        data = self.form_data()

        self.client.post(edit, data)
        self.document.refresh_from_db()
        self.assertEqual(self.document.file.filename, "first.pdf")

        self.client.post(edit, {**data, "file": pdf("second.pdf")})
        self.document.refresh_from_db()
        self.assertEqual(self.document.file.filename, "second.pdf")

        self.client.post(edit, {**data, "file-clear": "on"})
        self.document.refresh_from_db()
        self.assertFalse(self.document.file)

    def test_no_file_or_missing_file_is_404(self):
        url = reverse("pm:document-file", args=[self.document.pk])
        self.assertEqual(self.client.get(url).status_code, 404)
        Document.objects.filter(pk=self.document.pk).update(file=f"documents/{self.document.pk}/gone.pdf")
        self.assertEqual(self.client.get(url).status_code, 404)

    def test_login_required(self):
        self.document.file = pdf()
        self.document.save()
        self.client.logout()
        response = self.client.get(reverse("pm:document-file", args=[self.document.pk]))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("login"), response["Location"])


class DocumentFileAPITests(TempMediaMixin, TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user("tester", password="pw-123456!")
        self.client = APIClient()
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {Token.objects.create(user=self.user).key}")
        self.project = make_project()

    def test_upload_download_and_clear(self):
        response = self.client.post("/api/documents/", {
            "project": self.project.pk, "subject": "Basis of Design Report", "document_type": "REPORT",
            "document_date": "2026-02-01", "originating_organization": "Engineer", "recipient_organization": "Utility",
            "file": pdf("BODR.pdf"),
        }, format="multipart")
        self.assertEqual(response.status_code, 201, response.data)
        pk = response.data["id"]
        self.assertEqual(response.data["file_name"], "BODR.pdf")
        self.assertEqual(response.data["file"], f"http://testserver/api/documents/{pk}/file/")

        # Token clients can download through the API.
        download = self.client.get(f"/api/documents/{pk}/file/")
        self.assertEqual(download.status_code, 200)
        self.assertEqual(b"".join(download.streaming_content), PDF)

        response = self.client.patch(f"/api/documents/{pk}/", {"file": None}, format="json")
        self.assertEqual(response.status_code, 200, response.data)
        self.assertIsNone(response.data["file"])
        self.assertIsNone(response.data["file_name"])
        self.assertEqual(self.client.get(f"/api/documents/{pk}/file/").status_code, 404)

    def test_rejects_disallowed_type(self):
        document = make_document(self.project)
        response = self.client.patch(
            f"/api/documents/{document.pk}/", {"file": SimpleUploadedFile("x.exe", b"MZ")}, format="multipart"
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("file", response.data)
