# Agent Context for pdf-autofiller
**Location:** Windows — `C:/Users/nymil/Codepro/pdf-autofiller/`
**Git boundary:** Windows repo (`main` branch)

## Tech Stack
- **Language:** Python 3
- **UI:** Streamlit (`ui_app.py`)
- **Core CLI:** `fill_pdf.py` — AcroForm overlay fill engine
- **Mapping tools:** `gen_map.py`, `make_mapping_skeleton.py`, `pdfctl.py`
- **Key deps:** `pypdf==4.2.0`, `reportlab==4.1.0`, `PyYAML`, `jsonschema`, `streamlit`
- **Schema validation:** `schema.json` — YAML mappings must conform

## Build Commands
- `pip install -r requirements.txt`
- **Run UI:** `streamlit run ui_app.py`
- **Run CLI:** `python fill_pdf.py --help`
- **Generate skeleton mapping for new PDF:** `python make_mapping_skeleton.py <pdf>`

## Test Command
- `python docling_smoke_test.py`

## Local Rules
- Input PDFs → `inbox/`; filled output → `out/`
- Form mappings live in `mappings/` as YAML — validate against `schema.json` before using
- **Do NOT commit filled PDFs** — they contain PII
- `profile.yaml` holds the user data profile — never commit real PII to git
