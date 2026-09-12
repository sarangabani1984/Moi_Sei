import pyodbc
import streamlit as st

from db import (
    create_family,
    get_connection,
    get_event,
    get_event_with_host,
    get_family,
    get_family_by_phone,
    process_contribution,
)
from notifications import send_contribution_whatsapp


def format_family(family):
    st.markdown(f"**Family ID:** {family['id']}")
    st.write(f"**Husband:** {family['husband_name']}")
    st.write(f"**Wife:** {family['wife_name'] or 'Not provided'}")
    st.write(f"**Job:** {family['husband_job'] or 'Not provided'}")
    st.write(f"**Phone:** {family['phone_number']}")
    st.write(f"**Place:** {family['place'] or 'Not provided'}")
    st.write(f"**Family deity:** {family['family_deity'] or 'Not provided'}")
    st.write(f"**Email:** {family['email'] or 'Not provided'}")


def format_event(event):
    st.markdown(f"**Event ID:** {event['event_id']}")
    st.write(f"**Name:** {event['event_name']}")
    st.write(f"**Date:** {event['event_date']}")
    st.write(f"**Place:** {event['event_place'] or 'Not provided'}")
    st.write(f"**Location:** {event['event_location'] or 'Not provided'}")


st.set_page_config(page_title="Moi Sei", page_icon="M", layout="wide")
st.title("Moi Sei")
st.caption("Record a contribution after checking both families and the event.")

try:
    get_connection()
except pyodbc.Error as error:
    st.error("Could not connect to SQL Server.")
    st.code(str(error))
    st.stop()

st.subheader("Record Contribution")
st.write("Enter mobile numbers. The details will appear before you submit.")

input_col1, input_col2, input_col3, input_col4 = st.columns(4)
with input_col3:
    event_id = st.number_input("Event ID", min_value=101, step=1, value=101)

try:
    event_preview = get_event_with_host(int(event_id))
except pyodbc.Error:
    event_preview = None

with input_col1:
    contributor_phone = st.text_input("Contributor Mobile Number", placeholder="9000000001")
with input_col2:
    if event_preview and event_preview["host_user_id"]:
        receiver_phone = st.text_input(
            "Receiver Mobile Number",
            value=event_preview["host_phone_number"],
            disabled=True,
            help="This event's receiver is locked and cannot be changed.",
        )
    else:
        receiver_phone = st.text_input("Receiver Mobile Number", placeholder="9000000002")
with input_col4:
    amount = st.number_input("Amount", min_value=0.01, step=50.0, value=50.0, format="%.2f")

if event_preview:
    if event_preview["host_user_id"]:
        st.caption(
            f"\U0001F512 Receiver locked for this event: "
            f"**{event_preview['host_husband_name']}** ({event_preview['host_phone_number']})"
        )
    else:
        st.caption("No receiver locked yet for this event. The first contribution will lock it in.")
else:
    st.caption(f"Event ID {int(event_id)} was not found.")

check_button = st.button("Check Details", type="secondary", use_container_width=True)

if check_button:
    st.session_state.pop("new_family_role", None)
    st.session_state.pop("new_family_context", None)
    contributor_phone = contributor_phone.strip()
    receiver_phone = receiver_phone.strip()
    try:
        contributor = get_family_by_phone(contributor_phone) if contributor_phone else None
        receiver = get_family_by_phone(receiver_phone) if receiver_phone else None
        selected_event = get_event(int(event_id))

        if not contributor_phone:
            st.error("Enter the contributor's mobile number.")
        elif not contributor:
            st.warning(f"No family found for mobile number {contributor_phone}.")

        if not receiver_phone:
            st.error("Enter the receiver's mobile number.")
        elif not receiver:
            st.warning(f"No family found for mobile number {receiver_phone}.")

        if not selected_event:
            st.error(f"Event ID {int(event_id)} was not found.")

        if contributor and receiver and selected_event:
            st.session_state["checked_details"] = {
                "contributor_id": contributor["id"],
                "receiver_id": receiver["id"],
                "event_id": int(event_id),
            }
            st.session_state["contributor"] = contributor
            st.session_state["receiver"] = receiver
            st.session_state["event"] = selected_event
        elif selected_event and contributor_phone and receiver_phone and (not contributor or not receiver):
            # Ask for whichever family is missing first; the other side is handled once saved.
            if not contributor:
                missing_role, missing_phone, other_role, other_family = (
                    "contributor", contributor_phone, "receiver", receiver,
                )
            else:
                missing_role, missing_phone, other_role, other_family = (
                    "receiver", receiver_phone, "contributor", contributor,
                )
            st.session_state["new_family_role"] = missing_role
            st.session_state["new_family_context"] = {
                "phone_number": missing_phone,
                "other_role": other_role,
                "other_family": other_family,
                "event": selected_event,
                "event_id": int(event_id),
            }
    except pyodbc.Error as error:
        st.error("Could not read the requested details.")
        st.code(str(error))

