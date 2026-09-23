import os
import json
import datetime
import urllib.parse
import urllib.request

import streamlit as st
import streamlit.components.v1 as components
from streamlit_searchbox import st_searchbox

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
    get_last_contribution,
    delete_contribution,
)
from notifications import send_contribution_whatsapp, broadcast_event_announcement, send_green_api_whatsapp


@st.fragment  # ⚡ PERFORMANCE: Partial rerun for denomination inputs (avoids full-page rerun on Tab)
def render_contribution_form(denomination_col, selected_event, existing_family_id):
    """Render the cash denomination and amount input form.
    Using @st.fragment prevents full-page reruns when Tab is pressed in denomination fields.
    """
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
            if st.session_state.pop("focus_contribution_amount", False):
                focus_parent_element('input[aria-label="Amount *"]')
        
        st.caption("Enter note counts (use Tab ↹ to navigate).")
        # Setup Tab navigation from Amount field to first denomination
        setup_tab_from_amount_to_denominations()
        
        denominations = (1000, 500, 200, 100, 50, 20, 10)
        denomination_counts = {}
        denomination_subtotals = {}
        
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
        
        st.markdown('</div>', unsafe_allow_html=True)
        
        # Return values for parent scope to use
        return {
            "contribution_amount": contribution_amount,
            "denomination_counts": denomination_counts,
            "denomination_total": denomination_total,
            "note_count_total": note_count_total,
            "denomination_matches": denomination_matches,
        }


def build_quick_paste_suggestions(search_term, families):
    """Return matching family options plus a free-text new-user option."""
    search_term = search_term.strip()
    if not search_term:
        return []

    normalized_term = search_term.casefold()
    suggestions = []
    for family in families:
        searchable_values = (
            family.get("husband_name"),
            family.get("wife_name"),
            family.get("native_place"),
            family.get("current_place"),
            family.get("place"),
            family.get("husband_job"),
            family.get("wife_job"),
            family.get("search_alias"),
            family.get("others"),
            family.get("phone_number"),
        )
        if not any(
            normalized_term in str(value).casefold()
            for value in searchable_values
            if value
        ):
            continue

        place = family.get("current_place") or family.get("place") or "Place not recorded"
        wife_name = family.get("wife_name") or "Wife not recorded"
        label = (
            f"{family['husband_name']} | {wife_name} | {place} | "
            f"{family['phone_number']}"
        )
        suggestions.append((label, f"family:{family['id']}"))
        if len(suggestions) == 12:
            break

    suggestions.append((f'Use as new details: "{search_term}"', f"new:{search_term}"))
    return suggestions


def focus_parent_element(selector):
    """Focus a Streamlit widget rendered in the parent page."""
    components.html(
        f"""
        <script>
        const selector = {json.dumps(selector)};
        let attempts = 0;
        const timer = setInterval(() => {{
            const element = window.parent.document.querySelector(selector);
            if (element) {{
                element.scrollIntoView({{behavior: "smooth", block: "center"}});
                element.focus();
                clearInterval(timer);
            }} else if (++attempts >= 20) {{
                clearInterval(timer);
            }}
        }}, 100);
        </script>
        """,
        height=0,
    )


def focus_paste_details_box():
    """Auto-focus and scroll to the Paste details searchbox for next entry."""
    components.html(
        """
        <script>
        // Immediate scroll to top
        window.parent.document.documentElement.scrollTop = 0;
        window.parent.scrollTo(0, 0);
        
        // Wait for DOM to settle after Streamlit rerun, then attempt focus
        setTimeout(() => {
            let foundAndFocused = false;
            let attempts = 0;
            
            const attemptFocus = () => {
                // Look for input with "Type a name" placeholder
                const searchInput = window.parent.document.querySelector(
                    'input[placeholder*="Type a name"]'
                );
                
                if (searchInput && !foundAndFocused) {
                    try {
                        // Ensure the element is visible
                        const rect = searchInput.getBoundingClientRect();
                        if (rect.width > 0 && rect.height > 0) {
                            // Scroll into view
                            searchInput.scrollIntoView({behavior: 'smooth', block: 'start'});
                            
                            // Clear the input
                            searchInput.value = '';
                            
                            // Trigger input event to ensure Streamlit knows about the change
                            searchInput.dispatchEvent(new Event('input', { bubbles: true }));
                            searchInput.dispatchEvent(new Event('change', { bubbles: true }));
                            
                            // Now focus
                            setTimeout(() => {
                                searchInput.focus();
                                searchInput.click();
                            }, 100);
                            
                            foundAndFocused = true;
                            console.log('✅ Successfully focused Paste details box');
                        }
                    } catch (e) {
                        console.error('Error focusing:', e);
                    }
                }
                
                // Keep trying for 3 seconds if not found
                if (!foundAndFocused && attempts < 15) {
                    attempts++;
                    setTimeout(attemptFocus, 200);
                }
            };
            
            attemptFocus();
        }, 800);
        </script>
        """,
        height=0,
    )


