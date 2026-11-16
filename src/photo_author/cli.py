from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
import sys
from typing import Sequence

from photo_author.exiftool import (
    ExifToolError,
    find_executable,
    read_metadata,
    write_metadata,
)


AUTHOR_TAGS = (
    ("IFD0:Artist", "EXIF artist"),
    ("XMP-dc:Creator", "XMP creator"),
    ("IPTC:By-line", "IPTC by-line"),
    ("XMP-iptcCore:CreatorWorkEmail", "Creator email"),
)
RIGHTS_TAGS = (
    ("IFD0:Copyright", "EXIF copyright"),
    ("XMP-dc:Rights", "XMP rights"),
    ("IPTC:CopyrightNotice", "IPTC copyright notice"),
)
DISPLAY_TAGS = AUTHOR_TAGS + RIGHTS_TAGS
JPEG_SUFFIXES = {".jpg", ".jpeg"}


def non_empty_text(value: str) -> str:
    if not value.strip():
        raise argparse.ArgumentTypeError("must not be empty")
    return value


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="photo-author",
        description="Inspect and set author metadata in JPEG photos.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    show_parser = subparsers.add_parser("show", help="show author metadata")
    show_parser.add_argument("photos", nargs="+", type=Path, metavar="PHOTO")
    show_parser.add_argument(
        "--json",
        action="store_true",
        help="print raw metadata as JSON",
    )

    set_parser = subparsers.add_parser("set", help="set author metadata")
    set_parser.add_argument("photos", nargs="+", type=Path, metavar="PHOTO")
    set_parser.add_argument(
        "--name", required=True, type=non_empty_text, help="author name"
    )
    set_parser.add_argument(
        "--copyright",
        type=non_empty_text,
        help="copyright text; omit to leave copyright unchanged",
    )
    set_parser.add_argument(
        "--email",
        type=non_empty_text,
        help="creator email stored in XMP; Failiem.lv does not display it",
    )
    set_parser.add_argument(
        "--no-backup",
        action="store_true",
        help="do not create a .bak copy before updating",
    )
    set_parser.add_argument(
        "--dry-run",
        "--dryrun",
        dest="dry_run",
        action="store_true",
        help="show planned changes without modifying files",
    )
    return parser


def validate_photos(photos: Sequence[Path]) -> list[str]:
    errors: list[str] = []
    for photo in photos:
        if not photo.is_file():
            errors.append(f"not a file: {photo}")
        elif photo.suffix.lower() not in JPEG_SUFFIXES:
            errors.append(f"not a JPEG file: {photo}")
    return errors


def format_value(value: object) -> str:
    if isinstance(value, list):
        return ", ".join(str(item) for item in value)
    return str(value)


def print_human(metadata: Sequence[dict[str, object]]) -> None:
    for index, item in enumerate(metadata):
        if index:
            print()
        print(item.get("SourceFile", "unknown file"))
        for tag, label in DISPLAY_TAGS:
            value = item.get(tag)
            print(f"  {label}: {format_value(value) if value is not None else '(not set)'}")


def show(photos: Sequence[Path], as_json: bool) -> int:
    errors = validate_photos(photos)
    if errors:
        for error in errors:
            print(f"photo-author: {error}", file=sys.stderr)
        return 2

    try:
        exiftool = find_executable()
        metadata = read_metadata(
            photos, [tag for tag, _ in DISPLAY_TAGS], exiftool
        )
    except ExifToolError as error:
        print(f"photo-author: {error}", file=sys.stderr)
        return 1

    if as_json:
        print(json.dumps(metadata, ensure_ascii=False, indent=2))
    else:
        print_human(metadata)
    return 0


def next_backup_path(photo: Path) -> Path:
    candidate = Path(f"{photo}.bak")
    index = 1
    while candidate.exists():
        candidate = Path(f"{photo}.bak.{index}")
        index += 1
    return candidate


def metadata_values(
    name: str, copyright_text: str | None, email: str | None
) -> dict[str, str]:
    values = {
        "IFD0:Artist": name,
        "XMP-dc:Creator": name,
        "IPTC:By-line": name,
    }
    if copyright_text is not None:
        values.update(
            {
                "IFD0:Copyright": copyright_text,
                "XMP-dc:Rights": copyright_text,
                "IPTC:CopyrightNotice": copyright_text,
            }
        )
    if email is not None:
        values["XMP-iptcCore:CreatorWorkEmail"] = email
    return values


def verify_metadata(actual: dict[str, object], expected: dict[str, str]) -> list[str]:
    return [
        f"{tag}: expected {value!r}, got {actual.get(tag)!r}"
        for tag, value in expected.items()
        if actual.get(tag) != value
    ]


def print_dry_run(
    photos: Sequence[Path], values: dict[str, str], create_backup: bool
) -> None:
    for index, photo in enumerate(photos):
        if index:
            print()
        print(f"would update: {photo}")
        if create_backup:
            print(f"would backup: {next_backup_path(photo)}")
        else:
            print("backup: disabled")
        for tag, value in values.items():
            print(f"  {tag}: {value}")


def set_metadata(
    photos: Sequence[Path],
    name: str,
    copyright_text: str | None,
    email: str | None,
    create_backup: bool,
    dry_run: bool,
) -> int:
    errors = validate_photos(photos)
    if errors:
        for error in errors:
            print(f"photo-author: {error}", file=sys.stderr)
        return 2

    values = metadata_values(name, copyright_text, email)
    if dry_run:
        print_dry_run(photos, values, create_backup)
        return 0

    try:
        exiftool = find_executable()
    except ExifToolError as error:
        print(f"photo-author: {error}", file=sys.stderr)
        return 1

    backups: dict[Path, Path] = {}
    if create_backup:
        try:
            for photo in photos:
                backup = next_backup_path(photo)
                shutil.copy2(photo, backup)
                backups[photo] = backup
        except OSError as error:
            print(f"photo-author: failed to create backup for {photo}: {error}", file=sys.stderr)
            return 1

    try:
        warning = write_metadata(photos, values, exiftool)
        metadata = read_metadata(photos=photos, tags=list(values), executable=exiftool)
    except ExifToolError as error:
        print(f"photo-author: failed to update photos: {error}", file=sys.stderr)
        return 1

    metadata_by_source = {
        str(item.get("SourceFile")): item
        for item in metadata
        if item.get("SourceFile") is not None
    }
    failed = False
    for photo in photos:
        actual = metadata_by_source.get(str(photo))
        if actual is None:
            print(
                f"photo-author: failed to verify {photo}: no metadata returned",
                file=sys.stderr,
            )
            failed = True
            continue
        verification_errors = verify_metadata(actual, values)
        if verification_errors:
            print(
                f"photo-author: failed to verify {photo}: "
                + "; ".join(verification_errors),
                file=sys.stderr,
            )
            failed = True
            continue
        print(f"updated: {photo}")
        if photo in backups:
            print(f"backup: {backups[photo]}")
    if warning:
        print(f"warning: {warning}", file=sys.stderr)
    return 1 if failed else 0


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "show":
        return show(args.photos, args.json)
    if args.command == "set":
        return set_metadata(
            args.photos,
            args.name,
            args.copyright,
            args.email,
            not args.no_backup,
            args.dry_run,
        )
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
