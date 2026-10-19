import streamlit as st
import sqlite3
import pandas as pd
import io
import os
import json
import urllib.parse
import smtplib
from email.message import EmailMessage
from datetime import datetime, date, time, timedelta
from fpdf import FPDF

# Optional Google Drive API imports
try:
    from google.oauth2 import service_account
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaIoBaseUpload
    GDRIVE_AVAILABLE = True
except ImportError:
    GDRIVE_AVAILABLE = False

# ==============================================================================
# 1. PAGE CONFIGURATION & CUSTOM LOGIN CSS
# ==============================================================================
st.set_page_config(
    page_title="The aLGeBrA Playhouse",
    page_icon="🏛️",
    layout="wide",
    initial_sidebar_state="collapsed"
)

st.markdown("""
<style>
    /* Force Times New Roman across the app */
    html, body, [class*="css"], div, p, span, h1, h2, h3, h4, h5, h6, label, input, button, select, table, th, td {
        font-family: 'Times New Roman', Times, serif !important;
    }

    /* Hide default sidebar */
    [data-testid="collapsedControl"] { display: none; }
    section[data-testid="stSidebar"] { display: none; }

    .block-container {
        padding-top: 1rem;
        padding-bottom: 2rem;
        max-width: 1180px;
    }

    /* EXACT LOGIN SCREEN STYLING MATCHING REFERENCE IMAGE */
    .login-page-bg {
        background: linear-gradient(135deg, #1e3a4c 0%, #11222c 100%);
        min-height: 100vh;
        display: flex;
        align-items: center;
        justify-content: center;
        padding: 40px 20px;
    }
    .login-container {
        max-width: 420px;
        width: 100%;
        margin: 0 auto;
        text-align: center;
    }
    .login-title {
        color: #d1d5db;
        font-size: 1.6rem;
        letter-spacing: 3px;
        margin-bottom: 24px;
        font-weight: 400;
        text-transform: uppercase;
    }
    .login-box {
        background-color: #15222b;
        border: 1px solid #1f3340;
        border-radius: 4px;
        padding: 36px 32px;
        box-shadow: 0 10px 25px rgba(0,0,0,0.5);
        text-align: left;
    }
    .login-box label {
        color: #9ca3af !important;
        font-size: 0.9rem;
    }
    .stTextInput input {
        background-color: #e5e7eb !important;
        color: #111827 !important;
        border-radius: 2px !important;
        border: none !important;
        padding: 10px 14px !important;
    }
    .login-btn button {
        background-color: #4b6b7a !important;
        color: #ffffff !important;
        border: none !important;
        border-radius: 2px !important;
        width: 100% !important;
        padding: 12px !important;
        font-size: 1.05rem;
        letter-spacing: 1px;
        text-transform: uppercase;
        font-weight: bold;
        margin-top: 10px;
    }
    .login-btn button:hover {
        background-color: #3b5561 !important;
    }
    .register-btn button {
        background-color: #101a21 !important;
        color: #ffffff !important;
        border: 1px solid #233844 !important;
        border-radius: 2px !important;
        width: 100% !important;
        padding: 12px !important;
        font-size: 1rem;
        letter-spacing: 1px;
        text-transform: uppercase;
        margin-top: 16px;
    }
    .register-btn button:hover {
        background-color: #15222b !important;
    }

    /* Pure White Formal Cash Bill */
    .white-bill {
        background-color: #ffffff;
        color: #000000;
        padding: 24px;
        border: 1.5px solid #000000;
        border-radius: 4px;
        box-shadow: 0 2px 6px rgba(0,0,0,0.06);
    }
    .white-bill h2, .white-bill h3, .white-bill h4, .white-bill p {
        margin: 2px 0;
        color: #000000;
    }
    .bill-divider {
        border-top: 1px solid #000000;
        margin: 10px 0;
    }

    /* Monthly Membership Theme */
    .member-zone {
        background-color: #f8fafc;
        border: 2px solid #1e3a8a;
        border-radius: 6px;
        padding: 18px;
        margin-bottom: 16px;
    }
    .member-header {
        background-color: #1e3a8a;
        color: #ffffff !important;
        padding: 14px 18px;
        border-radius: 6px;
        margin-bottom: 14px;
    }

    .action-btn {
        display: block;
        width: 100%;
        text-align: center;
        padding: 10px 14px;
        border-radius: 4px;
        font-weight: bold;
        text-decoration: none !important;
        margin-top: 8px;
        font-size: 1rem;
    }
    .wa-btn {
        background-color: #15803d;
        color: #ffffff !important;
        border: 1px solid #14532d;
    }
    .sms-btn {
        background-color: #1d4ed8;
        color: #ffffff !important;
        border: 1px solid #1e3a8a;
    }
</style>
""", unsafe_allow_html=True)