def focus_parent_button(label):
    """Focus a Streamlit button by its visible text."""
    components.html(
        f"""
        <script>
        const label = {json.dumps(label)};
        let attempts = 0;
        const timer = setInterval(() => {{
            const buttons = [...window.parent.document.querySelectorAll('button')];
            const element = buttons.find(button => button.innerText.includes(label));
            if (element) {{
                element.scrollIntoView({{behavior: "smooth", block: "center"}});
                element.focus();
                clearInterval(timer);
            }} else if (++attempts >= 20) {{
                clearInterval(timer);
            }}
        }}, 100);
        </script>
        """,
        height=0,
    )


def setup_tab_to_load():
    """Setup Tab key in paste box to trigger auto-load and move focus to Amount field."""
    components.html(
        """
        <script>
        document.addEventListener('keydown', (e) => {
            // Listen for Tab in any input focused on the Paste details box
            if (e.key === 'Tab') {
                const focusedElement = window.parent.document.activeElement;
                const isInPasteBox = focusedElement && focusedElement.closest('[data-testid="stSearchBox"]');
                
                if (isInPasteBox) {
                    e.preventDefault();  // Prevent default Tab behavior
                    
                    // Trigger a search/submit by pressing Enter
                    const enterEvent = new KeyboardEvent('keydown', {
                        key: 'Enter',
                        code: 'Enter',
                        keyCode: 13,
                        which: 13,
                        bubbles: true,
                        cancelable: true
                    });
                    focusedElement.dispatchEvent(enterEvent);
                    
                    // Simulate Enter press on the input
                    focusedElement.value = focusedElement.value;
                    focusedElement.dispatchEvent(new Event('input', { bubbles: true }));
                    focusedElement.dispatchEvent(new Event('change', { bubbles: true }));
                    
                    console.log('Tab detected in Paste box - triggered load');
                }
            }
        });
        </script>
        """,
        height=0,
    )


def setup_keyboard_shortcuts(save_label):
    """Setup Ctrl+S to trigger Save button and auto-focus to Amount field."""
    components.html(
        f"""
        <script>
        const saveLabel = {json.dumps(save_label)};
        window.parent.document.addEventListener('keydown', (e) => {{
            // Ctrl+S or Cmd+S (for Mac)
            if ((e.ctrlKey || e.metaKey) && e.key === 's') {{
                e.preventDefault();
                // Find and click the Save button
                const buttons = [...window.parent.document.querySelectorAll('button')];
                const saveButton = buttons.find(btn => btn.innerText.includes(saveLabel));
                if (saveButton) {{
                    saveButton.click();
                    console.log('Saved via Ctrl+S');
                }}
            }}
        }});
        </script>
        """,
        height=0,
    )


def setup_tab_from_amount_to_denominations():
    """Setup Tab key to navigate through Amount field and all denomination count fields."""
    components.html(
        """
        <script>
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Tab') {
                const focusedElement = window.parent.document.activeElement;
                
                // Find all number inputs in the page
                const allInputs = [...window.parent.document.querySelectorAll('input[type="number"]')];
                if (allInputs.length === 0) return;
                
                const currentIndex = allInputs.indexOf(focusedElement);
                
                // Check if focused element is the Amount field OR a denomination field
                const isAmountField = focusedElement && 
                                     (focusedElement.getAttribute('aria-label')?.includes('Amount') || 
                                      focusedElement.placeholder?.includes('Amount'));
                const isDenominationField = currentIndex !== -1;
                
                if (isAmountField || isDenominationField) {
                    // Find next input to focus on Tab
                    let nextIndex = currentIndex + 1;
                    
                    // If we're at the last denomination field, wrap to Amount field
                    if (nextIndex >= allInputs.length) {
                        nextIndex = 0; // Go back to Amount
                    }
                    
                    e.preventDefault();
                    const nextInput = allInputs[nextIndex];
                    nextInput.focus();
                    nextInput.select();
                    console.log('Tab navigation: moved to next field');
                }
            }
        });
        </script>
        """,
        height=0,
    )


def install_contribution_save_shortcut():
    """Bind Ctrl+S to the enabled contribution save button."""
    components.html(
        """
        <script>
        const parentWindow = window.parent;
        if (parentWindow.__moiSeiSaveHandler) {
            parentWindow.document.removeEventListener(
                "keydown", parentWindow.__moiSeiSaveHandler
            );
        }
        parentWindow.__moiSeiSaveHandler = (event) => {
            if (!(event.ctrlKey || event.metaKey) || event.key.toLowerCase() !== "s") {
                return;
            }
            event.preventDefault();
            const buttons = [...parentWindow.document.querySelectorAll("button")];
            const saveButton = buttons.find(button =>
                button.innerText.includes("Save (Ctrl+S)")
            );
            if (saveButton && !saveButton.disabled) {
                saveButton.click();
            }
        };
        parentWindow.document.addEventListener(
            "keydown", parentWindow.__moiSeiSaveHandler
        );
        </script>
        """,
        height=0,
    )


