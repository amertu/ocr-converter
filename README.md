# OCR Converter

A clean, practical command‑line tool to OCR one or many documents at once.  
It wraps the excellent [`ocrmypdf`](https://ocrmypdf.readthedocs.io/) tool under a friendly CLI.

## Why this?
- **Batch or single file**: pass one file, many files, directories, or globs.
- **Predictable output**: creates `*_ocr.pdf` by default, in-place or to an output folder.
- **Fast**: parallel processing, progress bar, and safe skipping of already searchable PDFs.
- **Auditable**: optional CSV log (timestamp, input, output, return code, and snippet of logs).

## Requirements
- Python 3.9+
- System dependencies (install via your OS package manager or Docker):
  - `ocrmypdf`, `tesseract-ocr`, `ghostscript`, `qpdf`, `leptonica`/`tesseract` libs
- (Optional) `tesseract-ocr-<lang>` packages for your OCR languages (e.g., `deu`, `eng`).

### macOS (Homebrew)
```bash
brew install ocrmypdf tesseract ghostscript qpdf
```

### Ubuntu/Debian
```bash
sudo apt-get update
sudo apt-get install -y ocrmypdf tesseract-ocr tesseract-ocr-deu tesseract-ocr-eng ghostscript qpdf
```

### Windows
- Install Python 3.11+ from python.org.
- Install `ocrmypdf` and its dependencies from: https://ocrmypdf.readthedocs.io/en/latest/installation.html#windows
- Ensure `ocrmypdf.exe` is on your PATH.

## Install (this project)
```bash
pip install -e .
# or build:
# python -m build && pip install dist/ocr_converter-*.whl
```

## CLI usage
```bash
# Single file (in-place): produces file_ocr.pdf next to the input
ocrc /path/to/file.pdf

# Multiple files
ocrc file1.pdf file2.jpg file3.tiff

# Directory (recursive) -> write outputs to ./out
ocrc /path/to/folder --recursive -o out

# Globs
ocrc "*.pdf" "*.png" --recursive

# Force OCR even if text is detected; use 4 workers
ocrc docs/ --recursive --force --jobs 4

# Set languages (Tesseract codes) and log to CSV
ocrc docs/ --recursive --lang deu+eng --log ocr_log.csv

# In-place processing, overwrite existing outputs
ocrc docs/ --recursive --inplace --overwrite
```

## Options
Run `ocrc -h` for the full help.

## Docker (optional)
A convenient Dockerfile is provided. Build and run like this:
```bash
docker build -t ocr-converter .
docker run --rm -v "$PWD:/work" ocr-converter ocrc /work/docs --recursive -o /work/out --jobs 4
```

## Notes
- This project uses the system `ocrmypdf` for robustness. The Python package `ocrmypdf` may be installed, but the CLI executable must be available on PATH.
- For PDFs that are already searchable, `ocrmypdf` with `--skip-text` safely avoids re-OCR unless `--force` is given.
