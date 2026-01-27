import streamlit as st
import subprocess, tempfile, os, yaml

st.title("PDF Auto-Fill (Profile → Mapping → Filled PDF)")

profile_file = st.file_uploader("Profile (YAML/JSON)", type=["yaml","yml","json"])
mapping_file = st.file_uploader("Mapping YAML", type=["yaml","yml"])
pdf_file = st.file_uploader("PDF to fill", type=["pdf"])

out_name = st.text_input("Output filename", value="filled.pdf")

if st.button("Fill PDF", type="primary"):
    if not (profile_file and mapping_file and pdf_file):
        st.error("Please provide profile, mapping, and PDF.")
    else:
        with tempfile.TemporaryDirectory() as td:
            p_path = os.path.join(td, profile_file.name); open(p_path,"wb").write(profile_file.read())
            m_path = os.path.join(td, mapping_file.name); open(m_path,"wb").write(mapping_file.read())
            pdf_path = os.path.join(td, pdf_file.name); open(pdf_path,"wb").write(pdf_file.read())
            out_path = os.path.join(td, out_name)
            cmd = ["python","fill_pdf.py","--pdf", pdf_path,"--profile", p_path,"--map", m_path,"--out", out_path]
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode == 0 and os.path.exists(out_path):
                st.success("Done.")
                with open(out_path,"rb") as f:
                    st.download_button("Download filled PDF", f, file_name=out_name, mime="application/pdf")
            else:
                st.error("Error running fill. See logs below.")
                st.code(result.stdout + "\n" + result.stderr)
