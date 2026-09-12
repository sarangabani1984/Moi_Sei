import os
import re
import streamlit as st

# Check if psycopg2 is available for PostgreSQL (Supabase / Neon)
try:
    import psycopg2
    PSYCOPG2_AVAILABLE = True
except ImportError:
    PSYCOPG2_AVAILABLE = False

# Check if pyodbc is available for SQL Server (Local)
try:
    import pyodbc
    PYODBC_AVAILABLE = True
except ImportError:
    PYODBC_AVAILABLE = False


def _get_secret_or_env(key: str) -> str:
    """Retrieve secret from Streamlit secrets or environment variables."""
    try:
        if hasattr(st, "secrets") and key in st.secrets:
            return str(st.secrets[key])
    except Exception:
        pass
    return os.getenv(key, "")


def _clean_postgres_uri(uri: str) -> str:
    """Removes literal brackets like [password] if user left them in secrets."""
    if not uri:
        return ""
    # Clean up literal brackets around password in postgres URI
    cleaned = re.sub(r":\[([^\]]+)\]@", r":\1@", uri.strip())
    cleaned = re.sub(r":%5B([^%]+)%5D@", r":\1@", cleaned)
    # Fix postgresql:// scheme
    if cleaned.startswith("postgres://"):
        cleaned = "postgresql://" + cleaned[11:]
    return cleaned


def is_postgres_mode() -> bool:
    """Determines whether to use PostgreSQL or SQL Server based on secrets/env."""
    uri = _get_secret_or_env("MOI_SEI_POSTGRES_URL") or _get_secret_or_env("POSTGRES_URL")
    return bool(uri and PSYCOPG2_AVAILABLE)


@st.cache_resource
def get_connection():
    """Opens a connection to PostgreSQL (if configured) or SQL Server Express."""
    postgres_uri = _clean_postgres_uri(
        _get_secret_or_env("MOI_SEI_POSTGRES_URL") or _get_secret_or_env("POSTGRES_URL")
    )

    if postgres_uri and PSYCOPG2_AVAILABLE:
        return psycopg2.connect(postgres_uri)

    if PYODBC_AVAILABLE:
        server = os.getenv("MOI_SEI_SQL_SERVER", r"JNPR-WIN-MPRZ09\SQLEXPRESS")
        database = os.getenv("MOI_SEI_SQL_DATABASE", "MoiSei")
        connection_string = (
            "DRIVER={ODBC Driver 18 for SQL Server};"
            f"SERVER={server};"
            f"DATABASE={database};"
            "Trusted_Connection=yes;"
            "TrustServerCertificate=yes;"
        )
        return pyodbc.connect(connection_string)

    raise RuntimeError("Neither PostgreSQL (psycopg2) nor SQL Server (pyodbc) driver is available.")


def fetch_one(query_mssql, query_pg, parameter):
    """Executes a single-parameter lookup compatible with both MSSQL and Postgres."""
    connection = get_connection()
    cursor = connection.cursor()
    
    if is_postgres_mode():
        cursor.execute(query_pg, (parameter,))
    else:
        cursor.execute(query_mssql, (parameter,))
        
    row = cursor.fetchone()
    if row is None:
        return None
    columns = [column[0] for column in cursor.description]
    return dict(zip(columns, row))


