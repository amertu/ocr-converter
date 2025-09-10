from pathlib import Path
from ocr_converter.cli import expand_inputs, build_output_path, ALLOWED_SUFFIXES

def test_suffix_set():
    assert ".pdf" in ALLOWED_SUFFIXES
    assert ".png" in ALLOWED_SUFFIXES

def test_build_output_path(tmp_path: Path):
    f = tmp_path / "a.pdf"
    f.write_bytes(b"data")
    out1 = build_output_path(f, None, True, "_ocr")
    assert out1.name == "a_ocr.pdf"
    out2 = build_output_path(f, tmp_path/"out", False, "_ocr")
    assert out2.parent.name == "out"
    assert out2.name == "a_ocr.pdf"

def test_expand_inputs_glob(tmp_path: Path, monkeypatch):
    f1 = tmp_path / "x.pdf"
    f2 = tmp_path / "y.png"
    f3 = tmp_path / "z.txt"
    f1.write_bytes(b"")
    f2.write_bytes(b"")
    f3.write_bytes(b"")
    res = expand_inputs([str(tmp_path/"*.pdf"), str(tmp_path/"*.png")], recursive=False)
    assert f1 in res and f2 in res and f3 not in res
