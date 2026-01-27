#!/usr/bin/env python3
import argparse, os, sys, yaml
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pdf", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    try:
        from pypdf import PdfReader
    except Exception:
        print("Install pypdf first: pip install pypdf", file=sys.stderr)
        sys.exit(1)
    reader = PdfReader(args.pdf)
    skeleton = {"fields": {}}
    fields = {}
    try:
        fields = reader.get_fields() or {}
    except Exception:
        fields = {}
    if fields:
        for k in fields.keys():
            safe = k.replace(" ", "_")
            skeleton["fields"][safe] = {
                "source": "profile.<put_key_here>",
                "acro_field": k,
                "overlay": {"page": 0, "x": 50, "y": 700}
            }
    with open(args.out, "w", encoding="utf-8") as f:
        yaml.safe_dump(skeleton, f, sort_keys=False)
    print(f"Wrote skeleton: {args.out}")
if __name__ == "__main__":
    main()
