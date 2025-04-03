
import streamlit as st
import re
import json
from io import StringIO
import docx2txt
import pdfplumber
import os
from datetime import datetime
import shutil

st.title("Mental Health Dataset Creator - Alpha Prototype")
st.write("Upload raw text files to anonymize and structure into prompt/response format for AI training.")

STORAGE_DIR = "saved_datasets"
BACKUP_DIR = "backup_datasets"
VERSION_DIR = "versioned_datasets"
VERSION_LABELS_FILE = "version_labels.json"
os.makedirs(STORAGE_DIR, exist_ok=True)
os.makedirs(BACKUP_DIR, exist_ok=True)
os.makedirs(VERSION_DIR, exist_ok=True)

if os.path.exists(VERSION_LABELS_FILE):
    with open(VERSION_LABELS_FILE, "r") as f:
        version_labels = json.load(f)
else:
    version_labels = {}

uploaded_file = st.file_uploader("Upload a .txt, .pdf, or .docx file", type=["txt", "pdf", "docx"])
tag_input = st.text_input("Enter a custom tag for this dataset (e.g., grief, trauma, CBT):", value="mental_health")

def scrub_text(text):
    text = re.sub(r"\b[A-Z][a-z]+\s[A-Z][a-z]+\b", "[REDACTED_NAME]", text)
    text = re.sub(r"\d{1,2}/\d{1,2}/\d{2,4}", "[REDACTED_DATE]", text)
    text = re.sub(r"\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}", "[REDACTED_PHONE]", text)
    text = re.sub(r"[\w.-]+@[\w.-]+", "[REDACTED_EMAIL]", text)
    return text

def segment_into_pairs(text, tag):
    paragraphs = [p.strip() for p in text.split("\n") if p.strip() != ""]
    dataset = []
    for i in range(0, len(paragraphs)-1, 2):
        dataset.append({"prompt": paragraphs[i], "response": paragraphs[i+1], "tag": tag})
    return dataset

def extract_text(file):
    if file.type == "text/plain":
        return StringIO(file.getvalue().decode("utf-8")).read()
    elif file.type == "application/pdf":
        with pdfplumber.open(file) as pdf:
            return "\n".join(page.extract_text() for page in pdf.pages if page.extract_text())
    elif file.type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
        return docx2txt.process(file)
    return ""

def highlight(text, word):
    return text.replace(word, f"**:orange[{word}]**") if word else text

if uploaded_file:
    raw_text = extract_text(uploaded_file)
    scrubbed = scrub_text(raw_text)
    pairs = segment_into_pairs(scrubbed, tag_input)

    st.subheader("Preview (First 3 Entries)")
    for entry in pairs[:3]:
        st.json(entry)

    jsonl_data = "\n".join([json.dumps(p) for p in pairs])
    filename_base = f"{tag_input.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    filename = f"{filename_base}.jsonl"
    local_path = os.path.join(STORAGE_DIR, filename)

    with open(local_path, "w", encoding="utf-8") as f:
        f.write(jsonl_data)

    version_path = os.path.join(VERSION_DIR, filename)
    shutil.copy(local_path, version_path)

    version_label = st.text_input("Label this version (e.g., 'v1 baseline', 'v2 with emotion tags'):")
    if version_label:
        version_labels[filename] = version_label
        with open(VERSION_LABELS_FILE, "w") as f:
            json.dump(version_labels, f, indent=2)
        st.success(f"Version labeled: {version_label}")

    st.download_button("Download JSONL Dataset", data=jsonl_data, file_name=filename, mime="text/plain")

st.subheader("Compare Two Versions by Keyword, Tag, and View Stats")
versioned_files = sorted(os.listdir(VERSION_DIR), reverse=True)
if len(versioned_files) >= 2:
    v1 = st.selectbox("Select first version:", versioned_files, key="v1")
    v2 = st.selectbox("Select second version:", versioned_files, key="v2")
    keyword = st.text_input("Enter a keyword to search in both versions:").lower()
    tag_filter = st.text_input("Optional: Filter by tag (e.g., CBT, trauma, grief):").lower()

    if v1 != v2 and keyword:
        with open(os.path.join(VERSION_DIR, v1), "r", encoding="utf-8") as f1, open(os.path.join(VERSION_DIR, v2), "r", encoding="utf-8") as f2:
            data1 = [json.loads(line) for line in f1.readlines()]
            data2 = [json.loads(line) for line in f2.readlines()]

        matches1 = [entry for entry in data1 if (keyword in entry['prompt'].lower() or keyword in entry['response'].lower()) and (tag_filter in entry['tag'].lower() if tag_filter else True)]
        matches2 = [entry for entry in data2 if (keyword in entry['prompt'].lower() or keyword in entry['response'].lower()) and (tag_filter in entry['tag'].lower() if tag_filter else True)]

        st.write(f"### Summary Stats")
        st.write(f"- Matches in {v1}: {len(matches1)}")
        st.write(f"- Matches in {v2}: {len(matches2)}")
        st.write(f"- Total combined matches: {len(matches1) + len(matches2)}")

        st.write(f"**Matches in {v1} - {version_labels.get(v1, 'Unlabeled')}**")
        for entry in matches1:
            st.markdown(f"- **Prompt**: {highlight(entry['prompt'], keyword)}")
            st.markdown(f"- **Response**: {highlight(entry['response'], keyword)}")
            st.markdown(f"- **Tag**: *{entry['tag']}*")
            st.markdown("---")

        st.write(f"**Matches in {v2} - {version_labels.get(v2, 'Unlabeled')}**")
        for entry in matches2:
            st.markdown(f"- **Prompt**: {highlight(entry['prompt'], keyword)}")
            st.markdown(f"- **Response**: {highlight(entry['response'], keyword)}")
            st.markdown(f"- **Tag**: *{entry['tag']}*")
            st.markdown("---")

        combined = matches1 + matches2
        if combined:
            comparison_filename = f"comparison_{v1[:10]}_vs_{v2[:10]}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jsonl"
            comparison_data = "\n".join([json.dumps(p) for p in combined])
            st.download_button("Download All Matching Entries", data=comparison_data, file_name=comparison_filename, mime="text/plain")
