import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import pandas as pd
import json
import os

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
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]

    # Load and parse the JSON string
    creds_data = st.secrets["google_sheets_credentials"]
    credentials_dict = json.loads(creds_data)

    # Authenticate
    creds = ServiceAccountCredentials.from_json_keyfile_dict(credentials_dict, scope)
    client = gspread.authorize(creds)

    # Read spreadsheet
    sheet = client.open("Copy of Job & Reciept Full Data").worksheet("Target")
    data = sheet.get_all_values()


    df = pd.DataFrame(data[1:], columns=data[0])
    df["EMAIL"] = df.iloc[:, 10].astype(str).str.strip().str.lower()
    df["PASSWORD"] = df.iloc[:, 11].astype(str).str.strip()

    return any(
        (df["EMAIL"] == email.strip().lower()) &
        (df["PASSWORD"] == password.strip())
    )