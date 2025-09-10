# Minimal image with system deps for ocrmypdf
FROM python:3.11-slim

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y --no-install-recommends     ocrmypdf tesseract-ocr tesseract-ocr-deu tesseract-ocr-eng     ghostscript qpdf     && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY . /app
RUN pip install --no-cache-dir -e .

ENTRYPOINT ["ocrc"]
