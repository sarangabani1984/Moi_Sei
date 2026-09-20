import os
import json
import datetime
import urllib.parse
import urllib.request

import streamlit as st

from db import (
    create_family,
    change_event_receiver,
    get_active_events,
    get_active_families_for_search,
    get_connection,
    get_family,
    process_contribution,
    process_group_contribution,
    search_families,
    set_family_password,
    update_family_profile,
)
from notifications import send_contribution_whatsapp, broadcast_event_announcement, send_green_api_whatsapp


def get_admin_password():
    """Read the staff password from Streamlit Secrets or an environment variable."""
    try:
        if "MOI_SEI_ADMIN_PASSWORD" in st.secrets:
            return str(st.secrets["MOI_SEI_ADMIN_PASSWORD"])
    except Exception:
        pass
    return os.getenv("MOI_SEI_ADMIN_PASSWORD", "")


def require_admin_login():
    """Automatically authenticate user (no password required)."""
    # Auto-set admin_authenticated to True
    if not st.session_state.get("admin_authenticated"):
        st.session_state["admin_authenticated"] = True
    
    # Show logout button in sidebar
    if st.sidebar.button("Log out"):
        st.session_state.pop("admin_authenticated", None)
        st.rerun()


def show_whatsapp_test_panel():
    """Test WhatsApp delivery to any phone number."""
    with st.sidebar:
        st.markdown("---")
        st.markdown("### 📱 WhatsApp Test")
        
        test_phone = st.text_input(
            "Test phone number",
            placeholder="7411346811",
            help="Enter 10-digit phone number without +91",
            key="whatsapp_test_phone"
        )
        
        test_message = st.text_area(
            "Test message",
            value="🧪 Test message from Moi Sei app. If you see this, WhatsApp delivery is working!",
            height=80,
            key="whatsapp_test_message"
        )
        
        if st.button("🚀 Send Test WhatsApp", use_container_width=True):
            if not test_phone or len(test_phone) != 10 or not test_phone.isdigit():
                st.error("❌ Invalid phone. Must be 10 digits (e.g., 7411346811)")
            else:
                try:
                    success, msg = send_green_api_whatsapp(
                        id_instance=st.secrets.get("GREEN_API_ID_INSTANCE", ""),
                        api_token=st.secrets.get("GREEN_API_TOKEN_INSTANCE", ""),
                        phone_number=test_phone,
                        message_text=test_message,
                        default_country_code="+91"
                    )
                    
                    if success:
                        st.sidebar.success(f"✅ Sent! Message ID: {msg}")
                    else:
                        st.sidebar.error(f"❌ Failed: {msg}")
                except Exception as e:
                    st.sidebar.error(f"⚠️ Error: {str(e)}")


def initialize_contribution_amount():
    """Initialize contribution_amount in global scope if not set."""
    if "contribution_amount" not in st.session_state:
        st.session_state["contribution_amount"] = 50.0
    return st.session_state["contribution_amount"]


def set_family_form_values(family):
    """Put a selected family's stored details into the editable form fields."""
    # Reset every widget first so blank values from this family do not retain a prior family's data.
    for key in (
        "family_phone_number",
        "family_native_place",
        "family_current_place",
        "family_husband_name",
        "family_husband_job",
        "family_wife_name",
        "family_wife_job",
        "family_others",
        "family_deity",
        "family_email",
        "family_search_alias",
        "family_password",
    ):
        st.session_state[key] = ""

    st.session_state["family_id"] = family["id"]
    st.session_state["family_phone_number"] = family["phone_number"] or ""
    st.session_state["family_native_place"] = family.get("native_place") or ""
    st.session_state["family_current_place"] = family.get("current_place") or ""
    st.session_state["family_husband_name"] = family["husband_name"] or ""
    st.session_state["family_husband_job"] = family["husband_job"] or ""
    st.session_state["family_wife_name"] = family["wife_name"] or ""
    st.session_state["family_wife_job"] = family.get("wife_job") or ""
    st.session_state["family_others"] = family.get("others") or ""
    st.session_state["family_deity"] = family.get("family_deity") or ""
    st.session_state["family_email"] = family["email"] or ""
    st.session_state["family_search_alias"] = family.get("search_alias") or ""
    st.session_state["family_password"] = ""


def clear_family_form():
    """Clear form by resetting family_id only. Widgets auto-clear on rerun."""
    st.session_state["family_id"] = None
    st.session_state.pop("family_to_load", None)
    st.session_state.pop("selected_event_for_contribution", None)
    st.session_state.pop("contribution_receiver", None)
    # Reset password to default "111111" for testing
    st.session_state["family_password"] = "111111"


