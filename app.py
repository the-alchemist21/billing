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
# 1. PAGE CONFIGURATION & TIMES NEW ROMAN PROFESSIONAL UI
# ==============================================================================
st.set_page_config(
    page_title="The aLGeBrA Playhouse",
    page_icon="🏛️",
    layout="wide",
    initial_sidebar_state="collapsed"
)

st.markdown("""
<style>
    /* Force Times New Roman across the entire app */
    html, body, [class*="css"], div, p, span, h1, h2, h3, h4, h5, h6, label, input, button, select, table, th, td {
        font-family: 'Times New Roman', Times, serif !important;
    }

    /* Hide sidebar completely for clean mobile & desktop top-tab experience */
    [data-testid="collapsedControl"] { display: none; }
    section[data-testid="stSidebar"] { display: none; }

    .block-container {
        padding-top: 1rem;
        padding-bottom: 2rem;
        max-width: 1180px;
    }

    /* Minimalist White Cards */
    .clean-card {
        background: #ffffff;
        border: 1px solid #d1d5db;
        border-radius: 6px;
        padding: 18px;
        margin-bottom: 14px;
    }

    /* Pure White Formal Cash Bill */
    .white-bill {
        background-color: #ffffff;
        color: #000000;
        padding: 24px;
        border: 1.5px solid #000000;
        border-radius: 4px;
        box-shadow: 0 2px 6px rgba(0,0,0,0.06);
        font-family: 'Times New Roman', Times, serif !important;
    }
    .white-bill h2, .white-bill h3, .white-bill h4, .white-bill p {
        margin: 2px 0;
        color: #000000;
    }
    .bill-divider {
        border-top: 1px solid #000000;
        margin: 10px 0;
    }

    /* Distinct Monthly Membership Theme (Navy/Executive Border) */
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

    /* Action Buttons for WhatsApp & SMS */
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
DB_FILE = "algebra_playhouse_v3.db"

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

    # Ensure Admin exists with Official Email and ID 'ADMIN01'
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
    c.execute("SELECT value FROM settings WHERE key=?", (key,))
    row = c.fetchone()
    conn.close()
    return row[0] if row else default

def set_setting(key, val):
    conn = get_conn()
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, str(val)))
    conn.commit()
    conn.close()

# ==============================================================================
# 4. WHITE PDF INVOICE GENERATOR (TIMES NEW ROMAN) & CLOUD SYNC
# ==============================================================================
def generate_invoice_pdf_bytes(bill):
    pdf = FPDF(format=(105, 165))
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=8)

    pdf.set_font("Times", "B", 9)
    pdf.cell(45, 5, "CASH BILL", ln=0)
    pdf.cell(45, 5, f"GST No: {ENTERPRISE_GST}", ln=1, align="R")

    pdf.set_font("Times", "B", 14)
    pdf.cell(0, 6, ENTERPRISE_TITLE, ln=1, align="C")
    pdf.set_font("Times", "B", 9)
    pdf.cell(0, 4.5, ENTERPRISE_SUBTITLE, ln=1, align="C")
    pdf.set_font("Times", "", 8)
    pdf.multi_cell(0, 3.8, f"{ENTERPRISE_ADDRESS}\nPh: {OFFICIAL_PHONE} | {OFFICIAL_EMAIL}", align="C")
    pdf.ln(2)

    pdf.set_font("Times", "B", 8.5)
    pdf.cell(45, 4.5, f"S.No: {bill['sno']}", ln=0)
    pdf.cell(45, 4.5, f"Date: {bill['bill_date']}", ln=1, align="R")
    pdf.cell(45, 4.5, f"Cust ID: {bill['customer_id']}", ln=0)
    pdf.cell(45, 4.5, f"Time: {bill['time_in']} - {bill['time_out']}", ln=1, align="R")
    pdf.cell(0, 4.5, f"Name: {bill['adult_name']}  (Ph: {bill['phone']})", ln=1)

    pdf.line(10, pdf.get_y() + 1, 95, pdf.get_y() + 1)
    pdf.ln(2)

    pdf.set_font("Times", "B", 8.5)
    pdf.cell(44, 5, "DESCRIPTION", ln=0)
    pdf.cell(10, 5, "QTY", ln=0, align="C")
    pdf.cell(14, 5, "RATE", ln=0, align="R")
    pdf.cell(17, 5, "AMOUNT", ln=1, align="R")
    pdf.line(10, pdf.get_y(), 95, pdf.get_y())
    pdf.ln(1)

    pdf.set_font("Times", "", 8.5)
    pkg_label = "Group Combo" if bill["num_kids"] > 1 else bill["package"][:22]
    pdf.cell(44, 4.8, pkg_label, ln=0)
    pdf.cell(10, 4.8, str(bill["num_kids"]), ln=0, align="C")
    pdf.cell(14, 4.8, "-", ln=0, align="R")
    pdf.cell(17, 4.8, f"{bill['pkg_excl_gst']:.2f}", ln=1, align="R")

    if bill["num_socks"] > 0:
        pdf.cell(44, 4.8, "Socks", ln=0)
        pdf.cell(10, 4.8, str(bill["num_socks"]), ln=0, align="C")
        pdf.cell(14, 4.8, "-", ln=0, align="R")
        pdf.cell(17, 4.8, f"{bill['socks_excl_gst']:.2f}", ln=1, align="R")

    if bill["num_water"] > 0:
        pdf.cell(44, 4.8, "Water Bottle", ln=0)
        pdf.cell(10, 4.8, str(bill["num_water"]), ln=0, align="C")
        pdf.cell(14, 4.8, "-", ln=0, align="R")
        pdf.cell(17, 4.8, f"{bill['water_excl_gst']:.2f}", ln=1, align="R")

    pdf.ln(1)
    pdf.cell(44, 4.8, "SGST", ln=0)
    pdf.cell(10, 4.8, "", ln=0)
    pdf.cell(14, 4.8, "9%", ln=0, align="R")
    pdf.cell(17, 4.8, f"{bill['sgst_9']:.2f}", ln=1, align="R")

    pdf.cell(44, 4.8, "CGST", ln=0)
    pdf.cell(10, 4.8, "", ln=0)
    pdf.cell(14, 4.8, "9%", ln=0, align="R")
    pdf.cell(17, 4.8, f"{bill['cgst_9']:.2f}", ln=1, align="R")

    if bill["water_gst_amt"] > 0:
        pdf.cell(44, 4.8, "Water GST", ln=0)
        pdf.cell(10, 4.8, "", ln=0)
        pdf.cell(14, 4.8, f"{bill['water_gst_pct']:.0f}%", ln=0, align="R")
        pdf.cell(17, 4.8, f"{bill['water_gst_amt']:.2f}", ln=1, align="R")

    if bill["card_fee"] > 0:
        pdf.cell(44, 4.8, "Card Surcharge", ln=0)
        pdf.cell(10, 4.8, "", ln=0)
        pdf.cell(14, 4.8, "2%", ln=0, align="R")
        pdf.cell(17, 4.8, f"{bill['card_fee']:.2f}", ln=1, align="R")

    pdf.line(10, pdf.get_y() + 1, 95, pdf.get_y() + 1)
    pdf.ln(2)
    pdf.set_font("Times", "B", 10)
    pdf.cell(60, 6, f"Total ({bill['payment_method']})", ln=0)
    pdf.cell(25, 6, f"Rs. {bill['final_total']:.2f}", ln=1, align="R")
    pdf.line(10, pdf.get_y(), 95, pdf.get_y())

    pdf.ln(4)
    pdf.set_font("Times", "B", 8.5)
    pdf.cell(0, 4.5, f"For {ENTERPRISE_TITLE}", ln=1, align="R")
    pdf.set_font("Times", "", 7.5)
    pdf.cell(0, 4, f"Staff: {bill['emp_name']} ({bill['emp_id']})", ln=1, align="R")

    return bytes(pdf.output())

def upload_to_gdrive(file_bytes, filename, mime_type="application/pdf"):
    if not GDRIVE_AVAILABLE or "GDRIVE_SERVICE_ACCOUNT" not in st.secrets:
        return False, "Saved locally (Add Google Drive key in Streamlit Secrets for auto-cloud sync)."
    try:
        sa_info = json.loads(st.secrets["GDRIVE_SERVICE_ACCOUNT"])
        creds = service_account.Credentials.from_service_account_info(
            sa_info, scopes=["https://www.googleapis.com/auth/drive.file"]
        )
        service = build("drive", "v3", credentials=creds)
        folder_id = st.secrets.get("GDRIVE_FOLDER_ID", None)
        metadata = {"name": filename}
        if folder_id:
            metadata["parents"] = [folder_id]

        media = MediaIoBaseUpload(io.BytesIO(file_bytes), mimetype=mime_type)
        service.files().create(body=metadata, media_body=media, fields="id").execute()
        return True, f"Synced to {OFFICIAL_EMAIL} Google Drive"
    except Exception as e:
        return False, f"Drive Sync Note: {e}"

def send_email_with_excel(excel_bytes, filename, subject, body_text):
    admin_email = get_setting("admin_email", OFFICIAL_EMAIL)
    if "SMTP_PASSWORD" not in st.secrets:
        return False, f"Add Gmail App Password in Secrets to auto-email {admin_email}."
    sender_email = st.secrets.get("SMTP_EMAIL", OFFICIAL_EMAIL)
    try:
        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = sender_email
        msg["To"] = admin_email
        msg.set_content(body_text)
        msg.add_attachment(
            excel_bytes,
            maintype="application",
            subtype="vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            filename=filename
        )
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(sender_email, st.secrets["SMTP_PASSWORD"])
            server.send_message(msg)
        return True, f"Emailed to {admin_email}"
    except Exception as e:
        return False, f"Email Note: {e}"

def build_master_excel(tx_df, emp_summary_df, visits_df):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        emp_summary_df.to_excel(writer, index=False, sheet_name="Employee Summary")
        tx_df.to_excel(writer, index=False, sheet_name="All Invoices")
        visits_df.to_excel(writer, index=False, sheet_name="Member Utilization")
    return output.getvalue()

def time_overlaps(start_a_str, end_a_str, start_b, end_b):
    try:
        fmt = "%H:%M"
        s_a = datetime.strptime(start_a_str[:5], fmt).time()
        e_a = datetime.strptime(end_a_str[:5], fmt).time()
        return (s_a < end_b) and (e_a > start_b)
    except Exception:
        return False

# ==============================================================================
# 5. LOGIN SCREEN (EMPLOYEE ID + PASSWORD OR ADMIN GMAIL + PASSWORD)
# ==============================================================================
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.user = None
if "last_bill" not in st.session_state:
    st.session_state.last_bill = None

if not st.session_state.logged_in:
    st.write("")
    c1, c2, c3 = st.columns([1, 1.1, 1])
    with c2:
        st.markdown(f"""
        <div class="clean-card" style="text-align:center;">
            <h2>{ENTERPRISE_TITLE}</h2>
            <p><b>{ENTERPRISE_SUBTITLE}</b><br>{ENTERPRISE_ADDRESS}<br>Ph: {OFFICIAL_PHONE}</p>
        </div>
        """, unsafe_allow_html=True)
        with st.form("login_form"):
            login_input = st.text_input("Admin Gmail OR Employee ID", placeholder="e.g. thealgebraplayhouse@gmail.com OR EMP01")
            pwd_input = st.text_input("Password", type="password")
            login_btn = st.form_submit_button("Sign In", use_container_width=True, type="primary")

            if login_btn:
                conn = get_conn()
                c = conn.cursor()
                # Check matching either emp_id (case-insensitive) OR email (case-insensitive)
                c.execute(
                    "SELECT emp_id, name, email, role FROM users WHERE (lower(emp_id)=lower(?) OR lower(email)=lower(?)) AND password=?",
                    (login_input.strip(), login_input.strip(), pwd_input.strip())
                )
                row = c.fetchone()
                conn.close()
                if row:
                    st.session_state.logged_in = True
                    st.session_state.user = {
                        "emp_id": row[0],
                        "name": row[1],
                        "email": row[2],
                        "role": row[3]
                    }
                    st.rerun()
                else:
                    st.error("Invalid ID/Email or Password.")
    st.stop()

# ==============================================================================
# 6. TOP HEADER BAR & HORIZONTAL TABS
# ==============================================================================
user = st.session_state.user
hdr_left, hdr_right = st.columns([3.5, 1])
with hdr_left:
    st.markdown(f"## {ENTERPRISE_TITLE} — Portal")
    if user["role"] == "admin":
        st.caption(f"Logged in: **{user['name']}** (Admin | `{OFFICIAL_EMAIL}`)")
    else:
        st.caption(f"Logged in: **{user['name']}** (Employee ID: `{user['emp_id']}`)")
with hdr_right:
    if st.button("Sign Out", use_container_width=True):
        st.session_state.logged_in = False
        st.session_state.user = None
        st.session_state.last_bill = None
        st.rerun()

if user["role"] == "admin":
    tab_pos, tab_mem, tab_occ, tab_close, tab_admin = st.tabs([
        "1. New Bill (POS)",
        "2. Monthly Members",
        "3. Time-Slot Occupancy",
        "4. Shift Closing (24h)",
        "5. Admin & Staff Setup"
    ])
else:
    tab_pos, tab_mem, tab_occ, tab_close = st.tabs([
        "1. New Bill (POS)",
        "2. Monthly Members",
        "3. Time-Slot Occupancy",
        "4. Shift Closing (24h)"
    ])
    tab_admin = None

# ==============================================================================
# TAB 1: NEW BILL (POS)
# ==============================================================================
with tab_pos:
    col_form, col_bill = st.columns([1.25, 1])

    with col_form:
        st.markdown('<div class="clean-card">', unsafe_allow_html=True)
        st.markdown("#### Customer & Session Details")
        c1, c2 = st.columns(2)
        with c1:
            adult_name = st.text_input("Parent / Adult Name *", placeholder="Enter Full Name")
        with c2:
            phone = st.text_input("Customer Mobile / WhatsApp *", placeholder="10-digit mobile number", max_chars=15)

        now_dt = datetime.now()
        default_in = now_dt.time().replace(second=0, microsecond=0)
        default_out = (now_dt + timedelta(hours=1)).time().replace(second=0, microsecond=0)

        t1, t2 = st.columns(2)
        with t1:
            time_in = st.time_input("Time In", value=default_in)
        with t2:
            time_out = st.time_input("Time Out", value=default_out)

        st.markdown("#### Package & Add-Ons")
        p1, p2 = st.columns([2, 1])
        with p1:
            package_name = st.selectbox("Package (18% GST Inclusive)", list(RATES.keys()))
        with p2:
            num_kids = st.number_input("No. of Kids", min_value=1, step=1, value=1)

        s1, s2 = st.columns(2)
        with s1:
            num_socks = st.number_input("Socks Qty (Rs. 50 each)", min_value=0, step=1, value=0)
        with s2:
            socks_gst_pct = st.selectbox("Socks GST %", [18.0, 12.0, 6.0, 5.0, 0.0], index=0)

        w1, w2 = st.columns(2)
        with w1:
            num_water = st.number_input("Water Bottle Qty (Rs. 10 each)", min_value=0, step=1, value=0)
        with w2:
            water_gst_pct = st.selectbox("Water Bottle GST %", [6.0, 5.0, 12.0, 18.0, 0.0], index=0)

        st.markdown("#### Payment Method")
        payment_method = st.selectbox(
            "Select Payment Mode",
            ["Cash", "UPI / GPay", "Card (+2% Charge)"]
        )
        st.markdown('</div>', unsafe_allow_html=True)

    # CALCULATIONS
    base_pkg_rate = RATES[package_name]
    discount_per_kid = 50 if num_kids > 1 else 0
    effective_pkg_rate = base_pkg_rate - discount_per_kid

    pkg_total_incl = effective_pkg_rate * num_kids
    socks_total_incl = num_socks * 50
    water_total_incl = num_water * 10

    sgst_9 = round(pkg_total_incl * 0.09 + socks_total_incl * (socks_gst_pct / 200.0))
    cgst_9 = round(pkg_total_incl * 0.09 + socks_total_incl * (socks_gst_pct / 200.0))

    pkg_excl_gst = round(pkg_total_incl * 0.82)
    socks_excl_gst = round(socks_total_incl * (1.0 - (socks_gst_pct / 100.0)))

    water_gst_amt = round(water_total_incl * (water_gst_pct / 100.0), 2)
    water_excl_gst = round(water_total_incl - water_gst_amt, 2)

    total_excl_gst = round(pkg_excl_gst + socks_excl_gst + water_excl_gst, 2)
    total_gst = round(sgst_9 + cgst_9 + water_gst_amt, 2)
    subtotal_incl_gst = round(pkg_total_incl + socks_total_incl + water_total_incl, 2)

    card_fee_mode = get_setting("card_fee_base", "Including GST")
    if payment_method == "Card (+2% Charge)":
        base_for_card = subtotal_incl_gst if card_fee_mode == "Including GST" else total_excl_gst
        card_fee = round(base_for_card * 0.02, 2)
    else:
        card_fee = 0.0

    final_total = round(subtotal_incl_gst + card_fee, 2)

    next_sno = int(get_setting("next_sno", "1079"))
    preview_cust_id = f"CUST{next_sno}"
    today_str = date.today().strftime("%Y-%m-%d")
    time_in_str = time_in.strftime("%H:%M")
    time_out_str = time_out.strftime("%H:%M")
    invoice_filename = f"{today_str}_{preview_cust_id}_{time_in.strftime('%H-%M')}.pdf"

    with col_bill:
        pkg_display_label = f"Group Combo ({package_name})" if num_kids > 1 else package_name
        socks_row_html = f"<tr><td>Socks</td><td style='text-align:center;'>{num_socks}</td><td style='text-align:right;'>-</td><td style='text-align:right;'>{socks_excl_gst:.2f}</td></tr>" if num_socks > 0 else ""
        water_row_html = f"<tr><td>Water Bottle</td><td style='text-align:center;'>{num_water}</td><td style='text-align:right;'>-</td><td style='text-align:right;'>{water_excl_gst:.2f}</td></tr>" if num_water > 0 else ""
        water_gst_html = f"<tr><td>Water GST</td><td></td><td style='text-align:right;'>{water_gst_pct:.0f}%</td><td style='text-align:right;'>{water_gst_amt:.2f}</td></tr>" if water_gst_amt > 0 else ""
        card_fee_html = f"<tr><td>Card Charge (+2%)</td><td></td><td style='text-align:right;'>2%</td><td style='text-align:right;'>{card_fee:.2f}</td></tr>" if card_fee > 0 else ""

        st.markdown(f"""
        <div class="white-bill">
            <div style="display:flex; justify-content:space-between; font-size:0.85rem; font-weight:bold;">
                <span>CASH BILL</span>
                <span>GST No: {ENTERPRISE_GST}</span>
            </div>
            <h2 style="text-align:center; margin-top:6px;">{ENTERPRISE_TITLE}</h2>
            <p style="text-align:center; font-weight:bold; font-size:0.9rem;">{ENTERPRISE_SUBTITLE}</p>
            <p style="text-align:center; font-size:0.8rem;">{ENTERPRISE_ADDRESS}<br>Ph: {OFFICIAL_PHONE}</p>
            <div class="bill-divider"></div>
            <div style="display:flex; justify-content:space-between; font-size:0.9rem;">
                <span><b>S.No:</b> {next_sno} ({preview_cust_id})</span>
                <span><b>Date:</b> {date.today().strftime('%d/%m/%Y')}</span>
            </div>
            <div style="display:flex; justify-content:space-between; font-size:0.9rem; margin-top:4px;">
                <span><b>Name:</b> {adult_name or 'Walk-in'}</span>
                <span><b>Time:</b> {time_in_str} - {time_out_str}</span>
            </div>
            <div class="bill-divider"></div>
            <table style="width:100%; font-size:0.9rem; border-collapse:collapse;">
                <thead>
                    <tr style="border-bottom:1px solid #000;">
                        <th style="text-align:left; padding-bottom:4px;">DESCRIPTION</th>
                        <th style="text-align:center; padding-bottom:4px;">QTY</th>
                        <th style="text-align:right; padding-bottom:4px;">RATE</th>
                        <th style="text-align:right; padding-bottom:4px;">AMOUNT</th>
                    </tr>
                </thead>
                <tbody>
                    <tr>
                        <td style="padding-top:4px;">{pkg_display_label}</td>
                        <td style="text-align:center;">{num_kids}</td>
                        <td style="text-align:right;">-</td>
                        <td style="text-align:right;">{pkg_excl_gst:.2f}</td>
                    </tr>
                    {socks_row_html}
                    {water_row_html}
                    <tr>
                        <td>SGST</td>
                        <td></td>
                        <td style="text-align:right;">9%</td>
                        <td style="text-align:right;">{sgst_9:.2f}</td>
                    </tr>
                    <tr>
                        <td>CGST</td>
                        <td></td>
                        <td style="text-align:right;">9%</td>
                        <td style="text-align:right;">{cgst_9:.2f}</td>
                    </tr>
                    {water_gst_html}
                    {card_fee_html}
                </tbody>
            </table>
            <div class="bill-divider"></div>
            <div style="display:flex; justify-content:space-between; font-size:1.15rem; font-weight:bold;">
                <span>Total ({payment_method})</span>
                <span>Rs. {final_total:.2f}</span>
            </div>
            <p style="font-size:0.8rem; margin-top:4px;">
                Excl. GST: Rs. {total_excl_gst:.2f} | Total GST: Rs. {total_gst:.2f}
            </p>
            <div style="text-align:right; font-size:0.85rem; margin-top:12px; font-weight:bold;">
                For {ENTERPRISE_TITLE}<br>
                <span style="font-weight:normal;">Billed by: {user['name']} ({user['emp_id']})</span>
            </div>
        </div>
        """, unsafe_allow_html=True)

        st.caption(f"Drive File Name: `{invoice_filename}`")

        if st.button("Save Bill & Generate Invoice", type="primary", use_container_width=True):
            if not adult_name.strip() or not phone.strip():
                st.error("Please enter the Adult Name and Mobile Number.")
            else:
                bill_record = {
                    "sno": next_sno,
                    "customer_id": preview_cust_id,
                    "bill_date": today_str,
                    "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "emp_id": user["emp_id"],
                    "emp_name": user["name"],
                    "adult_name": adult_name.strip(),
                    "phone": phone.strip(),
                    "package": package_name,
                    "num_kids": num_kids,
                    "num_socks": num_socks,
                    "socks_gst_pct": socks_gst_pct,
                    "num_water": num_water,
                    "water_gst_pct": water_gst_pct,
                    "time_in": time_in_str,
                    "time_out": time_out_str,
                    "payment_method": payment_method,
                    "pkg_excl_gst": pkg_excl_gst,
                    "socks_excl_gst": socks_excl_gst,
                    "water_excl_gst": water_excl_gst,
                    "sgst_9": sgst_9,
                    "cgst_9": cgst_9,
                    "water_gst_amt": water_gst_amt,
                    "total_excl_gst": total_excl_gst,
                    "total_gst": total_gst,
                    "subtotal_incl_gst": subtotal_incl_gst,
                    "card_fee": card_fee,
                    "final_total": final_total,
                    "invoice_filename": invoice_filename
                }

                conn = get_conn()
                c = conn.cursor()
                c.execute('''INSERT INTO transactions (
                    sno, customer_id, bill_date, created_at, emp_id, emp_name,
                    adult_name, phone, package, num_kids, num_socks, socks_gst_pct,
                    num_water, water_gst_pct, time_in, time_out, payment_method,
                    pkg_excl_gst, socks_excl_gst, water_excl_gst, sgst_9, cgst_9,
                    water_gst_amt, total_excl_gst, total_gst, subtotal_incl_gst,
                    card_fee, final_total, invoice_filename, is_closed
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,0)''', (
                    bill_record["sno"], bill_record["customer_id"], bill_record["bill_date"],
                    bill_record["created_at"], bill_record["emp_id"], bill_record["emp_name"],
                    bill_record["adult_name"], bill_record["phone"], bill_record["package"],
                    bill_record["num_kids"], bill_record["num_socks"], bill_record["socks_gst_pct"],
                    bill_record["num_water"], bill_record["water_gst_pct"], bill_record["time_in"],
                    bill_record["time_out"], bill_record["payment_method"], bill_record["pkg_excl_gst"],
                    bill_record["socks_excl_gst"], bill_record["water_excl_gst"], bill_record["sgst_9"],
                    bill_record["cgst_9"], bill_record["water_gst_amt"], bill_record["total_excl_gst"],
                    bill_record["total_gst"], bill_record["subtotal_incl_gst"], bill_record["card_fee"],
                    bill_record["final_total"], bill_record["invoice_filename"]
                ))
                conn.commit()
                conn.close()

                set_setting("next_sno", str(next_sno + 1))

                pdf_bytes = generate_invoice_pdf_bytes(bill_record)
                os.makedirs("saved_invoices", exist_ok=True)
                with open(os.path.join("saved_invoices", invoice_filename), "wb") as f:
                    f.write(pdf_bytes)

                ok_drive, drive_msg = upload_to_gdrive(pdf_bytes, invoice_filename, "application/pdf")
                bill_record["pdf_bytes"] = pdf_bytes
                bill_record["drive_status"] = drive_msg
                st.session_state.last_bill = bill_record
                st.rerun()

        if st.session_state.last_bill:
            lb = st.session_state.last_bill
            st.success(f"Bill #{lb['sno']} Saved! ({lb['drive_status']})")

            clean_phone = "".join([ch for ch in lb["phone"] if ch.isdigit()])
            if len(clean_phone) == 10:
                clean_phone = "91" + clean_phone

            receipt_msg = (
                f"{ENTERPRISE_TITLE} ({ENTERPRISE_SUBTITLE})\n"
                f"GST: {ENTERPRISE_GST} | Ph: {OFFICIAL_PHONE}\n"
                f"S.No: {lb['sno']} | ID: {lb['customer_id']}\n"
                f"Date: {lb['bill_date']} ({lb['time_in']}-{lb['time_out']})\n"
                f"Name: {lb['adult_name']}\n"
                f"Pkg ({lb['num_kids']}): Rs.{lb['pkg_excl_gst']:.2f}\n"
                + (f"Socks ({lb['num_socks']}): Rs.{lb['socks_excl_gst']:.2f}\n" if lb["num_socks"] > 0 else "")
                + (f"Water ({lb['num_water']}): Rs.{lb['water_excl_gst']:.2f}\n" if lb["num_water"] > 0 else "")
                + f"SGST 9%: Rs.{lb['sgst_9']:.2f} | CGST 9%: Rs.{lb['cgst_9']:.2f}\n"
                + (f"Water GST: Rs.{lb['water_gst_amt']:.2f}\n" if lb["water_gst_amt"] > 0 else "")
                + (f"Card Fee 2%: Rs.{lb['card_fee']:.2f}\n" if lb["card_fee"] > 0 else "")
                + f"TOTAL ({lb['payment_method']}): Rs.{lb['final_total']:.2f}"
            )

            wa_url = f"https://wa.me/{clean_phone}?text={urllib.parse.quote(receipt_msg)}"
            sms_url = f"sms:+{clean_phone}?body={urllib.parse.quote(receipt_msg)}"

            b_col1, b_col2 = st.columns(2)
            with b_col1:
                st.markdown(f'<a href="{wa_url}" target="_blank" class="action-btn wa-btn">Send via WhatsApp</a>', unsafe_allow_html=True)
            with b_col2:
                st.markdown(f'<a href="{sms_url}" class="action-btn sms-btn">Send SMS ({OFFICIAL_PHONE})</a>', unsafe_allow_html=True)

            st.download_button(
                label=f"Download Official PDF ({lb['invoice_filename']})",
                data=lb["pdf_bytes"],
                file_name=lb["invoice_filename"],
                mime="application/pdf",
                use_container_width=True
            )

# ==============================================================================
# TAB 2: MONTHLY MEMBERSHIPS
# ==============================================================================
with tab_mem:
    st.markdown("""
    <div class="member-header">
        <h3 style="margin:0; color:white;">Monthly Membership Check-In & Directory</h3>
        <p style="margin:2px 0 0 0; font-size:0.9rem; color:#e2e8f0;">
            Attendance logs directly to Occupancy & Master Reports without generating a cash bill or sending an invoice.
        </p>
    </div>
    """, unsafe_allow_html=True)

    m_col1, m_col2 = st.columns([1.1, 1])

    conn = get_conn()
    members_df = pd.read_sql_query("SELECT * FROM members ORDER BY member_id DESC", conn)
    conn.close()

    with m_col1:
        st.markdown('<div class="member-zone">', unsafe_allow_html=True)
        st.markdown("#### Quick Member Check-In (Time In / Time Out)")
        if members_df.empty:
            st.info("No members registered yet. Add a member on the right first.")
        else:
            member_options = [
                f"{row['member_id']} — {row['child_name']} ({row['adult_name']} | {row['phone']})"
                for _, row in members_df.iterrows()
            ]
            selected_member_str = st.selectbox("Select Member ID", member_options)
            selected_member_id = selected_member_str.split(" — ")[0]
            m_row = members_df[members_df["member_id"] == selected_member_id].iloc[0]

            now_dt = datetime.now()
            mc1, mc2, mc3 = st.columns(3)
            with mc1:
                visit_date = st.date_input("Date", value=date.today())
            with mc2:
                m_time_in = st.time_input("Member Time In", value=now_dt.time().replace(second=0, microsecond=0))
            with mc3:
                m_time_out = st.time_input("Member Time Out", value=(now_dt + timedelta(hours=1)).time().replace(second=0, microsecond=0))

            if st.button("Log Member Visit (No Invoice)", type="primary", use_container_width=True):
                conn = get_conn()
                c = conn.cursor()
                c.execute('''INSERT INTO member_visits (
                    member_id, child_name, adult_name, phone, visit_date,
                    time_in, time_out, logged_by_id, logged_by_name, is_closed
                ) VALUES (?,?,?,?,?,?,?,?,?,0)''', (
                    m_row["member_id"], m_row["child_name"], m_row["adult_name"],
                    m_row["phone"], visit_date.strftime("%Y-%m-%d"),
                    m_time_in.strftime("%H:%M"), m_time_out.strftime("%H:%M"),
                    user["emp_id"], user["name"]
                ))
                conn.commit()
                conn.close()
                st.success(f"Visit logged for {m_row['child_name']} ({m_row['member_id']}) [{m_time_in.strftime('%H:%M')} - {m_time_out.strftime('%H:%M')}].")
        st.markdown('</div>', unsafe_allow_html=True)

    with m_col2:
        st.markdown('<div class="member-zone">', unsafe_allow_html=True)
        st.markdown("#### Register New Monthly Member")
        next_mem_num = 1001 + len(members_df)
        suggested_mem_id = f"MEM-{next_mem_num}"

        with st.form("new_member_form"):
            f1, f2 = st.columns(2)
            with f1:
                new_mem_id = st.text_input("Member ID", value=suggested_mem_id)
                child_name = st.text_input("Child Name *")
                m_adult_name = st.text_input("Parent Name *")
            with f2:
                m_phone = st.text_input("Mobile Number *")
                start_d = st.date_input("Start Date", value=date.today())
                expiry_d = st.date_input("Expiry Date", value=date.today() + timedelta(days=30))
            if st.form_submit_button("Register Member", use_container_width=True):
                if not child_name.strip() or not m_adult_name.strip() or not m_phone.strip():
                    st.error("All fields are required.")
                else:
                    conn = get_conn()
                    c = conn.cursor()
                    try:
                        c.execute('''INSERT INTO members (
                            member_id, child_name, adult_name, phone, start_date, expiry_date, notes, created_by
                        ) VALUES (?,?,?,?,?,?,?,?)''', (
                            new_mem_id.strip(), child_name.strip(), m_adult_name.strip(),
                            m_phone.strip(), start_d.strftime("%Y-%m-%d"),
                            expiry_d.strftime("%Y-%m-%d"), "", user["emp_id"]
                        ))
                        conn.commit()
                        st.success(f"Member {new_mem_id} created.")
                        st.rerun()
                    except sqlite3.IntegrityError:
                        st.error("Member ID already exists.")
                    finally:
                        conn.close()
        st.markdown('</div>', unsafe_allow_html=True)

    conn = get_conn()
    visits_df = pd.read_sql_query("SELECT * FROM member_visits ORDER BY id DESC", conn)
    conn.close()
    if not visits_df.empty:
        st.markdown("#### Member Utilization Summary")
        util_summary = visits_df.groupby(["member_id", "child_name", "adult_name", "phone"]).size().reset_index(name="Total Visits Logged")
        st.dataframe(util_summary, use_container_width=True)

# ==============================================================================
# TAB 3: LIVE OCCUPANCY & TIME-SLOT TRACKER
# ==============================================================================
with tab_occ:
    st.markdown("#### Check Headcount by Time Window (e.g. 10:00 to 11:00)")
    fc1, fc2, fc3 = st.columns(3)
    with fc1:
        slot_date = st.date_input("Select Date", value=date.today(), key="occ_date")
    with fc2:
        slot_start = st.time_input("From Time", value=time(10, 0), key="occ_start")
    with fc3:
        slot_end = st.time_input("To Time", value=time(11, 0), key="occ_end")

    slot_date_str = slot_date.strftime("%Y-%m-%d")
    conn = get_conn()
    day_tx = pd.read_sql_query("SELECT * FROM transactions WHERE bill_date=?", conn, params=(slot_date_str,))
    day_mem = pd.read_sql_query("SELECT * FROM member_visits WHERE visit_date=?", conn, params=(slot_date_str,))
    conn.close()

    walkin_rows = [r for _, r in day_tx.iterrows() if time_overlaps(r["time_in"], r["time_out"], slot_start, slot_end)]
    mem_rows = [r for _, r in day_mem.iterrows() if time_overlaps(r["time_in"], r["time_out"], slot_start, slot_end)]

    walkin_df = pd.DataFrame(walkin_rows)
    mem_slot_df = pd.DataFrame(mem_rows)

    x_regular_kids = int(walkin_df["num_kids"].sum()) if not walkin_df.empty else 0
    y_member_kids = len(mem_slot_df)

    m1, m2, m3 = st.columns(3)
    m1.metric("Regular Walk-In Kids (X)", x_regular_kids)
    m2.metric("Monthly Members Present (Y)", y_member_kids)
    m3.metric("Total Kids in Playhouse", x_regular_kids + y_member_kids)

    col_w, col_m = st.columns(2)
    with col_w:
        st.markdown("##### Walk-In Customers Present")
        if not walkin_df.empty:
            st.dataframe(walkin_df[["customer_id", "adult_name", "phone", "package", "num_kids", "time_in", "time_out", "emp_name"]], use_container_width=True)
        else:
            st.info("No walk-in customers during this window.")
    with col_m:
        st.markdown("##### Monthly Members Present")
        if not mem_slot_df.empty:
            st.dataframe(mem_slot_df[["member_id", "child_name", "adult_name", "phone", "time_in", "time_out", "logged_by_name"]], use_container_width=True)
        else:
            st.info("No monthly members during this window.")

# ==============================================================================
# TAB 4: 24-HOUR SHIFT CLOSING & NIL RESET
# ==============================================================================
with tab_close:
    st.markdown("#### Current 24-Hour Shift Summary & Complete Closing")
    conn = get_conn()
    if user["role"] == "admin":
        active_tx = pd.read_sql_query("SELECT * FROM transactions WHERE is_closed=0", conn)
    else:
        active_tx = pd.read_sql_query("SELECT * FROM transactions WHERE is_closed=0 AND emp_id=?", conn, params=(user["emp_id"],))
    all_active_tx = pd.read_sql_query("SELECT * FROM transactions WHERE is_closed=0", conn)
    all_active_visits = pd.read_sql_query("SELECT * FROM member_visits WHERE is_closed=0", conn)
    conn.close()

    my_tx_count = len(active_tx)
    my_revenue = float(active_tx["final_total"].sum()) if not active_tx.empty else 0.0
    my_cash = float(active_tx[active_tx["payment_method"] == "Cash"]["final_total"].sum()) if not active_tx.empty else 0.0
    my_upi = float(active_tx[active_tx["payment_method"] == "UPI / GPay"]["final_total"].sum()) if not active_tx.empty else 0.0
    my_card = float(active_tx[active_tx["payment_method"] == "Card (+2% Charge)"]["final_total"].sum()) if not active_tx.empty else 0.0

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Active Shift Bills", my_tx_count)
    k2.metric("Total Shift Collection", f"Rs. {my_revenue:.2f}")
    k3.metric("Cash / UPI", f"Rs. {my_cash:.0f} / Rs. {my_upi:.0f}")
    k4.metric("Card (+2%)", f"Rs. {my_card:.2f}")

    if not active_tx.empty:
        st.dataframe(active_tx[["sno", "customer_id", "adult_name", "phone", "package", "num_kids", "time_in", "time_out", "payment_method", "final_total", "emp_name"]], use_container_width=True)
    else:
        st.success("Shift counter is at NIL (0 active transactions). Ready for a new day.")

    if not all_active_tx.empty or not all_active_visits.empty:
        emp_summary = all_active_tx.groupby(["emp_id", "emp_name", "payment_method"]).agg(
            Transactions=("id", "count"),
            Total_Amount=("final_total", "sum")
        ).reset_index() if not all_active_tx.empty else pd.DataFrame()

        master_excel_bytes = build_master_excel(all_active_tx, emp_summary, all_active_visits)
        closing_filename = f"Master_Closing_{datetime.now().strftime('%Y-%m-%d_%H-%M')}.xlsx"

        st.download_button(
            "Download Shift Master Excel (.xlsx)",
            data=master_excel_bytes,
            file_name=closing_filename,
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

        if st.button("COMPLETE CLOSING — Email to Admin, Save to Drive & Reset Shift to Nil", type="primary", use_container_width=True):
            ok_mail, mail_msg = send_email_with_excel(
                master_excel_bytes,
                closing_filename,
                subject=f"[{ENTERPRISE_TITLE}] Daily Shift Closing Report - {date.today()}",
                body_text=f"Shift closed by {user['name']} ({user['emp_id']}). Master Excel attached."
            )
            ok_drive, drive_msg = upload_to_gdrive(
                master_excel_bytes,
                closing_filename,
                mime_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
            conn = get_conn()
            c = conn.cursor()
            c.execute("UPDATE transactions SET is_closed=1 WHERE is_closed=0")
            c.execute("UPDATE member_visits SET is_closed=1 WHERE is_closed=0")
            conn.commit()
            conn.close()

            st.session_state.last_bill = None
            st.success(f"Shift Reset to Nil! | {mail_msg} | {drive_msg}")
            st.rerun()

# ==============================================================================
# TAB 5: ADMIN MASTER PORTAL & STAFF MANAGEMENT
# ==============================================================================
if tab_admin is not None:
    with tab_admin:
        st.markdown("#### Consolidated Employee Master Report")
        conn = get_conn()
        all_tx = pd.read_sql_query("SELECT * FROM transactions ORDER BY id DESC", conn)
        all_visits = pd.read_sql_query("SELECT * FROM member_visits ORDER BY id DESC", conn)
        conn.close()

        if not all_tx.empty:
            emp_perf = all_tx.groupby(["emp_id", "emp_name"]).agg(
                Transactions=("id", "count"),
                Kids_Count=("num_kids", "sum"),
                Excl_GST=("total_excl_gst", "sum"),
                GST_Amount=("total_gst", "sum"),
                Card_Charges=("card_fee", "sum"),
                Total_Collected=("final_total", "sum")
            ).reset_index()
            st.dataframe(emp_perf, use_container_width=True)

            full_excel = build_master_excel(all_tx, emp_perf, all_visits)
            st.download_button(
                "Download Full Historical Master Excel (.xlsx)",
                data=full_excel,
                file_name=f"Algebra_Playhouse_Master_{date.today()}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                type="primary"
            )

        st.write("---")
        col_staff, col_cfg = st.columns(2)

        with col_staff:
            st.markdown("#### Create Employee Login (ID + Password)")
            with st.form("add_emp_form"):
                new_emp_id = st.text_input("Employee ID *", placeholder="e.g. EMP01")
                new_emp_name = st.text_input("Employee Name *", placeholder="e.g. Rahul")
                new_emp_pwd = st.text_input("Password *", type="password")
                new_emp_role = st.selectbox("Role", ["employee", "admin"])
                if st.form_submit_button("Create Staff Account", use_container_width=True):
                    if new_emp_id.strip() and new_emp_name.strip() and new_emp_pwd.strip():
                        conn = get_conn()
                        c = conn.cursor()
                        try:
                            c.execute(
                                "INSERT INTO users (emp_id, name, email, password, role) VALUES (?,?,?,?,?)",
                                (new_emp_id.strip(), new_emp_name.strip(), "", new_emp_pwd.strip(), new_emp_role)
                            )
                            conn.commit()
                            st.success(f"Employee {new_emp_id} added successfully.")
                            st.rerun()
                        except sqlite3.IntegrityError:
                            st.error("Employee ID already exists.")
                        finally:
                            conn.close()

            conn = get_conn()
            users_df = pd.read_sql_query("SELECT emp_id, name, email, role FROM users", conn)
            conn.close()
            st.dataframe(users_df, use_container_width=True)

        with col_cfg:
            st.markdown("#### Billing & Admin Settings")
            curr_sno = get_setting("next_sno", "1079")
            curr_card_mode = get_setting("card_fee_base", "Including GST")
            with st.form("settings_form"):
                st.text_input("Master Admin Email (Receives Closing Reports)", value=OFFICIAL_EMAIL, disabled=True)
                st.text_input("Official Dispatch Phone", value=OFFICIAL_PHONE, disabled=True)
                new_next_sno = st.number_input("Next Bill S.No", min_value=1, value=int(curr_sno))
                new_card_mode = st.selectbox(
                    "2% Card Surcharge Base",
                    ["Including GST", "Excluding GST"],
                    index=0 if curr_card_mode == "Including GST" else 1
                )
                if st.form_submit_button("Save Settings", use_container_width=True):
                    set_setting("next_sno", str(new_next_sno))
                    set_setting("card_fee_base", new_card_mode)
                    st.success("Settings saved.")
