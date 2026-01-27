#!/usr/bin/env python3
import argparse, json, os, re, sys
from typing import Any, Dict, Union
import yaml

def load_profile(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        if path.lower().endswith(".json"):
            import json
            return json.load(f)
        return yaml.safe_load(f)

def get_by_path(d: Dict[str, Any], path: str):
    cur = d
    token_re = re.compile(r"\.?([A-Za-z0-9_]+)(\[\d+\])?")
    for m in token_re.finditer(path):
        key = m.group(1)
        idx = m.group(2)
        if key:
            cur = cur.get(key, None) if isinstance(cur, dict) else None
        if cur is None:
            return None
        if idx:
            i = int(idx.strip("[]"))
            cur = cur[i] if isinstance(cur, list) and len(cur) > i else None
        if cur is None:
            return None
    return cur

def render_source(expr: Any, profile: Dict[str, Any]) -> Union[str, None]:
    """Render a mapping source value to a string, or None if not representable.

    Notes:
    - Strings beginning with "={...}" are formatted with Python's str.format and
      have access to the variable `profile` (e.g., "={profile['home']['city']}").
    - Strings beginning with "profile." dereference into the profile structure.
    - Dicts/Lists are skipped (return None) to avoid dumping raw objects onto the PDF.
    """
    # Simple scalar coercions
    if isinstance(expr, bool):
        return "Yes" if expr else "No"
    if isinstance(expr, (int, float)):
        return str(expr)

    # Template expression: "={...}"
    if isinstance(expr, str) and expr.startswith("={") and expr.endswith("}"):
        inner = expr[2:]
        try:
            return inner.format(profile=profile)
        except Exception:
            return None

    # profile.<path> dereference
    if isinstance(expr, str) and expr.startswith("profile."):
        val = get_by_path(profile, expr.replace("profile.", "", 1))
        # Skip complex structures by default; encourage explicit templates
        if isinstance(val, (dict, list)):
            return None
        return str(val) if val is not None else None

    # Skip complex objects; otherwise pass-through string
    if isinstance(expr, (dict, list)):
        return None
    return str(expr) if expr is not None else None

def fill_acroform(input_pdf: str, output_pdf: str, mapping: Dict[str, Any], profile: Dict[str, Any]) -> bool:
    """Fill AcroForm fields if present; returns True if anything was written.

    Uses PdfReader.get_fields() to discover available field names and updates
    values via PdfWriter.update_page_form_field_values.
    """
    try:
        from pypdf import PdfReader, PdfWriter
    except Exception:
        return False

    reader = PdfReader(input_pdf)
    writer = PdfWriter()
    writer.append_pages_from_reader(reader)

    # Discover available AcroForm fields from the reader (writer may not expose get_fields).
    try:
        available_fields = reader.get_fields() or {}
    except Exception:
        available_fields = {}

    wrote = False
    for _, cfg in (mapping.get("fields", {}) or {}).items():
        src = cfg.get("source")
        value = render_source(src, profile) if src is not None else ""
        acro = cfg.get("acro_field")
        if not acro or value is None:
            continue
        if available_fields and acro in available_fields:
            # Update all pages' form field values for this field name
            try:
                writer.update_page_form_field_values(writer.pages, {acro: str(value)})
                wrote = True
            except Exception:
                # Ignore and continue; we'll fall back to overlay
                pass

    if wrote:
        # Best-effort flatten: mark fields as read-only to persist values broadly
        for page in writer.pages:
            if "/Annots" in page:
                for annot in page["/Annots"]:
                    obj = annot.get_object()
                    if obj.get("/FT") and obj.get("/T"):
                        obj.update({"/Ff": 1})
        with open(output_pdf, "wb") as out:
            writer.write(out)
        return True
    return False

def overlay_text(input_pdf: str, output_pdf: str, mapping: Dict[str, Any], profile: Dict[str, Any]):
    from pypdf import PdfReader, PdfWriter
    from reportlab.pdfgen import canvas
    reader = PdfReader(input_pdf)
    writer = PdfWriter()

    # Helper: normalize field names to aid fuzzy matching
    def _normalize_name(s: str) -> str:
        return re.sub(r"[^a-z0-9]", "", s.lower()) if isinstance(s, str) else ""

    # Pre-scan widget annotations to gather field rectangles per page
    field_positions: Dict[str, Dict[str, Any]] = {}
    try:
        for pi, page in enumerate(reader.pages):
            if "/Annots" not in page:
                continue
            for annot in page["/Annots"]:
                obj = annot.get_object()
                if obj.get("/Subtype") != "/Widget":
                    continue
                name = obj.get("/T")
                if not name:
                    parent = obj.get("/Parent")
                    if parent:
                        name = parent.get("/T")
                if not name:
                    continue
                rect = obj.get("/Rect")
                if not rect or len(rect) != 4:
                    continue
                x0, y0, x1, y1 = [float(v) for v in rect]
                area = max(0.0, (x1 - x0) * (y1 - y0))
                key = str(name)
                prev = field_positions.get(key)
                if not prev or area > prev.get("area", 0):
                    field_positions[key] = {
                        "page": pi,
                        "rect": (x0, y0, x1, y1),
                        "area": area,
                        "norm": _normalize_name(key),
                    }
    except Exception:
        field_positions = {}

    norm_index = {v["norm"]: k for k, v in field_positions.items()}

    overlays = {}
    for i, page in enumerate(reader.pages):
        width = float(page.mediabox.width)
        height = float(page.mediabox.height)
        tmp_pdf = f"_overlay_page_{i}.pdf"
        c = canvas.Canvas(tmp_pdf, pagesize=(width, height))
        c.setFont("Helvetica", 9)
        for _, cfg in mapping.get("fields", {}).items():
            ov = cfg.get("overlay") or {}
            acro_name = cfg.get("acro_field")

            # Determine placement
            target_x: Union[float, None] = None
            target_y: Union[float, None] = None

            # 1) Explicit coordinates take priority
            if "x" in ov and "y" in ov:
                if int(ov.get("page", 0)) != i:
                    continue
                target_x = float(ov.get("x", 0))
                target_y = float(ov.get("y", 0))
            else:
                # 2) Auto placement using AcroForm widget rect
                chosen = None
                if acro_name and field_positions:
                    chosen = field_positions.get(acro_name)
                    if not chosen:
                        norm = _normalize_name(acro_name)
                        key = norm_index.get(norm)
                        if key:
                            chosen = field_positions.get(key)
                if chosen and chosen.get("page") == i:
                    x0, y0, x1, y1 = chosen["rect"]
                    inset_x = max(2.0, min(6.0, (x1 - x0) * 0.03))
                    inset_y = max(2.0, min(6.0, (y1 - y0) * 0.2))
                    target_x = x0 + inset_x
                    target_y = y0 + inset_y
                else:
                    # Respect explicit page filter if provided
                    if "page" in ov and int(ov.get("page", 0)) != i:
                        continue
                    # Without coords or a widget on this page, skip
                    if target_x is None or target_y is None:
                        continue

            src = cfg.get("source")
            value = render_source(src, profile) if src is not None else ""
            if value is None or str(value).strip() in ("", "None"):
                continue
            c.drawString(float(target_x), float(target_y), str(value))
        c.save()
        overlays[i] = tmp_pdf
    from pypdf import PdfReader as R2
    for i, page in enumerate(reader.pages):
        writer.add_page(page)
        if i in overlays:
            overlay_reader = R2(overlays[i])
            writer.pages[i].merge_page(overlay_reader.pages[0])
    with open(output_pdf, "wb") as out:
        writer.write(out)

def overlay_grid(input_pdf: str, output_pdf: str, step: int = 50):
    """Overlay a coordinate grid on each page to help calibrate x/y positions.

    Draws light grid lines every `step` points, darker every 100 points, and
    labels axes. Origin is bottom-left; units are PDF points (1/72 inch).
    """
    from pypdf import PdfReader, PdfWriter
    from reportlab.pdfgen import canvas
    from reportlab.lib.colors import Color, black, gray

    reader = PdfReader(input_pdf)
    writer = PdfWriter()
    tmp_paths = {}
    for i, page in enumerate(reader.pages):
        width = float(page.mediabox.width)
        height = float(page.mediabox.height)
        tmp_pdf = f"_grid_overlay_page_{i}.pdf"
        c = canvas.Canvas(tmp_pdf, pagesize=(width, height))

        # Draw grid lines
        for x in range(0, int(width) + 1, step):
            c.setStrokeColor(gray if x % 100 else black)
            c.setLineWidth(0.2 if x % 100 else 0.5)
            c.line(x, 0, x, height)
            if x % 100 == 0:
                c.setFont("Helvetica", 6)
                c.drawString(x + 2, 2, str(x))
        for y in range(0, int(height) + 1, step):
            c.setStrokeColor(gray if y % 100 else black)
            c.setLineWidth(0.2 if y % 100 else 0.5)
            c.line(0, y, width, y)
            if y % 100 == 0:
                c.setFont("Helvetica", 6)
                c.drawString(2, y + 2, str(y))

        # Title
        c.setFont("Helvetica-Bold", 8)
        c.drawString(6, height - 12, f"Grid: origin (0,0) bottom-left | page {i}")
        c.save()
        tmp_paths[i] = tmp_pdf

    from pypdf import PdfReader as R2
    for i, page in enumerate(reader.pages):
        writer.add_page(page)
        overlay_reader = R2(tmp_paths[i])
        writer.pages[i].merge_page(overlay_reader.pages[0])
    with open(output_pdf, "wb") as f:
        writer.write(f)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pdf", help="Input PDF to fill")
    ap.add_argument("--profile", required=True, help="profile.yaml|json")
    ap.add_argument("--map", dest="map_file", help="mapping yaml")
    ap.add_argument("--out", help="output PDF path")
    ap.add_argument("--validate", action="store_true")
    ap.add_argument("--grid-out", help="Write a coordinate grid overlay to this PDF and exit")
    args = ap.parse_args()
    # Grid generation mode (no filling performed)
    if args.grid_out and args.pdf:
        overlay_grid(args.pdf, args.grid_out)
        print(f"Wrote coordinate grid overlay: {args.grid_out}")
        return
    if args.validate and args.profile:
        try:
            import json, jsonschema
            schema_path = os.path.join(os.path.dirname(__file__), "schema.json")
            if os.path.exists(schema_path):
                with open(schema_path, "r", encoding="utf-8") as f: schema = json.load(f)
                with open(args.profile, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f) if args.profile.endswith((".yaml",".yml")) else json.load(f)
                jsonschema.validate(instance=data, schema=schema)
                print("Profile is valid against schema.json")
        except Exception as e:
            print(f"Validation error: {e}", file=sys.stderr)
            sys.exit(1)
        if not args.pdf and not args.map_file:
            return
    if not args.pdf or not args.map_file or not args.out:
        print("Missing required args. See --help", file=sys.stderr)
        sys.exit(2)
    profile = load_profile(args.profile)
    import yaml as _y
    mapping = _y.safe_load(open(args.map_file, "r", encoding="utf-8"))
    wrote = fill_acroform(args.pdf, args.out, mapping, profile)
    if not wrote:
        overlay_text(args.pdf, args.out, mapping, profile)
        print(f"Overlay mode wrote: {args.out}")
    else:
        print(f"AcroForm mode wrote: {args.out}")

if __name__ == "__main__":
    main()
