from __future__ import annotations

import argparse
import csv
import os
import shutil
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable, List, Sequence, Tuple, Optional, Set

try:
    from tqdm import tqdm  # type: ignore
except Exception:
    tqdm = None  # graceful fallback

ALLOWED_SUFFIXES: Set[str] = {".pdf", ".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp"}


@dataclass
class JobResult:
    input_path: Path
    output_path: Path
    returncode: int
    duration_s: float
    log_head: str


def which_ocrmypdf() -> Optional[str]:
    exe = shutil.which("ocrmypdf")
    return exe


def expand_inputs(inputs: Sequence[str], recursive: bool) -> List[Path]:
    paths: List[Path] = []
    for raw in inputs:
        p = Path(raw)
        if p.exists():
            if p.is_dir():
                if recursive:
                    for ext in ALLOWED_SUFFIXES:
                        paths.extend(p.rglob(f"*{ext}"))
                else:
                    paths.extend([x for x in p.iterdir() if x.is_file() and x.suffix.lower() in ALLOWED_SUFFIXES])
            else:
                if p.suffix.lower() in ALLOWED_SUFFIXES:
                    paths.append(p)
        else:
            # Treat as glob pattern
            import glob

            for g in glob.glob(raw, recursive=recursive):
                gp = Path(g)
                if gp.is_file() and gp.suffix.lower() in ALLOWED_SUFFIXES:
                    paths.append(gp)
    # De-duplicate while preserving order
    seen: Set[Path] = set()
    unique: List[Path] = []
    for x in paths:
        if x not in seen:
            unique.append(x)
            seen.add(x)
    return unique


def build_output_path(inp: Path, output_dir: Optional[Path], inplace: bool, suffix: str) -> Path:
    if output_dir and not inplace:
        output_dir.mkdir(parents=True, exist_ok=True)
        return output_dir / f"{inp.stem}{suffix}.pdf"
    # in-place next to the input
    return inp.with_name(f"{inp.stem}{suffix}.pdf")


def run_ocr(
    inp: Path,
    out: Path,
    lang: str,
    force: bool,
    overwrite: bool,
    pdfa: bool,
    ocrmypdf_exe: str,
    extra_args: Sequence[str] = (),
    quiet: bool = False,
) -> JobResult:
    if not overwrite and out.exists():
        # Simulate skip with 0 code, do not invoke ocrmypdf
        return JobResult(inp, out, 0, 0.0, "skipped: exists")

    cmd = [
        ocrmypdf_exe,
        "--optimize",
        "3",
        "--language",
        lang,
        str(inp),
        str(out),
    ]
    if force:
        cmd.insert(1, "--force-ocr")
    else:
        cmd.insert(1, "--skip-text")
    if pdfa:
        cmd.insert(1, "--pdfa-2")
    if extra_args:
        cmd[1:1] = list(extra_args)

    start = time.time()
    p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    dur = time.time() - start
    head = (p.stdout or "")[:1200]
    return JobResult(inp, out, p.returncode, dur, head)


def write_log_header_if_needed(log_path: Path) -> None:
    if not log_path.exists() or log_path.stat().st_size == 0:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with open(log_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["When", "Input", "Output", "ReturnCode", "DurationSec", "OutputLogHead"])