def install_focus_paste_details_shortcut():
    """Bind Ctrl+D and Ctrl+Shift+T to form reset and Tanglish toggle.
    
    Ctrl+D: Clears the form and prepares for next entry
    Ctrl+Shift+T: Toggles between English and Tanglish input mode
    """
    components.html(
        """
        <script>
        console.log('🔧 Keyboard shortcuts installed (Ctrl+D, Ctrl+Shift+T)');
        
        const parentWindow = window.parent;
        if (parentWindow.__moiSeiKeyboardHandler) {
            parentWindow.document.removeEventListener(
                "keydown", parentWindow.__moiSeiKeyboardHandler
            );
            console.log('Removed old keyboard handler');
        }
        
        parentWindow.__moiSeiKeyboardHandler = (event) => {
            // Check for Ctrl+D or Ctrl+Shift+T (or Cmd on Mac)
            const isCtrlOrCmd = event.ctrlKey || event.metaKey;
            const key = event.key.toLowerCase();
            const hasShift = event.shiftKey;
            
            if (!isCtrlOrCmd) {
                return;
            }
            
            // Ctrl+D
            if (key === "d") {
                event.preventDefault();
                console.log('✅ Ctrl+D pressed - triggering form reset');
                
                const buttons = [...parentWindow.document.querySelectorAll("button")];
                const resetButton = buttons.find(button =>
                    button.innerText.includes("Reset for Next Entry") || 
                    button.innerText.includes("Reset") ||
                    button.getAttribute("data-testid") === "reset-form-button"
                );
                
                if (resetButton) {
                    console.log('✅ Found reset button, clicking it');
                    resetButton.click();
                } else {
                    console.log('⚠️ Could not find reset button');
                }
            } 
            // Ctrl+Shift+T
            else if (key === "t" && hasShift) {
                event.preventDefault();
                console.log('✅ Ctrl+Shift+T pressed - toggling Tanglish mode');
                
                const buttons = [...parentWindow.document.querySelectorAll("button")];
                const tanglishButton = buttons.find(button =>
                    button.innerText.includes("Toggle Tanglish Mode") || 
                    button.getAttribute("data-testid") === "tanglish-toggle-button"
                );
                
                if (tanglishButton) {
                    console.log('✅ Found Tanglish toggle button, clicking it');
                    tanglishButton.click();
                } else {
                    console.log('⚠️ Could not find Tanglish toggle button');
                }
            }
        };
        
        parentWindow.document.addEventListener(
            "keydown", parentWindow.__moiSeiKeyboardHandler
        );
        console.log('✅ Keyboard listeners (Ctrl+D, Ctrl+Shift+T) attached');
        </script>
        """,
        height=0,
    )


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


def _get_credential(key: str, default: str = "") -> str:
    """
    Retrieves a configuration credential from Streamlit secrets or environment variables.
    Used for cloud-safe credential access (Streamlit Cloud secrets + environment variables).
    """
    try:
        if hasattr(st, "secrets") and key in st.secrets:
            return str(st.secrets[key])
    except Exception:
        pass
    return os.getenv(key, default)


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
                        id_instance=_get_credential("GREEN_API_ID_INSTANCE", ""),
                        api_token=_get_credential("GREEN_API_TOKEN_INSTANCE", ""),
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
        st.session_state["contribution_amount"] = 0.01
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
        "family_notes",
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
    st.session_state["family_notes"] = family.get("notes") or ""
    st.session_state["family_email"] = family["email"] or ""
    st.session_state["family_search_alias"] = family.get("search_alias") or ""
    st.session_state["family_password"] = ""
    st.session_state["contribution_amount"] = 0.01
    st.session_state["focus_contribution_amount"] = True