if "new_family_context" in st.session_state:
    context = st.session_state["new_family_context"]
    role_label = st.session_state["new_family_role"].capitalize()
    st.divider()
    st.subheader(f"Add New {role_label} Family")
    st.caption(
        f"No family is registered with mobile number {context['phone_number']}. "
        "Save their details, then continue."
    )

    with st.form("new_family_form"):
        form_col1, form_col2 = st.columns(2)
        with form_col1:
            new_husband_name = st.text_input("Husband name *")
            new_wife_name = st.text_input("Wife name")
            new_husband_job = st.text_input("Husband job")
            st.text_input("Phone number", value=context["phone_number"], disabled=True)
        with form_col2:
            new_place = st.text_input("Place")
            new_family_deity = st.text_input("Family deity")
            new_email = st.text_input("Email")

        create_button = st.form_submit_button("Save Family and Continue", type="primary")

    if create_button:
        if not new_husband_name.strip():
            st.error("Husband name is required.")
        else:
            success, result = create_family(
                new_husband_name.strip(),
                new_wife_name.strip(),
                new_husband_job.strip(),
                context["phone_number"],
                new_place.strip(),
                new_family_deity.strip(),
                new_email.strip(),
            )
            if success:
                new_family = get_family(result)
                if context["other_family"]:
                    role = st.session_state["new_family_role"]
                    contributor = new_family if role == "contributor" else context["other_family"]
                    receiver = new_family if role == "receiver" else context["other_family"]
                    st.session_state["checked_details"] = {
                        "contributor_id": contributor["id"],
                        "receiver_id": receiver["id"],
                        "event_id": context["event_id"],
                    }
                    st.session_state["contributor"] = contributor
                    st.session_state["receiver"] = receiver
                    st.session_state["event"] = context["event"]
                    st.session_state.pop("new_family_context", None)
                    st.session_state.pop("new_family_role", None)
                    st.success(f"Family saved with ID {result}.")
                    st.rerun()
                else:
                    # The other side was also missing; ask for it next.
                    st.session_state["new_family_role"] = context["other_role"]
                    st.session_state["new_family_context"] = {
                        "phone_number": receiver_phone if context["other_role"] == "receiver" else contributor_phone,
                        "other_role": st.session_state["new_family_role"],
                        "other_family": new_family,
                        "event": context["event"],
                        "event_id": context["event_id"],
                    }
                    st.success(f"Family saved with ID {result}. Now add the {context['other_role']} family.")
                    st.rerun()
            else:
                st.error("Could not save the new family.")
                st.code(result)

if "contributor" in st.session_state:
    st.divider()
    st.subheader("Verify Before Saving")
    details_col1, details_col2, details_col3 = st.columns(3)
    with details_col1:
        st.markdown("#### Contributor")
        format_family(st.session_state["contributor"])
    with details_col2:
        st.markdown("#### Receiver")
        format_family(st.session_state["receiver"])
    with details_col3:
        st.markdown("#### Event")
        format_event(st.session_state["event"])

    checked = st.session_state["checked_details"]
    st.info(f"Amount to record: **{float(amount):.2f}**")

    notify_channel = st.radio(
        "Send Confirmation Via",
        ["WhatsApp", "None"],
        horizontal=True,
        index=0,
    )

    if checked["contributor_id"] == checked["receiver_id"]:
        st.error("Contributor and receiver must be different families.")
    elif st.button("Submit Contribution", type="primary", use_container_width=True):
        contributor = st.session_state.get("contributor", {})
        receiver = st.session_state.get("receiver", {})
        event_info = st.session_state.get("event", {})

        success, message = process_contribution(
            checked["contributor_id"],
            checked["receiver_id"],
            checked["event_id"],
            float(amount),
        )
        if success:
            st.success(message)

            # Send Notification based on chosen channel
            if notify_channel == "WhatsApp":
                wa_sent, wa_msg = send_contribution_whatsapp(
                    contributor_phone=contributor.get("phone_number", ""),
                    contributor_name=contributor.get("husband_name", "Contributor"),
                    amount=float(amount),
                    event_name=event_info.get("event_name", "Event"),
                    receiver_name=receiver.get("husband_name", "Host"),
                )
                if wa_sent:
                    st.info(f"💬 {wa_msg}")
                else:
                    st.caption(f"ℹ️ WhatsApp Notification: {wa_msg}")

            st.session_state.pop("checked_details", None)
            st.session_state.pop("contributor", None)
            st.session_state.pop("receiver", None)
            st.session_state.pop("event", None)
        else:
            st.error(message)

