import json
import hashlib
import os
import re
import urllib.parse
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


def hash_password(password: str) -> str:
    """Create a salted PBKDF2 password hash; only this hash is stored."""
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 200_000)
    return f"pbkdf2_sha256$200000${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored_hash: str) -> bool:
    """Verify a password against a stored PBKDF2 hash."""
    try:
        algorithm, iterations, salt_hex, digest_hex = stored_hash.split("$")
        if algorithm != "pbkdf2_sha256":
            return False
        candidate = hashlib.pbkdf2_hmac(
            "sha256", password.encode(), bytes.fromhex(salt_hex), int(iterations)
        )
        return candidate.hex() == digest_hex
    except (AttributeError, ValueError):
        return False


def parse_pg_uri(uri: str):
    """Parses any Postgres URI into explicit kwargs for psycopg2.
    Handles unencoded @ or [brackets] in password gracefully.
    """
    if not uri:
        return None
    raw = uri.strip()
    raw = re.sub(r"^(postgres|postgresql)://", "", raw)
    at_idx = raw.rfind("@")
    if at_idx == -1:
        return None
    user_pass = raw[:at_idx]
    host_db = raw[at_idx + 1 :]

    if ":" in user_pass:
        user, pwd = user_pass.split(":", 1)
    else:
        user, pwd = user_pass, ""

    pwd = urllib.parse.unquote(re.sub(r"^\[|\]$", "", pwd))

    m_host = re.match(r"^([^/@:]+)(?::(\d+))?/(.+)$", host_db)
    if not m_host:
        return None
    host, port, db = m_host.groups()
    db = db.split("?")[0]

    return {
        "user": user,
        "password": pwd,
        "host": host,
        "port": int(port) if port else 5432,
        "dbname": db,
        "sslmode": "require",
        "connect_timeout": 15,
    }


def is_postgres_mode() -> bool:
    """Determines whether to use PostgreSQL or SQL Server based on secrets/env."""
    uri = _get_secret_or_env("MOI_SEI_POSTGRES_URL") or _get_secret_or_env("POSTGRES_URL")
    return bool(uri and PSYCOPG2_AVAILABLE)


@st.cache_resource
def get_connection():
    """Opens a connection to PostgreSQL (if configured) or SQL Server Express."""
    postgres_uri = _get_secret_or_env("MOI_SEI_POSTGRES_URL") or _get_secret_or_env("POSTGRES_URL")

    if postgres_uri and PSYCOPG2_AVAILABLE:
        conn_kwargs = parse_pg_uri(postgres_uri)
        if conn_kwargs:
            try:
                connection = psycopg2.connect(**conn_kwargs)
                connection.autocommit = True
                return connection
            except Exception as exc1:
                try:
                    connection = psycopg2.connect(postgres_uri, sslmode="require")
                    connection.autocommit = True
                    return connection
                except Exception as exc2:
                    raise RuntimeError(
                        f"Failed to connect to PostgreSQL database. Details: {exc1}"
                    ) from exc1
        try:
            return psycopg2.connect(postgres_uri, sslmode="require")
        except Exception as exc:
            raise RuntimeError(
                f"Failed to connect to PostgreSQL database. Details: {exc}"
            ) from exc

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


def get_family_by_husband_name(husband_name):
    """Find one active family by an exact husband name, case-insensitively."""
    sql_mssql = """
        SELECT TOP 1 id FROM dbo.users
        WHERE LOWER(husband_name) = LOWER(?) AND is_active = 1
    """
    sql_pg = """
        SELECT id FROM users
        WHERE LOWER(husband_name) = LOWER(%s) AND is_active = TRUE
        LIMIT 1
    """
    row = fetch_one(sql_mssql, sql_pg, husband_name.strip())
    return get_family(row["id"]) if row else None


