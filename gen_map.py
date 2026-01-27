#!/usr/bin/env python3
import argparse, os, sys, yaml
from dotenv import load_dotenv
def extract_text(pdf_path):
    try:
        from pypdf import PdfReader
    except Exception:
        print("Install pypdf first: pip install pypdf", file=sys.stderr)
        sys.exit(1)
    r = PdfReader(pdf_path)
    pages = []
    for i,p in enumerate(r.pages):
        try:
            text = p.extract_text() or ""
        except Exception:
            text = ""
        pages.append({"index": i, "text": text[:4000]})
    return pages
def load_profile(profile_path):
    import json
    with open(profile_path, "r", encoding="utf-8") as f:
        if profile_path.endswith(('.yaml','.yml')):
            return yaml.safe_load(f)
        return json.load(f)
PROMPT = """You are a PDF-to-profile mapping assistant.
Given:
- Profile keys (YAML-like structure) and sample values
- Extracted text from each PDF page (approximate labels)

Output a YAML mapping with this shape only:
fields:
  <semantic_key>:
    source: profile.<path>
    acro_field: "<pdf_field_name_if_known_else_empty>"
    overlay: {page: <int>, x: <guess>, y: <guess>}

Rules:
- Prefer acro_field if you can infer one; else leave empty.
- Provide overlay guesses (page 0 baseline; x 100–500; y 200–750).
- Use "={...}" inline template when concatenating multiple profile fields.
- Keep keys simple and consistent (e.g., full_name, work_phone).
"""
def main():
    load_dotenv()
    ap = argparse.ArgumentParser()
    ap.add_argument("--pdf", required=True)
    ap.add_argument("--profile", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--model", default=os.environ.get("OPENAI_MODEL", "gpt-4o-mini"))
    args = ap.parse_args()
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        print("Set OPENAI_API_KEY or pass via environment.", file=sys.stderr)
        sys.exit(1)
    profile = load_profile(args.profile)
    pages = extract_text(args.pdf)
    profile_preview = yaml.safe_dump(profile, sort_keys=False)[:4000]
    page_blobs = "\\n\\n".join([f"--- Page {p['index']} ---\\n{p['text']}" for p in pages])
    try:
        from openai import OpenAI
    except Exception:
        print("Install openai first: pip install openai", file=sys.stderr)
        sys.exit(1)
    client = OpenAI(api_key=api_key)
    msg = [
        {"role":"system","content":"You write only YAML mappings per instructions."},
        {"role":"user","content":PROMPT + f"\\n\\nPROFILE:\\n{profile_preview}\\n\\nPDF TEXT:\\n{page_blobs}\\n\\nReturn only YAML."}
    ]
    resp = client.chat.completions.create(model=args.model, messages=msg, temperature=0.2)
    yaml_text = resp.choices[0].message.content.strip()
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        f.write(yaml_text)
    print(f"Wrote mapping draft: {args.out}")
if __name__ == "__main__":
    main()
