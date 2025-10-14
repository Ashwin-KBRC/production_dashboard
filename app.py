import streamlit as st
import pandas as pd
import os

# -----------------------------
# File Upload Section
# -----------------------------
uploaded_file = st.file_uploader("Upload Excel file", type=["xlsx", "csv"])

if uploaded_file:
    # Example: read uploaded file
    if uploaded_file.name.endswith(".csv"):
        df = pd.read_csv(uploaded_file)
    else:
        df = pd.read_excel(uploaded_file)

    # Optional: show preview
    st.dataframe(df.head())

    # Save to local folder
    save_path = f"data/{uploaded_file.name}"
    os.makedirs("data", exist_ok=True)
    df.to_csv(save_path, index=False)
    st.success(f"File saved to {save_path}")

    # -----------------------------
    # Rerun app safely
    # -----------------------------
    if st.button("Reload App to view updates"):
        st.experimental_rerun()