def search_families(search_text):
    """Return active families whose Tamil/English name, alias, or phone matches."""
    search_text = search_text.strip()
    connection = get_connection()
    cursor = connection.cursor()
    pattern = f"%{search_text}%"
    if is_postgres_mode():
        cursor.execute(
            """
                        SELECT id, husband_name, wife_name, phone_number, place
            FROM users
            WHERE is_active = TRUE
                            AND (husband_name ILIKE %s OR wife_name ILIKE %s OR phone_number LIKE %s OR search_alias ILIKE %s)
            ORDER BY husband_name
            LIMIT 10;
            """,
            (pattern, pattern, pattern, pattern),
        )
    else:
        cursor.execute(
            """
                        SELECT TOP 10 id, husband_name, wife_name, phone_number, place
            FROM dbo.users
            WHERE is_active = 1
                            AND (husband_name LIKE ? OR wife_name LIKE ? OR phone_number LIKE ? OR search_alias LIKE ?)
            ORDER BY husband_name;
            """,
            (pattern, pattern, pattern, pattern),
        )
    columns = [column[0] for column in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


def get_active_families_for_search():
    """Return active family choices for the staff searchable name field."""
    connection = get_connection()
    cursor = connection.cursor()
    if is_postgres_mode():
        cursor.execute(
            """
            SELECT id, husband_name, phone_number, place, search_alias
            FROM users
            WHERE is_active = TRUE
            ORDER BY husband_name;
            """
        )
    else:
        cursor.execute(
            """
            SELECT id, husband_name, phone_number, place, search_alias
            FROM dbo.users
            WHERE is_active = 1
            ORDER BY husband_name;
            """
        )
    columns = [column[0] for column in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


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
             place, family_deity, email, search_alias, password_hash, is_active
        FROM dbo.users
        WHERE id = ?
    """
    sql_pg = """
         SELECT id, husband_name, wife_name, husband_job, phone_number,
             place, family_deity, email, search_alias, password_hash, is_active
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


def get_active_events():
    """Return active events for the staff contribution entry screen."""
    connection = get_connection()
    cursor = connection.cursor()
    if is_postgres_mode():
        cursor.execute(
            """
            SELECT event_id, event_name, event_date, event_place, host_user_id
            FROM event
            WHERE is_active = TRUE
            ORDER BY event_date DESC, event_id DESC;
            """
        )
    else:
        cursor.execute(
            """
            SELECT event_id, event_name, event_date, event_place, host_user_id
            FROM dbo.event
            WHERE is_active = 1
            ORDER BY event_date DESC, event_id DESC;
            """
        )
    columns = [column[0] for column in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


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


def create_family(husband_name, wife_name, husband_job, phone_number, place, family_deity, email, search_alias, password):
    """Insert a new family record and return its new permanent id."""
    connection = get_connection()
    cursor = connection.cursor()
    try:
        if is_postgres_mode():
            cursor.execute(
                """
                INSERT INTO users
                    (husband_name, wife_name, husband_job, phone_number, place, family_deity, email, search_alias, password_hash)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
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
                    search_alias or None,
                    hash_password(password),
                ),
            )
            new_id = cursor.fetchone()[0]
        else:
            cursor.execute(
                """
                INSERT INTO dbo.users
                    (husband_name, wife_name, husband_job, phone_number, place, family_deity, email, search_alias, password_hash)
                OUTPUT INSERTED.id
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                husband_name,
                wife_name or None,
                husband_job or None,
                phone_number,
                place or None,
                family_deity or None,
                email or None,
                search_alias or None,
                hash_password(password),
            )
            new_id = cursor.fetchone()[0]
        connection.commit()
        return True, new_id
    except Exception as error:
        connection.rollback()
        return False, str(error)


def set_family_password(user_id, password):
    """Set or replace the portal password for an existing family."""
    connection = get_connection()
    cursor = connection.cursor()
    try:
        if is_postgres_mode():
            cursor.execute("UPDATE users SET password_hash = %s WHERE id = %s", (hash_password(password), user_id))
        else:
            cursor.execute("UPDATE dbo.users SET password_hash = ? WHERE id = ?", hash_password(password), user_id)
        connection.commit()
        return True, "Password created successfully."
    except Exception as error:
        connection.rollback()
        return False, str(error)


def update_family_profile(
    user_id,
    husband_name,
    wife_name,
    husband_job,
    place,
    family_deity,
    email,
    search_alias,
):
    """Update editable profile fields while keeping the login phone unchanged."""
    connection = get_connection()
    cursor = connection.cursor()
    try:
        if is_postgres_mode():
            cursor.execute(
                """
                UPDATE users
                SET husband_name = %s, wife_name = %s, husband_job = %s,
                    place = %s, family_deity = %s, email = %s,
                    search_alias = %s, updated_at = NOW()
                WHERE id = %s AND is_active = TRUE
                """,
                (husband_name, wife_name or None, husband_job or None, place or None,
                 family_deity or None, email or None, search_alias or None, user_id),
            )
        else:
            cursor.execute(
                """
                UPDATE dbo.users
                SET husband_name = ?, wife_name = ?, husband_job = ?,
                    place = ?, family_deity = ?, email = ?,
                    search_alias = ?, updated_at = SYSDATETIME()
                WHERE id = ? AND is_active = 1
                """,
                husband_name, wife_name or None, husband_job or None, place or None,
                family_deity or None, email or None, search_alias or None, user_id,
            )
        if cursor.rowcount != 1:
            connection.rollback()
            return False, "Family profile was not found or is inactive."
        connection.commit()
        return True, "Profile updated successfully."
    except Exception as error:
        connection.rollback()
        return False, str(error)


def change_event_receiver(event_id, receiver_id):
    """Change an event's receiver before its first contribution is recorded."""
    connection = get_connection()
    cursor = connection.cursor()
    try:
        if is_postgres_mode():
            cursor.execute(
                "SELECT COUNT(*) FROM journal_entries WHERE event_id = %s",
                (event_id,),
            )
            contribution_count = cursor.fetchone()[0]
            if contribution_count:
                return False, "The receiver cannot be changed after contributions have been recorded for this event."
            cursor.execute(
                """
                UPDATE event
                SET host_user_id = %s, updated_at = NOW()
                WHERE event_id = %s AND is_active = TRUE
                """,
                (receiver_id, event_id),
            )
        else:
            cursor.execute(
                "SELECT COUNT(*) FROM dbo.journal_entries WHERE event_id = ?",
                event_id,
            )
            contribution_count = cursor.fetchone()[0]
            if contribution_count:
                return False, "The receiver cannot be changed after contributions have been recorded for this event."
            cursor.execute(
                """
                UPDATE dbo.event
                SET host_user_id = ?, updated_at = SYSDATETIME()
                WHERE event_id = ? AND is_active = 1
                """,
                receiver_id,
                event_id,
            )
        if cursor.rowcount != 1:
            connection.rollback()
            return False, "The event was not found or is inactive."
        connection.commit()
        return True, "Event receiver changed successfully."
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


def get_my_hosted_events(host_user_id):
    """Fetch all events hosted by a specific family (past & upcoming)."""
    connection = get_connection()
    cursor = connection.cursor()
    if is_postgres_mode():
        cursor.execute(
            """
            SELECT event_id, event_name, event_date, event_place, event_location, is_active
            FROM event
            WHERE host_user_id = %s AND is_active = TRUE
            ORDER BY event_date DESC;
            """,
            (host_user_id,),
        )
    else:
        cursor.execute(
            """
            SELECT event_id, event_name, event_date, event_place, event_location, is_active
            FROM dbo.event
            WHERE host_user_id = ? AND is_active = 1
            ORDER BY event_date DESC;
            """,
            (host_user_id,),
        )
    columns = [column[0] for column in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


def create_event_by_host(event_name, event_date, event_place, event_location, host_user_id):
    """Allows a family to schedule/announce an upcoming event where they are the host."""
    connection = get_connection()
    cursor = connection.cursor()
    try:
        if is_postgres_mode():
            cursor.execute(
                """
                INSERT INTO event (event_name, event_date, event_place, event_location, host_user_id)
                VALUES (%s, %s, %s, %s, %s)
                RETURNING event_id;
                """,
                (event_name, event_date, event_place, event_location or None, host_user_id),
            )
            new_id = cursor.fetchone()[0]
        else:
            cursor.execute(
                """
                INSERT INTO dbo.event (event_name, event_date, event_place, event_location, host_user_id)
                OUTPUT INSERTED.event_id
                VALUES (?, ?, ?, ?, ?)
                """,
                event_name,
                event_date,
                event_place,
                event_location or None,
                host_user_id,
            )
            new_id = cursor.fetchone()[0]
        connection.commit()
        return True, new_id
    except Exception as error:
        connection.rollback()
        return False, str(error)


def update_event_by_host(event_id, event_name, event_date, event_place, event_location, host_user_id):
    """Allows a host family to update or reschedule their upcoming event details."""
    connection = get_connection()
    cursor = connection.cursor()
    try:
        if is_postgres_mode():
            cursor.execute(
                """
                UPDATE event
                SET event_name = %s, event_date = %s, event_place = %s, event_location = %s, updated_at = NOW()
                WHERE event_id = %s AND host_user_id = %s AND is_active = TRUE;
                """,
                (event_name, event_date, event_place, event_location or None, event_id, host_user_id),
            )
        else:
            cursor.execute(
                """
                UPDATE dbo.event
                SET event_name = ?, event_date = ?, event_place = ?, event_location = ?, updated_at = SYSDATETIME()
                WHERE event_id = ? AND host_user_id = ? AND is_active = 1;
                """,
                event_name,
                event_date,
                event_place,
                event_location or None,
                event_id,
                host_user_id,
            )
        connection.commit()
        return True, "Event updated successfully."
    except Exception as error:
        connection.rollback()
        return False, str(error)


def get_upcoming_partner_events(user_id):
    """Returns upcoming events hosted by families with whom `user_id` has exchanged contributions."""
    connection = get_connection()
    cursor = connection.cursor()
    if is_postgres_mode():
        cursor.execute(
            """
            WITH partner_ids AS (
                SELECT DISTINCT 
                    CASE WHEN c.user_id = %s THEN r.user_id ELSE c.user_id END AS partner_id
                FROM journal_entries c
                JOIN journal_entries r ON r.transaction_id = c.transaction_id AND r.entry_type = 'RECEIVED'
                WHERE c.entry_type = 'CONTRIBUTED' AND (c.user_id = %s OR r.user_id = %s)
            )
            SELECT 
                e.event_id,
                e.event_name,
                e.event_date,
                e.event_place,
                e.event_location,
                h.id AS host_id,
                h.husband_name AS host_husband_name,
                h.wife_name AS host_wife_name,
                h.phone_number AS host_phone_number,
                h.place AS host_place,
                COALESCE((
                    SELECT SUM(incoming.amount)
                    FROM journal_entries incoming
                    JOIN journal_entries outgoing
                        ON outgoing.transaction_id = incoming.transaction_id
                       AND outgoing.entry_type = 'CONTRIBUTED'
                    WHERE incoming.entry_type = 'RECEIVED'
                      AND incoming.user_id = %s
                      AND outgoing.user_id = e.host_user_id
                ), 0) AS partner_contributed_to_you
                                , COALESCE((
                                        SELECT SUM(outgoing.amount)
                                        FROM journal_entries outgoing
                                        JOIN journal_entries incoming
                                                ON incoming.transaction_id = outgoing.transaction_id
                                             AND incoming.entry_type = 'RECEIVED'
                                        WHERE outgoing.entry_type = 'CONTRIBUTED'
                                            AND outgoing.user_id = %s
                                            AND incoming.user_id = e.host_user_id
                                ), 0) AS you_contributed_to_host
                                , COALESCE((
                                        SELECT SUM(incoming.amount)
                                        FROM journal_entries incoming
                                        JOIN journal_entries outgoing
                                                ON outgoing.transaction_id = incoming.transaction_id
                                             AND outgoing.entry_type = 'CONTRIBUTED'
                                        WHERE incoming.entry_type = 'RECEIVED'
                                            AND incoming.user_id = %s
                                            AND outgoing.user_id = e.host_user_id
                                ), 0)
                                - COALESCE((
                                        SELECT SUM(outgoing.amount)
                                        FROM journal_entries outgoing
                                        JOIN journal_entries incoming
                                                ON incoming.transaction_id = outgoing.transaction_id
                                             AND incoming.entry_type = 'RECEIVED'
                                        WHERE outgoing.entry_type = 'CONTRIBUTED'
                                            AND outgoing.user_id = %s
                                            AND incoming.user_id = e.host_user_id
                                ), 0) AS net_difference
            FROM event e
            JOIN users h ON h.id = e.host_user_id
            JOIN partner_ids p ON p.partner_id = e.host_user_id
            WHERE e.is_active = TRUE
              AND e.event_date >= CURRENT_DATE
            ORDER BY e.event_date ASC;
            """,
            (user_id, user_id, user_id, user_id, user_id, user_id, user_id),
        )
    else:
        cursor.execute(
            """
            WITH partner_ids AS (
                SELECT DISTINCT 
                    CASE WHEN c.user_id = ? THEN r.user_id ELSE c.user_id END AS partner_id
                FROM journal_entries c
                JOIN journal_entries r ON r.transaction_id = c.transaction_id AND r.entry_type = 'RECEIVED'
                WHERE c.entry_type = 'CONTRIBUTED' AND (c.user_id = ? OR r.user_id = ?)
            )
            SELECT 
                e.event_id,
                e.event_name,
                e.event_date,
                e.event_place,
                e.event_location,
                h.id AS host_id,
                h.husband_name AS host_husband_name,
                h.wife_name AS host_wife_name,
                h.phone_number AS host_phone_number,
                h.place AS host_place,
                ISNULL((
                    SELECT SUM(incoming.amount)
                    FROM journal_entries incoming
                    JOIN journal_entries outgoing
                        ON outgoing.transaction_id = incoming.transaction_id
                       AND outgoing.entry_type = 'CONTRIBUTED'
                    WHERE incoming.entry_type = 'RECEIVED'
                      AND incoming.user_id = ?
                      AND outgoing.user_id = e.host_user_id
                ), 0) AS partner_contributed_to_you
                                , ISNULL((
                                        SELECT SUM(outgoing.amount)
                                        FROM journal_entries outgoing
                                        JOIN journal_entries incoming
                                                ON incoming.transaction_id = outgoing.transaction_id
                                             AND incoming.entry_type = 'RECEIVED'
                                        WHERE outgoing.entry_type = 'CONTRIBUTED'
                                            AND outgoing.user_id = ?
                                            AND incoming.user_id = e.host_user_id
                                ), 0) AS you_contributed_to_host
                                , ISNULL((
                                        SELECT SUM(incoming.amount)
                                        FROM journal_entries incoming
                                        JOIN journal_entries outgoing
                                                ON outgoing.transaction_id = incoming.transaction_id
                                             AND outgoing.entry_type = 'CONTRIBUTED'
                                        WHERE incoming.entry_type = 'RECEIVED'
                                            AND incoming.user_id = ?
                                            AND outgoing.user_id = e.host_user_id
                                ), 0)
                                - ISNULL((
                                        SELECT SUM(outgoing.amount)
                                        FROM journal_entries outgoing
                                        JOIN journal_entries incoming
                                                ON incoming.transaction_id = outgoing.transaction_id
                                             AND incoming.entry_type = 'RECEIVED'
                                        WHERE outgoing.entry_type = 'CONTRIBUTED'
                                            AND outgoing.user_id = ?
                                            AND incoming.user_id = e.host_user_id
                                ), 0) AS net_difference
            FROM dbo.event e
            JOIN dbo.users h ON h.id = e.host_user_id
            JOIN partner_ids p ON p.partner_id = e.host_user_id
            WHERE e.is_active = 1
              AND e.event_date >= CONVERT(DATE, SYSDATETIME())
            ORDER BY e.event_date ASC;
            """,
            (user_id, user_id, user_id, user_id, user_id, user_id, user_id),
        )
    columns = [column[0] for column in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]
