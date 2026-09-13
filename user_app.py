import datetime
import streamlit as st

from db import (
    create_event_by_host,
    get_connection,
    get_family_by_phone,
    get_my_contributions,
    get_my_hosted_events,
    get_my_partner_history,
    get_my_partner_transactions,
    get_my_received_contributions,
    get_upcoming_partner_events,
    set_family_password,
    update_event_by_host,
    verify_password,
)


st.set_page_config(page_title="Moi Sei Family Portal", page_icon="F", layout="wide")
st.title("Moi Sei Family Portal")
st.caption("View only your family's contribution and received history.")

try:
    get_connection()
except Exception as error:
    st.error("Could not connect to database.")
    st.code(str(error))
    st.stop()

phone_number = st.text_input("Registered phone number", placeholder="9000000001")
portal_password = st.text_input("Portal password", type="password")

if st.button("Sign In", type="primary", use_container_width=True):
    try:
        family = get_family_by_phone(phone_number.strip())
        if family is None:
            st.error("No active family was found for that phone number.")
            st.session_state.pop("logged_in_family", None)
        elif not portal_password:
            st.error("Enter your portal password.")
        elif not family.get("password_hash"):
            st.session_state["password_setup_family"] = family
            st.info("This family does not have a portal password yet. Create one below.")
        elif not verify_password(portal_password, family["password_hash"]):
            st.error("Incorrect phone number or password.")
        else:
            st.session_state["logged_in_family"] = family
    except Exception as error:
        st.error("Could not load family records.")
        st.code(str(error))

if "password_setup_family" in st.session_state:
    setup_family = st.session_state["password_setup_family"]
    st.subheader("Create Your Portal Password")
    with st.form("password_setup_form"):
        first_password = st.text_input("New password", type="password")
        confirm_password = st.text_input("Confirm password", type="password")
        setup_button = st.form_submit_button("Create Password", type="primary")
    if setup_button:
        if len(first_password) < 6:
            st.error("Password must be at least 6 characters.")
        elif first_password != confirm_password:
            st.error("Passwords do not match.")
        else:
            setup_success, setup_message = set_family_password(setup_family["id"], first_password)
            if setup_success:
                st.session_state.pop("password_setup_family", None)
                st.success("Password created. Click Sign In to continue.")
            else:
                st.error(setup_message)

