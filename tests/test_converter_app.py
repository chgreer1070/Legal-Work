"""Tests for the Outlook-to-PDF converter Flask application."""

import io
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch

# Prevent cleanup thread from starting during tests
import app as app_module

app_module.app.config["TESTING"] = True


class TestConverterRoutes(unittest.TestCase):
    """Test Flask route responses."""

    def setUp(self):
        self.client = app_module.app.test_client()

    def test_index_returns_200(self):
        resp = self.client.get("/")
        self.assertEqual(resp.status_code, 200)

    def test_jobs_returns_list(self):
        resp = self.client.get("/jobs")
        self.assertEqual(resp.status_code, 200)
        self.assertIsInstance(resp.get_json(), list)

    def test_convert_no_files_returns_400(self):
        resp = self.client.post("/convert")
        self.assertEqual(resp.status_code, 400)
        self.assertIn("error", resp.get_json())

    def test_convert_empty_files_returns_400(self):
        resp = self.client.post(
            "/convert",
            data={"files": (io.BytesIO(b""), "")},
            content_type="multipart/form-data",
        )
        self.assertEqual(resp.status_code, 400)

    def test_convert_unsupported_ext_returns_400(self):
        resp = self.client.post(
            "/convert",
            data={"files": (io.BytesIO(b"data"), "test.exe")},
            content_type="multipart/form-data",
        )
        self.assertEqual(resp.status_code, 400)
        body = resp.get_json()
        self.assertIn("rejected", body)
        self.assertIn("test.exe", body["rejected"])

    def test_status_unknown_job_returns_404(self):
        resp = self.client.get("/status/nonexistent-id")
        self.assertEqual(resp.status_code, 404)

    def test_download_unknown_job_returns_404(self):
        resp = self.client.get("/download/nonexistent-id")
        self.assertEqual(resp.status_code, 404)


class TestJobLifecycle(unittest.TestCase):
    """Test the job creation and status tracking."""

    def setUp(self):
        self.client = app_module.app.test_client()

    @patch("app._run_conversion")
    def test_convert_creates_job(self, mock_convert):
        mock_convert.return_value = None
        resp = self.client.post(
            "/convert",
            data={"files": (io.BytesIO(b"fake pdf"), "test.pdf")},
            content_type="multipart/form-data",
        )
        self.assertEqual(resp.status_code, 200)
        body = resp.get_json()
        self.assertIn("job_id", body)
        self.assertEqual(body["status"], "processing")
        self.assertIn("test.pdf", body["files"])

        # Verify job appears in status endpoint
        job_id = body["job_id"]
        status_resp = self.client.get(f"/status/{job_id}")
        self.assertEqual(status_resp.status_code, 200)
        self.assertEqual(status_resp.get_json()["status"], "processing")

    @patch("app._run_conversion")
    def test_job_appears_in_jobs_list(self, mock_convert):
        mock_convert.return_value = None
        resp = self.client.post(
            "/convert",
            data={"files": (io.BytesIO(b"fake pdf"), "doc.pdf")},
            content_type="multipart/form-data",
        )
        job_id = resp.get_json()["job_id"]
        jobs_resp = self.client.get("/jobs")
        job_ids = [j["job_id"] for j in jobs_resp.get_json()]
        self.assertIn(job_id, job_ids)

    @patch("app._run_conversion")
    def test_download_processing_job_returns_202(self, mock_convert):
        mock_convert.return_value = None
        resp = self.client.post(
            "/convert",
            data={"files": (io.BytesIO(b"data"), "report.docx")},
            content_type="multipart/form-data",
        )
        job_id = resp.get_json()["job_id"]
        dl_resp = self.client.get(f"/download/{job_id}")
        self.assertEqual(dl_resp.status_code, 202)


