"""Initial Opposition Brief application."""

import streamlit as st

st.set_page_config(
    page_title="Opposition Brief",
    page_icon="⚽",
    layout="wide",
)

st.title("Opposition Brief")

st.write("Convert recent opponent event data into an evidence-linked match-preparation report.")

uploaded_files = st.file_uploader(
    "Upload opponent event CSV files",
    type=["csv"],
    accept_multiple_files=True,
)

left, right = st.columns(2)

with left:
    st.subheader("Project status")
    st.metric("Matches uploaded", len(uploaded_files))
    st.metric("Candidate findings", 0)

with right:
    st.subheader("Planned analyses")
    st.write("Progression routes")
    st.write("Possession losses and recoveries")
    st.write("Progressive player combinations")
    st.write("Supporting possession sequences")

st.info("The first milestone is one useful opposition report.")
