from __future__ import annotations

from pathlib import Path


def main() -> int:
    try:
        from docling.document_converter import DocumentConverter
    except Exception as exc:  # noqa: BLE001
        print(f"Docling import failed: {exc}")
        return 1

    inbox = Path(__file__).parent / "inbox"
    print(f"Inbox: {inbox}")
    print(f"Inbox exists: {inbox.exists()}")

    pdfs = sorted(inbox.glob("*.pdf"))
    print(f"PDF count in inbox: {len(pdfs)}")

    if not pdfs:
        print("Drop a PDF into pdf-autofiller/inbox and re-run.")
        return 0

    pdf_path = pdfs[0]
    print(f"Converting: {pdf_path}")

    converter = DocumentConverter()
    result = converter.convert(str(pdf_path))
    doc = result.document

    # Docling exposes different export helpers depending on version.
    export_methods = [m for m in dir(doc) if m.startswith("export_")]
    print(f"Available export methods: {export_methods}")

    if hasattr(doc, "export_to_markdown"):
        md = doc.export_to_markdown()
        print(f"Markdown chars: {len(md)}")
        print(md[:800])
    elif hasattr(doc, "export_to_text"):
        txt = doc.export_to_text()
        print(f"Text chars: {len(txt)}")
        print(txt[:800])
    else:
        print(f"Converted document type: {type(doc)}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
