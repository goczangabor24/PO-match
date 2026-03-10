import io
import zipfile
from pathlib import Path

import streamlit as st
from pypdf import PdfReader, PdfWriter


st.set_page_config(page_title="PDF First Page Extractor", page_icon="📄", layout="centered")

st.title("📄 PDF First Page Extractor")
st.write(
    "Upload one or more PDF files. The app will extract only the first page from each file and package the results into a ZIP for download."
)

uploaded_files = st.file_uploader(
    "Upload PDF files",
    type=["pdf"],
    accept_multiple_files=True,
)


def sanitize_name(filename: str) -> str:
    stem = Path(filename).stem
    safe = "".join(c if c.isalnum() or c in ("-", "_") else "_" for c in stem).strip("_")
    return safe or "document"


if uploaded_files:
    extracted_items: list[tuple[str, bytes]] = []
    skipped_files: list[str] = []

    with st.spinner("Processing PDFs..."):
        for uploaded_file in uploaded_files:
            try:
                pdf_bytes = uploaded_file.read()
                reader = PdfReader(io.BytesIO(pdf_bytes))

                if len(reader.pages) == 0:
                    skipped_files.append(f"{uploaded_file.name} (no pages)")
                    continue

                writer = PdfWriter()
                writer.add_page(reader.pages[0])

                output_buffer = io.BytesIO()
                writer.write(output_buffer)
                output_buffer.seek(0)

                output_name = f"{sanitize_name(uploaded_file.name)}_first_page.pdf"
                extracted_items.append((output_name, output_buffer.getvalue()))

            except Exception as e:
                skipped_files.append(f"{uploaded_file.name} ({e})")

    if extracted_items:
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
            for output_name, file_bytes in extracted_items:
                zf.writestr(output_name, file_bytes)

        zip_buffer.seek(0)

        st.success(f"Done. Extracted first pages from {len(extracted_items)} PDF file(s).")

        st.download_button(
            label="Download ZIP",
            data=zip_buffer.getvalue(),
            file_name="first_pages.zip",
            mime="application/zip",
        )

        with st.expander("Processed files"):
            for output_name, _ in extracted_items:
                st.write(f"- {output_name}")

    if skipped_files:
        st.warning("Some files could not be processed:")
        for item in skipped_files:
            st.write(f"- {item}")

else:
    st.info("Upload one or more PDF files to begin.")


st.caption("Requires: streamlit, pypdf")