# ==============================================================================
# 2. BUSINESS DETAILS & RATE CARD
# ==============================================================================
ENTERPRISE_TITLE = "The aLGeBrA Playhouse"
ENTERPRISE_SUBTITLE = "JEYHUMRUTH"
ENTERPRISE_ADDRESS = "No.32/27, 27th Street, Thillai Ganga Nagar, Chennai - 600 061."
ENTERPRISE_GST = "33AAVFJ5819R1ZD"
OFFICIAL_EMAIL = "thealgebraplayhouse@gmail.com"
OFFICIAL_PHONE = "9345611235"

RATES = {
    "Full House (Weekday)": 600,
    "Full House (Weekend / Holiday)": 650,
    "Soft Play (Weekday)": 350,
    "Soft Play (Weekend / Holiday)": 400,
    "Toddler Play (Weekday)": 500,
    "Toddler Play (Weekend / Holiday)": 550,
    "Day Pass (Unlimited)": 1450,
    "Weekend Pass (Unlimited)": 4250,
    "Monthly Membership": 5899,
}

# ==============================================================================
# 3. DATABASE INITIALIZATION
# ==============================================================================
DB_FILE = "algebra_playhouse_v4.db"

def get_conn():
    return sqlite3.connect(DB_FILE, check_same_thread=False)

def init_db():
    conn = get_conn()
    c = conn.cursor()

    c.execute('''CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY,
        value TEXT
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS users (
        emp_id TEXT PRIMARY KEY,
        name TEXT,
        email TEXT,
        password TEXT,
        role TEXT
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS transactions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        sno INTEGER,
        customer_id TEXT,
        bill_date TEXT,
        created_at TEXT,
        emp_id TEXT,
        emp_name TEXT,
        adult_name TEXT,
        phone TEXT,
        package TEXT,
        num_kids INTEGER,
        num_socks INTEGER,
        socks_gst_pct REAL,
        num_water INTEGER,
        water_gst_pct REAL,
        time_in TEXT,
        time_out TEXT,
        payment_method TEXT,
        pkg_excl_gst REAL,
        socks_excl_gst REAL,
        water_excl_gst REAL,
        sgst_9 REAL,
        cgst_9 REAL,
        water_gst_amt REAL,
        total_excl_gst REAL,
        total_gst REAL,
        subtotal_incl_gst REAL,
        card_fee REAL,
        final_total REAL,
        invoice_filename TEXT,
        is_closed INTEGER DEFAULT 0
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS members (
        member_id TEXT PRIMARY KEY,
        child_name TEXT,
        adult_name TEXT,
        phone TEXT,
        start_date TEXT,
        expiry_date TEXT,
        notes TEXT,
        created_by TEXT
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS member_visits (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        member_id TEXT,
        child_name TEXT,
        adult_name TEXT,
        phone TEXT,
        visit_date TEXT,
        time_in TEXT,
        time_out TEXT,
        logged_by_id TEXT,
        logged_by_name TEXT,
        is_closed INTEGER DEFAULT 0
    )''')

    c.execute("SELECT * FROM users WHERE role='admin'")
    if not c.fetchone():
        c.execute('''INSERT INTO users (emp_id, name, email, password, role)
                     VALUES ('ADMIN01', 'Administrator', ?, 'admin123', 'admin')''', (OFFICIAL_EMAIL,))
    else:
        c.execute("UPDATE users SET email=? WHERE emp_id='ADMIN01'", (OFFICIAL_EMAIL,))

    default_settings = {
        "next_sno": "1079",
        "admin_email": OFFICIAL_EMAIL,
        "sender_phone": OFFICIAL_PHONE,
        "card_fee_base": "Including GST"
    }
    for k, v in default_settings.items():
        c.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", (k, v))

    conn.commit()
    conn.close()

init_db()

def get_setting(key, default=""):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT value FROM settings WHERE key=
