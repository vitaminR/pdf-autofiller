#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path


REPO_DIR = Path(__file__).resolve().parent
INBOX_DIR = REPO_DIR / "inbox"
OUT_DIR = REPO_DIR / "out"


def _pick_pdf(pdf_arg: str | None) -> Path:
    if pdf_arg:
        p = Path(pdf_arg)
        if not p.is_absolute():
            p = (REPO_DIR / p).resolve()
        if p.exists():
            return p

        # Fuzzy match: treat the argument as a substring of a PDF in inbox/
        # (useful for '--pdf d25' instead of typing the full filename).
        needle = pdf_arg.lower()
        candidates = sorted(INBOX_DIR.glob("*.pdf"))
        matches = [c for c in candidates if needle in c.name.lower()]
        if len(matches) == 1:
            return matches[0]
        if len(matches) > 1:
            names = "\n".join(f"- {m.name}" for m in matches)
            raise SystemExit(f"Ambiguous --pdf '{pdf_arg}'. Matches:\n{names}")

        raise SystemExit(f"PDF not found: {p}")

    pdfs = sorted(INBOX_DIR.glob("*.pdf"))
    if not pdfs:
        raise SystemExit(
            f"No PDFs found in {INBOX_DIR}. Drop a PDF there or pass --pdf PATH."
        )
    return pdfs[0]


def cmd_list(_: argparse.Namespace) -> int:
    INBOX_DIR.mkdir(parents=True, exist_ok=True)
    pdfs = sorted(INBOX_DIR.glob("*.pdf"))
    if not pdfs:
        print(f"No PDFs in {INBOX_DIR}")
        return 0
    for p in pdfs:
        size_mb = p.stat().st_size / 1024 / 1024
        print(f"{size_mb:6.1f} MB  {p.name}")
    return 0


def cmd_info(args: argparse.Namespace) -> int:
    pdf_path = _pick_pdf(args.pdf)

    from pypdf import PdfReader

    reader = PdfReader(str(pdf_path))
    pages = len(reader.pages)
    fields = {}
    try:
        fields = reader.get_fields() or {}
    except Exception:
        fields = {}

    size_mb = pdf_path.stat().st_size / 1024 / 1024

    print(f"PDF: {pdf_path}")
    print(f"Size: {size_mb:.1f} MB")
    print(f"Pages: {pages}")
    print(f"AcroForm fields: {len(fields)}")

    if args.fields and fields:
        for name in sorted(fields.keys()):
            print(name)

    return 0


def cmd_grid(args: argparse.Namespace) -> int:
    pdf_path = _pick_pdf(args.pdf)
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    out_path = Path(args.out) if args.out else (OUT_DIR / f"{pdf_path.stem}__grid.pdf")

    from fill_pdf import overlay_grid

    overlay_grid(str(pdf_path), str(out_path), step=args.step)
    print(f"Wrote: {out_path}")
    return 0


def cmd_extract_md(args: argparse.Namespace) -> int:
    pdf_path = _pick_pdf(args.pdf)
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    out_path = Path(args.out) if args.out else (OUT_DIR / f"{pdf_path.stem}.md")

    from docling.document_converter import DocumentConverter

    converter = DocumentConverter()
    result = converter.convert(str(pdf_path))
    doc = result.document

    if not hasattr(doc, "export_to_markdown"):
        raise SystemExit(
            "This docling version does not expose export_to_markdown(). "
            "Try updating docling or use the JSON/text export."
        )

    md = doc.export_to_markdown()
    out_path.write_text(md, encoding="utf-8")
    print(f"Wrote: {out_path}")
    return 0


def cmd_extract_text(args: argparse.Namespace) -> int:
    pdf_path = _pick_pdf(args.pdf)
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    out_path = Path(args.out) if args.out else (OUT_DIR / f"{pdf_path.stem}.txt")

    from docling.document_converter import DocumentConverter

    converter = DocumentConverter()
    result = converter.convert(str(pdf_path))
    doc = result.document

    if hasattr(doc, "export_to_text"):
        text = doc.export_to_text()
    elif hasattr(doc, "export_to_markdown"):
        text = doc.export_to_markdown()
    else:
        text = str(doc)

    out_path.write_text(text, encoding="utf-8")
    print(f"Wrote: {out_path}")
    return 0


def cmd_move_page(args: argparse.Namespace) -> int:
    pdf_path = _pick_pdf(args.pdf)
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    from pypdf import PdfReader, PdfWriter

    reader = PdfReader(str(pdf_path))
    page_count = len(reader.pages)

    if args.page < 1 or args.page > page_count:
        raise SystemExit(f"--page must be 1..{page_count} (got {args.page})")

    from_index = args.page - 1
    order = [i for i in range(page_count) if i != from_index]

    if args.to == "end":
        order.append(from_index)
        dest_label = "end"
    else:
        if args.to < 1 or args.to > page_count:
            raise SystemExit(f"--to must be 1..{page_count} or 'end' (got {args.to})")

        # Insert before the target position (1-based). After removing the source
        # page, the valid insertion range is 1..page_count.
        insert_at = args.to - 1
        if insert_at < 0:
            insert_at = 0
        if insert_at > len(order):
            insert_at = len(order)

        order.insert(insert_at, from_index)
        dest_label = str(args.to)

    out_path = (
        Path(args.out)
        if args.out
        else (OUT_DIR / f"{pdf_path.stem}__move_p{args.page}_to_{dest_label}.pdf")
    )

    writer = PdfWriter()
    for i in order:
        writer.add_page(reader.pages[i])

    try:
        if reader.metadata:
            writer.add_metadata(reader.metadata)
    except Exception:
        pass

    with open(out_path, "wb") as f:
        writer.write(f)

    print(f"Wrote: {out_path}")
    return 0


