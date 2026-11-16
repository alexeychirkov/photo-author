from pathlib import Path
import subprocess
from unittest.mock import patch

from photo_author.exiftool import write_metadata


def test_write_metadata_marks_iptc_as_utf8() -> None:
    completed = subprocess.CompletedProcess(
        args=[], returncode=0, stdout="", stderr=""
    )

    with patch("photo_author.exiftool.subprocess.run", return_value=completed) as run:
        write_metadata(
            [Path("photo.jpg")],
            {"IPTC:By-line": "Camille Noël"},
            "/usr/bin/exiftool",
        )

    command = run.call_args.args[0]
    assert command[:5] == [
        "/usr/bin/exiftool",
        "-overwrite_original",
        "-charset",
        "IPTC=UTF8",
        "-IPTC:CodedCharacterSet=UTF8",
    ]
    assert "-IPTC:By-line=Camille Noël" in command
