import os
import json
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
    search_families,
    set_family_password,
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
    """Block this staff page until the configured password is entered."""
    expected_password = get_admin_password()
    if not expected_password:
        st.error("Admin password is not configured. Add MOI_SEI_ADMIN_PASSWORD to app secrets.")
        st.stop()

    if st.session_state.get("admin_authenticated"):
        if st.sidebar.button("Log out"):
            st.session_state.pop("admin_authenticated", None)
            st.rerun()
        return

    st.subheader("Staff Sign In")
    entered_password = st.text_input("Admin password", type="password")
    if st.button("Sign In", type="primary"):
        if entered_password == expected_password:
            st.session_state["admin_authenticated"] = True
            st.rerun()
        st.error("Incorrect admin password.")
    st.stop()


def set_family_form_values(family):
    """Put a selected family's stored details into the editable form fields."""
    # Reset every widget first so blank values from this family do not retain a prior family's data.
    for key in (
        "family_husband_name",
        "family_wife_name",
        "family_husband_job",
        "family_phone_number",
        "family_place",
        "family_deity",
        "family_email",
        "family_search_alias",
        "family_password",
    ):
        st.session_state[key] = ""

    st.session_state["family_id"] = family["id"]
    st.session_state["family_husband_name"] = family["husband_name"] or ""
    st.session_state["family_wife_name"] = family["wife_name"] or ""
    st.session_state["family_husband_job"] = family["husband_job"] or ""
    st.session_state["family_phone_number"] = family["phone_number"] or ""
    st.session_state["family_place"] = family["place"] or ""
    st.session_state["family_deity"] = family["family_deity"] or ""
    st.session_state["family_email"] = family["email"] or ""
    st.session_state["family_search_alias"] = family.get("search_alias") or ""
    st.session_state["family_password"] = ""


def clear_family_form():
    """Clear form values so staff can register a new family."""
    st.session_state["family_id"] = None
    st.session_state.pop("family_to_load", None)
    for key in (
        "family_husband_name",
        "family_wife_name",
        "family_husband_job",
        "family_phone_number",
        "family_place",
        "family_deity",
        "family_email",
        "family_search_alias",
        "family_password",
    ):
        st.session_state[key] = ""


def parse_family_details(pasted_text):
    """Parse labeled lines or one-value-per-line details without changing widgets yet."""
    aliases = {
        "husband": "family_husband_name",
        "husband name": "family_husband_name",
        "wife": "family_wife_name",
        "wife name": "family_wife_name",
        "job": "family_husband_job",
        "husband job": "family_husband_job",
        "phone": "family_phone_number",
        "phone number": "family_phone_number",
        "mobile": "family_phone_number",
        "place": "family_place",
        "location": "family_place",
        "deity": "family_deity",
        "family deity": "family_deity",
        "email": "family_email",
        "alias": "family_search_alias",
        "search alias": "family_search_alias",
        "password": "family_password",
    }
    parsed_details = {}
    unlabeled_values = []
    for line in pasted_text.splitlines():
        line = line.strip()
        if not line:
            continue
        if ":" not in line:
            unlabeled_values.append(line)
            continue
        label, value = line.split(":", 1)
        field_name = aliases.get(label.strip().lower())
        if field_name and value.strip():
            parsed_details[field_name] = value.strip()

    # Fast-entry order: Phone, Husband, Wife, Place, Job, Deity, Email, Alias, Password.
    positional_fields = (
        "family_phone_number",
        "family_husband_name",
        "family_wife_name",
        "family_place",
        "family_husband_job",
        "family_deity",
        "family_email",
        "family_search_alias",
        "family_password",
    )
    for field_name, value in zip(positional_fields, unlabeled_values):
        parsed_details[field_name] = value
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


st.set_page_config(page_title="Moi Sei Staff", page_icon="M", layout="wide")
st.title("Moi Sei")
st.caption("Family registration")
require_admin_login()

try:
    get_connection()
except Exception as error:
    st.error("Could not connect to database.")
    st.code(str(error))
    st.stop()

st.subheader("Quick Paste for a New Family")
st.caption("Paste one value per line in this order: Phone, Husband, Wife, Place, Job, Deity, Email, Tanglish alias, Password.")
pasted_details = st.text_area(
    "Paste family details",
    key="family_paste_details",
    placeholder=(
        "7411346811\nSarangabani\nSaranya\nKalluthu\nIT\nNalla Kurumban\n"
        "family@example.com\nsarangabani\nwelcome123"
    ),
)
if st.button("Parse Details", type="secondary"):
    parsed_details = parse_family_details(pasted_details)
    if parsed_details:
        st.session_state["parsed_family_details"] = parsed_details
        st.session_state.pop("family_id", None)
        st.rerun()
    else:
        st.error("Paste at least Phone, Husband, Wife, and Place, one value per line.")

st.divider()
st.subheader("Family Details")
st.caption("Type a husband name or mobile number. Matching families appear directly under that field.")

