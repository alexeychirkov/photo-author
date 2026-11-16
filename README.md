# photo-author

Read and update author metadata in JPEG photos from the command line.
Set a consistent creator name, copyright notice, and contact email across a batch
of images with ExifTool.

## Install

Requires Python 3.11 or newer, ExifTool, and uv. On macOS, install ExifTool
and uv with Homebrew:

```bash
brew install exiftool uv
```

From the root of this repository:

```bash
uv tool install .
uv tool update-shell
```

Open a new terminal if the command is still missing from your PATH.

## Usage

Read the existing author metadata in one or more photos:

```bash
photo-author show photo.jpg another.jpeg
photo-author show --json photo.jpg
```

Preview a batch update:

```bash
photo-author set ./*.jpg \
  --name "Morgan Lee" \
  --copyright "© Morgan Lee" \
  --email "morgan@example.com" \
  --dry-run
```

Once the preview looks right, run the same command without `--dry-run`
to write the metadata.

- `show` reads metadata without changing the image.
- `set` requires `--name` and writes the creator name to EXIF, XMP, and IPTC.
  Copyright is optional and uses the same three formats. Contact email is
  optional and stored in XMP. Omitted optional values are preserved.
- Updates create a `.bak` copy by default. Subsequent backups get numbered suffixes.
  Use `--no-backup` to skip backup creation.
- `--dry-run` prints the target files and planned changes without writing metadata
  or creating backups.

## Development

From the repository root:

```bash
uv tool install --editable .
uv run --with pytest pytest
```

## License

MIT. See [LICENSE](LICENSE).
