import streamlit as st

# Configure page layout and title
st.set_page_config(page_title="The aLGeBrA Playhouse - Billing", page_icon="🎈", layout="centered")

# Rate card rates (Inclusive of 18% GST per head/package)
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

SOCK_RATE_PER_PAIR = 50  # Inclusive of GST

st.title("🎈 The aLGeBrA Playhouse")
st.subheader("Billing Calculator")
st.write("---")

# Customer / Bill Details
col1, col2 = st.columns(2)
with col1:
    customer_name = st.text_input("Customer Name", value="Walk-in Customer")
with col2:
    selected_package = st.selectbox("Select Package", list(RATES.keys()))

col3, col4 = st.columns(2)
with col3:
    num_kids = st.number_input("Number of Kids Playing", min_value=1, step=1, value=1)
with col4:
    num_socks = st.number_input("Number of Socks Required (₹50 each)", min_value=0, step=1, value=0)

# Calculations
base_rate = RATES[selected_package]

# Apply group discount: ₹50 discount per head if more than 1 child
discount_per_kid = 50 if num_kids > 1 else 0
effective_rate_per_kid = base_rate - discount_per_kid

# Gross package and socks total (inclusive of GST)
total_package_inclusive = effective_rate_per_kid * num_kids
total_socks_inclusive = num_socks * SOCK_RATE_PER_PAIR
total_bill_inclusive = total_package_inclusive + total_socks_inclusive

# Standard receipt reverse breakdown (18% GST = 9% SGST + 9% CGST)
sgst_amount = round(total_bill_inclusive * 0.09)
cgst_amount = round(total_bill_inclusive * 0.09)

# Base taxable amounts (excluding 18% GST)
package_taxable = round(total_package_inclusive * 0.82)
socks_taxable = round(total_socks_inclusive * 0.82)
subtotal_taxable = package_taxable + socks_taxable

st.write("---")
st.subheader("🧾 Invoice Summary")

if num_kids > 1:
    st.success(f"🎉 Group discount applied: ₹50 off per head (-₹{discount_per_kid * num_kids} total)")

# Display formatted invoice table
invoice_data = [
    {
        "Description": f"{selected_package} ({num_kids} kids)",
        "Rate/Item (Inc.)": f"₹{effective_rate_per_kid}",
        "Qty": num_kids,
        "Excl. 18% GST": f"₹{package_taxable}",
        "Total (Inc.)": f"₹{total_package_inclusive}"
    }
]

if num_socks > 0:
    invoice_data.append({
        "Description": "Socks",
        "Rate/Item (Inc.)": f"₹{SOCK_RATE_PER_PAIR}",
        "Qty": num_socks,
        "Excl. 18% GST": f"₹{socks_taxable}",
        "Total (Inc.)": f"₹{total_socks_inclusive}"
    })

st.table(invoice_data)

# Breakdown totals matching the yellow receipt layout
st.markdown(
    f"""
    **Subtotal (Excl. GST):** ₹{subtotal_taxable}  
    **SGST (9%):** ₹{sgst_amount}  
    **CGST (9%):** ₹{cgst_amount}  
    ### **Total Amount Payable: ₹{total_bill_inclusive}**
    """
)
