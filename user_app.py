import pyodbc
import streamlit as st

from db import (
    get_connection,
    get_family_by_phone,
    get_my_contributions,
    get_my_partner_history,
    get_my_partner_transactions,
    get_my_received_contributions,
)


st.set_page_config(page_title="Moi Sei Family Portal", page_icon="F", layout="wide")
st.title("Moi Sei Family Portal")
st.caption("View only your family's contribution and received history.")

try:
    get_connection()
except pyodbc.Error as error:
    st.error("Could not connect to SQL Server.")
    st.code(str(error))
    st.stop()

phone_number = st.text_input(
    "Registered phone number",
    placeholder="9000000001",
)

if st.button("View My Records", type="primary", use_container_width=True):
    try:
        family = get_family_by_phone(phone_number.strip())
        if family is None:
            st.error("No active family was found for that phone number.")
            st.session_state.pop("logged_in_family", None)
        else:
            st.session_state["logged_in_family"] = family
    except pyodbc.Error as error:
        st.error("Could not load family records.")
        st.code(str(error))

if "logged_in_family" in st.session_state:
    family = st.session_state["logged_in_family"]
    st.success(f"Signed in as {family['husband_name']} family.")
    st.write(f"**Family ID:** {family['id']}")
    st.write(f"**Phone:** {family['phone_number']}")

    try:
        contribution_rows = get_my_contributions(family["id"])
        received_rows = get_my_received_contributions(family["id"])

        st.subheader("My Contributions")
        if contribution_rows:
            st.dataframe(contribution_rows, use_container_width=True, hide_index=True)
        else:
            st.info("No contribution records found.")

        st.subheader("My Received Contributions")
        if received_rows:
            st.dataframe(received_rows, use_container_width=True, hide_index=True)
        else:
            st.info("No received contribution records found.")

        st.subheader("Give & Take History (All Events)")
        st.caption(
            "For each family you've exchanged with, across every event combined: "
            "what you've given them, what you've received from them, and the difference."
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
    except pyodbc.Error as error:
        st.error("Could not load this family's records.")
        st.code(str(error))
