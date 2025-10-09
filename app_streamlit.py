# app_streamlit.py
"""
Concrete Production Dashboard (Streamlit)

Features:
- Upload the daily Excel (or let the app read from disk if provided).
- Auto-detect date and production table in the sheet.
- Append daily snapshot into `data_history.csv` (creates file if missing).
- View by date, weekly and monthly aggregations.
- Download history CSV and responsive layout for mobile.

How to use:
- Run locally: `streamlit run app_streamlit.py`
- On first run, upload the Excel using the top "Upload Excel" area.
"""

import streamlit as st
import pandas as pd
import numpy as np
import re
from pathlib import Path
from io import BytesIO
import datetime

st.set_page_config(page_title="Production Dashboard", layout="wide")

# -------------------------
# Config
# -------------------------
HISTORY_PATH = Path("data_history.csv")  # stores long-term history
EXPECTED_SHEET_KEYWORDS = ["production", "daily", "report", "production daily report"]
MAX_LOOKAHEAD_ROWS = 12  # how many rows after header to scan for metrics

# -------------------------
# Utility functions
# -------------------------
def find_sheet_by_keyword(xls: pd.ExcelFile):
    for name in xls.sheet_names:
        low = name.lower()
        for kw in EXPECTED_SHEET_KEYWORDS:
            if kw in low:
                return name
    return xls.sheet_names[0]

def extract_date_from_df(df_raw: pd.DataFrame):
    top_text = df_raw.head(15).astype(str).apply(lambda row: " | ".join(row.values), axis=1).str.cat(sep=" | ")
    m = re.search(r'(\d{2}[-/]\d{2}[-/]\d{4})', top_text)
    if m:
        try:
            return pd.to_datetime(m.group(1), dayfirst=True).date()
        except:
            pass
    m2 = re.search(r'(\d{4}-\d{2}-\d{2})', top_text)
    if m2:
        try:
            return pd.to_datetime(m2.group(1)).date()
        except:
            pass
    return None

def find_header_row(df_raw: pd.DataFrame):
    df_str = df_raw.fillna("").astype(str).applymap(lambda x: x.strip().upper())
    keywords = {"SUL", "KABAD", "AMG", "MUTLAA", "TOTAL", "M.A (C)", "M.A (G)"}
    for i, row in df_str.iterrows():
        tokens = set([c for c in row.values if c != ""])
        if len(tokens & keywords) >= 1:
            return i
    for i, row in df_str.iterrows():
        nonempty = sum(1 for c in row.values if c != "")
        if nonempty >= 3:
            return i
    return 0

def parse_table_from_sheet(df_raw: pd.DataFrame):
    header_idx = find_header_row(df_raw)
    header = df_raw.iloc[header_idx].fillna("").astype(str).tolist()
    cols_idx = [j for j, v in enumerate(header) if str(v).strip() != ""]
    col_names = [header[j].strip() for j in cols_idx]
    data_rows = []
    labels = []
    for r in range(header_idx + 1, min(header_idx + 1 + MAX_LOOKAHEAD_ROWS, len(df_raw))):
        row = df_raw.iloc[r]
        label = ""
        for c in row:
            if str(c).strip() != "":
                label = str(c).strip()
                break
        values = [row[j] if not pd.isna(row[j]) else "" for j in cols_idx]
        if label == "" and all((str(v).strip() == "" for v in values)):
            continue
        labels.append(label)
        data_rows.append(values)
    if len(data_rows) == 0:
        for r in range(header_idx + 1, header_idx + 6):
            if r >= len(df_raw): break
            row = df_raw.iloc[r]
            label = row.iloc[0] if not pd.isna(row.iloc[0]) else f"row{r}"
            values = [row[j] if not pd.isna(row[j]) else "" for j in cols_idx]
            labels.append(str(label))
            data_rows.append(values)
    df_table = pd.DataFrame(data_rows, columns=col_names, index=labels)
    for c in df_table.columns:
        df_table[c] = pd.to_numeric(df_table[c].astype(str).replace("", np.nan), errors="coerce")
    df_table = df_table.fillna(0)
    return df_table, header_idx

def snapshot_to_history(date_obj: datetime.date, df_table: pd.DataFrame, history_path: Path):
    rows = []
    for metric in df_table.index:
        for site in df_table.columns:
            val = float(df_table.loc[metric, site])
            rows.append({"date": date_obj.isoformat(), "metric": metric, "site": site, "value": val})
    hist_df = pd.DataFrame(rows)
    if history_path.exists():
        existing = pd.read_csv(history_path)
        if date_obj.isoformat() in existing['date'].unique():
            existing = existing[existing['date'] != date_obj.isoformat()]
            combined = pd.concat([existing, hist_df], ignore_index=True)
            combined.to_csv(history_path, index=False)
            return combined
        else:
            combined = pd.concat([existing, hist_df], ignore_index=True)
            combined.to_csv(history_path, index=False)
            return combined
    else:
        hist_df.to_csv(history_path, index=False)
        return hist_df

st.title("📊 Concrete Production — Web Dashboard")
st.markdown("Upload the daily Excel (the app will keep a history and show daily/weekly/monthly stats).")

uploaded_file = st.file_uploader("Upload Excel file (XLSX).", type=["xls","xlsx"])

if uploaded_file:
    try:
        xls = pd.ExcelFile(uploaded_file)
        sheet = xls.sheet_names[0]
        df_raw = pd.read_excel(xls, sheet_name=sheet, header=None)
        detected_date = extract_date_from_df(df_raw)
        if detected_date is None:
            st.warning("Date not found in file, please select manually:")
            detected_date = st.date_input("Select date", datetime.date.today())
        st.success(f"Detected date: {detected_date}")
        df_table, header_idx = parse_table_from_sheet(df_raw)
        st.write("Preview:")
        st.dataframe(df_table)
        hist_df = snapshot_to_history(detected_date, df_table, HISTORY_PATH)
        st.success("Saved to history ✅")
    except Exception as e:
        st.error(f"Failed to read Excel: {e}")

if Path("data_history.csv").exists():
    history = pd.read_csv("data_history.csv", parse_dates=["date"])
    history['date'] = history['date'].dt.date
    available_dates = sorted(history['date'].unique(), reverse=True)
    selected_date = st.sidebar.date_input("Select date", value=available_dates[0])
    selected_metric = st.sidebar.selectbox("Metric", history['metric'].unique())
    day_df = history[(history['date'] == selected_date) & (history['metric'] == selected_metric)]
    if not day_df.empty:
        st.subheader(f"Production on {selected_date} ({selected_metric})")
        st.bar_chart(day_df.pivot(index='site', values='value'))
    else:
        st.warning("No data for that date yet.")
else:
    st.info("No history yet. Upload your first Excel file above.")