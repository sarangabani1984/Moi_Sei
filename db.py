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
    """Run a plain SELECT with one parameter and return the first row as a dict.

    Used for direct table lookups (get_family, get_event, ...). Returns None
    if no matching row exists.
    """
    connection = get_connection()
    cursor = connection.cursor()
    cursor.execute(query, parameter)
    row = cursor.fetchone()
    if row is None:
        return None
    columns = [column[0] for column in cursor.description]
    return dict(zip(columns, row))


def fetch_procedure_rows(call, *parameters):
    """Execute a stored procedure call and return every row as a list of dicts.

    `call` is an ODBC call string, e.g. "{CALL dbo.sp_GetMyContributions (?)}".
    `*parameters` are passed positionally to fill the procedure's `?` placeholders,
    so this works for procedures with one parameter or several.
    """
    connection = get_connection()
    cursor = connection.cursor()
    cursor.execute(call, *parameters)
    columns = [column[0] for column in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


def get_family_by_phone(phone_number):
    """Log a family in by phone number and return their full profile.

    Calls sp_GetFamilyByPhone to resolve the phone number to the family's
    permanent id, then fetches the complete record via get_family(). Returns
    None if no active family is registered with that phone number.
    """
    rows = fetch_procedure_rows(
        "{CALL dbo.sp_GetFamilyByPhone (?)}",
        phone_number,
    )
    if not rows:
        return None
    # The procedure only returns login fields; fetch the full record for display.
    return get_family(rows[0]["id"])


def get_my_contributions(user_id):
    """Return every contribution this family has given, with receiver details.

    Calls sp_GetMyContributions. Each row includes the receiver's full profile
    and the related event, so the caller never needs a second lookup.
    """
    return fetch_procedure_rows(
        "{CALL dbo.sp_GetMyContributions (?)}",
        user_id,
    )


def get_my_received_contributions(user_id):
    """Return every amount this family has received, with contributor details.

    Calls sp_GetMyReceivedContributions. Mirror of get_my_contributions: each
    row includes the contributor's full profile and the related event.
    """
    return fetch_procedure_rows(
        "{CALL dbo.sp_GetMyReceivedContributions (?)}",
        user_id,
    )


def get_my_partner_history(user_id):
    """Return one summary row per family this user has ever exchanged with.

    Calls sp_GetMyPartnerHistory. Each row totals what was given to, and
    received from, that one counterpart family across every event combined,
    plus the net difference (positive = this family gave more).
    """
    return fetch_procedure_rows(
        "{CALL dbo.sp_GetMyPartnerHistory (?)}",
        user_id,
    )


def get_my_partner_transactions(user_id, other_user_id):
    """Return the full chronological transaction history with one specific family.

    Calls sp_GetMyPartnerTransactions. Each row is one transaction between
    `user_id` and `other_user_id`, in date order, with a running net balance.
    """
    return fetch_procedure_rows(
        "{CALL dbo.sp_GetMyPartnerTransactions (?, ?)}",
        user_id,
        other_user_id,
    )


def get_family(user_id):
    """Fetch one family's full profile by their permanent id, or None if not found."""
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
    """Fetch one event's details by its id, or None if not found."""
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
    """Fetch one event's details plus the profile of its locked-in host (receiver).

    `host_user_id` and the joined `host_husband_name`/`host_phone_number` are
    None if the event has not received its first contribution yet, since the
    host is only locked in at that point (see sp_ProcessContribution).
    """
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
    """Insert a new family record and return its new permanent id.

    Used by the admin app when a contributor or receiver's phone number isn't
    registered yet, so staff can add them on the spot without leaving the flow.
    All fields except husband_name and phone_number are optional (blank string
    or falsy values are stored as NULL).

    Returns:
        (True, new_id) on success.
        (False, error_message) if the insert fails (e.g. duplicate phone number).
    """
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
    """Record one contribution by calling sp_ProcessContribution.

    This is the only function that writes a contribution. All validation
    (matching families, valid amount, one-host-per-event rule) happens inside
    the stored procedure, not here.

    Returns:
        (True, success_message) on success.
        (False, error_message) if the procedure rejects or fails the request.
    """
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
