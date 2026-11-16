from pathlib import Path
from unittest.mock import patch

import pytest

from photo_author.cli import (
    format_value,
    main,
    metadata_values,
    next_backup_path,
    validate_photos,
)


def test_validate_photos_accepts_jpeg(tmp_path: Path) -> None:
    photo = tmp_path / "photo.JPG"
    photo.touch()

    assert validate_photos([photo]) == []


def test_validate_photos_rejects_missing_file(tmp_path: Path) -> None:
    photo = tmp_path / "missing.jpg"

    assert validate_photos([photo]) == [f"not a file: {photo}"]


def test_format_value_joins_list_values() -> None:
    assert format_value(["Morgan", "Alice"]) == "Morgan, Alice"


def test_show_prints_metadata(tmp_path: Path, capsys) -> None:
    photo = tmp_path / "photo.jpg"
    photo.touch()
    metadata = [
        {
            "SourceFile": str(photo),
            "IFD0:Artist": "Morgan Lee",
            "XMP-iptcCore:CreatorWorkEmail": "morgan@example.com",
        }
    ]

    with (
        patch("photo_author.cli.find_executable", return_value="/usr/bin/exiftool"),
        patch("photo_author.cli.read_metadata", return_value=metadata),
    ):
        exit_code = main(["show", str(photo)])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "EXIF artist: Morgan Lee" in captured.out
    assert "XMP creator: (not set)" in captured.out
    assert "Creator email: morgan@example.com" in captured.out


def test_show_rejects_non_jpeg(tmp_path: Path, capsys) -> None:
    photo = tmp_path / "photo.png"
    photo.touch()

    exit_code = main(["show", str(photo)])

    assert exit_code == 2
    assert f"not a JPEG file: {photo}" in capsys.readouterr().err


def test_metadata_values_keeps_copyright_separate() -> None:
    values = metadata_values(
        "Morgan Lee",
        "Morgan Lee, morgan@example.com",
        "morgan@example.com",
    )

    assert values["IFD0:Artist"] == "Morgan Lee"
    assert values["XMP-dc:Rights"] == "Morgan Lee, morgan@example.com"
    assert values["XMP-iptcCore:CreatorWorkEmail"] == "morgan@example.com"


def test_metadata_values_name_only_does_not_touch_copyright() -> None:
    values = metadata_values("Camille Noël", None, None)

    assert values == {
        "IFD0:Artist": "Camille Noël",
        "XMP-dc:Creator": "Camille Noël",
        "IPTC:By-line": "Camille Noël",
    }


def test_next_backup_path_does_not_overwrite_existing_backup(tmp_path: Path) -> None:
    photo = tmp_path / "photo.jpg"
    Path(f"{photo}.bak").touch()

    assert next_backup_path(photo) == Path(f"{photo}.bak.1")


def test_set_batches_writes_and_verification(tmp_path: Path, capsys) -> None:
    photos = [tmp_path / "one.jpg", tmp_path / "two.jpg"]
    for photo in photos:
        photo.write_bytes(f"jpeg data: {photo.name}".encode())
    expected = metadata_values("Morgan", "Morgan, morgan@example.com", None)

    with (
        patch("photo_author.cli.find_executable", return_value="/usr/bin/exiftool"),
        patch("photo_author.cli.write_metadata") as write,
        patch(
            "photo_author.cli.read_metadata",
            return_value=[
                {"SourceFile": str(photo), **expected} for photo in photos
            ],
        ),
    ):
        exit_code = main(
            [
                "set",
                *(str(photo) for photo in photos),
                "--name",
                "Morgan",
                "--copyright",
                "Morgan, morgan@example.com",
            ]
        )

    assert exit_code == 0
    for photo in photos:
        assert Path(f"{photo}.bak").read_bytes() == photo.read_bytes()
    write.assert_called_once_with(photos, expected, "/usr/bin/exiftool")
    output = capsys.readouterr().out
    assert all(f"updated: {photo}" in output for photo in photos)


def test_dry_run_does_not_modify_file_or_create_backup(tmp_path: Path, capsys) -> None:
    photo = tmp_path / "photo.jpg"
    photo.write_bytes(b"original jpeg data")

    with (
        patch("photo_author.cli.find_executable") as find_executable,
        patch("photo_author.cli.write_metadata") as write_metadata,
        patch("photo_author.cli.read_metadata") as read_metadata,
    ):
        exit_code = main(
            [
                "set",
                str(photo),
                "--name",
                "Morgan",
                "--copyright",
                "Morgan, morgan@example.com",
                "--dry-run",
            ]
        )

    output = capsys.readouterr().out
    assert exit_code == 0
    assert photo.read_bytes() == b"original jpeg data"
    assert not Path(f"{photo}.bak").exists()
    assert f"would update: {photo}" in output
    assert f"would backup: {photo}.bak" in output
    assert "XMP-dc:Rights: Morgan, morgan@example.com" in output
    find_executable.assert_not_called()
    write_metadata.assert_not_called()
    read_metadata.assert_not_called()


def test_dryrun_alias_respects_no_backup(tmp_path: Path, capsys) -> None:
    photo = tmp_path / "photo.jpg"
    photo.touch()

    exit_code = main(
        [
            "set",
            str(photo),
            "--name",
            "Morgan",
            "--copyright",
            "Copyright",
            "--no-backup",
            "--dryrun",
        ]
    )

    assert exit_code == 0
    assert "backup: disabled" in capsys.readouterr().out


def test_empty_copyright_is_rejected(tmp_path: Path, capsys) -> None:
    photo = tmp_path / "photo.jpg"
    photo.touch()

    with pytest.raises(SystemExit) as error:
        main(
            [
                "set",
                str(photo),
                "--name",
                "Camille Noël",
                "--copyright",
                "",
            ]
        )

    assert error.value.code == 2
    assert "argument --copyright: must not be empty" in capsys.readouterr().err
