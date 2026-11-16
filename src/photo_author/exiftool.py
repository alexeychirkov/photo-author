from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess
from typing import Mapping, Sequence


class ExifToolError(RuntimeError):
    """Raised when ExifTool cannot complete an operation."""


def find_executable() -> str:
    executable = shutil.which("exiftool")
    if executable is None:
        raise ExifToolError("ExifTool is required but was not found in PATH")
    return executable


def read_metadata(
    photos: Sequence[Path], tags: Sequence[str], executable: str
) -> list[dict[str, object]]:
    command = [
        executable,
        "-json",
        "-G1",
        "-s",
        *(f"-{tag}" for tag in tags),
        *(str(photo) for photo in photos),
    ]
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise ExifToolError(result.stderr.strip() or "ExifTool failed")

    try:
        metadata = json.loads(result.stdout)
    except json.JSONDecodeError as error:
        raise ExifToolError("ExifTool returned invalid JSON") from error

    if not isinstance(metadata, list):
        raise ExifToolError("ExifTool returned unexpected data")
    return metadata


def write_metadata(
    photos: Sequence[Path], values: Mapping[str, str], executable: str
) -> str:
    command = [
        executable,
        "-overwrite_original",
        "-charset",
        "IPTC=UTF8",
        "-IPTC:CodedCharacterSet=UTF8",
        *(f"-{tag}={value}" for tag, value in values.items()),
        "-IPTCDigest=new",
        *(str(photo) for photo in photos),
    ]
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise ExifToolError(result.stderr.strip() or "ExifTool failed")
    return result.stderr.strip()
