#!/usr/bin/env python3
"""Build the Windows source bundle and Chinese PDF from one maintained guide."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
from xml.sax.saxutils import escape
import zipfile

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "output" / "windows-delivery"


def build_pdf(target: Path) -> None:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, PageBreak

    candidates = [
        os.environ.get("PIXEL3MF_PDF_FONT", ""),
        "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
        "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
    ]
    font = next((Path(p) for p in candidates if p and Path(p).is_file()), None)
    if font is None:
        raise FileNotFoundError("Set PIXEL3MF_PDF_FONT to a Chinese TrueType font")
    pdfmetrics.registerFont(TTFont("CJK", str(font)))
    navy = colors.HexColor("#163442")
    styles = {
        "title": ParagraphStyle("title", fontName="CJK", fontSize=23, leading=32,
                                textColor=navy, spaceAfter=20, wordWrap="CJK"),
        "heading": ParagraphStyle("heading", fontName="CJK", fontSize=13, leading=20,
                                  textColor=colors.HexColor("#167D83"), spaceBefore=9,
                                  spaceAfter=7, wordWrap="CJK", keepWithNext=True),
        "body": ParagraphStyle("body", fontName="CJK", fontSize=10, leading=16,
                               textColor=navy, spaceAfter=9, wordWrap="CJK"),
        "code": ParagraphStyle("code", fontName="CJK", fontSize=9, leading=15,
                               textColor=navy, backColor=colors.HexColor("#EDF5F4"),
                               borderPadding=9, spaceBefore=5, spaceAfter=12,
                               wordWrap="CJK"),
    }
    story = []
    code = None
    for line in (ROOT / "docs/windows-deployment.md").read_text().splitlines():
        if line.startswith("```"):
            if code is None:
                code = []
            else:
                story.append(Paragraph("<br/>".join(map(escape, code)), styles["code"]))
                code = None
            continue
        if code is not None:
            code.append(line)
            continue
        if line == "---":
            story.append(PageBreak())
        elif line.startswith("# "):
            story.append(Paragraph(escape(line[2:]), styles["title"]))
        elif line.startswith("## "):
            story.append(Paragraph(escape(line[3:]), styles["heading"]))
        elif line.strip():
            story.append(Paragraph(escape(line), styles["body"]))
        else:
            story.append(Spacer(1, 2))

    def footer(canvas, doc):
        width, height = A4
        canvas.setStrokeColor(colors.HexColor("#D3E0E2"))
        canvas.line(44, 42, width - 44, 42)
        canvas.setFont("CJK", 8)
        canvas.setFillColor(colors.HexColor("#576B73"))
        canvas.drawString(44, 28, "PIXEL3MF  /  Windows deployment")
        canvas.drawRightString(width - 44, 28, str(doc.page))
        canvas.drawString(44, height - 28, "部署与使用  ·  Windows x64")

    SimpleDocTemplate(str(target), pagesize=A4, rightMargin=44, leftMargin=44,
                      topMargin=54, bottomMargin=57, title="Pixel3MF Windows 部署指南",
                      author="Pixel3MF").build(story, onFirstPage=footer, onLaterPages=footer)
    from pypdf import PdfReader
    pages = PdfReader(target).pages
    if len(pages) != 5 or any(not page.extract_text().strip() for page in pages):
        raise RuntimeError(f"Expected five nonempty guide pages, got {len(pages)}")


def bundle_files() -> list[Path]:
    files = [ROOT / name for name in (
        "01_install_windows.cmd", "02_convert_image.cmd", "README.md",
        "requirements-pixel3mf.txt", "docs/windows-deployment.md",
    )]
    for directory in ("tools", "windows", "profiles", "skills", "guides", "examples"):
        base = ROOT / directory
        for path in base.rglob("*"):
            relative = path.relative_to(ROOT)
            if (path.is_file() and not path.is_symlink()
                    and not any(part.startswith(".") or part == "__pycache__" for part in relative.parts)
                    and path.suffix.lower() in {".py", ".ps1", ".json", ".md", ".yaml", ".png", ".jpg"}):
                files.append(path)
    return sorted(set(files))


def main() -> None:
    DIST.mkdir(parents=True, exist_ok=True)
    pdf = DIST / "pixel3mf-windows-guide.pdf"
    build_pdf(pdf)
    preview_copy = ROOT / "output/pdf" / pdf.name
    preview_copy.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(pdf, preview_copy)
    revision = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    dirty = bool(subprocess.check_output(
        ["git", "status", "--porcelain", "--untracked-files=no"], cwd=ROOT, text=True).strip())
    info = {"source_commit": revision, "tracked_worktree_changes": dirty,
            "windows_install_check": os.environ.get("PIXEL3MF_WINDOWS_CHECK", "not_run"),
            "full_conversion_check": "not_run", "bundle_type": "online_source_installer"}
    archive_path = DIST / "pixel3mf-windows.zip"
    with zipfile.ZipFile(archive_path, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in bundle_files():
            data = path.read_bytes()
            # CMD uses CRLF; PS5 needs a BOM to interpret Chinese filenames reliably.
            if path.suffix in {".cmd", ".ps1"}:
                data = path.read_text(encoding="utf-8-sig").replace("\r\n", "\n").replace("\n", "\r\n").encode("utf-8")
                if path.suffix == ".ps1":
                    data = b"\xef\xbb\xbf" + data
            archive.writestr("pixel3mf/" + path.relative_to(ROOT).as_posix(), data)
        archive.write(pdf, "pixel3mf/pixel3mf-windows-guide.pdf")
        archive.writestr("pixel3mf/BUILD-INFO.json", json.dumps(info, ensure_ascii=False, indent=2) + "\n")
        archive.writestr("pixel3mf/output/.gitkeep", "")
    with zipfile.ZipFile(archive_path) as archive:
        if archive.testzip() is not None:
            raise RuntimeError("ZIP integrity check failed")
        if any(re.search(r"/(\.git|\.venv|\.cache|Lumina-Layers)/", name) for name in archive.namelist()):
            raise RuntimeError("Unexpected runtime or private repository files in bundle")
    (DIST / "SHA256SUMS.txt").write_text("".join(
        f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.name}\n"
        for path in (archive_path, pdf)
    ))
    print(archive_path)
    print(pdf)


if __name__ == "__main__":
    main()
