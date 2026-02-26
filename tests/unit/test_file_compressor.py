"""Tests for portal.tools.data_tools.file_compressor"""

import os
import tarfile
import zipfile

import pytest

from portal.tools.data_tools.file_compressor import FileCompressorTool


class TestFileCompressorMetadata:
    def test_metadata(self):
        tool = FileCompressorTool()
        meta = tool._get_metadata()
        assert meta.name == "file_compressor"
        assert meta.requires_confirmation is True


class TestFileCompressorCompress:
    @pytest.mark.asyncio
    async def test_compress_zip(self, tmp_path):
        f1 = tmp_path / "a.txt"
        f1.write_text("hello")
        f2 = tmp_path / "b.txt"
        f2.write_text("world")
        archive = str(tmp_path / "out.zip")

        tool = FileCompressorTool()
        result = await tool.execute({
            "action": "compress",
            "files": [str(f1), str(f2)],
            "archive_path": archive,
            "format": "zip",
        })
        assert result["success"] is True
        assert os.path.exists(archive)
        with zipfile.ZipFile(archive) as zf:
            assert len(zf.namelist()) == 2

    @pytest.mark.asyncio
    async def test_compress_tar(self, tmp_path):
        f1 = tmp_path / "a.txt"
        f1.write_text("hello")
        archive = str(tmp_path / "out.tar")

        tool = FileCompressorTool()
        result = await tool.execute({
            "action": "compress",
            "files": [str(f1)],
            "archive_path": archive,
            "format": "tar",
        })
        assert result["success"] is True
        assert os.path.exists(archive)

    @pytest.mark.asyncio
    async def test_compress_tar_gz(self, tmp_path):
        f1 = tmp_path / "a.txt"
        f1.write_text("hello")
        archive = str(tmp_path / "out.tar.gz")

        tool = FileCompressorTool()
        result = await tool.execute({
            "action": "compress",
            "files": [str(f1)],
            "archive_path": archive,
            "format": "tar.gz",
        })
        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_compress_no_files(self, tmp_path):
        tool = FileCompressorTool()
        result = await tool.execute({
            "action": "compress",
            "files": [],
            "archive_path": str(tmp_path / "out.zip"),
        })
        assert result["success"] is False

    @pytest.mark.asyncio
    async def test_compress_unsupported_format(self, tmp_path):
        f1 = tmp_path / "a.txt"
        f1.write_text("hello")
        tool = FileCompressorTool()
        result = await tool.execute({
            "action": "compress",
            "files": [str(f1)],
            "archive_path": str(tmp_path / "out.7z"),
            "format": "7z",
        })
        assert result["success"] is False

    @pytest.mark.asyncio
    async def test_compress_nonexistent_file(self, tmp_path):
        archive = str(tmp_path / "out.zip")
        tool = FileCompressorTool()
        result = await tool.execute({
            "action": "compress",
            "files": ["/nonexistent/file.txt"],
            "archive_path": archive,
            "format": "zip",
        })
        assert result["success"] is True  # Silently skips missing files


class TestFileCompressorExtract:
    @pytest.mark.asyncio
    async def test_extract_zip(self, tmp_path):
        # Create a zip first
        f1 = tmp_path / "a.txt"
        f1.write_text("extracted content")
        archive = str(tmp_path / "test.zip")
        with zipfile.ZipFile(archive, 'w') as zf:
            zf.write(str(f1), "a.txt")

        tool = FileCompressorTool()
        old_cwd = os.getcwd()
        try:
            os.chdir(tmp_path)
            result = await tool.execute({
                "action": "extract",
                "archive_path": archive,
            })
            assert result["success"] is True
        finally:
            os.chdir(old_cwd)

    @pytest.mark.asyncio
    async def test_extract_tar_gz(self, tmp_path):
        f1 = tmp_path / "b.txt"
        f1.write_text("tar content")
        archive = str(tmp_path / "test.tar.gz")
        with tarfile.open(archive, "w:gz") as tf:
            tf.add(str(f1), arcname="b.txt")

        tool = FileCompressorTool()
        old_cwd = os.getcwd()
        try:
            os.chdir(tmp_path)
            result = await tool.execute({
                "action": "extract",
                "archive_path": archive,
            })
            assert result["success"] is True
        finally:
            os.chdir(old_cwd)

    @pytest.mark.asyncio
    async def test_extract_nonexistent(self):
        tool = FileCompressorTool()
        result = await tool.execute({
            "action": "extract",
            "archive_path": "/nonexistent/archive.zip",
        })
        assert result["success"] is False

    @pytest.mark.asyncio
    async def test_extract_unsupported_format(self, tmp_path):
        f = tmp_path / "test.rar"
        f.write_text("not a rar")
        tool = FileCompressorTool()
        old_cwd = os.getcwd()
        try:
            os.chdir(tmp_path)
            result = await tool.execute({
                "action": "extract",
                "archive_path": str(f),
            })
            assert result["success"] is False
        finally:
            os.chdir(old_cwd)


class TestFileCompressorActions:
    @pytest.mark.asyncio
    async def test_unknown_action(self):
        tool = FileCompressorTool()
        result = await tool.execute({
            "action": "nope",
            "archive_path": "x",
        })
        assert result["success"] is False