# A selected match is loaded before Streamlit creates the form fields below.
if "family_to_load" in st.session_state:
    set_family_form_values(get_family(st.session_state.pop("family_to_load")))

if "family_save_message" in st.session_state:
    st.success(st.session_state.pop("family_save_message"))

# Parsed paste values must also be applied before Streamlit creates the input widgets.
if "parsed_family_details" in st.session_state:
    for field_name, value in st.session_state.pop("parsed_family_details").items():
        st.session_state[field_name] = value

if "tamil_converted_details" in st.session_state:
    for field_name, value in st.session_state.pop("tamil_converted_details").items():
        st.session_state[field_name] = value

new_family_col, _ = st.columns([1, 5])
with new_family_col:
    st.write("")
    if st.button("New Family", type="secondary", use_container_width=True):
        clear_family_form()
        st.rerun()

form_col1, form_col2 = st.columns(2)
with form_col1:
    phone_number = st.text_input("Phone number *", key="family_phone_number", placeholder="Enter mobile digits")
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
                    f"{family_match['husband_name']} | {family_match['phone_number']} | "
                    f"{family_match['place'] or 'Place not provided'}"
                )
                if st.button(label, key=f"phone_match_{family_match['id']}"):
                    st.session_state["family_to_load"] = family_match["id"]
                    st.rerun()

    wife_name = st.text_input("Wife name *", key="family_wife_name")
    husband_job = st.text_input("Husband job", key="family_husband_job")
    email = st.text_input("Email", key="family_email")
with form_col2:
    husband_name = st.text_input("Husband name *", key="family_husband_name")
    if husband_name.strip() and not st.session_state.get("family_id"):
        husband_matches = search_families(husband_name)
        if husband_matches:
            st.caption("Matching families")
            for family_match in husband_matches:
                label = (
                    f"{family_match['husband_name']} | {family_match['phone_number']} | "
                    f"{family_match['place'] or 'Place not provided'}"
                )
                if st.button(label, key=f"husband_match_{family_match['id']}"):
                    st.session_state["family_to_load"] = family_match["id"]
                    st.rerun()
    place = st.text_input("Place *", key="family_place")
    family_deity = st.text_input("Family deity", key="family_deity")
    search_alias = st.text_input("English / Tanglish search name", key="family_search_alias")
    portal_password = st.text_input(
        "Portal password (new families or reset)",
        type="password",
        key="family_password",
    )

existing_family_id = st.session_state.get("family_id")
if existing_family_id:
    st.success(
        f"Existing family loaded: Family ID {existing_family_id}. "
        "The details above came from the database."
    )

action_col1, action_col2, _ = st.columns([1, 1, 4])
with action_col1:
    save_new_family = st.button(
        "Save New Family",
        type="primary",
        disabled=bool(existing_family_id),
    )
with action_col2:
    st.button("Clear All Fields", type="secondary", on_click=clear_family_form)

reset_password = st.button(
    "Reset Portal Password",
    type="secondary",
    disabled=not bool(existing_family_id),
)

if reset_password:
    if not portal_password:
        st.error("Enter a new portal password before resetting it.")
    elif len(portal_password) < 6:
        st.error("Portal password must be at least 6 characters.")
    else:
        reset_success, reset_message = set_family_password(existing_family_id, portal_password)
        if reset_success:
            st.success("Portal password reset successfully. Share the new password securely with the family.")
        else:
            st.error(f"Could not reset the portal password: {reset_message}")

convert_col, _ = st.columns([1, 5])
with convert_col:
    convert_to_tamil = st.button("Convert Tanglish to Tamil", type="secondary")

if convert_to_tamil:
    original_husband_name = husband_name.strip()
    converted_fields = {
        "family_husband_name": transliterate_to_tamil(original_husband_name),
        "family_wife_name": transliterate_to_tamil(wife_name.strip()),
        "family_husband_job": transliterate_to_tamil(husband_job.strip()),
        "family_place": transliterate_to_tamil(place.strip()),
        "family_deity": transliterate_to_tamil(family_deity.strip()),
    }
    if original_husband_name and not search_alias.strip():
        converted_fields["family_search_alias"] = original_husband_name
    st.session_state["tamil_converted_details"] = converted_fields
    st.rerun()

if save_new_family:
        if not husband_name.strip() or not wife_name.strip() or not phone_number.strip() or not place.strip() or not portal_password:
            st.error("Phone number, husband name, wife name, place, and initial portal password are required.")
        elif len(portal_password) < 6:
            st.error("Portal password must be at least 6 characters.")
        else:
            success, result = create_family(
                husband_name.strip(),
                wife_name.strip(),
                husband_job.strip(),
                phone_number.strip(),
                place.strip(),
                family_deity.strip(),
                email.strip(),
                search_alias.strip(),
                portal_password,
            )
            if success:
                st.session_state["family_to_load"] = result
                st.session_state["family_save_message"] = (
                    f"New family saved successfully. Family ID: {result}"
                )
                st.rerun()
            else:
                st.error("Could not save family. The phone number may already exist.")
                st.code(result)