def append_log(log_path: Path, result: JobResult) -> None:
    with open(log_path, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                datetime.now().isoformat(timespec="seconds"),
                str(result.input_path),
                str(result.output_path),
                result.returncode,
                f"{result.duration_s:.2f}",
                result.log_head.replace("\n", " ").replace("\r", " ")[:2000],
            ]
        )


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(
        prog="ocrc",
        description="OCR one or many documents at once using ocrmypdf (PDFs and common image formats).",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    ap.add_argument("inputs", nargs="+", help="Files, folders, or glob patterns. Use --recursive for folders/globs.")
    ap.add_argument("-o", "--output", type=Path, default=None, help="Output directory (mutually exclusive with --inplace).")
    ap.add_argument("--inplace", action="store_true", help="Write outputs next to inputs (adds suffix).")
    ap.add_argument("--suffix", default="_ocr", help="Suffix for output filenames (before .pdf).")
    ap.add_argument("--lang", default="deu+eng", help="OCR languages (Tesseract codes, e.g., 'eng', 'deu+eng').")
    ap.add_argument("--jobs", type=int, default=max(1, (os.cpu_count() or 2) // 2), help="Parallel workers.")
    ap.add_argument("--recursive", action="store_true", help="Recurse into folders / expand glob patterns recursively.")
    ap.add_argument("--overwrite", action="store_true", help="Overwrite existing outputs.")
    ap.add_argument("--force", action="store_true", help="Force OCR even if the PDF already contains text.")
    ap.add_argument("--pdfa", action="store_true", help="Output PDF/A-2 for archival.")
    ap.add_argument("--extra", nargs=argparse.REMAINDER, help="Pass additional raw args directly to ocrmypdf.")
    ap.add_argument("--log", type=Path, default=Path("ocr_log.csv"), help="CSV log path.")
    ap.add_argument("--dry-run", action="store_true", help="Show what would be processed without running OCR.")
    ap.add_argument("--no-progress", action="store_true", help="Disable progress bar.")
    ap.add_argument("-q", "--quiet", action="store_true", help="Less console output.")
    ap.add_argument("-v", "--verbose", action="store_true", help="More console output.")
    args = ap.parse_args(argv)

    if args.output and args.inplace:
        ap.error("Use either --output or --inplace (not both).")
    if not args.output and not args.inplace:
        # default to inplace if neither is set
        args.inplace = True
    if args.jobs < 1:
        ap.error("--jobs must be >= 1")
    return args


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)

    exe = which_ocrmypdf()
    if not exe:
        print("[ERR] 'ocrmypdf' executable not found on PATH. Please install system dependencies.", file=sys.stderr)
        return 127

    inputs = expand_inputs(args.inputs, recursive=args.recursive)
    if not inputs:
        print("[INFO] No matching files.", file=sys.stderr)
        return 0

    # Compute output paths and skip list
    jobs: List[Tuple[Path, Path]] = []
    for inp in inputs:
        out = build_output_path(inp, args.output, args.inplace, args.suffix)
        # avoid creating output that equals input (shouldn't happen but be safe)
        if out.resolve() == inp.resolve():
            out = out.with_name(out.stem + "_out.pdf")
        jobs.append((inp, out))

    if args.dry_run:
        print("Planned jobs:")
        for inp, out in jobs:
            print(f"  {inp}  ->  {out}")
        return 0

    write_log_header_if_needed(args.log)

    # progress
    use_progress = (tqdm is not None) and (not args.no_progress) and (not args.quiet)
    pbar = tqdm(total=len(jobs), desc="OCR", unit="file") if use_progress else None

    failures = 0
    skipped = 0
    results: List[JobResult] = []

    def submit_job(inp_out: Tuple[Path, Path]) -> JobResult:
        inp, out = inp_out
        res = run_ocr(
            inp=inp,
            out=out,
            lang=args.lang,
            force=args.force,
            overwrite=args.overwrite,
            pdfa=args.pdfa,
            ocrmypdf_exe=exe,
            extra_args=args.extra or (),
            quiet=args.quiet,
        )
        append_log(args.log, res)
        return res

    with ThreadPoolExecutor(max_workers=args.jobs) as pool:
        futures = {pool.submit(submit_job, job): job for job in jobs}
        for fut in as_completed(futures):
            res = fut.result()
            results.append(res)
            if res.returncode != 0 and res.log_head != "skipped: exists":
                failures += 1
            if res.log_head == "skipped: exists":
                skipped += 1
            if pbar:
                pbar.update(1)

    if pbar:
        pbar.close()

    done = len(jobs) - skipped
    if not args.quiet:
        print(f"[SUMMARY] inputs={len(jobs)} processed={done} skipped_existing={skipped} failures={failures}")
        if args.verbose:
            for r in results[:10]:
                print(f" - {r.input_path.name}: rc={r.returncode}, out={r.output_path.name}, took={r.duration_s:.2f}s")

    return 1 if failures > 0 else 0


if __name__ == "__main__":
    raise SystemExit(main())