def cmd_crop(args: argparse.Namespace) -> int:
    pdf_path = _pick_pdf(args.pdf)
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    from pypdf import PdfReader, PdfWriter

    reader = PdfReader(str(pdf_path))
    page_count = len(reader.pages)

    if args.bottom_px <= 0:
        raise SystemExit("--bottom-px must be > 0")

    # Convert pixels to PDF points (1 inch = 72 points). Default assumes 96 DPI.
    # points = px * 72 / dpi
    delta_pts = float(args.bottom_px) * 72.0 / float(args.dpi)

    pages_to_crop: set[int]
    if args.pages:
        pages_to_crop = set()
        for part in args.pages.split(","):
            part = part.strip()
            if not part:
                continue
            if "-" in part:
                a_s, b_s = part.split("-", 1)
                a = int(a_s)
                b = int(b_s)
                for p in range(min(a, b), max(a, b) + 1):
                    pages_to_crop.add(p)
            else:
                pages_to_crop.add(int(part))

        for p in sorted(pages_to_crop):
            if p < 1 or p > page_count:
                raise SystemExit(f"--pages contains out-of-range page {p} (1..{page_count})")
    else:
        pages_to_crop = set(range(1, page_count + 1))

    out_path = (
        Path(args.out)
        if args.out
        else (OUT_DIR / f"{pdf_path.stem}__crop_bottom_{args.bottom_px}px.pdf")
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)

    writer = PdfWriter()
    for i, page in enumerate(reader.pages, start=1):
        if i in pages_to_crop:
            # CropBox defaults to MediaBox if not explicitly set.
            crop = page.cropbox
            x0, y0 = float(crop.left), float(crop.bottom)
            x1, y1 = float(crop.right), float(crop.top)
            new_y0 = min(y1, y0 + delta_pts)
            page.cropbox.lower_left = (x0, new_y0)
            page.cropbox.upper_right = (x1, y1)

        writer.add_page(page)

    try:
        if reader.metadata:
            writer.add_metadata(reader.metadata)
    except Exception:
        pass

    with open(out_path, "wb") as f:
        writer.write(f)

    print(f"Wrote: {out_path}")
    print(f"Cropped bottom by ~{delta_pts:.2f} points ({args.bottom_px}px @ {args.dpi}dpi)")
    return 0


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        prog="pdfctl",
        description="Agent-friendly PDF utilities for the pdf-autofiller workspace.",
    )

    sub = ap.add_subparsers(dest="cmd", required=True)

    p_list = sub.add_parser("list", help="List PDFs in inbox/")
    p_list.set_defaults(func=cmd_list)

    p_info = sub.add_parser("info", help="Show basic PDF info")
    p_info.add_argument("--pdf", help="PDF path (default: first PDF in inbox/)")
    p_info.add_argument(
        "--fields", action="store_true", help="Also print AcroForm field names"
    )
    p_info.set_defaults(func=cmd_info)

    p_grid = sub.add_parser("grid", help="Write a coordinate grid overlay PDF")
    p_grid.add_argument("--pdf", help="PDF path (default: first PDF in inbox/)")
    p_grid.add_argument("--out", help="Output PDF path (default: out/<stem>__grid.pdf)")
    p_grid.add_argument("--step", type=int, default=50, help="Grid spacing in points")
    p_grid.set_defaults(func=cmd_grid)

    p_md = sub.add_parser("extract-md", help="Extract Markdown using docling")
    p_md.add_argument("--pdf", help="PDF path (default: first PDF in inbox/)")
    p_md.add_argument("--out", help="Output .md path (default: out/<stem>.md)")
    p_md.set_defaults(func=cmd_extract_md)

    p_txt = sub.add_parser("extract-text", help="Extract text using docling")
    p_txt.add_argument("--pdf", help="PDF path (default: first PDF in inbox/)")
    p_txt.add_argument("--out", help="Output .txt path (default: out/<stem>.txt)")
    p_txt.set_defaults(func=cmd_extract_text)

    p_move = sub.add_parser("move-page", help="Move one page to a new position")
    p_move.add_argument("--pdf", help="PDF path (default: first PDF in inbox/)")
    p_move.add_argument(
        "--page",
        type=int,
        required=True,
        help="1-based page number to move (e.g., 7)",
    )
    p_move.add_argument(
        "--to",
        required=True,
        help="Destination: 'end' or a 1-based page position",
    )
    p_move.add_argument(
        "--out",
        help="Output PDF path (default: out/<stem>__move_pN_to_<dest>.pdf)",
    )
    p_move.set_defaults(func=cmd_move_page)

    p_crop = sub.add_parser("crop", help="Crop pages (non-destructive CropBox)")
    p_crop.add_argument("--pdf", help="PDF path or fuzzy name (default: first PDF in inbox/)")
    p_crop.add_argument(
        "--bottom-px",
        type=int,
        required=True,
        help="Pixels to trim from bottom (converted to points via --dpi)",
    )
    p_crop.add_argument(
        "--dpi",
        type=int,
        default=96,
        help="DPI used for px→points conversion (default: 96)",
    )
    p_crop.add_argument(
        "--pages",
        help="Pages to crop, e.g. '1,2,5-7' (default: all pages)",
    )
    p_crop.add_argument(
        "--out",
        help="Output PDF path (default: out/<stem>__crop_bottom_<px>px.pdf)",
    )
    p_crop.set_defaults(func=cmd_crop)

    return ap


def main() -> int:
    args = build_parser().parse_args()
    if args.cmd == "move-page" and isinstance(getattr(args, "to", None), str):
        if args.to != "end":
            try:
                args.to = int(args.to)
            except ValueError as exc:
                raise SystemExit("--to must be 'end' or an integer") from exc
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