st.divider()
st.subheader("Record Contribution")
st.caption("The family selected above is the contributor. Select an event and verify the cash denomination total before saving.")

if not existing_family_id:
    st.info("First select an existing family or save a new family above. That family will become the contributor.")
else:
    contributor = get_family(existing_family_id)
    events = get_active_events()
    event_options = {
        f"{event['event_id']} | {event['event_name']} | {event['event_date']}": event
        for event in events
    }

    if not event_options:
        st.warning("No active events are available. Create an event before recording contributions.")
    else:
        st.markdown("#### Contribution Details")
        st.write(f"**Contributor:** {contributor['husband_name']} ({contributor['phone_number']})")
        event_label = st.selectbox("Event", list(event_options), key="contribution_event")
        selected_event = event_options[event_label]

        if selected_event["host_user_id"]:
            receiver = get_family(selected_event["host_user_id"])
            st.write(f"**Receiver:** {receiver['husband_name']} ({receiver['phone_number']})")
            st.caption("This event already has a receiver. You can change it below if no contribution has been recorded yet.")
            receiver_options = {
                f"{family['husband_name']} | {family['phone_number']}": family
                for family in get_active_families_for_search()
                if family["id"] != contributor["id"]
            }
            change_receiver_label = st.selectbox(
                "Change receiver for this event",
                list(receiver_options),
                index=next(
                    (
                        index
                        for index, family_option in enumerate(receiver_options.values())
                        if family_option["id"] == receiver["id"]
                    ),
                    0,
                ),
                key="change_event_receiver",
            )
            new_receiver = receiver_options[change_receiver_label]
            receiver_changed = new_receiver["id"] != receiver["id"]
            if not receiver_changed:
                st.caption(
                    f"{receiver['husband_name']} is already assigned as this event's receiver. "
                    "Select a different family only if this event has no contributions yet."
                )
            if st.button("Save Event Receiver", type="secondary", disabled=not receiver_changed):
                change_success, change_message = change_event_receiver(
                    selected_event["event_id"],
                    new_receiver["id"],
                )
                if change_success:
                    st.success(change_message)
                    st.rerun()
                else:
                    st.error(change_message)
        else:
            receiver_options = {
                f"{family['husband_name']} | {family['phone_number']}": family
                for family in get_active_families_for_search()
                if family["id"] != contributor["id"]
            }
            receiver_label = st.selectbox(
                "Receiver for this event",
                list(receiver_options),
                key="contribution_receiver",
            )
            receiver = receiver_options[receiver_label]
            st.caption("This first receiver will be locked as the event host after saving.")

        contribution_amount = st.number_input(
            "Contribution amount *",
            min_value=0.01,
            step=50.0,
            value=50.0,
            format="%.2f",
        )

        st.markdown("#### Cash Denomination")
        st.caption("Enter the note count. The subtotal for each denomination appears below it.")
        denominations = (1000, 500, 200, 100, 50, 20, 10)
        denomination_columns = st.columns(len(denominations))
        denomination_counts = {}
        denomination_subtotals = {}
        for denomination, denomination_column in zip(denominations, denomination_columns):
            with denomination_column:
                st.markdown(f"**₹{denomination} notes**")
                note_count = st.number_input(
                    "Count",
                    min_value=0,
                    step=1,
                    value=0,
                    key=f"contribution_denomination_{denomination}",
                )
                denomination_counts[denomination] = note_count
                denomination_subtotals[denomination] = denomination * note_count
                st.caption(f"Total: ₹{denomination_subtotals[denomination]:,.2f}")

        denomination_total = sum(
            denomination * note_count
            for denomination, note_count in denomination_counts.items()
        )
        note_count_total = sum(denomination_counts.values())
        denomination_matches = abs(float(contribution_amount) - float(denomination_total)) < 0.001

        st.markdown(f"**Notes:** {note_count_total}  |  **Cash total:** ₹{denomination_total:,.2f}")

        if denomination_matches:
            st.success("Contribution amount matches the cash denomination total.")
        elif denomination_total < contribution_amount:
            st.error(
                f"Cash total ₹{denomination_total:,.2f} is less than the "
                f"contribution amount ₹{contribution_amount:,.2f}."
            )
        else:
            st.warning(
                f"Cash total ₹{denomination_total:,.2f} is more than the "
                f"contribution amount ₹{contribution_amount:,.2f}."
            )

        if contributor["id"] == receiver["id"]:
            st.error("Contributor and receiver must be different families.")
        elif st.button("Save Contribution", type="primary", disabled=not denomination_matches):
            success, message = process_contribution(
                contributor["id"],
                receiver["id"],
                selected_event["event_id"],
                contribution_amount,
            )
            if success:
                st.success(f"Contribution recorded successfully: ₹{contribution_amount:,.2f}")
            else:
                st.error(message)

