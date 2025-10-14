import streamlit as st
import subprocess
from pathlib import Path
import pandas as pd
import os

st.set_page_config(page_title="GitHub Push Test", layout="centered", page_icon="🔧")

st.title("🔧 GitHub Push Test")

# --- Load secrets (from Streamlit Secrets or environment)
try:
    GITHUB_TOKEN = st.secrets["GITHUB_TOKEN"]
    GITHUB_REPO = st.secrets["GITHUB_REPO"]
    GITHUB_USER = st.secrets["GITHUB_USER"]
    GITHUB_EMAIL = st.secrets["GITHUB_EMAIL"]
except Exception as e:
    st.error(f"Missing secrets: {e}")
    st.stop()

# --- Show what was read
if st.checkbox("Show loaded secrets"):
    st.write("GITHUB_REPO:", GITHUB_REPO)
    st.write("GITHUB_USER:", GITHUB_USER)
    st.write("GITHUB_EMAIL:", GITHUB_EMAIL)
    st.write("Token length:", len(GITHUB_TOKEN) if GITHUB_TOKEN else "❌ Missing")

# --- Create a dummy CSV to test
test_path = Path("data/test_push.csv")
test_path.parent.mkdir(exist_ok=True)
df = pd.DataFrame({"Plant": ["A", "B", "C"], "Production": [10, 20, 30]})
df.to_csv(test_path, index=False)

st.write("📄 Created test file:", test_path)

# --- Git push logic
def attempt_git_push(file_path: Path, commit_message: str):
    remote = f"https://{GITHUB_TOKEN}@github.com/{GITHUB_REPO}.git"
    try:
        subprocess.run(["git", "config", "--global", "user.email", GITHUB_EMAIL], check=False)
        subprocess.run(["git", "config", "--global", "user.name", GITHUB_USER], check=False)
        subprocess.run(["git", "add", str(file_path)], check=True)
        commit = subprocess.run(["git", "commit", "-m", commit_message],
                                capture_output=True, text=True)
        if commit.returncode != 0:
            return False, f"Git commit failed: {commit.stderr or commit.stdout}"

        push = subprocess.run(["git", "push", remote, "main"],
                              capture_output=True, text=True)
        if push.returncode != 0:
            return False, f"Git push failed: {push.stderr or push.stdout}"

        return True, "✅ Successfully pushed to GitHub."
    except Exception as e:
        return False, f"Exception: {e}"

# --- Run the test
if st.button("🚀 Test GitHub Push"):
    ok, msg = attempt_git_push(test_path, "Test push from Streamlit")
    if ok:
        st.success(msg)
    else:
        st.error(msg)