def smart_parse_and_search(pasted_text):
    """Smart search: first value→phone search, text-only→husband search, otherwise→parse as new user."""
    if not pasted_text.strip():
        return None

    # Get first word (phone or name)
    first_word = pasted_text.split()[0].strip() if pasted_text.split() else ""
    has_digits = any(char.isdigit() for char in first_word)
    
    # Try to search by phone if first word has digits
    if has_digits:
        phone_matches = search_families(first_word)
        if phone_matches:
            # Return ALL matches (not just first) so user can select
            return {"multiple_matches": phone_matches}
    else:
        # Try to search by name
        name_matches = search_families(first_word)
        if name_matches:
            # Return ALL matches (not just first) so user can select
            return {"multiple_matches": name_matches}
    
    # No match found → parse & convert to Tamil for new user
    parsed = parse_family_details(pasted_text)
    tamil_parsed = convert_parsed_fields_to_tamil(parsed)
    return tamil_parsed


def convert_name_keep_initial(name):
    """Convert name to Tamil but keep the initial part (before dot) in English.
    Example: s.anandselvaraj → s.ஆனந்தசெல்வராஜ்
    """
    if not name or "." not in name:
        return name  # No initial, convert whole name
    
    parts = name.split(".", 1)  # Split on first dot only
    initial = parts[0] + "."  # Keep initial + dot
    name_part = parts[1].strip() if len(parts) > 1 else ""
    
    if not name_part:
        return initial
    
    # Convert only the name part to Tamil
    tamil_name = transliterate_to_tamil(name_part)
    return initial + tamil_name


def convert_pasted_to_tamil(pasted_text):
    """Convert space-separated pasted text to Tamil (for text fields only, keep numbers as-is)."""
    tamil_words = []
    for word in pasted_text.split():
        word = word.strip()
        # Convert only non-numeric words to Tamil
        if word and not any(c.isdigit() for c in word):
            tamil_words.append(transliterate_to_tamil(word))
        else:
            tamil_words.append(word)  # Keep phone/amount as-is
    return " ".join(tamil_words)


def convert_parsed_fields_to_tamil(parsed_details):
    """Convert all text fields to Tamil, keep numeric fields as-is."""
    if not parsed_details:
        return parsed_details
    
    converted = parsed_details.copy()
    
    # Text fields to convert to Tamil (skip phone_number, husband_name, wife_name, and contribution_amount)
    tamil_fields = [
        "family_native_place",
        "family_current_place",
        "family_husband_job",
        "family_wife_job",
        "family_others",
    ]
    
    for field in tamil_fields:
        if field in converted and converted[field]:
            converted[field] = transliterate_to_tamil(str(converted[field]))
    
    return converted


def parse_family_details(pasted_text):
    """Parse space-separated quick-entry. Intelligently extracts amount from end first.
    Format: Phone Native_Place Current_Place Husband_Name Husband_Job Wife Wife_Job Place Others Amount
    
    Example: 1234 china hosur sarangabani IT Saranya housewife 10000
    → Phone=1234, Native=china, Current=hosur, Husband=sarangabani, Job=IT, Wife=Saranya, WifeJob=housewife, 
      Place=(empty), Others=(empty), Amount=10000
    """
    # Split by space (single or multiple spaces treated as one delimiter)
    values = pasted_text.split()
    
    parsed_details = {}
    
    # Field mapping: positional order (all text fields first, amount last)
    text_fields = (
        "family_phone_number",
        "family_native_place",
        "family_current_place",
        "family_husband_name",
        "family_husband_job",
        "family_wife_name",
        "family_wife_job",
        "family_others",
    )
    
    amount_value = None
    
    # **Smart extraction**: If last value is numeric, treat it as amount
    if values:
        last_val = values[-1].strip()
        try:
            amount_value = float(last_val)
            values = values[:-1]  # Remove amount from values list
        except ValueError:
            # Last value is not numeric, keep it as-is
            pass
    
    # Map remaining values to text fields
    for field_name, value in zip(text_fields, values):
        parsed_details[field_name] = value.strip()
    
    # Fill any missing text fields with empty strings
    for field_name in text_fields:
        if field_name not in parsed_details:
            parsed_details[field_name] = ""
    
    # Set amount if extracted
    if amount_value is not None:
        parsed_details["contribution_amount"] = amount_value

    return parsed_details


def transliterate_to_tamil(text):
    """Return the first Tamil suggestion for Tanglish text, or the original text on failure."""
    if not text.strip():
        return text
    query = urllib.parse.urlencode(
        {"text": text, "itc": "ta-t-i0-und", "num": 1, "cp": 0, "cs": 1, "ie": "utf-8", "oe": "utf-8"}
    )
    try:
        with urllib.request.urlopen(
            f"https://inputtools.google.com/request?{query}", timeout=5
        ) as response:
            payload = json.loads(response.read().decode("utf-8"))
        suggestions = payload[1][0][1]
        return suggestions[0] if suggestions else text
    except Exception:
        return text


st.set_page_config(page_title="மொய்செய்", page_icon="ம", layout="wide")

# Custom CSS for styled boxes in columns
st.markdown("""
<style>
    .box-container {
        border: 2px solid #d4a5d4;
        border-radius: 12px;
        padding: 20px 18px;
        background: linear-gradient(135deg, #f9f5fb 0%, #faf8fc 100%);
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.08);
        margin: 0 0 0 0;
    }
    .box-container-dark {
        border: 2px solid #d4a5d4;
        border-radius: 12px;
        padding: 20px 18px;
        background: linear-gradient(135deg, #fef9f3 0%, #fffbf7 100%);
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.08);
    }
    .box-title {
        font-size: 1.2rem;
        font-weight: 700;
        color: #000000;
        background-color: #f4b942;
        padding: 6px 12px;
        margin: -20px -18px 8px -18px;
        border-radius: 10px 10px 0 0;
        display: block;
    }
</style>
""", unsafe_allow_html=True)

