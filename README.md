# PDF Auto-Fill Pro Kit (Profile → Any PDF)

## Put this whole folder at your **repo root**

```
.
├─ .github/workflows/autofill.yml          # CI auto-fill on push
├─ .devcontainer/devcontainer.json         # Codespaces: zero-install
├─ fill_pdf.py                             # Core CLI (AcroForm → overlay)
├─ make_mapping_skeleton.py                # New form starter mapping
├─ gen_map.py                              # (Optional) LLM-assisted mapping draft
├─ ui_app.py                               # (Optional) Streamlit drag-and-drop
├─ requirements.txt
├─ profile.yaml
├─ mappings/
│  └─ agsc_1b_e.yaml
├─ inbox/                                  # Drop PDFs here
│  └─ .gitkeep
└─ out/                                    # Filled PDFs land here
   └─ .gitkeep
```

### Quick start

```bash
pip install -r requirements.txt
python fill_pdf.py --pdf "AGSC 1B-E.pdf" --profile profile.yaml --map mappings/agsc_1b_e.yaml --out out/AGSC_1B-E_filled.pdf
```

### Drop-a-PDF workflow (agent-friendly)

1. Put PDFs in `inbox/`
2. Use `pdfctl.py` to inspect/extract outputs into `out/`

```bash
python pdfctl.py list
python pdfctl.py info --pdf inbox/YourFile.pdf --fields
python pdfctl.py extract-md --pdf inbox/YourFile.pdf
python pdfctl.py extract-text --pdf inbox/YourFile.pdf
python pdfctl.py grid --pdf inbox/YourFile.pdf
```

### Codespaces

Open in Codespaces → dependencies auto-install → run the same command above.

### CI (GitHub Actions)

Commit a PDF to `inbox/` and ensure a mapping with the same stem in `mappings/`. The action writes results to `out/` artifact.

### UI (optional)

```bash
streamlit run ui_app.py
```

### LLM mapping (optional)

Copy `.env.example` to `.env` and set your `OPENAI_API_KEY`, then:

```bash
python gen_map.py --pdf NewForm.pdf --profile profile.yaml --out mappings/newform.yaml
```