def fetch_procedure_rows(proc_name, *parameters):
    """Executes a stored procedure / function compatible with both MSSQL and Postgres."""
    connection = get_connection()
    cursor = connection.cursor()

    if is_postgres_mode():
        placeholders = ", ".join(["%s"] * len(parameters))
        sql = f"SELECT * FROM {proc_name}({placeholders});"
        cursor.execute(sql, parameters)
    else:
        placeholders = ", ".join(["?"] * len(parameters))
        sql = f"{{CALL dbo.{proc_name} ({placeholders})}}"
        cursor.execute(sql, parameters)

    columns = [column[0] for column in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


def get_family_by_phone(phone_number):
    """Log a family in by phone number and return their full profile."""
    rows = fetch_procedure_rows("sp_GetFamilyByPhone", phone_number)
    if not rows:
        return None
    return get_family(rows[0]["id"])


def get_my_contributions(user_id):
    """Return every contribution this family has given, with receiver details."""
    return fetch_procedure_rows("sp_GetMyContributions", user_id)


def get_my_received_contributions(user_id):
    """Return every amount this family has received, with contributor details."""
    return fetch_procedure_rows("sp_GetMyReceivedContributions", user_id)


def get_my_partner_history(user_id):
    """Return one summary row per family this user has ever exchanged with."""
    return fetch_procedure_rows("sp_GetMyPartnerHistory", user_id)


def get_my_partner_transactions(user_id, other_user_id):
    """Return the full chronological transaction history with one specific family."""
    return fetch_procedure_rows("sp_GetMyPartnerTransactions", user_id, other_user_id)


def get_family(user_id):
    """Fetch one family's full profile by their permanent id, or None if not found."""
    sql_mssql = """
        SELECT id, husband_name, wife_name, husband_job, phone_number,
               place, family_deity, email, is_active
        FROM dbo.users
        WHERE id = ?
    """
    sql_pg = """
        SELECT id, husband_name, wife_name, husband_job, phone_number,
               place, family_deity, email, is_active
        FROM users
        WHERE id = %s
    """
    return fetch_one(sql_mssql, sql_pg, user_id)


def get_event(event_id):
    """Fetch one event's details by its id, or None if not found."""
    sql_mssql = """
        SELECT event_id, event_name, event_date, event_place,
               event_location, is_active
        FROM dbo.event
        WHERE event_id = ?
    """
    sql_pg = """
        SELECT event_id, event_name, event_date, event_place,
               event_location, is_active
        FROM event
        WHERE event_id = %s
    """
    return fetch_one(sql_mssql, sql_pg, event_id)


def get_event_with_host(event_id):
    """Fetch one event's details plus the profile of its locked-in host (receiver)."""
    sql_mssql = """
        SELECT e.event_id, e.event_name, e.event_date, e.event_place,
               e.event_location, e.is_active, e.host_user_id,
               h.husband_name AS host_husband_name,
               h.phone_number AS host_phone_number
        FROM dbo.event e
        LEFT JOIN dbo.users h ON h.id = e.host_user_id
        WHERE e.event_id = ?
    """
    sql_pg = """
        SELECT e.event_id, e.event_name, e.event_date, e.event_place,
               e.event_location, e.is_active, e.host_user_id,
               h.husband_name AS host_husband_name,
               h.phone_number AS host_phone_number
        FROM event e
        LEFT JOIN users h ON h.id = e.host_user_id
        WHERE e.event_id = %s
    """
    return fetch_one(sql_mssql, sql_pg, event_id)


def create_family(husband_name, wife_name, husband_job, phone_number, place, family_deity, email):
    """Insert a new family record and return its new permanent id."""
    connection = get_connection()
    cursor = connection.cursor()
    try:
        if is_postgres_mode():
            cursor.execute(
                """
                INSERT INTO users
                    (husband_name, wife_name, husband_job, phone_number, place, family_deity, email)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                RETURNING id;
                """,
                (
                    husband_name,
                    wife_name or None,
                    husband_job or None,
                    phone_number,
                    place or None,
                    family_deity or None,
                    email or None,
                ),
            )
            new_id = cursor.fetchone()[0]
        else:
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
    except Exception as error:
        connection.rollback()
        return False, str(error)


def process_contribution(contributor_id, receiver_id, event_id, amount):
    """Record one contribution by executing sp_ProcessContribution."""
    connection = get_connection()
    cursor = connection.cursor()
    try:
        if is_postgres_mode():
            cursor.execute(
                "SELECT sp_ProcessContribution(%s, %s, %s, %s);",
                (contributor_id, receiver_id, event_id, amount),
            )
        else:
            cursor.execute(
                "{CALL dbo.sp_ProcessContribution (?, ?, ?, ?)}",
                contributor_id,
                receiver_id,
                event_id,
                amount,
            )
        connection.commit()
        return True, "Contribution recorded successfully."
    except Exception as error:
        connection.rollback()
        return False, str(error)
