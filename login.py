import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import pandas as pd

def login():
    st.sidebar.header("🔐 User Login")

    email_input = st.sidebar.text_input("Email")
    password_input = st.sidebar.text_input("Password", type="password")

    if st.sidebar.button("Login"):
        if authenticate_user(email_input, password_input):
            st.session_state["logged_in_user"] = email_input
            st.success("✅ Login successful!")
            return email_input
        else:
            st.error("❌ Invalid email or password.")
            return None
    else:
        return st.session_state.get("logged_in_user", None)


def authenticate_user(email, password):
    # Google Sheets connection
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_name("Credential.json", scope)
    client = gspread.authorize(creds)

    # Load raw values (skips header processing)
    sheet = client.open("Copy of Job & Reciept Full Data").worksheet("Target")
    data = sheet.get_all_values()

    # Convert to DataFrame without forcing header uniqueness
    df = pd.DataFrame(data[1:], columns=data[0])  # First row is header

    # Get email/password columns by index
    df["EMAIL"] = df.iloc[:, 10].astype(str).str.strip().str.lower()  # Column K
    df["PASSWORD"] = df.iloc[:, 11].astype(str).str.strip()           # Column L

    # Authentication check
    return any(
        (df["EMAIL"] == email.strip().lower()) &
        (df["PASSWORD"] == password.strip())
    )