def clear_family_form():
    """Clear all form fields and reset to initial state."""
    # Clear all family detail fields using pop() instead of assignment
    # This avoids Streamlit's "cannot modify after widget instantiated" error
    family_fields = [
        "family_id",
        "family_phone_number",
        "family_native_place",
        "family_current_place",
        "family_husband_name",
        "family_husband_job",
        "family_wife_name",
        "family_wife_job",
        "family_others",
        "family_deity",
        "family_notes",
        "family_email",
        "family_search_alias",
        "family_password",
    ]
    
    for key in family_fields:
        st.session_state.pop(key, None)
    
    # Clear denomination counters - set to 0 explicitly
    for denom in [1000, 500, 200, 100, 50, 20, 10]:
        st.session_state[f"contribution_denomination_{denom}"] = 0
    
    # Clear other related flags
    st.session_state.pop("family_to_load", None)
    st.session_state.pop("selected_event_for_contribution", None)
    st.session_state.pop("contribution_receiver", None)
    st.session_state.pop("parsed_family_details", None)
    st.session_state.pop("multiple_family_matches", None)
    st.session_state.pop("form_auto_populated_valid", None)
    
    # Reset contribution amount and focus
    st.session_state["contribution_amount"] = 0.01
    st.session_state["focus_contribution_amount"] = True


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
    
    # No match found → parse as new user WITHOUT converting to Tamil (keep original text)
    parsed = parse_family_details(pasted_text)
    return parsed


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
    Format: Phone Native_Place Current_Place Husband_Name Husband_Job Wife Wife_Job Others Deity Notes Amount
    
    Use ~ or - to skip a field. 
    Example: 1234 ~ hosur sarangabani IT Saranya housewife 5000
    → Phone=1234, Native=(skip), Current=hosur, Husband=sarangabani, Job=IT, Wife=Saranya, WifeJob=housewife, 
      Others=(empty), Deity=(empty), Notes=(empty), Amount=5000
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
        "family_deity",
        "family_notes",
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
    
    # Map remaining values to text fields, respecting skip placeholders (~ or -)
    field_index = 0
    for value in values:
        if field_index >= len(text_fields):
            break  # Extra values ignored
        
        value = value.strip()
        
        # If value is a skip placeholder (~, -), leave field empty and move to next field
        if value in ('~', '-'):
            parsed_details[text_fields[field_index]] = ""
        else:
            parsed_details[text_fields[field_index]] = value
        
        field_index += 1
    
    # Fill any remaining text fields with empty strings
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
    .block-container {
        max-width: 100%;
        padding-top: 0.15rem;
        padding-bottom: 0.25rem;
    }
    .st-key-quick_paste_panel {
        position: sticky;
        top: 2.75rem;
        z-index: 50;
        background: #0e1117;
        padding: 0.1rem 0 0;
    }
    .st-key-quick_paste_panel [data-testid="stCaptionContainer"] {
        margin-bottom: 0;
    }
    div[data-testid="stTextInput"] input,
    div[data-testid="stNumberInput"] input {
        min-height: 2rem;
        height: 2rem;
        padding-top: 0.2rem;
        padding-bottom: 0.2rem;
    }
    div[data-testid="stButton"] button {
        min-height: 2rem;
        padding-top: 0.25rem;
        padding-bottom: 0.25rem;
    }
    div[data-testid="stAlert"] {
        padding-top: 0.45rem;
        padding-bottom: 0.45rem;
    }
    .box-container {
        border: 2px solid #0e8b8e;
        border-radius: 12px;
        padding: 20px 18px;
        background: linear-gradient(135deg, #252f3d 0%, #2d3e50 100%);
        box-shadow: 0 4px 12px rgba(14, 139, 142, 0.2);
        margin: 0 0 0 0;
    }
    .box-container-dark {
        border: 2px solid #0e8b8e;
        border-radius: 12px;
        padding: 20px 18px;
        background: linear-gradient(135deg, #252f3d 0%, #2d3e50 100%);
        box-shadow: 0 4px 12px rgba(14, 139, 142, 0.2);
    }
    .box-title {
        font-size: 1.2rem;
        font-weight: 700;
        color: #ffffff;
        background-color: #0e8b8e;
        padding: 6px 12px;
        margin: -20px -18px 8px -18px;
        border-radius: 10px 10px 0 0;
        display: block;
    }
</style>
""", unsafe_allow_html=True)

require_admin_login()

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
        st.session_state["family_notes"] = family.get("notes", "")
        st.session_state["family_email"] = family.get("email", "")
        st.session_state["family_search_alias"] = family.get("search_alias", "")
        # Keep password as default "111111" for testing
        st.session_state["family_password"] = "111111"
        # Always reset amount when loading new family
        st.session_state["contribution_amount"] = 0.01
        st.session_state["focus_contribution_amount"] = True
        # Clear the quick paste box after loading family
        st.session_state["family_paste_details"] = ""
        st.session_state.pop("family_quick_paste_search", None)
        # Clear denomination counters for new family - set to 0 explicitly
        for denom in [1000, 500, 200, 100, 50, 20, 10]:
            st.session_state[f"contribution_denomination_{denom}"] = 0

# Initialize all form field keys early to prevent NoneType errors
form_field_keys = [
    "family_phone_number", "family_native_place", "family_current_place",
    "family_husband_name", "family_husband_job", "family_wife_name", 
    "family_wife_job", "family_others", "family_deity", "family_notes", "family_email", 
    "family_search_alias", "family_password"
]
for key in form_field_keys:
    if key not in st.session_state:
        # Set default password to "111111" for testing
        st.session_state[key] = "111111" if key == "family_password" else ""

# Initialize denomination counters to 0 if not set
for denom in [1000, 500, 200, 100, 50, 20, 10]:
    denom_key = f"contribution_denomination_{denom}"
    if denom_key not in st.session_state:
        st.session_state[denom_key] = 0

# Initialize Tanglish mode (False = English, True = Tanglish/auto-convert)
if "tanglish_mode" not in st.session_state:
    st.session_state["tanglish_mode"] = False

# Initialize contribution_amount early (before any widgets that use it)
initialize_contribution_amount()

# ============================================================================
# SIDEBAR: Event Setup, Staff Login & Collection Summary
# ============================================================================
with st.sidebar:
    st.markdown("## மொய்செய்")
    
    # Event Details at the top
    events = get_active_events()
    event_options = {
        f"{event['event_id']} | {event['event_name']} | {event['event_date']}": event
        for event in events
    }
    if event_options:
        st.markdown("**📅 Event Detail**")
        event_label = st.selectbox("Event for today's collection", list(event_options), key="selected_event_for_contribution")
        selected_event = event_options[event_label]
        st.info(event_label)
        
        # Initialize event collection tracking structure
        event_key = f"event_collection_{selected_event['event_id']}"
        if event_key not in st.session_state:
            st.session_state[event_key] = {}
        
        # ============ STAFF LOGIN ============
        st.markdown("---")
        st.markdown("**👤 Staff Login**")
        
        # Get list of staff who've already worked on this event (for dropdown)
        event_staff_data = st.session_state[event_key]
        staff_list = list(event_staff_data.keys()) if event_staff_data else []
        
        # Check if current staff is locked (has contributions)
        current_staff_locked = False
        if "current_staff_name" in st.session_state:
            locked_staff = st.session_state.get("current_staff_name")
            if locked_staff in event_staff_data and event_staff_data[locked_staff]["family_count"] > 0:
                current_staff_locked = True
        
        # Create dropdown with recent staff + option to add new
        if staff_list:
            staff_options = staff_list + ["➕ Add New Staff"]
            
            if current_staff_locked:
                # Staff is locked - show locked indicator with option to change
                locked_staff = st.session_state.get("current_staff_name")
                st.info(f"🔒 **Locked as: {locked_staff}**")
                
                if st.button("🔄 Change Staff", use_container_width=True, type="secondary"):
                    st.session_state["confirm_staff_change"] = True
                    st.rerun()
                
                if st.session_state.get("confirm_staff_change"):
                    st.warning("⚠️ Are you sure? Switching staff will lock you to a different person.")
                    col1, col2 = st.columns(2)
                    with col1:
                        if st.button("❌ Cancel", use_container_width=True):
                            st.session_state["confirm_staff_change"] = False
                            st.rerun()
                    with col2:
                        if st.button("✅ Confirm Change", use_container_width=True, type="secondary"):
                            st.session_state["confirm_staff_change"] = False
                            st.session_state.pop("current_staff_name", None)
                            st.session_state.pop("current_staff_selection", None)
                            st.rerun()
                
                current_staff_name = locked_staff
            else:
                # Staff not locked - allow selection
                staff_selection = st.selectbox(
                    "Select or add staff",
                    options=staff_options,
                    key="current_staff_selection",
                    help="Choose your name to begin collection"
                )
                
                if staff_selection == "➕ Add New Staff":
                    current_staff_name = st.text_input(
                        "Enter your name",
                        key="new_staff_name_input",
                        placeholder="e.g., Suresh, Rajesh, Mohan",
                    )
                else:
                    current_staff_name = staff_selection
        else:
            # First staff entry - show text input
            current_staff_name = st.text_input(
                "Enter your name",
                key="staff_name_input",
                placeholder="e.g., Suresh, Rajesh, Mohan",
                help="Enter staff name to begin collection"
            )
        
        # Store current staff in session state
        if current_staff_name and current_staff_name.strip():
            current_staff_name = current_staff_name.strip()
            st.session_state["current_staff_name"] = current_staff_name
            
            # Initialize this staff's collection data if new
            if current_staff_name not in event_staff_data:
                event_staff_data[current_staff_name] = {
                    "total_amount": 0.0,
                    "family_count": 0,
                    "denominations": {1000: 0, 500: 0, 200: 0, 100: 0, 50: 0, 20: 0, 10: 0},
                    "last_contribution_id": None
                }
            
            # ============ CURRENT STAFF COLLECTION SUMMARY ============
            st.markdown("---")
            st.markdown(f"**📊 {current_staff_name}'s Collection**")
            
            staff_data = event_staff_data[current_staff_name]
            
            # Large total at top
            st.metric(
                label="Your Total",
                value=f"₹{staff_data['total_amount']:,.2f}",
                delta=f"{staff_data['family_count']} families"
            )
            
            # Denomination breakdown
            st.markdown("**Your Denomination Count:**")
            denom_display = []
            for denom in (1000, 500, 200, 100, 50, 20, 10):
                count = staff_data["denominations"].get(denom, 0)
                if count > 0:
                    denom_display.append(f"₹{denom}: {count}")
            
            if denom_display:
                st.caption(" | ".join(denom_display))
            else:
                st.caption("No contributions yet")
            
            # ============ UNDO LAST ENTRY ============
            if staff_data.get("last_contribution_id"):
                if st.button("↩️ Undo Last Entry", use_container_width=True, type="secondary"):
                    st.session_state["confirm_undo"] = True
                
                if st.session_state.get("confirm_undo"):
                    st.warning("⚠️ This will remove the last contribution from your total.")
                    col1, col2 = st.columns(2)
                    with col1:
                        if st.button("❌ Cancel Undo", use_container_width=True):
                            st.session_state["confirm_undo"] = False
                            st.rerun()
                    with col2:
                        if st.button("✅ Confirm Undo", use_container_width=True, type="secondary"):
                            # Delete contribution from DB
                            undo_success, undo_msg = delete_contribution(staff_data["last_contribution_id"])
                            if undo_success:
                                # Revert from sidebar totals
                                last_cont_id = staff_data["last_contribution_id"]
                                # We need to get the amount to subtract - for now, we'll refresh from DB
                                # A better approach would be to store the amount when we saved it
                                # For simplicity, let's ask the user to refresh
                                st.session_state["confirm_undo"] = False
                                st.success("✅ Last contribution undone! Reloading...")
                                st.session_state.pop("current_staff_name", None)
                                st.rerun()
                            else:
                                st.error(f"❌ Undo failed: {undo_msg}")
                                st.session_state["confirm_undo"] = False
            
            # ============ ALL STAFF COMPARISON ============
            if len(event_staff_data) > 1:
                st.markdown("---")
                st.markdown("**👥 All Staff Today**")
                
                for staff_name, data in event_staff_data.items():
                    if staff_name != current_staff_name:
                        col1, col2 = st.columns([0.6, 0.4])
                        with col1:
                            st.caption(f"**{staff_name}**")
                        with col2:
                            st.caption(f"₹{data['total_amount']:,.2f}")
                
                # Event total
                total_amount = sum(data["total_amount"] for data in event_staff_data.values())
                total_families = sum(data["family_count"] for data in event_staff_data.values())
                st.markdown("---")
                st.markdown(f"**📈 EVENT TOTAL: ₹{total_amount:,.2f}** ({total_families} families)")
        else:
            st.warning("⚠️ Enter your name to continue")
    else:
        selected_event = None
        st.warning("No active events are available.")

    st.divider()
    
    # Ensure group mode is always off (checkbox removed)
    if "group_family_matches" in st.session_state:
        del st.session_state["group_family_matches"]

# ============================================================================
# QUICK PASTE BOX (Full Width)
# ============================================================================
with st.container(key="quick_paste_panel"):
    group_mode = st.session_state.get("group_mode", False)
    if group_mode:
        st.markdown('<div class="box-container"><div class="box-title">📋 Group Contribution Mode</div>', unsafe_allow_html=True)
        st.caption("Paste phone numbers or names (one per line) to add multiple families")
    else:
        st.caption("Quick Paste: search existing data or enter Mobile, Husband, Place, Amount")

    def auto_populate_on_paste():
        """Smart search: text→husband name, numbers→phone, no match→parse as new user. 
        ⚡ OPTIMIZED: Stores results WITHOUT rerunning on every keystroke.
        Only reruns when user clicks Load/Select button.
        """
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
            # NO rerun here - just store results
        else:
            # NORMAL MODE: Smart search single entry
            result = smart_parse_and_search(pasted_text)
            if result:
                if "multiple_matches" in result:
                    # Multiple families found → STORE but don't rerun yet
                    matches = result["multiple_matches"]
                    st.session_state["paste_search_results"] = matches
                    st.session_state["paste_has_results"] = True
                    # If only 1 match, auto-load (definite match)
                    if len(matches) == 1:
                        st.session_state["family_to_load"] = matches[0]["id"]
                        st.session_state.pop("family_id", None)
                        st.rerun()  # Only rerun for definite single match
                    # If multiple matches, show selection UI (no rerun needed)
                else:
                    # No match → parse as new user with Tamil already converted
                    st.session_state["parsed_family_details"] = result
                    if "contribution_amount" in result:
                        st.session_state["contribution_amount"] = result["contribution_amount"]
                    st.session_state.pop("family_id", None)
                    st.session_state["form_auto_populated_valid"] = True
                    st.rerun()  # Only rerun when actually loading new user data

    if group_mode:
        st.text_area(
            "Paste details",
            key="family_paste_details",
            placeholder="Enter one phone number or name per line",
            height=100,
            on_change=auto_populate_on_paste,
        )
        # Add Load Details button for manual trigger (Tab doesn't auto-trigger on_change)
        if st.button("⏎ Load Details", type="secondary", use_container_width=True):
            auto_populate_on_paste()
    else:
        searchable_families = get_active_families_for_search()

        def quick_paste_search(search_term):
            return build_quick_paste_suggestions(search_term, searchable_families)

        def submit_quick_paste(selection):
            """⚡ OPTIMIZED: Only reruns for definite matches (family ID or new user data)."""
            if not selection:
                return
            selection_type, value = selection.split(":", 1)
            
            if selection_type == "family":
                # Definite match: load the family
                st.session_state["family_to_load"] = int(value)
                st.session_state["show_amount_section"] = True
                st.session_state["focus_contribution_amount"] = True
                st.session_state.pop("family_id", None)
                st.rerun()  # Only rerun for definite family match
            else:
                # Text entry: store but don't rerun (let user click Load button or wait for Enter)
                st.session_state["family_paste_details"] = value
                st.session_state["focus_family_auto_save"] = True
                # Trigger search but DON'T auto-rerun (just store results)
                auto_populate_on_paste()

        st_searchbox(
            quick_paste_search,
            label="Paste details",
            placeholder="Type a name, place, phone, or new-user details",
            key="family_quick_paste_search",
            submit_function=submit_quick_paste,
            clear_on_submit=False,
            edit_after_submit="current",
            debounce=150,
            help="Type to see matches. Use Up/Down arrows and Enter to select (or press Tab to load). Quick jump: Press Ctrl+D after save.",
        )
        # Setup Tab key to trigger paste loading for custom data
        setup_tab_to_load()
    if group_mode:
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

st.markdown('<div style="height: 0.25rem;"></div>', unsafe_allow_html=True)

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
    # CHECK: Staff name must be entered before showing form
    current_staff_name = st.session_state.get("current_staff_name")
    
    if not current_staff_name:
        st.warning("⚠️ **Please enter your staff name in the sidebar to begin data entry.**")
        st.stop()
    
    # Install keyboard shortcuts (must be at top level so always active)
    install_contribution_save_shortcut()
    install_focus_paste_details_shortcut()
    
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
        
        # Auto-focus paste details box for next entry
        if st.session_state.pop("focus_paste_details", False):
            focus_paste_details_box()
        
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

    # Create 2-column layout
    family_col, denomination_col = st.columns([1, 0.9], gap="medium")

    # ====== COLUMN 1: FAMILY DETAILS ======
    with family_col:
        st.markdown('<div class="box-container"><div class="box-title">📋 குடும்ப விவரங்கள்</div>', unsafe_allow_html=True)

        # ============ ORDERED FIELDS: 2-COLUMN LAYOUT ============
        left_col, right_col = st.columns(2, gap="medium")
        
        with left_col:
            # 1. Phone
            st.markdown("**போன்*** ", unsafe_allow_html=True)
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
            st.markdown("**சொந்த ஊர்** ", unsafe_allow_html=True)
            native_place = st.text_input("Native Place", key="family_native_place", label_visibility="collapsed")

            # 3. Current Place
            st.markdown("**இருப்பு** ", unsafe_allow_html=True)
            current_place = st.text_input("Current Place", key="family_current_place", label_visibility="collapsed")

            # 4. Husband Name
            st.markdown("**கணவர்*** ", unsafe_allow_html=True)
            husband_name = st.text_input("Husband *", key="family_husband_name", label_visibility="collapsed")

            # 5. Husband Job
            st.markdown("**கணவர் தொழில்** ", unsafe_allow_html=True)
            husband_job = st.text_input("Husband Job", key="family_husband_job", label_visibility="collapsed")

        with right_col:
            # 6. Wife
            st.markdown("**மனைவி*** ", unsafe_allow_html=True)
            wife_name = st.text_input("Wife *", key="family_wife_name", label_visibility="collapsed")

            # 7. Wife Job
            st.markdown("**மனைவி தொழில்** ", unsafe_allow_html=True)
            wife_job = st.text_input("Wife Job", key="family_wife_job", label_visibility="collapsed")

            # 8. Others
            st.markdown("**தட்டு** ", unsafe_allow_html=True)
            others = st.text_input("Others", key="family_others", label_visibility="collapsed")

            # 9. Kuladeivam (family deity)
            st.markdown("**குலதெய்வம்** ", unsafe_allow_html=True)
            family_deity = st.text_input("Kuladeivam", key="family_deity", label_visibility="collapsed")

            # 10. Kurrippu (notes/remarks)
            st.markdown("**குறிப்பு** ", unsafe_allow_html=True)
            notes = st.text_input("Kurrippu", key="family_notes", label_visibility="collapsed")

        # Email, Search name stay in session_state/DB but are hidden from this form.
        email = st.session_state.get("family_email", "") or ""
        search_alias = st.session_state.get("family_search_alias", "") or ""

        existing_family_id = st.session_state.get("family_id")
        if existing_family_id:
            st.success(f"✓ Family ID {existing_family_id}")

        # Auto-save button if form was auto-populated with valid data
        form_auto_populated = st.session_state.get("form_auto_populated_valid", False)
        if form_auto_populated and not existing_family_id:
            st.info("✨ Form ready! Click below to save and jump to amount field → (or press Ctrl+S)")
            auto_save_button = st.button(
                "⏎ Save & Go to Amount",
                type="primary",
                use_container_width=True,
                key="family_auto_save_button",
            )
            # Setup Ctrl+S shortcut for auto-save button
            setup_keyboard_shortcuts("Save & Go to Amount")
            if st.session_state.pop("focus_family_auto_save", False):
                focus_parent_button("Save & Go to Amount")
        else:
            auto_save_button = False
            save_new_family_label = "Save New"
            st.info("💾 Press **Ctrl+S** to save and jump to amount field (or click button)")
            save_new_family = st.button(save_new_family_label, type="primary", disabled=bool(existing_family_id), use_container_width=True)
            # Setup Ctrl+S shortcut for Save New button (for new families only)
            if not existing_family_id:
                setup_keyboard_shortcuts(save_new_family_label)

        if st.button("Clear", type="secondary", use_container_width=True):
            clear_family_form()
            st.session_state.pop("form_auto_populated_valid", None)
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
            
            if missing_fields:
                st.error(f"Missing: {', '.join(missing_fields)}")
            else:
                # Login password defaults to the family's phone number (no manual entry).
                portal_password = phone_number.strip()
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
                    notes=notes.strip(),
                )
                if success:
                    st.session_state["family_to_load"] = result
                    st.session_state["family_save_message"] = f"✅ Family saved! Now enter amount (₹) below →"
                    st.session_state["show_amount_section"] = True  # Flag to highlight amount section
                    st.session_state["focus_contribution_amount"] = True
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
                            id_instance=_get_credential("GREEN_API_ID_INSTANCE", ""),
                            api_token=_get_credential("GREEN_API_TOKEN_INSTANCE", ""),
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

# ⚡ CALL FRAGMENT: Render contribution form with partial reruns for Tab key performance
contribution_data = render_contribution_form(denomination_col, selected_event, existing_family_id)

if contribution_data:
    contribution_amount = contribution_data["contribution_amount"]
    denomination_counts = contribution_data["denomination_counts"]
    denomination_total = contribution_data["denomination_total"]
    note_count_total = contribution_data["note_count_total"]
    denomination_matches = contribution_data["denomination_matches"]

    # Status message and button BELOW denomination (OUTSIDE fragment for control)
    with denomination_col:
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

        save_button_label = "💾 Save (Ctrl+S)" if not ready_to_save else "💾 Save (Ctrl+S) ✓ Ready"
        if st.button(save_button_label, type="primary", use_container_width=True, disabled=not ready_to_save, key="save_contribution_btn"):
            success, message = process_contribution(
                contributor["id"],
                receiver["id"],
                selected_event["event_id"],
                contribution_amount,
            )
            if success:
                # Get last contribution ID for undo feature
                last_contribution = get_last_contribution(contributor["id"], selected_event["event_id"])
                if last_contribution:
                    event_key = f"event_collection_{selected_event['event_id']}"
                    current_staff_name = st.session_state.get("current_staff_name", "Unknown Staff")
                    if event_key in st.session_state and current_staff_name in st.session_state[event_key]:
                        st.session_state[event_key][current_staff_name]["last_contribution_id"] = last_contribution["id"]
                
                # Update collection tracking in session state (for sidebar summary) - BY STAFF
                event_key = f"event_collection_{selected_event['event_id']}"
                current_staff_name = st.session_state.get("current_staff_name", "Unknown Staff")
                
                if event_key in st.session_state:
                    event_staff_data = st.session_state[event_key]
                    if current_staff_name in event_staff_data:
                        staff_collection = event_staff_data[current_staff_name]
                        staff_collection["total_amount"] += contribution_amount
                        staff_collection["family_count"] += 1
                        # Add denomination counts
                        for denom, count in denomination_counts.items():
                            staff_collection["denominations"][denom] += count
                
                st.session_state["contribution_save_message"] = f"Contribution recorded: {contributor['husband_name']} → {receiver['husband_name']} | ₹{contribution_amount:,.2f}"
                
                # Set flag to auto-focus paste details box for next entry
                st.session_state["focus_paste_details"] = True
                
                # Clear paste details box for next entry (form fields will reset on rerun via initialization)
                st.session_state["family_paste_details"] = ""
                
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
        
        # Hidden reset button that Ctrl+D will trigger
        # This button clears the form and prepares for the next family entry
        if st.button("Reset for Next Entry", key="reset_form_button"):
            clear_family_form()
            st.session_state["family_paste_details"] = ""
            st.session_state["focus_family_auto_save"] = False
            st.rerun()
        
        install_contribution_save_shortcut()
        install_focus_paste_details_shortcut()
        st.markdown('</div>', unsafe_allow_html=True)