st.markdown(
    """
    <div style="text-align: center; padding: 0.35rem 0 1rem;">
        <div style="
            color: #f4b942;
            font-size: 3.2rem;
            font-weight: 800;
            letter-spacing: 0.04em;
            line-height: 1.15;
            text-shadow: 0 2px 14px rgba(244, 185, 66, 0.28);
        ">மொய்செய்</div>
        <div style="color: #e7a9c5; font-size: 1rem; margin-top: 0.25rem;">
            குடும்ப பதிவு மற்றும் பங்களிப்பு நிர்வாகம்
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)
require_admin_login()
show_whatsapp_test_panel()

try:
    get_connection()
except Exception as error:
    st.error("Could not connect to database.")
    st.code(str(error))
    st.stop()

# LOAD EXISTING FAMILY FIRST (before form field initialization)
# This ensures form fields get the correct values when initialized
if "family_to_load" in st.session_state:
    family_id = st.session_state.pop("family_to_load")
    family = get_family(family_id)
    if family:
        st.session_state["family_id"] = family_id
        # Safely set form field values from database
        st.session_state["family_phone_number"] = family.get("phone_number", "")
        st.session_state["family_native_place"] = family.get("native_place", "")
        st.session_state["family_current_place"] = family.get("current_place", "")
        st.session_state["family_husband_name"] = family.get("husband_name", "")
        st.session_state["family_husband_job"] = family.get("husband_job", "")
        st.session_state["family_wife_name"] = family.get("wife_name", "")
        st.session_state["family_wife_job"] = family.get("wife_job", "")
        st.session_state["family_others"] = family.get("others", "")
        st.session_state["family_deity"] = family.get("family_deity", "")
        st.session_state["family_email"] = family.get("email", "")
        st.session_state["family_search_alias"] = family.get("search_alias", "")
        # Keep password as default "111111" for testing
        st.session_state["family_password"] = "111111"
        # Clear the quick paste box after loading family
        st.session_state["family_paste_details"] = ""

# Initialize all form field keys early to prevent NoneType errors
form_field_keys = [
    "family_phone_number", "family_native_place", "family_current_place",
    "family_husband_name", "family_husband_job", "family_wife_name", 
    "family_wife_job", "family_others", "family_deity", "family_email", 
    "family_search_alias", "family_password"
]
for key in form_field_keys:
    if key not in st.session_state:
        # Set default password to "111111" for testing
        st.session_state[key] = "111111" if key == "family_password" else ""

# Initialize contribution_amount early (before any widgets that use it)
initialize_contribution_amount()

# ============================================================================
# TOP SECTION: Event Setup & Event Detail
# ============================================================================
st.subheader("Select Event & Contribute")

top_col1, top_col2, top_col3 = st.columns([2, 1, 0.8])

with top_col1:
    st.caption("Choose the event for today's collection.")
    events = get_active_events()
    event_options = {
        f"{event['event_id']} | {event['event_name']} | {event['event_date']}": event
        for event in events
    }
    if event_options:
        event_label = st.selectbox("Event for today's collection", list(event_options), key="selected_event_for_contribution")
        selected_event = event_options[event_label]
    else:
        selected_event = None
        st.warning("No active events are available.")

with top_col2:
    # Event detail box in top right
    if event_options:
        event_label_text = list(event_options.keys())[0]
        st.markdown('<div class="box-container"><div class="box-title">📅 Event Detail</div>', unsafe_allow_html=True)
        st.info(event_label_text)
        st.markdown('</div>', unsafe_allow_html=True)

with top_col3:
    # Group Mode toggle
    st.markdown("<div style='height: 20px;'></div>", unsafe_allow_html=True)
    if st.checkbox("👥 Group Mode", value=st.session_state.get("group_mode", False), key="group_mode"):
        st.caption("Record multiple families at once")
    else:
        if "group_family_matches" in st.session_state:
            del st.session_state["group_family_matches"]

# ============================================================================
# QUICK PASTE BOX (Full Width)
# ============================================================================
with st.container():
    group_mode = st.session_state.get("group_mode", False)
    if group_mode:
        st.markdown('<div class="box-container"><div class="box-title">📋 Group Contribution Mode</div>', unsafe_allow_html=True)
        st.caption("Paste phone numbers or names (one per line) to add multiple families")
    else:
        st.markdown('<div class="box-container"><div class="box-title">📋 Quick Paste Box</div>', unsafe_allow_html=True)
        st.caption("Smart search: text→husband name, numbers→phone, new→sequence order")
        st.caption("(New users: Mobile, Husband, Place, Amount — in that order)")
    
    def auto_populate_on_paste():
        """Smart search: text→husband name, numbers→phone, no match→parse as new user. Auto-convert to Tamil."""
        pasted_text = st.session_state.get("family_paste_details", "").strip()
        group_mode = st.session_state.get("group_mode", False)
        
        if not pasted_text:
            return
        
        if group_mode:
            # GROUP MODE: Parse multiple lines as phone numbers/names
            lines = [line.strip() for line in pasted_text.split("\n") if line.strip()]
            group_matches = {}
            for line in lines:
                matches = search_families(line)
                if matches:
                    for match in matches:
                        family_id = match["id"]
                        if family_id not in group_matches:
                            group_matches[family_id] = match
            st.session_state["group_family_matches"] = group_matches
        else:
            # NORMAL MODE: Smart search single entry
            result = smart_parse_and_search(pasted_text)
            if result:
                if "multiple_matches" in result:
                    # Multiple families found → show options for user to select
                    matches = result["multiple_matches"]
                    if len(matches) == 1:
                        # Only one match → auto-load it
                        st.session_state["family_to_load"] = matches[0]["id"]
                        st.session_state.pop("family_id", None)
                        st.rerun()
                    else:
                        # Multiple matches → show list for user to select
                        st.session_state["multiple_family_matches"] = matches
                        st.session_state.pop("family_id", None)
                else:
                    # No match → parse as new user with Tamil already converted
                    st.session_state["parsed_family_details"] = result
                    # Also update contribution_amount if present in parsed data
                    if "contribution_amount" in result:
                        st.session_state["contribution_amount"] = result["contribution_amount"]
                    st.session_state.pop("family_id", None)
                    # Mark form as ready to auto-save
                    st.session_state["form_auto_populated_valid"] = True
                    st.rerun()  # Trigger rerun to apply parsed values and amount
    
    st.text_area(
        "Paste details",
        key="family_paste_details",
        placeholder="New user format (space-separated):\n7411346811 madras madras Rajesh engineer Priya homemaker notes 1000\n\nField order: Phone NativePlace CurrentPlace Husband HusbandJob Wife WifeJob Others Amount",
        height=50,
        on_change=auto_populate_on_paste,
    )
    st.markdown('</div>', unsafe_allow_html=True)

# Display multiple family matches (for user to select from)
if "multiple_family_matches" in st.session_state:
    matches = st.session_state.pop("multiple_family_matches")
    if matches:
        st.info(f"🔍 Found **{len(matches)} matching families**. Select the one you want:")
        cols = st.columns(len(matches) if len(matches) <= 3 else 2)
        for idx, match in enumerate(matches):
            col = cols[idx % len(cols)]
            with col:
                label = f"**{match['husband_name']}**\n📱 {match['phone_number']}"
                if st.button(label, key=f"match_family_{match['id']}", use_container_width=True):
                    st.session_state["family_to_load"] = match["id"]
                    st.session_state.pop("multiple_family_matches", None)
                    st.rerun()

st.divider()

# ============================================================================
# GROUP MODE SECTION (if enabled)
# ============================================================================
if st.session_state.get("group_mode", False):
    with st.container():
        st.markdown('<div class="box-container"><div class="box-title">👥 Selected Families</div>', unsafe_allow_html=True)
        
        group_matches = st.session_state.get("group_family_matches", {})
        if group_matches:
            # Display selected families
            family_list = []
            total_selected = len(group_matches)
            for fam_id, fam in group_matches.items():
                family_list.append(f"✓ {fam['husband_name']} ({fam['phone_number']})")
            
            st.info(f"**{total_selected} families selected:**\n" + "\n".join(family_list))
            
            # Group amount input
            col_label, col_input = st.columns([0.3, 0.7])
            with col_label:
                st.markdown("**Amount per family*** ", unsafe_allow_html=True)
            with col_input:
                group_amount = st.number_input(
                    "Amount per family",
                    value=50.0,
                    min_value=1.0,
                    step=1.0,
                    key="group_contribution_amount",
                    label_visibility="collapsed"
                )
            
            # Group Total Preview
            group_total = group_amount * total_selected
            st.metric("Group Total", f"₹{group_total:.2f}")
            
            # Record Group Contribution button
            if st.button("🎯 Record Group Contribution", type="primary", use_container_width=True):
                if not st.session_state.get("selected_event_for_contribution"):
                    st.error("Please select an event first.")
                else:
                    selected_event = event_options.get(st.session_state.get("selected_event_for_contribution"))
                    if selected_event:
                        contributor_ids = list(group_matches.keys())
                        # For group mode, receiver is the first contributor (or locked host)
                        # Actually, in group mode, we need a receiver. Let's assume the event has a host.
                        receiver_id = selected_event.get("host_user_id")
                        if not receiver_id:
                            st.error("Event must have a receiver/host assigned. Try recording one normal contribution first.")
                        else:
                            success, result = process_group_contribution(
                                contributor_ids,
                                receiver_id,
                                selected_event["event_id"],
                                group_amount
                            )
                            if success:
                                st.success(f"✓ Group contribution recorded! {total_selected} families × ₹{group_amount} = ₹{group_total}")
                                st.info(f"Group ID: {result} (for receipt tracking)")
                                # Clear group mode
                                st.session_state["family_paste_details"] = ""
                                st.session_state.pop("group_family_matches", None)
                                st.rerun()
                            else:
                                st.error(f"Error: {result}")
        else:
            st.warning("Paste family phone numbers/names above to search and add them.")
        
        st.markdown('</div>', unsafe_allow_html=True)

# ============================================================================
# 3-COLUMN LAYOUT: Family Details | Cash Denomination | Receipt Preview
# ============================================================================
# (Hidden in Group Mode)
if not st.session_state.get("group_mode", False):
    # Show save confirmation if present
    if "family_save_message" in st.session_state:
        message = st.session_state.pop("family_save_message")
        st.success(f"✅ {message}")
        st.balloons()  # Celebration animation
    
    # Show contribution confirmation if present
    if "contribution_save_message" in st.session_state:
        message = st.session_state.pop("contribution_save_message")
        st.success(f"✅ {message}")
        st.balloons()  # Celebration animation
        
        # Show WhatsApp message content if available (RIGHT BELOW SUCCESS)
        if "whatsapp_message_content" in st.session_state:
            whatsapp_text = st.session_state.pop("whatsapp_message_content")
            st.warning("📱 **WhatsApp Message Sent to Contributor:**")
            st.code(whatsapp_text, language="text")

    # Auto-populate from quick paste
    if "parsed_family_details" in st.session_state:
        parsed = st.session_state.pop("parsed_family_details")
        for field_name, value in parsed.items():
            st.session_state[field_name] = value

    if "tamil_converted_details" in st.session_state:
        converted = st.session_state.pop("tamil_converted_details")
        for field_name, value in converted.items():
            st.session_state[field_name] = value

    # Create 3-column layout
    family_col, denomination_col, receipt_col = st.columns([1, 0.9, 1.5], gap="medium")

    # ====== COLUMN 1: FAMILY DETAILS ======
    with family_col:
        st.markdown('<div class="box-container"><div class="box-title">📋 Family Details</div>', unsafe_allow_html=True)
        st.caption("Search or add family.")
        
        if st.button("➕ New Family", type="secondary", use_container_width=True):
            st.rerun()

        # ============ ORDERED FIELDS ============
        # 1. Phone
        col_label, col_input = st.columns([0.2, 0.8])
        with col_label:
            st.markdown("**Phone*** ", unsafe_allow_html=True)
        with col_input:
            phone_number = st.text_input("Phone *", key="family_phone_number", placeholder="Mobile digits", label_visibility="collapsed")
        
        if phone_number.strip() and not st.session_state.get("family_id"):
            phone_matches = [
                family_match
                for family_match in search_families(phone_number)
                if phone_number.strip() in family_match["phone_number"]
            ]
            if phone_matches:
                st.caption("Matching families")
                for family_match in phone_matches:
                    label = (
                        f"{family_match['husband_name']} | {family_match['phone_number']}"
                    )
                    if st.button(label, key=f"phone_match_{family_match['id']}", use_container_width=True):
                        st.session_state["family_to_load"] = family_match["id"]
                        st.rerun()

        # 2. Native Place
        col_label, col_input = st.columns([0.2, 0.8])
        with col_label:
            st.markdown("**Native Place** ", unsafe_allow_html=True)
        with col_input:
            native_place = st.text_input("Native Place", key="family_native_place", label_visibility="collapsed")

        # 3. Current Place
        col_label, col_input = st.columns([0.2, 0.8])
        with col_label:
            st.markdown("**Current Place** ", unsafe_allow_html=True)
        with col_input:
            current_place = st.text_input("Current Place", key="family_current_place", label_visibility="collapsed")

        # 4. Husband Name (Initial)
        col_label, col_input = st.columns([0.2, 0.8])
        with col_label:
            st.markdown("**Husband*** ", unsafe_allow_html=True)
        with col_input:
            husband_name = st.text_input("Husband *", key="family_husband_name", label_visibility="collapsed")

        # 5. Husband Job
        col_label, col_input = st.columns([0.2, 0.8])
        with col_label:
            st.markdown("**Husband Job** ", unsafe_allow_html=True)
        with col_input:
            husband_job = st.text_input("Husband Job", key="family_husband_job", label_visibility="collapsed")

        # 6. Wife
        col_label, col_input = st.columns([0.2, 0.8])
        with col_label:
            st.markdown("**Wife*** ", unsafe_allow_html=True)
        with col_input:
            wife_name = st.text_input("Wife *", key="family_wife_name", label_visibility="collapsed")

        # 7. Wife Job
        col_label, col_input = st.columns([0.2, 0.8])
        with col_label:
            st.markdown("**Wife Job** ", unsafe_allow_html=True)
        with col_input:
            wife_job = st.text_input("Wife Job", key="family_wife_job", label_visibility="collapsed")

        # 9. Others
        col_label, col_input = st.columns([0.2, 0.8])
        with col_label:
            st.markdown("**Others** ", unsafe_allow_html=True)
        with col_input:
            others = st.text_input("Others", key="family_others", label_visibility="collapsed")

        # Password field
        col_label, col_input = st.columns([0.2, 0.8])
        with col_label:
            st.markdown("**Password** ", unsafe_allow_html=True)
        with col_input:
            portal_password = st.text_input("Password", key="family_password", type="password", label_visibility="collapsed")
        
        # Deity, Email, Search name stay in session_state/DB but are hidden from this form.
        family_deity = st.session_state.get("family_deity", "") or ""
        email = st.session_state.get("family_email", "") or ""
        search_alias = st.session_state.get("family_search_alias", "") or ""

        existing_family_id = st.session_state.get("family_id")
        if existing_family_id:
            st.success(f"✓ Family ID {existing_family_id}")

        # Auto-save button if form was auto-populated with valid data
        form_auto_populated = st.session_state.get("form_auto_populated_valid", False)
        if form_auto_populated and not existing_family_id:
            st.info("✨ Form ready! Click below to save and jump to amount field →")
            auto_save_button = st.button("⏎ Save & Go to Amount", type="primary", use_container_width=True)
        else:
            auto_save_button = False
            save_new_family_label = "Save New"
            save_new_family = st.button(save_new_family_label, type="primary", disabled=bool(existing_family_id), use_container_width=True)

        if st.button("Clear", type="secondary", use_container_width=True):
            clear_family_form()
            st.session_state.pop("form_auto_populated_valid", None)
            st.rerun()

        save_family_changes = st.button("Save Changes", type="secondary", disabled=not bool(existing_family_id), use_container_width=True)

        if save_family_changes:
            # Check which fields are missing
            missing_fields = []
            if not husband_name.strip():
                missing_fields.append("Husband")
            if not wife_name.strip():
                missing_fields.append("Wife")
            
            if missing_fields:
                st.error(f"Missing: {', '.join(missing_fields)}")
            else:
                update_success, update_message = update_family_profile(
                    user_id=existing_family_id,
                    native_place=native_place.strip(),
                    current_place=current_place.strip(),
                    husband_name=husband_name.strip(),
                    husband_job=husband_job.strip(),
                    wife_name=wife_name.strip(),
                    wife_job=wife_job.strip(),
                    place="",  # Empty placeholder for database compatibility
                    others=others.strip(),
                    family_deity=family_deity.strip(),
                    email=email.strip(),
                    search_alias=search_alias.strip(),
                )
                if update_success:
                    st.session_state["family_to_load"] = existing_family_id
                    st.session_state["family_save_message"] = "Family updated successfully!"
                    st.rerun()
                else:
                    st.error(update_message)

        reset_password = st.button("Reset Password", type="secondary", disabled=not bool(existing_family_id), use_container_width=True)
        if reset_password:
            if not portal_password:
                st.error("Enter password.")
            elif len(portal_password) < 6:
                st.error("Min 6 chars.")
            else:
                reset_success, reset_message = set_family_password(existing_family_id, portal_password)
                if reset_success:
                    st.success("Password reset.")
                else:
                    st.error(reset_message)

        convert_to_tamil = st.button("Convert → Tamil", type="secondary", use_container_width=True)
        if convert_to_tamil:
            converted_fields = {
                "family_native_place": transliterate_to_tamil(native_place.strip()),
                "family_current_place": transliterate_to_tamil(current_place.strip()),
                "family_husband_name": convert_name_keep_initial(husband_name.strip()),  # Keep initial, convert rest
                "family_husband_job": transliterate_to_tamil(husband_job.strip()),
                "family_wife_name": convert_name_keep_initial(wife_name.strip()),  # Keep initial, convert rest
                "family_wife_job": transliterate_to_tamil(wife_job.strip()),
                "family_others": transliterate_to_tamil(others.strip()),
                "family_deity": transliterate_to_tamil(family_deity.strip()),
            }
            if husband_name.strip() and not search_alias.strip():
                converted_fields["family_search_alias"] = husband_name.strip()
            # Store converted fields to apply before next widget render
            st.session_state["tamil_converted_details"] = converted_fields
            st.rerun()

        # Handle both auto-save button and manual save button
        trigger_save = (auto_save_button and form_auto_populated) or ("save_new_family" in locals() and save_new_family)
        
        if trigger_save:
            # Check which fields are missing
            missing_fields = []
            if not phone_number.strip():
                missing_fields.append("Phone")
            if not husband_name.strip():
                missing_fields.append("Husband")
            if not wife_name.strip():
                missing_fields.append("Wife")
            if not portal_password:
                missing_fields.append("Password")
            
            if missing_fields:
                st.error(f"Missing: {', '.join(missing_fields)}")
            elif len(portal_password) < 6:
                st.error("Password must be at least 6 characters.")
            else:
                success, result = create_family(
                    phone_number=phone_number.strip(),
                    native_place=native_place.strip(),
                    current_place=current_place.strip(),
                    husband_name=husband_name.strip(),
                    husband_job=husband_job.strip(),
                    wife_name=wife_name.strip(),
                    wife_job=wife_job.strip(),
                    others=others.strip(),
                    family_deity=family_deity.strip(),
                    email=email.strip(),
                    search_alias=search_alias.strip(),
                    password=portal_password,
                )
                if success:
                    st.session_state["family_to_load"] = result
                    st.session_state["family_save_message"] = f"✅ Family saved! Now enter amount (₹) below →"
                    st.session_state["show_amount_section"] = True  # Flag to highlight amount section
                    st.session_state.pop("form_auto_populated_valid", None)
                    
                    # Send welcome WhatsApp message to new family
                    try:
                        welcome_msg = (
                            f"🎉 Welcome to *Moi Sei*! 🎉\n\n"
                            f"Dear *{husband_name.strip()}* family,\n\n"
                            f"You have been successfully registered in the Moi Sei Family Contribution Tracking System.\n\n"
                            f"📝 *Your Family ID:* {result}\n"
                            f"📱 *Portal Password:* {portal_password}\n\n"
                            f"You can now log in to track contributions and events.\n\n"
                            f"🙏 Thank you for joining our community!\n"
                            f"Best regards,\n"
                            f"Moi Sei Admin"
                        )
                        whatsapp_success, whatsapp_msg = send_green_api_whatsapp(
                            id_instance=st.secrets.get("GREEN_API_ID_INSTANCE", ""),
                            api_token=st.secrets.get("GREEN_API_TOKEN_INSTANCE", ""),
                            phone_number=phone_number.strip(),
                            message_text=welcome_msg
                        )
                        if whatsapp_success:
                            st.session_state["family_save_message"] += f"\n✅ Welcome WhatsApp sent"
                    except Exception as e:
                        pass  # Don't disrupt UI if WhatsApp fails
                    
                    st.rerun()
                else:
                    st.error("Could not save family.")
                    st.code(result)
        st.markdown('</div>', unsafe_allow_html=True)

# ====== COLUMN 2 & 3: CASH DENOMINATION + RECEIPT (always visible; Save is what stays gated) ======

existing_family_id = st.session_state.get("family_id")
selected_event = st.session_state.get("selected_event_for_contribution")
if isinstance(selected_event, str) and "|" in selected_event:
    selected_event = event_options.get(selected_event)
else:
    selected_event = None

contributor = get_family(existing_family_id) if existing_family_id else None

# Set receiver only once contributor + event are both known.
receiver = None
if contributor and selected_event:
    if selected_event["host_user_id"]:
        receiver = get_family(selected_event["host_user_id"])
    else:
        receiver_options = {
            f"{family['husband_name']} | {family['phone_number']}": family
            for family in get_active_families_for_search()
            if family["id"] != contributor["id"]
        }
        if receiver_options:
            receiver_label = denomination_col.selectbox("Receiver", list(receiver_options), key="contribution_receiver")
            receiver = receiver_options[receiver_label]
        else:
            denomination_col.error("No other families available to receive.")

denominations = (1000, 500, 200, 100, 50, 20, 10)
denomination_counts = {}
denomination_subtotals = {}

with denomination_col:
        with st.container():
            # Highlight if just saved a family
            show_amount_section = st.session_state.pop("show_amount_section", False)
            if show_amount_section:
                st.markdown('<div style="background-color: #90EE90; padding: 12px; border-radius: 8px; margin-bottom: 10px;"><strong>✨ Now enter amount (₹) and use Tab ↹ to navigate denominations</strong></div>', unsafe_allow_html=True)
            
            st.markdown('<div class="box-container-dark"><div class="box-title">💰 Cash Denomination</div>', unsafe_allow_html=True)
            
            # Amount field moved inside box for header alignment
            contribution_amount = st.number_input(
                "Amount *",
                min_value=0.01,
                step=50.0,
                format="%.2f",
                key="contribution_amount",
            )
        
        st.caption("Enter note counts (use Tab ↹ to navigate).")
        
        for denomination in denominations:
            denom_row = st.columns([0.8, 0.7, 0.9])
            with denom_row[0]:
                st.markdown(f"**₹{denomination}**")
            with denom_row[1]:
                note_count = st.number_input(
                    "Count",
                    min_value=0,
                    step=1,
                    value=0,
                    label_visibility="collapsed",
                    key=f"contribution_denomination_{denomination}",
                )
            denomination_counts[denomination] = note_count
            denomination_subtotals[denomination] = denomination * note_count
            with denom_row[2]:
                st.caption(f"₹{denomination_subtotals[denomination]:,.2f}")

        denomination_total = sum(
            denomination * note_count
            for denomination, note_count in denomination_counts.items()
        )
        note_count_total = sum(denomination_counts.values())
        denomination_matches = abs(float(contribution_amount) - float(denomination_total)) < 0.001

        # Status message and button BELOW denomination
        st.markdown("---")
        status_msg = f"**Notes:** {note_count_total} | **Cash:** ₹{denomination_total:,.2f}"
        st.write(status_msg)

        if denomination_matches:
            st.success("✓ Amount matches.")
        elif denomination_total < contribution_amount:
            st.error(f"❌ Cash ₹{denomination_total:,.2f} < ₹{contribution_amount:,.2f}")
        else:
            st.warning(f"⚠️ Cash ₹{denomination_total:,.2f} > ₹{contribution_amount:,.2f}")

        ready_to_save = bool(contributor and receiver and selected_event and denomination_matches)
        if contributor and receiver and contributor["id"] == receiver["id"]:
            st.error("Contributor ≠ Receiver")

        save_button_label = "💾 Save (Tab here, then Enter)" if not ready_to_save else "💾 Save (Tab here, then Enter) ✓ Ready"
        if st.button(save_button_label, type="primary", use_container_width=True, disabled=not ready_to_save, key="save_contribution_btn"):
            success, message = process_contribution(
                contributor["id"],
                receiver["id"],
                selected_event["event_id"],
                contribution_amount,
            )
            if success:
                st.session_state["contribution_save_message"] = f"Contribution recorded: {contributor['husband_name']} → {receiver['husband_name']} | ₹{contribution_amount:,.2f}"
                
                # Create WhatsApp message content (same format as notifications.py)
                whatsapp_message_text = (
                    f"📱 *Moi Sei Confirmation*\n\n"
                    f"Dear *{contributor['husband_name']}*,\n\n"
                    f"Your contribution of *Rs. {contribution_amount:,.2f}* for *'{selected_event['event_name']}'* "
                    f"(Host: *{receiver['husband_name']}*) has been successfully recorded.\n\n"
                    f"Thank you! 🙏"
                )
                
                # Send WhatsApp confirmation to contributor
                try:
                    whatsapp_success, whatsapp_msg = send_contribution_whatsapp(
                        contributor_phone=contributor['phone_number'],
                        contributor_name=contributor['husband_name'],
                        amount=contribution_amount,
                        event_name=selected_event['event_name'],
                        receiver_name=receiver['husband_name']
                    )
                    if whatsapp_success:
                        st.session_state["contribution_save_message"] += f"\n✅ WhatsApp sent to {contributor['phone_number']}"
                        st.session_state["whatsapp_message_content"] = whatsapp_message_text
                    else:
                        st.warning(f"⚠️ WhatsApp failed: {whatsapp_msg}")
                except Exception as e:
                    st.warning(f"⚠️ WhatsApp notification error: {str(e)}")
                
                st.rerun()
            else:
                st.error(message)
        st.markdown('</div>', unsafe_allow_html=True)

with receipt_col:
    with st.container():
        st.markdown('<div class="box-container"><div class="box-title">🧾 Receipt Preview</div>', unsafe_allow_html=True)
        st.caption("Review before saving.")
        
        if not (contributor and receiver and selected_event):
            st.info("Complete family details, pick an event, and set the receiver to preview the receipt.")
        else:
            receipt_timestamp = datetime.datetime.now().strftime("%Y-%m-%d %I:%M:%S %p")
            st.markdown(
                f"""
                <div style="text-align: center; padding: 0.3rem 0 0.5rem;">
                    <h4 style="margin: 0.2rem 0;">{selected_event['event_name']}</h4>
                    <div style="font-size: 0.9em;">Event ID: <strong>{selected_event['event_id']}</strong></div>
                    <div style="font-size: 0.9em;">Event date: <strong>{selected_event['event_date']}</strong></div>
                </div>
                """,
                unsafe_allow_html=True,
            )
            st.markdown(
                f"**Contributor:** {contributor['husband_name']}  \n"
                f"**Phone:** {contributor['phone_number']}  \n"
                f"**Receiver:** {receiver['husband_name']}  \n"
                f"**Phone:** {receiver['phone_number']}"
            )

            receipt_rows = [
                f"₹{denomination}: {denomination_counts[denomination]} notes = ₹{denomination_subtotals[denomination]:,.2f}"
                for denomination in denominations
                if denomination_counts[denomination] > 0
            ]
            st.markdown("**Breakdown:**  " + ("  \n".join(receipt_rows) if receipt_rows else "No notes entered"))

            st.markdown(
                f"**Notes:** {note_count_total} | **Cash:** ₹{denomination_total:,.2f}  \n"
                f"**Contribution:** ₹{contribution_amount:,.2f}"
            )

            receipt_text = "\n".join(
                [
                    "MOI SEI CONTRIBUTION RECEIPT",
                    "=" * 34,
                    f"Event: {selected_event['event_name']}",
                    f"Event ID: {selected_event['event_id']}",
                    f"Event date: {selected_event['event_date']}",
                    f"Receipt date/time: {receipt_timestamp}",
                    "",
                    f"Contributor: {contributor['husband_name']} ({contributor['phone_number']})",
                    f"Receiver: {receiver['husband_name']} ({receiver['phone_number']})",
                    "",
                    "Denomination Details:",
                    *receipt_rows,
                    f"Total notes: {note_count_total}",
                    f"Cash total: INR {denomination_total:,.2f}",
                    f"Contribution amount: INR {contribution_amount:,.2f}",
                ]
            )
            st.download_button(
                "Download Receipt",
                data=receipt_text,
                file_name=f"moi_sei_receipt_event_{selected_event['event_id']}.txt",
                mime="text/plain",
                disabled=not denomination_matches,
                use_container_width=True,
            )
        st.markdown('</div>', unsafe_allow_html=True)

