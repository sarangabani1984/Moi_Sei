import datetime
import pandas as pd
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
    update_family_profile,
    update_event_by_host,
    verify_password,
    get_all_transaction_partners,
    search_contributions_by_amount,
    search_family_contributions_many,
)
from notifications import broadcast_event_announcement
from voice_ai import (
    build_tamil_contribution_response,
    parse_contribution_query_with_gpt,
    text_to_speech_openai,
    transcribe_audio_with_whisper,
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

    tab_profile, tab_upcoming, tab_my_events, tab_history, tab_voice = st.tabs([
        "👤 My Profile",
        "📅 Upcoming Partner Events",
        "📣 Schedule & Manage My Events",
        "📊 My Give & Take History",
        "🎙️ AI Assistant",
    ])

    # -------------------------------------------------------------------------
    # TAB 0: Family Profile
    # -------------------------------------------------------------------------
    with tab_profile:
        st.subheader("My Family Profile")
        st.caption(
            "Review and update your family details. The registered phone number "
            "stays unchanged because it is your login ID."
        )

        with st.form("family_profile_form"):
            profile_col1, profile_col2 = st.columns(2)
            with profile_col1:
                st.text_input(
                    "Registered phone number",
                    value=family["phone_number"] or "",
                    disabled=True,
                )
                profile_husband_name = st.text_input(
                    "Husband name *", value=family["husband_name"] or ""
                )
                profile_wife_name = st.text_input(
                    "Wife name", value=family["wife_name"] or ""
                )
                profile_husband_job = st.text_input(
                    "Husband job", value=family["husband_job"] or ""
                )
                profile_email = st.text_input(
                    "Email", value=family["email"] or ""
                )
            with profile_col2:
                st.text_input("Family ID", value=str(family["id"]), disabled=True)
                profile_place = st.text_input(
                    "Place", value=family["place"] or ""
                )
                profile_family_deity = st.text_input(
                    "Family deity", value=family["family_deity"] or ""
                )
                profile_search_alias = st.text_input(
                    "English / Tanglish search name",
                    value=family.get("search_alias") or "",
                )

            profile_save_button = st.form_submit_button(
                "Save Profile Changes", type="primary"
            )

        if profile_save_button:
            if not profile_husband_name.strip():
                st.error("Husband name is required.")
            else:
                profile_success, profile_message = update_family_profile(
                    user_id=family["id"],
                    husband_name=profile_husband_name.strip(),
                    wife_name=profile_wife_name.strip(),
                    husband_job=profile_husband_job.strip(),
                    place=profile_place.strip(),
                    family_deity=profile_family_deity.strip(),
                    email=profile_email.strip(),
                    search_alias=profile_search_alias.strip(),
                )
                if profile_success:
                    st.session_state["logged_in_family"] = get_family_by_phone(
                        family["phone_number"]
                    )
                    st.success(profile_message)
                    st.rerun()
                else:
                    st.error(profile_message)

        st.divider()
        st.subheader("Change Portal Password")
        with st.form("family_password_change_form"):
            current_password = st.text_input("Current password", type="password")
            new_password = st.text_input("New password", type="password")
            confirm_new_password = st.text_input(
                "Confirm new password", type="password"
            )
            password_change_button = st.form_submit_button(
                "Change Password", type="secondary"
            )

        if password_change_button:
            if not current_password or not verify_password(
                current_password, family.get("password_hash") or ""
            ):
                st.error("Current password is incorrect.")
            elif len(new_password) < 6:
                st.error("New password must be at least 6 characters.")
            elif new_password != confirm_new_password:
                st.error("New passwords do not match.")
            else:
                password_success, password_message = set_family_password(
                    family["id"], new_password
                )
                if password_success:
                    st.success("Portal password changed successfully.")
                else:
                    st.error(password_message)

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
                    "you_contributed_to_host",
                    "net_difference",
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
                            "Previously Received from Host",
                            format="%.2f",
                        ),
                        "you_contributed_to_host": st.column_config.NumberColumn(
                            "Previously Given to Host",
                            format="%.2f",
                        ),
                        "net_difference": st.column_config.NumberColumn(
                            "Net Difference",
                            format="%.2f",
                        ),
                    },
                    column_order=upcoming_columns,
                )
                total_partner_contributions = sum(
                    float(row["partner_contributed_to_you"] or 0)
                    for row in partner_events
                )
                total_given_to_user = sum(float(row["partner_contributed_to_you"] or 0) for row in partner_events)
                total_user_given = sum(float(row["you_contributed_to_host"] or 0) for row in partner_events)
                st.write(f"**Total previously received from these hosts:** {total_given_to_user:,.2f}")
                st.write(f"**Total previously given to these hosts:** {total_user_given:,.2f}")
                st.metric("Overall Net Difference", f"{total_given_to_user - total_user_given:,.2f}")
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

                st.markdown("#### 📱 Send WhatsApp Invitation to Partners")
                st.caption("Broadcast your event details to all families you've transacted with (gave or received money)")
                
                event_options = {
                    f"ID {evt['event_id']}: {evt['event_name']} ({evt['event_date']})": evt
                    for evt in my_events
                }
                selected_evt_label = st.selectbox("Select Event to Announce", list(event_options.keys()), key="whatsapp_event_select")
                selected_evt = event_options[selected_evt_label]

                # Show message preview
                st.markdown("**📋 Message Preview:**")
                preview_msg = (
                    f"🎉 *Event Announcement* 🎉\n\n"
                    f"Dear Friend,\n\n"
                    f"*{family['husband_name']}* family cordially invites you to:\n\n"
                    f"📌 *Event:* {selected_evt['event_name']}\n"
                    f"📅 *Date:* {selected_evt['event_date']}\n"
                    f"🏛️ *Venue:* {selected_evt['event_place']}\n"
                    f"📍 *Location:* {selected_evt['event_location'] or 'TBA'}\n\n"
                    f"🙏 We invite you to join us!\n"
                    f"Please confirm your attendance.\n\n"
                    f"📞 *Contact:* {family['phone_number']}\n\n"
                    f"Best regards,\n"
                    f"{family['husband_name']} Family"
                )
                st.text_area("Message to be sent via WhatsApp:", value=preview_msg, height=250, disabled=True)

                # File upload for invitation (optional)
                st.markdown("**📎 Optional: Attach Invitation (PDF or Image)**")
                uploaded_file = st.file_uploader(
                    "Upload invitation file",
                    type=["pdf", "jpg", "jpeg", "png"],
                    help="Optional: Add a PDF or image invitation to the WhatsApp message"
                )
                if uploaded_file:
                    st.info(f"✅ File selected: {uploaded_file.name}")

                # Send button with confirmation
                if st.button("📤 Send WhatsApp to All Partners", type="primary", use_container_width=True):
                    try:
                        # Get all transaction partners
                        partners = get_all_transaction_partners(family["id"])
                        if not partners:
                            st.warning("No reciprocity partners found to send to. (You must have exchanged contributions with families first)")
                        else:
                            partner_phones = [p["phone_number"] for p in partners if p.get("phone_number")]
                            
                            if not partner_phones:
                                st.error("No valid phone numbers found in partner list.")
                            else:
                                # Show confirmation dialog
                                st.info(f"📤 Sending WhatsApp message to {len(partner_phones)} partner(s)...")
                                
                                # Send broadcast
                                sent_count, status_msg = broadcast_event_announcement(
                                    family_phone=family["phone_number"],
                                    family_name=family["husband_name"],
                                    event_name=selected_evt["event_name"],
                                    event_date=str(selected_evt["event_date"]),
                                    event_place=selected_evt["event_place"],
                                    event_location=selected_evt["event_location"] or "",
                                    partner_phone_numbers=partner_phones,
                                )
                                
                                if sent_count > 0:
                                    st.success(status_msg)
                                    st.balloons()
                                else:
                                    st.error(status_msg)
                    except Exception as error:
                        st.error(f"Error sending WhatsApp messages: {str(error)}")

                st.divider()
                st.markdown("#### Update / Reschedule an Existing Event")
                
                selected_evt_label_update = st.selectbox("Select Event to Update", list(event_options.keys()), key="update_event_select")
                selected_evt_update = event_options[selected_evt_label_update]

                with st.form("update_event_form"):
                    up_col1, up_col2 = st.columns(2)
                    with up_col1:
                        up_event_name = st.text_input("Function Name", value=selected_evt_update["event_name"])
                        # Parse date
                        evt_d = selected_evt_update["event_date"]
                        if isinstance(evt_d, str):
                            evt_d = datetime.datetime.strptime(evt_d, "%Y-%m-%d").date()
                        up_event_date = st.date_input("Reschedule Date", value=evt_d)
                    with up_col2:
                        up_event_place = st.text_input("Venue / Mandapam", value=selected_evt_update["event_place"] or "")
                        up_event_location = st.text_input("Location / City", value=selected_evt_update["event_location"] or "")

                    update_evt_button = st.form_submit_button("Update Event Details", type="secondary")

                if update_evt_button:
                    up_success, up_msg = update_event_by_host(
                        event_id=selected_evt_update["event_id"],
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
                summary_df = pd.DataFrame(partner_rows)
                total_given = summary_df["total_given"].sum()
                total_received = summary_df["total_received"].sum()
                net_overall = total_given - total_received

                st.markdown("#### 📊 At a Glance")
                kpi1, kpi2, kpi3 = st.columns(3)
                kpi1.metric("Total Given", f"₹{total_given:,.0f}")
                kpi2.metric("Total Received", f"₹{total_received:,.0f}")
                kpi3.metric(
                    "Net Balance",
                    f"₹{net_overall:,.0f}",
                    delta=("You've given more" if net_overall > 0 else "You've received more" if net_overall < 0 else "Even"),
                )

                chart_col1, chart_col2 = st.columns([3, 2])
                with chart_col1:
                    st.markdown("**Given vs Received, by Family**")
                    chart_df = summary_df.set_index("other_husband_name")[["total_given", "total_received"]]
                    chart_df = chart_df.rename(columns={"total_given": "Given", "total_received": "Received"})
                    st.bar_chart(chart_df, use_container_width=True)
                with chart_col2:
                    st.markdown("**Overall Split**")
                    pie_df = pd.DataFrame(
                        {"Type": ["Given", "Received"], "Amount": [total_given, total_received]}
                    )
                    st.altair_chart(
                        {
                            "mark": {"type": "arc", "innerRadius": 60},
                            "encoding": {
                                "theta": {"field": "Amount", "type": "quantitative"},
                                "color": {"field": "Type", "type": "nominal"},
                                "tooltip": [
                                    {"field": "Type", "type": "nominal"},
                                    {"field": "Amount", "type": "quantitative"},
                                ],
                            },
                            "data": {"values": pie_df.to_dict("records")},
                        },
                        use_container_width=True,
                    )

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

    # -------------------------------------------------------------------------
    # TAB 4: Voice AI Assistant (scoped to this family's received contributions)
    # -------------------------------------------------------------------------
    with tab_voice:
        st.subheader("My Voice Assistant")
        st.caption(
            "Ask in Tamil or English about contributions received by your family. "
            "Other families' private records are not searched."
        )

        def reset_portal_voice():
            st.session_state["portal_voice_generation"] = (
                st.session_state.get("portal_voice_generation", 0) + 1
            )
            for key in (
                "portal_voice_transcript",
                "portal_voice_plan",
                "portal_voice_results",
                "portal_voice_response",
                "portal_voice_audio",
                "portal_voice_error",
            ):
                st.session_state.pop(key, None)

        st.button(
            "New question / Reset",
            key="portal_voice_reset",
            on_click=reset_portal_voice,
            use_container_width=True,
        )
        voice_generation = st.session_state.get("portal_voice_generation", 0)
        voice_recording = st.audio_input(
            "Ask about contributions received by your family",
            sample_rate=16000,
            key=f"portal_voice_recording_{voice_generation}",
        )
        voice_typed_query = st.text_input(
            "Or type your question",
            placeholder="Who contributed more than 10000?",
            key=f"portal_voice_text_{voice_generation}",
        )

        if st.button(
            "Find my contribution",
            type="primary",
            key="portal_voice_find",
            use_container_width=True,
        ):
            question = voice_typed_query.strip()
            if voice_recording is not None:
                with st.spinner("Converting speech to text..."):
                    transcription_ok, transcription = transcribe_audio_with_whisper(
                        voice_recording.getvalue()
                    )
                if transcription_ok:
                    question = transcription.strip()
                else:
                    st.session_state["portal_voice_error"] = transcription

            if not question:
                st.session_state["portal_voice_error"] = (
                    "Record a message or type a question."
                )
            else:
                st.session_state["portal_voice_transcript"] = question
                with st.spinner("Understanding your question..."):
                    query_plan = parse_contribution_query_with_gpt(question)
                if query_plan.get("error"):
                    st.session_state["portal_voice_error"] = query_plan["error"]
                else:
                    st.session_state.pop("portal_voice_error", None)
                    st.session_state["portal_voice_plan"] = query_plan
                    if query_plan["query_type"] == "amount_filter":
                        voice_results = search_contributions_by_amount(
                            query_plan["amount"],
                            query_plan["operator"],
                            receiver_id=family["id"],
                        )
                    else:
                        voice_results = search_family_contributions_many(
                            query_plan.get(
                                "husband_names", [query_plan["husband_name"]]
                            ),
                            query_plan["current_place"],
                            receiver_id=family["id"],
                        )
                    st.session_state["portal_voice_results"] = voice_results
                    visible_response = build_tamil_contribution_response(
                        voice_results, query_plan
                    )
                    spoken_response = build_tamil_contribution_response(
                        voice_results, query_plan, spoken=True
                    )
                    st.session_state["portal_voice_response"] = visible_response
                    speech_ok, speech_audio = text_to_speech_openai(spoken_response)
                    st.session_state["portal_voice_audio"] = (
                        speech_audio if speech_ok else None
                    )

        if "portal_voice_transcript" in st.session_state:
            st.markdown("**Recognized request**")
            st.write(st.session_state["portal_voice_transcript"])
        if "portal_voice_error" in st.session_state:
            st.error(st.session_state["portal_voice_error"])
        if "portal_voice_results" in st.session_state:
            voice_results = st.session_state["portal_voice_results"]
            st.metric("Matching people", len(voice_results))
            if voice_results and st.session_state["portal_voice_plan"]["response_mode"] == "list":
                st.dataframe(
                    voice_results,
                    use_container_width=True,
                    hide_index=True,
                    column_order=[
                        "husband_name",
                        "wife_name",
                        "current_place",
                        "total_contributed",
                        "contribution_count",
                    ],
                    column_config={
                        "husband_name": "Husband Name",
                        "wife_name": "Wife Name",
                        "current_place": "Current Place",
                        "total_contributed": st.column_config.NumberColumn(
                            "Amount Received", format="₹%.2f"
                        ),
                        "contribution_count": "Contributions",
                    },
                )
            st.markdown("**தமிழ் பதில்**")
            st.write(st.session_state["portal_voice_response"])
            if st.session_state.get("portal_voice_audio"):
                st.audio(
                    st.session_state["portal_voice_audio"],
                    format="audio/mp3",
                    autoplay=True,
                )

