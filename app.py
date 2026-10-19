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
# 1. PAGE CONFIGURATION & MINIMALIST RESPONSIVE UI/UX
# ==============================================================================
st.set_page_config(
    page_title="The aLGeBrA Playhouse | POS & Admin",
    page_icon="🎈",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
    /* Clean Minimalist Responsive UI */
    .block-container { padding-top: 1.2rem; padding-bottom: 2rem; max-width: 1280px; }
    .pos-card {
        background: #ffffff;
        border: 1px solid #e5e7eb;
        border-radius: 12px;
        padding: 20px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.04);
        margin-bottom: 16px;
    }
    /* Yellow Cash Bill Preview Styling */
    .cash-bill {
        background-color: #fef08a;
        color: #1f2937;
        padding: 22px;
        border-radius: 8px;
        border: 2px solid #ca8a04;
        font-family: 'Courier New', Courier, monospace;
        box-shadow: 0 4px 10px rgba(0,0,0,0.08);
    }
    .cash-bill h3, .cash-bill h4, .cash-bill p { margin: 2px 0; color: #111827; }
    .bill-hr { border-top: 1px dashed #854d0e; margin: 10px 0; }
    
    /* Distinct Monthly Membership Theme (Royal Purple Accent) */
    .member-banner {
        background: linear-gradient(135deg, #4c1d95 0%, #7c3aed 100%);
        color: white;
        padding: 20px;
        border-radius: 12px;
        margin-bottom: 18px;
    }
    .member-card {
        background-color: #f5f3ff;
        border: 2px solid #c4b5fd;
        border-radius: 12px;
        padding: 18px;
        margin-bottom: 16px;
    }
    /* WhatsApp Button */
    .wa-btn {
        display: inline-block;
        width: 100%;
        text-align: center;
        background-color: #25D366;
        color: white !important;
        font-weight: 600;
        padding: 12px 16px;
        border-radius: 8px;
        text-decoration: none;
        margin-top: 8px;
    }
    .wa-btn:hover { background-color: #1ebe57; }
</style>
""", unsafe_allow_html=True)

# ==============================================================================
# 2. CONSTANTS & RATE CARD
# ==============================================================================
ENTERPRISE_TITLE = "The aLGeBrA Playhouse"
ENTERPRISE_SUBTITLE = "JEYHUMRUTH"
ENTERPRISE_ADDRESS = "No.32/27, 27th Street, Thillai Ganga Nagar, Chennai - 600 061."
ENTERPRISE_GST = "33AAVFJ5819R1ZD"

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
DB_FILE = "algebra_playhouse.db"

def get_conn():
    return sqlite3.connect(DB_FILE, check_same_thread=False)

def init_db():
    conn = get_conn()
    c = conn.cursor()

    # Settings table (Admin Gmail, Next S.No, Card Fee Mode)
    c.execute('''CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY,
        value TEXT
    )''')

    # Users table
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        emp_id TEXT PRIMARY KEY,
        name TEXT,
        email TEXT,
        password TEXT,
        role TEXT
    )''')

    # Transactions table (is_closed=0 means current active 24hr shift; is_closed=1 means archived)
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

    # Monthly Members directory
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

    # Member Visit / Attendance table (is_closed=0 for current shift, 1 for archived)
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

    # Default Admin User
    c.execute("SELECT * FROM users WHERE role='admin'")
    if not c.fetchone():
        c.execute('''INSERT INTO users (emp_id, name, email, password, role)
                     VALUES ('ADMIN01', 'Playhouse Admin', 'admin@gmail.com', 'admin123', 'admin')''')

    # Default Settings
    default_settings = {
        "next_sno": "1079",
        "admin_email": "admin@gmail.com",
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
# 4. PDF RECEIPT GENERATOR, GOOGLE DRIVE UPLOAD & EMAIL HELPERS
# ==============================================================================
def generate_invoice_pdf_bytes(bill):
    """Generates a clean PDF matching the yellow CASH BILL layout."""
    pdf = FPDF(format=(105, 165))  # A6 Receipt size
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=8)

    # Header
    pdf.set_font("Courier", "B", 9)
    pdf.cell(45, 5, "CASH BILL", ln=0)
    pdf.cell(45, 5, f"GST: {ENTERPRISE_GST}", ln=1, align="R")

    pdf.set_font("Courier", "B", 13)
    pdf.cell(0, 6, ENTERPRISE_TITLE, ln=1, align="C")
    pdf.set_font("Courier", "B", 9)
    pdf.cell(0, 4, ENTERPRISE_SUBTITLE, ln=1, align="C")
    pdf.set_font("Courier", "", 7)
    pdf.multi_cell(0, 3.5, ENTERPRISE_ADDRESS, align="C")
    pdf.ln(2)

    # Meta info
    pdf.set_font("Courier", "B", 8)
    pdf.cell(45, 4.5, f"S.No: {bill['sno']}", ln=0)
    pdf.cell(45, 4.5, f"Date: {bill['bill_date']}", ln=1, align="R")
    pdf.cell(45, 4.5, f"Cust ID: {bill['customer_id']}", ln=0)
    pdf.cell(45, 4.5, f"Time: {bill['time_in']}-{bill['time_out']}", ln=1, align="R")
    pdf.cell(0, 4.5, f"Name: {bill['adult_name']} ({bill['phone']})", ln=1)

    pdf.cell(0, 2, "-" * 48, ln=1)
    pdf.set_font("Courier", "B", 8)
    pdf.cell(46, 4.5, "DESCRIPTION", ln=0)
    pdf.cell(10, 4.5, "QTY", ln=0, align="C")
    pdf.cell(14, 4.5, "RATE", ln=0, align="R")
    pdf.cell(18, 4.5, "AMOUNT", ln=1, align="R")
    pdf.cell(0, 2, "-" * 48, ln=1)

    pdf.set_font("Courier", "", 8)
    # 1. Package Row (Excl GST)
    pkg_label = "Group Combo" if bill["num_kids"] > 1 else bill["package"][:20]
    pdf.cell(46, 4.5, pkg_label, ln=0)
    pdf.cell(10, 4.5, str(bill["num_kids"]), ln=0, align="C")
    pdf.cell(14, 4.5, "-", ln=0, align="R")
    pdf.cell(18, 4.5, f"{bill['pkg_excl_gst']:.2f}", ln=1, align="R")

    # 2. Socks Row (Excl GST)
    if bill["num_socks"] > 0:
        pdf.cell(46, 4.5, "Socks", ln=0)
        pdf.cell(10, 4.5, str(bill["num_socks"]), ln=0, align="C")
        pdf.cell(14, 4.5, "-", ln=0, align="R")
        pdf.cell(18, 4.5, f"{bill['socks_excl_gst']:.2f}", ln=1, align="R")

    # 3. Water Row (Excl GST)
    if bill["num_water"] > 0:
        pdf.cell(46, 4.5, f"Water ({bill['water_gst_pct']:.0f}% GST)", ln=0)
        pdf.cell(10, 4.5, str(bill["num_water"]), ln=0, align="C")
        pdf.cell(14, 4.5, "-", ln=0, align="R")
        pdf.cell(18, 4.5, f"{bill['water_excl_gst']:.2f}", ln=1, align="R")

    # Taxes
    pdf.ln(1)
    pdf.cell(46, 4.5, "SGST", ln=0)
    pdf.cell(10, 4.5, "", ln=0)
    pdf.cell(14, 4.5, "9%", ln=0, align="R")
    pdf.cell(18, 4.5, f"{bill['sgst_9']:.2f}", ln=1, align="R")

    pdf.cell(46, 4.5, "CGST", ln=0)
    pdf.cell(10, 4.5, "", ln=0)
    pdf.cell(14, 4.5, "9%", ln=0, align="R")
    pdf.cell(18, 4.5, f"{bill['cgst_9']:.2f}", ln=1, align="R")

    if bill["water_gst_amt"] > 0:
        pdf.cell(46, 4.5, "Water GST", ln=0)
        pdf.cell(10, 4.5, "", ln=0)
        pdf.cell(14, 4.5, f"{bill['water_gst_pct']:.0f}%", ln=0, align="R")
        pdf.cell(18, 4.5, f"{bill['water_gst_amt']:.2f}", ln=1, align="R")

    if bill["card_fee"] > 0:
        pdf.cell(46, 4.5, "Card Charge (+2%)", ln=0)
        pdf.cell(10, 4.5, "", ln=0)
        pdf.cell(14, 4.5, "2%", ln=0, align="R")
        pdf.cell(18, 4.5, f"{bill['card_fee']:.2f}", ln=1, align="R")

    pdf.cell(0, 2, "-" * 48, ln=1)
    pdf.set_font("Courier", "B", 10)
    pdf.cell(65, 6, f"Total ({bill['payment_method']})", ln=0)
    pdf.cell(23, 6, f"Rs.{bill['final_total']:.2f}", ln=1, align="R")
    pdf.cell(0, 2, "-" * 48, ln=1)

    pdf.ln(3)
    pdf.set_font("Courier", "B", 8)
    pdf.cell(0, 4, f"For {ENTERPRISE_TITLE}", ln=1, align="R")
    pdf.set_font("Courier", "", 7)
    pdf.cell(0, 4, f"Billed by: {bill['emp_name']} ({bill['emp_id']})", ln=1, align="R")

    return bytes(pdf.output())

def upload_to_gdrive(file_bytes, filename, mime_type="application/pdf"):
    """Uploads an invoice or Excel master report to the Admin's Google Drive folder if configured."""
    if not GDRIVE_AVAILABLE or "GDRIVE_SERVICE_ACCOUNT" not in st.secrets:
        return False, "Google Drive Service Account not configured in Secrets (Saved locally)."
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
        return True, f"Uploaded '{filename}' to Admin Google Drive."
    except Exception as e:
        return False, f"Drive Upload Error: {e}"

def send_email_with_excel(excel_bytes, filename, subject, body_text):
    """Emails the Master Excel file to the Admin's Gmail address."""
    admin_email = get_setting("admin_email", "admin@gmail.com")
    if "SMTP_EMAIL" not in st.secrets or "SMTP_PASSWORD" not in st.secrets:
        return False, f"SMTP credentials not set in Streamlit Secrets yet. Target Admin Gmail: {admin_email}"
    try:
        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = st.secrets["SMTP_EMAIL"]
        msg["To"] = admin_email
        msg.set_content(body_text)
        msg.add_attachment(
            excel_bytes,
            maintype="application",
            subtype="vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            filename=filename
        )
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(st.secrets["SMTP_EMAIL"], st.secrets["SMTP_PASSWORD"])
            server.send_message(msg)
        return True, f"Master Excel sent to {admin_email}!"
    except Exception as e:
        return False, f"Email Error: {e}"

def build_master_excel(tx_df, emp_summary_df, visits_df):
    """Creates a multi-sheet Master Excel workbook."""
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        emp_summary_df.to_excel(writer, index=False, sheet_name="Employee Summary")
        tx_df.to_excel(writer, index=False, sheet_name="All Invoices")
        visits_df.to_excel(writer, index=False, sheet_name="Member Utilization")
    return output.getvalue()

def time_overlaps(start_a_str, end_a_str, start_b, end_b):
    """Checks if a logged visit [start_a, end_a] overlaps with filter [start_b, end_b]."""
    try:
        fmt = "%H:%M"
        s_a = datetime.strptime(start_a_str[:5], fmt).time()
        e_a = datetime.strptime(end_a_str[:5], fmt).time()
        return (s_a < end_b) and (e_a > start_b)
    except Exception:
        return False

# ==============================================================================
# 5. AUTHENTICATION / LOGIN SCREEN
# ==============================================================================
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.user = None
if "last_bill" not in st.session_state:
    st.session_state.last_bill = None

if not st.session_state.logged_in:
    st.markdown("<br>", unsafe_allow_html=True)
    c1, c2, c3 = st.columns([1, 1.1, 1])
    with c2:
        st.markdown(f"""
        <div class="pos-card" style="text-align:center;">
            <h2>🎈 {ENTERPRISE_TITLE}</h2>
            <p style="color:#6b7280; font-size:0.9rem;">{ENTERPRISE_SUBTITLE} • Staff & Admin Portal</p>
        </div>
        """, unsafe_allow_html=True)
        with st.form("login_form"):
            login_input = st.text_input("Employee ID or Admin Gmail", placeholder="e.g. ADMIN01 or EMP01")
            pwd_input = st.text_input("Password", type="password")
            login_btn = st.form_submit_button("Sign In to Dashboard", use_container_width=True, type="primary")

            if login_btn:
                conn = get_conn()
                c = conn.cursor()
                c.execute(
                    "SELECT emp_id, name, email, role FROM users WHERE (emp_id=? OR lower(email)=lower(?)) AND password=?",
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
                    st.error("Invalid Employee ID / Gmail or Password.")
    st.stop()

# ==============================================================================
# 6. SIDEBAR NAVIGATION
# ==============================================================================
user = st.session_state.user
st.sidebar.markdown(f"### 🎈 {ENTERPRISE_TITLE}")
st.sidebar.caption(f"Logged in: **{user['name']}** (`{user['emp_id']}`)")

nav_options = [
    "🧾 POS Billing (Walk-ins)",
    "👑 Monthly Memberships",
    "🕒 Live Occupancy & Slot Tracker",
    "🔒 Shift Closing (24-Hr Reset)"
]
if user["role"] == "admin":
    nav_options.append("📊 Admin Master Portal & Staff")

page = st.sidebar.radio("Navigation", nav_options)

st.sidebar.write("---")
if st.sidebar.button("🚪 Logout", use_container_width=True):
    st.session_state.logged_in = False
    st.session_state.user = None
    st.session_state.last_bill = None
    st.rerun()

# ==============================================================================
# PAGE 1: POS BILLING (WALK-INS)
# ==============================================================================
if page == "🧾 POS Billing (Walk-ins)":
    st.subheader("🧾 Customer Billing & Official Cash Bill")

    col_form, col_preview = st.columns([1.35, 1])

    with col_form:
        st.markdown('<div class="pos-card">', unsafe_allow_html=True)
        st.markdown("##### 1. Customer & Session Timing")
        r1c1, r1c2 = st.columns(2)
        with r1c1:
            adult_name = st.text_input("Parent / Adult Name *", placeholder="e.g. Ramachandran")
        with r1c2:
            phone = st.text_input("WhatsApp Phone Number *", placeholder="10-digit mobile number", max_chars=15)

        now_dt = datetime.now()
        default_in = now_dt.time().replace(second=0, microsecond=0)
        default_out = (now_dt + timedelta(hours=1)).time().replace(second=0, microsecond=0)

        r2c1, r2c2 = st.columns(2)
        with r2c1:
            time_in = st.time_input("Time In (Start Time)", value=default_in)
        with r2c2:
            time_out = st.time_input("Expected Time Out", value=default_out)

        st.markdown("##### 2. Package, Kids & Add-ons")
        p1, p2 = st.columns([2, 1])
        with p1:
            package_name = st.selectbox("Select Package (18% GST Inclusive)", list(RATES.keys()))
        with p2:
            num_kids = st.number_input("No. of Kids Playing", min_value=1, step=1, value=1)

        s1, s2 = st.columns(2)
        with s1:
            num_socks = st.number_input("Socks Qty (₹50 / pair)", min_value=0, step=1, value=0)
        with s2:
            socks_gst_pct = st.selectbox("Socks GST %", [18.0, 12.0, 6.0, 5.0, 0.0], index=0)

        w1, w2 = st.columns(2)
        with w1:
            num_water = st.number_input("Water Bottle Qty (₹10 / bottle)", min_value=0, step=1, value=0)
        with w2:
            water_gst_pct = st.selectbox("Water Bottle GST %", [6.0, 5.0, 12.0, 18.0, 0.0], index=0)

        st.markdown("##### 3. Payment Method")
        payment_method = st.radio(
            "Choose Payment Mode",
            ["Cash", "UPI / GPay", "Card (+2% Charge)"],
            horizontal=True
        )
        st.markdown('</div>', unsafe_allow_html=True)

    # ---------------- BILL MATH (MATCHING YELLOW CASH BILL) ----------------
    base_pkg_rate = RATES[package_name]
    discount_per_kid = 50 if num_kids > 1 else 0
    effective_pkg_rate = base_pkg_rate - discount_per_kid

    pkg_total_incl = effective_pkg_rate * num_kids
    socks_total_incl = num_socks * 50
    water_total_incl = num_water * 10

    # Package & Socks GST (9% SGST + 9% CGST on inclusive price, matching receipt 1300 -> 989, 82, 117, 117)
    sgst_9 = round(pkg_total_incl * 0.09 + socks_total_incl * (socks_gst_pct / 200.0))
    cgst_9 = round(pkg_total_incl * 0.09 + socks_total_incl * (socks_gst_pct / 200.0))

    pkg_excl_gst = round(pkg_total_incl * 0.82)
    socks_excl_gst = round(socks_total_incl * (1.0 - (socks_gst_pct / 100.0)))

    # Water GST (6% default on ₹10)
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

    # ---------------- LIVE YELLOW CASH BILL PREVIEW ----------------
    with col_preview:
        pkg_display_label = f"Group Combo ({package_name})" if num_kids > 1 else package_name
        socks_row_html = f"<tr><td>Socks</td><td style='text-align:center;'>{num_socks}</td><td style='text-align:right;'>-</td><td style='text-align:right;'>{socks_excl_gst:.2f}</td></tr>" if num_socks > 0 else ""
        water_row_html = f"<tr><td>Water Bottle</td><td style='text-align:center;'>{num_water}</td><td style='text-align:right;'>-</td><td style='text-align:right;'>{water_excl_gst:.2f}</td></tr>" if num_water > 0 else ""
        water_gst_html = f"<tr><td>Water GST</td><td></td><td style='text-align:right;'>{water_gst_pct:.0f}%</td><td style='text-align:right;'>{water_gst_amt:.2f}</td></tr>" if water_gst_amt > 0 else ""
        card_fee_html = f"<tr><td>Card Fee (+2%)</td><td></td><td style='text-align:right;'>2%</td><td style='text-align:right;'>{card_fee:.2f}</td></tr>" if card_fee > 0 else ""

        st.markdown(f"""
        <div class="cash-bill">
            <div style="display:flex; justify-content:space-between; font-size:0.8rem; font-weight:bold;">
                <span>CASH BILL</span>
                <span>GST No: {ENTERPRISE_GST}</span>
            </div>
            <h3 style="text-align:center; margin-top:6px;">{ENTERPRISE_TITLE}</h3>
            <p style="text-align:center; font-weight:bold; font-size:0.85rem;">{ENTERPRISE_SUBTITLE}</p>
            <p style="text-align:center; font-size:0.75rem;">{ENTERPRISE_ADDRESS}</p>
            <div class="bill-hr"></div>
            <div style="display:flex; justify-content:space-between; font-size:0.85rem;">
                <span><b>S.No:</b> {next_sno} ({preview_cust_id})</span>
                <span><b>Date:</b> {date.today().strftime('%d/%m/%Y')}</span>
            </div>
            <div style="display:flex; justify-content:space-between; font-size:0.85rem; margin-top:4px;">
                <span><b>Name:</b> {adult_name or 'Walk-in'}</span>
                <span><b>Slot:</b> {time_in_str} - {time_out_str}</span>
            </div>
            <div class="bill-hr"></div>
            <table style="width:100%; font-size:0.85rem; border-collapse:collapse;">
                <thead>
                    <tr style="border-bottom:1px solid #854d0e;">
                        <th style="text-align:left;">DESCRIPTION</th>
                        <th style="text-align:center;">QTY</th>
                        <th style="text-align:right;">RATE</th>
                        <th style="text-align:right;">AMOUNT</th>
                    </tr>
                </thead>
                <tbody>
                    <tr>
                        <td>{pkg_display_label}</td>
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
            <div class="bill-hr"></div>
            <div style="display:flex; justify-content:space-between; font-size:1.1rem; font-weight:bold;">
                <span>Total ({payment_method})</span>
                <span>₹ {final_total:.2f}</span>
            </div>
            <p style="font-size:0.75rem; color:#4b5563; margin-top:4px;">
                Excl. GST: ₹{total_excl_gst:.2f} | Total GST: ₹{total_gst:.2f}
            </p>
            <div style="text-align:right; font-size:0.8rem; margin-top:10px; font-weight:bold;">
                For {ENTERPRISE_TITLE}<br>
                <span style="font-weight:normal;">Logged by: {user['name']} ({user['emp_id']})</span>
            </div>
        </div>
        """, unsafe_allow_html=True)

        st.caption(f"📁 Drive File Format: `{invoice_filename}`")

        if st.button("✅ Generate Official Bill & Save to Drive", type="primary", use_container_width=True):
            if not adult_name.strip() or not phone.strip():
                st.error("Please enter both the Adult Name and WhatsApp Phone Number.")
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

                # Increment S.No
                set_setting("next_sno", str(next_sno + 1))

                # Generate PDF and save locally + upload to Drive
                pdf_bytes = generate_invoice_pdf_bytes(bill_record)
                os.makedirs("saved_invoices", exist_ok=True)
                with open(os.path.join("saved_invoices", invoice_filename), "wb") as f:
                    f.write(pdf_bytes)

                ok_drive, drive_msg = upload_to_gdrive(pdf_bytes, invoice_filename, "application/pdf")
                bill_record["pdf_bytes"] = pdf_bytes
                bill_record["drive_status"] = drive_msg
                st.session_state.last_bill = bill_record
                st.rerun()

        # Post-save WhatsApp & PDF Download Actions
        if st.session_state.last_bill:
            lb = st.session_state.last_bill
            st.success(f"Bill #{lb['sno']} Logged! ({lb['drive_status']})")

            clean_phone = "".join([ch for ch in lb["phone"] if ch.isdigit()])
            if len(clean_phone) == 10:
                clean_phone = "91" + clean_phone

            wa_text = (
                f"*{ENTERPRISE_TITLE} ({ENTERPRISE_SUBTITLE})*\n"
                f"GST No: {ENTERPRISE_GST}\n"
                f"------------------------\n"
                f"S.No: {lb['sno']} | Cust ID: {lb['customer_id']}\n"
                f"Date: {lb['bill_date']}\n"
                f"Customer: {lb['adult_name']}\n"
                f"Slot: {lb['time_in']} to {lb['time_out']}\n"
                f"------------------------\n"
                f"Package ({lb['num_kids']} kids): Rs.{lb['pkg_excl_gst']:.2f}\n"
                + (f"Socks ({lb['num_socks']}): Rs.{lb['socks_excl_gst']:.2f}\n" if lb["num_socks"] > 0 else "")
                + (f"Water ({lb['num_water']}): Rs.{lb['water_excl_gst']:.2f}\n" if lb["num_water"] > 0 else "")
                + f"SGST (9%): Rs.{lb['sgst_9']:.2f}\n"
                f"CGST (9%): Rs.{lb['cgst_9']:.2f}\n"
                + (f"Water GST: Rs.{lb['water_gst_amt']:.2f}\n" if lb["water_gst_amt"] > 0 else "")
                + (f"Card Fee (2%): Rs.{lb['card_fee']:.2f}\n" if lb["card_fee"] > 0 else "")
                + f"------------------------\n"
                f"*TOTAL PAID ({lb['payment_method']}): Rs.{lb['final_total']:.2f}*\n"
                f"Thank you for visiting {ENTERPRISE_TITLE}!"
            )
            wa_url = f"https://wa.me/{clean_phone}?text={urllib.parse.quote(wa_text)}"

            st.markdown(f'<a href="{wa_url}" target="_blank" class="wa-btn">📲 Send Invoice Copy to Customer WhatsApp</a>', unsafe_allow_html=True)
            st.download_button(
                label=f"⬇️ Download PDF Invoice ({lb['invoice_filename']})",
                data=lb["pdf_bytes"],
                file_name=lb["invoice_filename"],
                mime="application/pdf",
                use_container_width=True
            )

# ==============================================================================
# PAGE 2: MONTHLY MEMBERSHIPS (ROYAL PURPLE DISTINCT UI - NO INVOICE / NO WHATSAPP)
# ==============================================================================
elif page == "👑 Monthly Memberships":
    st.markdown("""
    <div class="member-banner">
        <h2 style="margin:0; color:white;">👑 Monthly Membership Lounge & Check-In</h2>
        <p style="margin:4px 0 0 0; opacity:0.9;">
            Separate Member Zone • Attendance logs directly to Live Occupancy & Master Report without creating a bill or sending WhatsApp invoices.
        </p>
    </div>
    """, unsafe_allow_html=True)

    tab_checkin, tab_register, tab_history = st.tabs([
        "✅ Quick Member Check-In (Time In / Out)",
        "➕ Register New Monthly Member",
        "📊 Member Utilization History"
    ])

    conn = get_conn()
    members_df = pd.read_sql_query("SELECT * FROM members ORDER BY member_id DESC", conn)
    conn.close()

    with tab_checkin:
        st.markdown('<div class="member-card">', unsafe_allow_html=True)
        st.subheader("Log Member Play Session")
        if members_df.empty:
            st.info("No monthly members registered yet. Use the 'Register New Monthly Member' tab first.")
        else:
            member_options = [
                f"{row['member_id']} — {row['child_name']} (Parent: {row['adult_name']} | {row['phone']})"
                for _, row in members_df.iterrows()
            ]
            selected_member_str = st.selectbox("Select Member ID", member_options)
            selected_member_id = selected_member_str.split(" — ")[0]
            m_row = members_df[members_df["member_id"] == selected_member_id].iloc[0]

            mc1, mc2, mc3 = st.columns(3)
            now_dt = datetime.now()
            with mc1:
                visit_date = st.date_input("Visit Date", value=date.today())
            with mc2:
                m_time_in = st.time_input("Member Time In", value=now_dt.time().replace(second=0, microsecond=0))
            with mc3:
                m_time_out = st.time_input("Expected Time Out", value=(now_dt + timedelta(hours=1)).time().replace(second=0, microsecond=0))

            if st.button("👑 Log Member Attendance (No Invoice / No WhatsApp)", type="primary", use_container_width=True):
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
                st.success(f"Logged visit for Member `{m_row['member_id']}` ({m_row['child_name']}) from {m_time_in.strftime('%H:%M')} to {m_time_out.strftime('%H:%M')}!")
        st.markdown('</div>', unsafe_allow_html=True)

    with tab_register:
        st.markdown('<div class="member-card">', unsafe_allow_html=True)
        st.subheader("Create New Monthly Subscription ID")
        next_mem_num = 1001 + len(members_df)
        suggested_mem_id = f"MEM-{next_mem_num}"

        with st.form("new_member_form"):
            f1, f2 = st.columns(2)
            with f1:
                new_mem_id = st.text_input("Member ID", value=suggested_mem_id)
                child_name = st.text_input("Child Name *")
                adult_name = st.text_input("Parent / Adult Name *")
            with f2:
                m_phone = st.text_input("Phone Number *")
                start_d = st.date_input("Start Date", value=date.today())
                expiry_d = st.date_input("Expiry Date (30 Days)", value=date.today() + timedelta(days=30))
            notes = st.text_input("Notes (Optional)")
            reg_btn = st.form_submit_button("Save New Monthly Member", type="primary")

            if reg_btn:
                if not child_name.strip() or not adult_name.strip() or not m_phone.strip():
                    st.error("Please fill in Child Name, Parent Name, and Phone Number.")
                else:
                    conn = get_conn()
                    c = conn.cursor()
                    try:
                        c.execute('''INSERT INTO members (
                            member_id, child_name, adult_name, phone, start_date, expiry_date, notes, created_by
                        ) VALUES (?,?,?,?,?,?,?,?)''', (
                            new_mem_id.strip(), child_name.strip(), adult_name.strip(),
                            m_phone.strip(), start_d.strftime("%Y-%m-%d"),
                            expiry_d.strftime("%Y-%m-%d"), notes.strip(), user["emp_id"]
                        ))
                        conn.commit()
                        st.success(f"Monthly Member `{new_mem_id}` created!")
                        st.rerun()
                    except sqlite3.IntegrityError:
                        st.error("That Member ID already exists.")
                    finally:
                        conn.close()
        st.markdown('</div>', unsafe_allow_html=True)

    with tab_history:
        conn = get_conn()
        visits_df = pd.read_sql_query("SELECT * FROM member_visits ORDER BY id DESC", conn)
        conn.close()

        st.markdown("##### Member Utilization Summary (Total Visits per Member)")
        if not visits_df.empty:
            util_summary = visits_df.groupby(["member_id", "child_name", "adult_name", "phone"]).size().reset_index(name="Total Visits")
            st.dataframe(util_summary, use_container_width=True)
            st.markdown("##### Detailed Check-In Logs")
            st.dataframe(visits_df, use_container_width=True)
        else:
            st.info("No member visits logged yet.")

# ==============================================================================
# PAGE 3: LIVE OCCUPANCY & TIME-SLOT TRACKER (e.g. 10:00 TO 11:00)
# ==============================================================================
elif page == "🕒 Live Occupancy & Slot Tracker":
    st.subheader("🕒 Time-Slot Occupancy Tracker")
    st.caption("See exactly how many walk-in kids (X) and monthly members (Y) were inside the playhouse during any time window.")

    fc1, fc2, fc3 = st.columns(3)
    with fc1:
        slot_date = st.date_input("Select Date", value=date.today())
    with fc2:
        slot_start = st.time_input("From Time (e.g. 10:00)", value=time(10, 0))
    with fc3:
        slot_end = st.time_input("To Time (e.g. 11:00)", value=time(11, 0))

    slot_date_str = slot_date.strftime("%Y-%m-%d")

    conn = get_conn()
    day_tx = pd.read_sql_query("SELECT * FROM transactions WHERE bill_date=?", conn, params=(slot_date_str,))
    day_mem = pd.read_sql_query("SELECT * FROM member_visits WHERE visit_date=?", conn, params=(slot_date_str,))
    conn.close()

    # Filter overlapping walk-in bills
    active_walkins = []
    for _, row in day_tx.iterrows():
        if time_overlaps(row["time_in"], row["time_out"], slot_start, slot_end):
            active_walkins.append(row)
    walkin_df = pd.DataFrame(active_walkins)

    # Filter overlapping member visits
    active_members = []
    for _, row in day_mem.iterrows():
        if time_overlaps(row["time_in"], row["time_out"], slot_start, slot_end):
            active_members.append(row)
    mem_slot_df = pd.DataFrame(active_members)

    x_regular_kids = int(walkin_df["num_kids"].sum()) if not walkin_df.empty else 0
    y_member_kids = len(mem_slot_df)
    total_kids_in_slot = x_regular_kids + y_member_kids

    m1, m2, m3 = st.columns(3)
    m1.metric("🧒 X: Walk-In Kids in Slot", x_regular_kids, f"{len(walkin_df)} Bookings")
    m2.metric("👑 Y: Monthly Members in Slot", y_member_kids, "Active Members")
    m3.metric("🎈 Total Headcount in Playhouse", total_kids_in_slot, f"{slot_start.strftime('%H:%M')} - {slot_end.strftime('%H:%M')}")

    st.write("---")
    col_w, col_m = st.columns(2)
    with col_w:
        st.markdown(f"##### 🧾 Walk-In Customers ({slot_start.strftime('%H:%M')} – {slot_end.strftime('%H:%M')})")
        if not walkin_df.empty:
            st.dataframe(
                walkin_df[["customer_id", "adult_name", "phone", "package", "num_kids", "time_in", "time_out", "emp_name"]],
                use_container_width=True
            )
        else:
            st.info("No walk-in customers during this time slot.")

    with col_m:
        st.markdown(f"##### 👑 Monthly Members Present ({slot_start.strftime('%H:%M')} – {slot_end.strftime('%H:%M')})")
        if not mem_slot_df.empty:
            st.dataframe(
                mem_slot_df[["member_id", "child_name", "adult_name", "phone", "time_in", "time_out", "logged_by_name"]],
                use_container_width=True
            )
        else:
            st.info("No monthly members logged during this time slot.")

# ==============================================================================
# PAGE 4: 24-HOUR SHIFT CLOSING & RESET TO NIL
# ==============================================================================
elif page == "🔒 Shift Closing (24-Hr Reset)":
    st.subheader("🔒 Active Shift Summary & Complete Closing")
    st.caption("Closing the shift consolidates all active transactions into a Master Excel Report, sends it to the Admin Gmail & Drive, and resets the shift dashboard back to zero (Nil) for the next day.")

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
    k2.metric("Shift Total Revenue", f"₹ {my_revenue:.2f}")
    k3.metric("Cash / UPI", f"₹ {my_cash:.0f} / ₹ {my_upi:.0f}")
    k4.metric("Card (+2%)", f"₹ {my_card:.2f}")

    st.markdown("##### 📋 Active Shift Bills (Current 24-Hr Cycle)")
    if not active_tx.empty:
        st.dataframe(
            active_tx[["sno", "customer_id", "adult_name", "phone", "package", "num_kids", "time_in", "time_out", "payment_method", "final_total", "emp_name"]],
            use_container_width=True
        )
    else:
        st.success("✨ Dashboard is currently at NIL (0 active transactions). Ready for a fresh shift!")

    st.write("---")
    st.markdown("### 🚨 Complete Closing (End of 24-Hour Shift)")
    st.warning("Clicking **Complete Closing** will generate the consolidated Master Excel Report, send it to the Admin's Email & Google Drive, and reset all active shift counters to **0 (Nil)** for tomorrow.")

    if not all_active_tx.empty or not all_active_visits.empty:
        emp_summary = all_active_tx.groupby(["emp_id", "emp_name", "payment_method"]).agg(
            Transactions=("id", "count"),
            Total_Amount=("final_total", "sum")
        ).reset_index() if not all_active_tx.empty else pd.DataFrame()

        master_excel_bytes = build_master_excel(all_active_tx, emp_summary, all_active_visits)
        closing_filename = f"Master_Closing_Report_{datetime.now().strftime('%Y-%m-%d_%H-%M')}.xlsx"

        st.download_button(
            "⬇️ Download Current Shift Master Excel (.xlsx)",
            data=master_excel_bytes,
            file_name=closing_filename,
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

        if st.button("✅ COMPLETE CLOSING — Send Master Report & Reset Dashboard to Nil", type="primary", use_container_width=True):
            # 1. Email Excel Report to Admin
            ok_mail, mail_msg = send_email_with_excel(
                master_excel_bytes,
                closing_filename,
                subject=f"[{ENTERPRISE_TITLE}] Complete Shift Closing Report - {date.today()}",
                body_text=f"Shift closed by {user['name']} ({user['emp_id']}). Attached is the consolidated Master Excel Report."
            )
            # 2. Upload Master Excel to Admin Google Drive
            ok_drive, drive_msg = upload_to_gdrive(
                master_excel_bytes,
                closing_filename,
                mime_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
            # 3. Reset active shift transactions & visits to Nil (is_closed = 1)
            conn = get_conn()
            c = conn.cursor()
            c.execute("UPDATE transactions SET is_closed=1 WHERE is_closed=0")
            c.execute("UPDATE member_visits SET is_closed=1 WHERE is_closed=0")
            conn.commit()
            conn.close()

            st.session_state.last_bill = None
            st.success(f"Shift Closed & Reset to Nil! | {mail_msg} | {drive_msg}")
            st.rerun()

# ==============================================================================
# PAGE 5: ADMIN MASTER PORTAL & EMPLOYEE MANAGEMENT
# ==============================================================================
elif page == "📊 Admin Master Portal & Staff" and user["role"] == "admin":
    st.subheader("📊 Admin Master Consolidation & Staff Management")

    t_master, t_staff, t_settings = st.tabs([
        "📈 Consolidated Master Report",
        "👥 Create & Manage Employee Accounts",
        "⚙️ GST, S.No & Admin Gmail Settings"
    ])

    with t_master:
        conn = get_conn()
        all_tx = pd.read_sql_query("SELECT * FROM transactions ORDER BY id DESC", conn)
        all_visits = pd.read_sql_query("SELECT * FROM member_visits ORDER BY id DESC", conn)
        conn.close()

        if not all_tx.empty:
            st.markdown("##### 👨‍💼 Employee-Wise Consolidated Performance")
            emp_perf = all_tx.groupby(["emp_id", "emp_name"]).agg(
                Total_Bills=("id", "count"),
                Kids_Served=("num_kids", "sum"),
                Excl_GST_Total=("total_excl_gst", "sum"),
                GST_Collected=("total_gst", "sum"),
                Card_Fees=("card_fee", "sum"),
                Grand_Total_Collected=("final_total", "sum")
            ).reset_index()
            st.dataframe(emp_perf, use_container_width=True)

            full_excel = build_master_excel(all_tx, emp_perf, all_visits)
            st.download_button(
                "📥 Download Complete Historical Master Excel Report",
                data=full_excel,
                file_name=f"Algebra_Playhouse_Master_{date.today()}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                type="primary"
            )

            st.markdown("##### 🧾 All Logged Invoices (Active + Archived Shifts)")
            st.dataframe(all_tx, use_container_width=True)
        else:
            st.info("No transactions logged yet.")

    with t_staff:
        c_add, c_list = st.columns([1, 1.3])
        with c_add:
            st.markdown("##### ➕ Add Employee / Admin Account")
            with st.form("add_emp_form"):
                new_emp_id = st.text_input("Employee ID *", placeholder="e.g. EMP01")
                new_emp_name = st.text_input("Employee Full Name *", placeholder="e.g. Karthik")
                new_emp_email = st.text_input("Email / Gmail", placeholder="staff@gmail.com")
                new_emp_pwd = st.text_input("Password *", type="password")
                new_emp_role = st.selectbox("Role", ["employee", "admin"])
                save_emp = st.form_submit_button("Create Account", type="primary")

                if save_emp:
                    if not new_emp_id.strip() or not new_emp_name.strip() or not new_emp_pwd.strip():
                        st.error("Employee ID, Name, and Password are required.")
                    else:
                        conn = get_conn()
                        c = conn.cursor()
                        try:
                            c.execute(
                                "INSERT INTO users (emp_id, name, email, password, role) VALUES (?,?,?,?,?)",
                                (new_emp_id.strip(), new_emp_name.strip(), new_emp_email.strip(), new_emp_pwd.strip(), new_emp_role)
                            )
                            conn.commit()
                            st.success(f"Created account `{new_emp_id}` for {new_emp_name}!")
                            st.rerun()
                        except sqlite3.IntegrityError:
                            st.error("Employee ID already exists.")
                        finally:
                            conn.close()

        with c_list:
            st.markdown("##### 👥 Registered Staff Accounts")
            conn = get_conn()
            users_df = pd.read_sql_query("SELECT emp_id, name, email, role FROM users", conn)
            conn.close()
            st.dataframe(users_df, use_container_width=True)

    with t_settings:
        st.markdown("##### ⚙️ Playhouse Master Configuration")
        curr_sno = get_setting("next_sno", "1079")
        curr_admin_email = get_setting("admin_email", "admin@gmail.com")
        curr_card_mode = get_setting("card_fee_base", "Including GST")

        with st.form("settings_form"):
            new_admin_email = st.text_input("Admin Master Gmail ID (Receives Closing Excel Reports)", value=curr_admin_email)
            new_next_sno = st.number_input("Next Cash Bill S.No (Matches Physical Bill Book)", min_value=1, value=int(curr_sno))
            new_card_mode = st.selectbox(
                "2% Card Payment Fee Calculation Base",
                ["Including GST", "Excluding GST"],
                index=0 if curr_card_mode == "Including GST" else 1
            )
            if st.form_submit_button("Save Master Settings", type="primary"):
                set_setting("admin_email", new_admin_email.strip())
                set_setting("next_sno", str(new_next_sno))
                set_setting("card_fee_base", new_card_mode)
                # Also update ADMIN01 email so Admin can log in with their Gmail directly
                conn = get_conn()
                c = conn.cursor()
                c.execute("UPDATE users SET email=? WHERE emp_id='ADMIN01'", (new_admin_email.strip(),))
                conn.commit()
                conn.close()
                st.success("Master settings updated! You can now log in with your Admin Gmail.")