class TestJobTTLCleanup(unittest.TestCase):
    """Test the TTL-based job cleanup."""

    def test_cleanup_removes_expired_jobs(self):
        old_ts = time.time() - app_module._JOB_TTL_SECONDS - 1
        test_id = "test-expired-job"
        with app_module._jobs_lock:
            app_module._jobs[test_id] = {
                "status": "done",
                "_created_ts": old_ts,
                "created_at": "2020-01-01T00:00:00+00:00",
                "files": [],
                "results": [],
                "errors": [],
            }

        app_module._cleanup_expired_jobs()

        with app_module._jobs_lock:
            self.assertNotIn(test_id, app_module._jobs)

    def test_cleanup_keeps_fresh_jobs(self):
        test_id = "test-fresh-job"
        with app_module._jobs_lock:
            app_module._jobs[test_id] = {
                "status": "done",
                "_created_ts": time.time(),
                "created_at": "2020-01-01T00:00:00+00:00",
                "files": [],
                "results": [],
                "errors": [],
            }

        app_module._cleanup_expired_jobs()

        with app_module._jobs_lock:
            self.assertIn(test_id, app_module._jobs)
            del app_module._jobs[test_id]

    def test_cleanup_enforces_max_jobs(self):
        with app_module._jobs_lock:
            for i in range(app_module._MAX_JOBS + 50):
                app_module._jobs[f"overflow-{i}"] = {
                    "status": "done",
                    "_created_ts": time.time() - i,
                    "created_at": "2020-01-01T00:00:00+00:00",
                    "files": [],
                    "results": [],
                    "errors": [],
                }

        app_module._cleanup_expired_jobs()

        with app_module._jobs_lock:
            self.assertLessEqual(len(app_module._jobs), app_module._MAX_JOBS)
            # Clean up
            keys = [k for k in app_module._jobs if k.startswith("overflow-")]
            for k in keys:
                del app_module._jobs[k]


class TestDatetimeHandling(unittest.TestCase):
    """Verify datetime.utcnow() is not used."""

    def test_no_utcnow_in_app(self):
        import inspect
        source = inspect.getsource(app_module)
        self.assertNotIn("utcnow", source)

    def test_job_created_at_is_utc_iso(self):
        with app_module._jobs_lock:
            app_module._jobs["tz-test"] = {
                "status": "done",
                "_created_ts": time.time(),
                "created_at": app_module.datetime.now(
                    app_module.timezone.utc
                ).isoformat(),
                "files": [],
                "results": [],
                "errors": [],
            }
            created = app_module._jobs["tz-test"]["created_at"]
            del app_module._jobs["tz-test"]

        self.assertIn("+00:00", created)


class TestAllowedFiles(unittest.TestCase):
    """Test file extension validation."""

    def test_allowed_extensions(self):
        for ext in [".msg", ".pdf", ".doc", ".docx", ".ppt", ".pptx"]:
            self.assertTrue(app_module._allowed(f"file{ext}"), f"{ext} should be allowed")

    def test_rejected_extensions(self):
        for ext in [".exe", ".sh", ".py", ".js", ".bat"]:
            self.assertFalse(app_module._allowed(f"file{ext}"), f"{ext} should be rejected")


class TestRateLimiting(unittest.TestCase):
    """Test the IP-based rate limiter."""

    def setUp(self):
        self.client = app_module.app.test_client()
        with app_module._rate_lock:
            app_module._rate_store.clear()

    def test_rate_limiter_allows_under_limit(self):
        self.assertFalse(app_module._is_rate_limited("test-ip"))

    def test_rate_limiter_blocks_over_limit(self):
        for _ in range(app_module._RATE_LIMIT):
            app_module._is_rate_limited("flood-ip")
        self.assertTrue(app_module._is_rate_limited("flood-ip"))

    @patch("app._run_conversion")
    def test_convert_returns_429_when_limited(self, mock_convert):
        mock_convert.return_value = None
        with app_module._rate_lock:
            app_module._rate_store.clear()

        for _ in range(app_module._RATE_LIMIT):
            app_module._is_rate_limited("127.0.0.1")

        resp = self.client.post(
            "/convert",
            data={"files": (io.BytesIO(b"data"), "test.pdf")},
            content_type="multipart/form-data",
        )
        self.assertEqual(resp.status_code, 429)
        self.assertIn("Rate limit", resp.get_json()["error"])

    def tearDown(self):
        with app_module._rate_lock:
            app_module._rate_store.clear()


if __name__ == "__main__":
    unittest.main()
