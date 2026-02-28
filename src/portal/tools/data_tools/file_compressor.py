"""File Compressor Tool - Archive handling"""

import os
import tarfile
import zipfile
from pathlib import Path
from typing import Any

from portal.core.interfaces.tool import BaseTool, ToolCategory, ToolMetadata, ToolParameter


class FileCompressorTool(BaseTool):
    """Compress and decompress files/archives"""

    def _get_metadata(self) -> ToolMetadata:
        return ToolMetadata(
            name="file_compressor",
            description="Compress files to ZIP/TAR or extract archives",
            category=ToolCategory.UTILITY,
            version="1.0.0",
            requires_confirmation=True,
            parameters=[
                ToolParameter(
                    name="action",
                    param_type="string",
                    description="Action: compress or extract",
                    required=True,
                ),
                ToolParameter(
                    name="files",
                    param_type="list",
                    description="List of file paths to compress",
                    required=False,
                ),
                ToolParameter(
                    name="archive_path",
                    param_type="string",
                    description="Path to archive file",
                    required=True,
                ),
                ToolParameter(
                    name="format",
                    param_type="string",
                    description="Archive format: zip, tar, tar.gz",
                    required=False,
                    default="zip",
                ),
            ],
            examples=["Compress files to backup.zip"],
        )

    async def execute(self, parameters: dict[str, Any]) -> dict[str, Any]:
        """Compress or extract files"""
        try:
            action = parameters.get("action", "").lower()
            archive_path = parameters.get("archive_path", "")
            fmt = parameters.get("format", "zip").lower()

            if action == "compress":
                files = parameters.get("files", [])
                if not files:
                    return self._error_response("No files to compress")
                return await self._compress(files, archive_path, fmt)

            elif action == "extract":
                if not os.path.exists(archive_path):
                    return self._error_response(f"Archive not found: {archive_path}")
                return await self._extract(archive_path)

            else:
                return self._error_response(f"Unknown action: {action}")

        except Exception as e:
            return self._error_response(str(e))

    async def _compress(self, files: list[str], archive_path: str, fmt: str) -> dict[str, Any]:
        """Compress files"""
        if fmt not in ("zip", "tar", "tar.gz"):
            return self._error_response(f"Unsupported format: {fmt}")
        if fmt == "zip":
            with zipfile.ZipFile(archive_path, "w", zipfile.ZIP_DEFLATED) as zf:
                for file_path in files:
                    if os.path.exists(file_path):
                        zf.write(file_path, os.path.basename(file_path))
        if fmt in ("tar", "tar.gz"):
            mode = "w:gz" if fmt == "tar.gz" else "w"
            with tarfile.open(archive_path, mode) as tf:
                for file_path in files:
                    if os.path.exists(file_path):
                        tf.add(file_path, arcname=os.path.basename(file_path))

        size = os.path.getsize(archive_path)
        return self._success_response(
            {
                "message": f"Created archive: {archive_path}",
                "size_bytes": size,
                "files_added": len(files),
            }
        )

    async def _extract(self, archive_path: str) -> dict[str, Any]:
        """Extract archive"""
        output_dir = Path(archive_path).stem + "_extracted"
        os.makedirs(output_dir, exist_ok=True)

        extracted = []

        if archive_path.endswith(".zip"):
            with zipfile.ZipFile(archive_path, "r") as zf:
                zf.extractall(output_dir)
                extracted = zf.namelist()
        elif archive_path.endswith((".tar", ".tar.gz", ".tgz")):
            with tarfile.open(archive_path, "r:*") as tf:
                tf.extractall(output_dir)
                extracted = tf.getnames()
        else:
            return self._error_response("Unsupported archive format")

        return self._success_response(
            {
                "message": f"Extracted to: {output_dir}",
                "files_extracted": len(extracted),
                "files": extracted[:10],  # First 10 files
            }
        )
