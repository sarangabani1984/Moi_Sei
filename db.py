import os

import pyodbc
import streamlit as st


SERVER = os.getenv("MOI_SEI_SQL_SERVER", r"JNPR-WIN-MPRZ09\SQLEXPRESS")
DATABASE = os.getenv("MOI_SEI_SQL_DATABASE", "MoiSei")


@st.cache_resource
def get_connection():
    """Open one reusable Windows-authenticated connection to SQL Server."""
    connection_string = (
        "DRIVER={ODBC Driver 18 for SQL Server};"
        f"SERVER={SERVER};"
        f"DATABASE={DATABASE};"
        "Trusted_Connection=yes;"
        "TrustServerCertificate=yes;"
    )
    return pyodbc.connect(connection_string)


def fetch_one(query, parameter):
    connection = get_connection()
    cursor = connection.cursor()
    cursor.execute(query, parameter)
    row = cursor.fetchone()
    if row is None:
        return None
    columns = [column[0] for column in cursor.description]
    return dict(zip(columns, row))


def fetch_procedure_rows(call, *parameters):
    connection = get_connection()
    cursor = connection.cursor()
    cursor.execute(call, *parameters)
    columns = [column[0] for column in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


def get_family_by_phone(phone_number):
    rows = fetch_procedure_rows(
        "{CALL dbo.sp_GetFamilyByPhone (?)}",
        phone_number,
    )
    if not rows:
        return None
    # The procedure only returns login fields; fetch the full record for display.
    return get_family(rows[0]["id"])


def get_my_contributions(user_id):
    return fetch_procedure_rows(
        "{CALL dbo.sp_GetMyContributions (?)}",
        user_id,
    )


def get_my_received_contributions(user_id):
    return fetch_procedure_rows(
        "{CALL dbo.sp_GetMyReceivedContributions (?)}",
        user_id,
    )


def get_my_partner_history(user_id):
    return fetch_procedure_rows(
        "{CALL dbo.sp_GetMyPartnerHistory (?)}",
        user_id,
    )


def get_my_partner_transactions(user_id, other_user_id):
    return fetch_procedure_rows(
        "{CALL dbo.sp_GetMyPartnerTransactions (?, ?)}",
        user_id,
        other_user_id,
    )


def get_family(user_id):
    return fetch_one(
        """
        SELECT id, husband_name, wife_name, husband_job, phone_number,
               place, family_deity, email, is_active
        FROM dbo.users
        WHERE id = ?
        """,
        user_id,
    )


def get_event(event_id):
    return fetch_one(
        """
        SELECT event_id, event_name, event_date, event_place,
               event_location, is_active
        FROM dbo.event
        WHERE event_id = ?
        """,
        event_id,
    )


def get_event_with_host(event_id):
    return fetch_one(
        """
        SELECT e.event_id, e.event_name, e.event_date, e.event_place,
               e.event_location, e.is_active, e.host_user_id,
               h.husband_name AS host_husband_name,
               h.phone_number AS host_phone_number
        FROM dbo.event e
        LEFT JOIN dbo.users h ON h.id = e.host_user_id
        WHERE e.event_id = ?
        """,
        event_id,
    )



def create_family(husband_name, wife_name, husband_job, phone_number, place, family_deity, email):
    connection = get_connection()
    cursor = connection.cursor()
    try:
        cursor.execute(
            """
            INSERT INTO dbo.users
                (husband_name, wife_name, husband_job, phone_number, place, family_deity, email)
            OUTPUT INSERTED.id
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            husband_name,
            wife_name or None,
            husband_job or None,
            phone_number,
            place or None,
            family_deity or None,
            email or None,
        )
        new_id = cursor.fetchone()[0]
        connection.commit()
        return True, new_id
    except pyodbc.Error as error:
        connection.rollback()
        return False, str(error)


def process_contribution(contributor_id, receiver_id, event_id, amount):
    connection = get_connection()
    cursor = connection.cursor()
    try:
        cursor.execute(
            "{CALL dbo.sp_ProcessContribution (?, ?, ?, ?)}",
            contributor_id,
            receiver_id,
            event_id,
            amount,
        )
        connection.commit()
        return True, "Contribution recorded successfully."
    except pyodbc.Error as error:
        connection.rollback()
        return False, str(error)
