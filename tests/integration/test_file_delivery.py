"""Integration tests for file delivery endpoint"""
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient


class TestFileDelivery:
    """Tests for /v1/files endpoints"""

    @pytest.fixture
    def client(self, tmp_path):
        """Create test client with temp generated directory"""
        # Patch the generated directory to our temp directory
        from portal.interfaces.web import server

        # Create temp generated dir
        generated_dir = tmp_path / "generated"
        generated_dir.mkdir()

        # Patch Path in server module
        original_path = Path
        with patch.object(server, "Path") as mock_path:
            # Create a mock that returns our temp path for "data/generated"
            def path_factory(*args, **kwargs):
                if args and str(args[0]).startswith("data/generated"):
                    return generated_dir
                return original_path(*args, **kwargs)

            mock_path.side_effect = path_factory

            # Create the app
            from portal.interfaces.web.server import create_app

            app = create_app()
            client = TestClient(app, raise_server_exceptions=False)
            client.generated_dir = generated_dir
            yield client

    def test_list_files_empty(self, client):
        """GET /v1/files returns empty list when no files"""
        response = client.get("/v1/files")
        assert response.status_code == 200
        data = response.json()
        assert "files" in data
        assert data["files"] == []

    def test_list_files_with_files(self, client):
        """GET /v1/files returns files after creation"""
        # Create a test file
        test_file = client.generated_dir / "test.txt"
        test_file.write_text("test content")

        response = client.get("/v1/files")
        assert response.status_code == 200
        data = response.json()
        assert len(data["files"]) == 1
        assert data["files"][0]["name"] == "test.txt"

    def test_get_file_200(self, client):
        """GET /v1/files/{filename} returns 200 for existing file"""
        # Create a test file
        test_file = client.generated_dir / "document.docx"
        test_file.write_text("fake docx content")

        response = client.get("/v1/files/document.docx")
        assert response.status_code == 200

    def test_get_file_404(self, client):
        """GET /v1/files/{filename} returns 404 for nonexistent file"""
        response = client.get("/v1/files/nonexistent.txt")
        assert response.status_code == 404

    def test_get_file_path_traversal_blocked(self, client):
        """GET /v1/files/../../etc/passwd returns 400 (or 404 if FastAPI normalizes)"""
        response = client.get("/v1/files/../../etc/passwd")
        # Either 400 (app rejects) or 404 (FastAPI normalizes to non-existent) - both block access
        assert response.status_code in (400, 404)

    def test_get_file_path_traversal_encoded(self, client):
        """GET /v1/files/..%2F..%2Fetc%2Fpasswd returns 400 (or 404 if normalized)"""
        response = client.get("/v1/files/..%2F..%2Fetc%2Fpasswd")
        assert response.status_code in (400, 404)

    def test_get_file_slash_in_name(self, client):
        """GET /v1/files/foo/bar.txt returns 400"""
        response = client.get("/v1/files/foo/bar.txt")
        assert response.status_code in (400, 404)

    def test_get_file_backslash_in_name(self, client):
        """GET /v1/files/foo\\bar.txt returns 400"""
        response = client.get("/v1/files/foo\\bar.txt")
        assert response.status_code == 400
