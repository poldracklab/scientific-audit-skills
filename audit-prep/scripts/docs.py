# /// script
# requires-python = ">=3.11"
# dependencies = ["openpyxl"]
# ///
"""Convert PDFs, DOCX and XLSX into audit-friendly text, images and CSV."""

import csv
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

TOOLS = ("pdftotext", "pdftoppm", "pandoc", "zstd", "docling", "git")
DOCLING = ["uvx", "--from", "docling", "docling"]


def pdf_to_text(pdf: Path, out: Path) -> Path:
    out.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["pdftotext", "-layout", str(pdf), str(out)], check=True)
    return out


def pdf_to_pages(pdf: Path, out_dir: Path, dpi: int = 110) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    cmd = ["pdftoppm", "-png", "-r", str(dpi), str(pdf), str(out_dir / "p")]
    subprocess.run(cmd, check=True)
    return _renamed_pages(out_dir)


def _renamed_pages(out_dir: Path) -> list[Path]:
    pages = []
    for src in sorted(out_dir.glob("p-*.png")):
        number = int(src.stem.split("-")[1])
        dest = out_dir / f"p-{number:03d}.png"
        if src != dest:
            src.rename(dest)
        pages.append(dest)
    return sorted(pages)


def docx_to_md(docx: Path, out: Path, media_dir: Path) -> Path:
    out.parent.mkdir(parents=True, exist_ok=True)
    cmd = ["pandoc", str(docx), "-t", "gfm", "-o", str(out), f"--extract-media={media_dir}"]
    subprocess.run(cmd, check=True)
    return out


def _safe_sheet_name(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9_-]", "_", name)


def xlsx_to_csv(xlsx: Path, out_dir: Path) -> list[Path]:
    import openpyxl

    out_dir.mkdir(parents=True, exist_ok=True)
    wb = openpyxl.load_workbook(xlsx, read_only=True, data_only=True)
    files = []
    for ws in wb.worksheets:
        dest = out_dir / f"{_safe_sheet_name(ws.title)}.csv"
        _write_rows(dest, ([_cell(v) for v in row] for row in ws.iter_rows(values_only=True)))
        files.append(dest)
    return files


def _cell(value) -> str:
    return "" if value is None else str(value)


def _write_rows(dest: Path, rows) -> None:
    with dest.open("w", newline="") as fh:
        csv.writer(fh).writerows(rows)


# --- docling structured export -------------------------------------------------


def _md_row(cells) -> str:
    return "| " + " | ".join(str(c).replace("|", "\\|").replace("\n", " ") for c in cells) + " |"


def _write_index(path: Path, rows: list[list]) -> None:
    lines = [_md_row(["file", "page", "caption"]), _md_row(["---", "---", "---"])]
    lines += [_md_row(r) for r in rows]
    path.write_text("\n".join(lines) + "\n")


def _caption(item: dict, doc: dict) -> str:
    texts = doc.get("texts", [])
    parts = []
    for ref in item.get("captions", []):
        match = re.fullmatch(r"#/texts/(\d+)", ref.get("$ref", ""))
        if match and int(match.group(1)) < len(texts):
            parts.append(texts[int(match.group(1))].get("text", ""))
    return " ".join(parts)


def _page(item: dict) -> int | str:
    prov = item.get("prov") or [{}]
    return prov[0].get("page_no", "")


def _picture_source(item: dict, base: Path) -> Path | None:
    uri = (item.get("image") or {}).get("uri", "")
    if not uri or uri.startswith("data:"):
        return None
    src = base / uri
    return src if src.is_file() else None


def _index_figures(doc: dict, base: Path, out_dir: Path) -> dict[str, str]:
    """Copy pictures to figures/fig-NN.png; return {docling image uri: new relative path}."""
    fig_dir = out_dir / "figures"
    fig_dir.mkdir(parents=True, exist_ok=True)
    rows, moved = [], {}
    for item in doc.get("pictures", []):
        src = _picture_source(item, base)
        if src is None:
            continue
        name = f"fig-{len(rows) + 1:02d}.png"
        shutil.copyfile(src, fig_dir / name)
        moved[item["image"]["uri"]] = f"figures/{name}"
        rows.append([name, _page(item), _caption(item, doc)])
    _write_index(fig_dir / "figures.md", rows)
    return moved


def _rewrite_links(markdown: Path, moved: dict[str, str]) -> None:
    if not markdown.is_file():
        return
    text = markdown.read_text()
    for old, new in moved.items():
        text = text.replace(old, new)
    markdown.write_text(text)


def _grid(item: dict) -> list[list[str]]:
    grid = (item.get("data") or {}).get("grid", [])
    return [[cell.get("text", "") for cell in row] for row in grid]


def _index_tables(doc: dict, out_dir: Path) -> int:
    tab_dir = out_dir / "tables"
    tab_dir.mkdir(parents=True, exist_ok=True)
    rows = []
    for item in doc.get("tables", []):
        name = f"table-{len(rows) + 1:02d}.csv"
        _write_rows(tab_dir / name, _grid(item))
        rows.append([name, _page(item), _caption(item, doc)])
    _write_index(tab_dir / "tables.md", rows)
    return len(rows)


def _index_docling(json_path: Path, out_dir: Path) -> tuple[int, int]:
    import json

    doc = json.loads(json_path.read_text())
    moved = _index_figures(doc, json_path.parent, out_dir)
    _rewrite_links(out_dir / f"{json_path.stem}.md", moved)
    return len(moved), _index_tables(doc, out_dir)


def _run_docling(pdf: Path, work: Path, run) -> None:
    cmd = DOCLING + ["--to", "md", "--to", "json", "--image-export-mode", "referenced"]
    result = run(cmd + ["--output", str(work), str(pdf)], capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(result.stderr or f"docling exited with {result.returncode}")


def _convert(pdf: Path, out_dir: Path, run, work: Path) -> dict:
    _run_docling(pdf, work, run)
    markdown = out_dir / f"{pdf.stem}.md"
    shutil.copyfile(work / f"{pdf.stem}.md", markdown)
    figures, tables = _index_docling(work / f"{pdf.stem}.json", out_dir)
    return {"status": "ok", "reason": "", "markdown": str(markdown), "figures": figures, "tables": tables}


def pdf_to_structured(pdf: Path, out_dir: Path, run=subprocess.run) -> dict:
    failed = {"status": "failed", "reason": "", "markdown": None, "figures": 0, "tables": 0}
    try:
        out_dir.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory() as tmp:
            return _convert(pdf, out_dir, run, Path(tmp))
    except Exception as exc:  # noqa: BLE001 - failures are recorded, never raised
        return {**failed, "reason": str(exc) or type(exc).__name__}


# --- tool versions -------------------------------------------------------------


def _first_line(cmd: list[str], timeout: int) -> str | None:
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except (OSError, subprocess.SubprocessError):
        return None
    lines = (r.stdout or r.stderr).strip().splitlines()
    return lines[0] if lines else None


def _tool_version(tool: str) -> str | None:
    if tool == "docling":
        return _first_line(DOCLING + ["--version"], 20) if shutil.which("uvx") else None
    if not shutil.which(tool):
        return None
    return _first_line([tool, "--version"], 10)


def tool_versions() -> dict[str, str | None]:
    return {tool: _tool_version(tool) for tool in TOOLS}