if "logged_in_family" in st.session_state:
    family = st.session_state["logged_in_family"]
    st.success(f"Signed in as **{family['husband_name']}** family.")
    
    col_info1, col_info2, col_info3 = st.columns(3)
    with col_info1:
        st.write(f"**Family ID:** {family['id']}")
    with col_info2:
        st.write(f"**Phone:** {family['phone_number']}")
    with col_info3:
        st.write(f"**Place:** {family['place'] or 'Not specified'}")

    st.divider()

    tab_upcoming, tab_my_events, tab_history = st.tabs([
        "📅 Upcoming Partner Events",
        "📣 Schedule & Manage My Events",
        "📊 My Give & Take History",
    ])

    # -------------------------------------------------------------------------
    # TAB 1: Upcoming Events from Reciprocity Partners
    # -------------------------------------------------------------------------
    with tab_upcoming:
        st.subheader("Upcoming Functions from Your Partners")
        st.caption(
            "These upcoming functions belong to families you have exchanged contributions with. "
            "Plan in advance to attend and return your reciprocity contribution (*Moi*)!"
        )
        try:
            partner_events = get_upcoming_partner_events(family["id"])
            if partner_events:
                upcoming_columns = [
                    "event_name",
                    "event_date",
                    "event_location",
                    "host_husband_name",
                    "host_phone_number",
                    "partner_contributed_to_you",
                ]
                st.dataframe(
                    partner_events,
                    use_container_width=True,
                    hide_index=True,
                    column_config={
                        "event_name": "Function Name",
                        "event_date": st.column_config.DateColumn("Date", format="YYYY-MM-DD"),
                        "event_location": "Location",
                        "host_husband_name": "Host Name",
                        "host_phone_number": "Host Mobile",
                        "partner_contributed_to_you": st.column_config.NumberColumn(
                            "Host Contributed to You",
                            format="%.2f",
                        ),
                    },
                    column_order=upcoming_columns,
                )
                total_partner_contributions = sum(
                    float(row["partner_contributed_to_you"] or 0)
                    for row in partner_events
                )
                st.metric(
                    "Total Previously Contributed by These Hosts",
                    f"{total_partner_contributions:,.2f}",
                )
            else:
                st.info("No upcoming functions scheduled by your reciprocity partners yet.")
        except Exception as error:
            st.error("Could not load upcoming partner events.")
            st.code(str(error))

    # -------------------------------------------------------------------------
    # TAB 2: Schedule & Manage My Hosted Events
    # -------------------------------------------------------------------------
    with tab_my_events:
        st.subheader("Announce / Schedule a New Function")
        st.caption(
            "When you schedule a function date here, it will automatically reflect under the "
            "'Upcoming Partner Events' section for all families who have exchanged contributions with you!"
        )

        with st.form("schedule_event_form"):
            form_col1, form_col2 = st.columns(2)
            with form_col1:
                new_event_name = st.text_input("Function Name *", placeholder="e.g. Wedding Ceremony / Ear Piercing")
                new_event_date = st.date_input("Function Date *", min_value=datetime.date.today())
            with form_col2:
                new_event_place = st.text_input("Venue / Mandapam *", placeholder="e.g. Sri Raja Mandapam")
                new_event_location = st.text_input("Location / City", placeholder="e.g. Madurai")

            save_event_button = st.form_submit_button("Announce Function", type="primary")

        if save_event_button:
            if not new_event_name.strip() or not new_event_place.strip():
                st.error("Function Name and Venue/Mandapam are required.")
            else:
                success, result = create_event_by_host(
                    event_name=new_event_name.strip(),
                    event_date=new_event_date.strftime("%Y-%m-%d"),
                    event_place=new_event_place.strip(),
                    event_location=new_event_location.strip(),
                    host_user_id=family["id"],
                )
                if success:
                    st.success(f"🎉 Function announced successfully! Event ID assigned: **{result}**.")
                    st.rerun()
                else:
                    st.error("Could not announce function.")
                    st.code(result)

        st.divider()
        st.subheader("My Announced / Hosted Events")
        try:
            my_events = get_my_hosted_events(family["id"])
            if my_events:
                st.dataframe(my_events, use_container_width=True, hide_index=True)

                st.markdown("#### Update / Reschedule an Existing Event")
                event_options = {
                    f"ID {evt['event_id']}: {evt['event_name']} ({evt['event_date']})": evt
                    for evt in my_events
                }
                selected_evt_label = st.selectbox("Select Event to Update", list(event_options.keys()))
                selected_evt = event_options[selected_evt_label]

                with st.form("update_event_form"):
                    up_col1, up_col2 = st.columns(2)
                    with up_col1:
                        up_event_name = st.text_input("Function Name", value=selected_evt["event_name"])
                        # Parse date
                        evt_d = selected_evt["event_date"]
                        if isinstance(evt_d, str):
                            evt_d = datetime.datetime.strptime(evt_d, "%Y-%m-%d").date()
                        up_event_date = st.date_input("Reschedule Date", value=evt_d)
                    with up_col2:
                        up_event_place = st.text_input("Venue / Mandapam", value=selected_evt["event_place"] or "")
                        up_event_location = st.text_input("Location / City", value=selected_evt["event_location"] or "")

                    update_evt_button = st.form_submit_button("Update Event Details", type="secondary")

                if update_evt_button:
                    up_success, up_msg = update_event_by_host(
                        event_id=selected_evt["event_id"],
                        event_name=up_event_name.strip(),
                        event_date=up_event_date.strftime("%Y-%m-%d"),
                        event_place=up_event_place.strip(),
                        event_location=up_event_location.strip(),
                        host_user_id=family["id"],
                    )
                    if up_success:
                        st.success("Updated event date and details successfully! All partners will see the updated schedule.")
                        st.rerun()
                    else:
                        st.error(up_msg)
            else:
                st.info("You haven't scheduled any functions yet.")
        except Exception as error:
            st.error("Could not load your hosted events.")
            st.code(str(error))

    # -------------------------------------------------------------------------
    # TAB 3: My Give & Take History
    # -------------------------------------------------------------------------
    with tab_history:
        try:
            contribution_rows = get_my_contributions(family["id"])
            received_rows = get_my_received_contributions(family["id"])

            st.subheader("My Contributions (Given)")
            if contribution_rows:
                st.dataframe(contribution_rows, use_container_width=True, hide_index=True)
            else:
                st.info("No contribution records found.")

            st.subheader("My Received Contributions")
            if received_rows:
                st.dataframe(received_rows, use_container_width=True, hide_index=True)
            else:
                st.info("No received contribution records found.")

            st.subheader("Give & Take Summary (All Events)")
            st.caption(
                "For each family you've exchanged with, across every event combined: "
                "what you've given them, what you've received from them, and the net difference."
            )
            partner_rows = get_my_partner_history(family["id"])
            if partner_rows:
                st.dataframe(
                    partner_rows,
                    use_container_width=True,
                    hide_index=True,
                    column_config={
                        "net_difference": st.column_config.NumberColumn(
                            "Net Difference (+ = you gave more)",
                            format="%.2f",
                        ),
                    },
                )

                st.markdown("#### Transaction Timeline With One Family")
                partner_options = {
                    f"{row['other_husband_name']} ({row['other_phone_number']})": row["other_user_id"]
                    for row in partner_rows
                }
                selected_label = st.selectbox("Choose a family", list(partner_options.keys()))
                timeline_rows = get_my_partner_transactions(
                    family["id"], partner_options[selected_label]
                )
                if timeline_rows:
                    st.dataframe(
                        timeline_rows,
                        use_container_width=True,
                        hide_index=True,
                        column_config={
                            "amount": st.column_config.NumberColumn("Amount", format="%.2f"),
                            "running_net_difference": st.column_config.NumberColumn(
                                "Running Net (+ = you're ahead)", format="%.2f"
                            ),
                        },
                    )
                else:
                    st.info("No transactions found with this family.")
            else:
                st.info("No shared history with any family yet.")
        except Exception as error:
            st.error("Could not load this family's records.")
            st.code(str(error))
