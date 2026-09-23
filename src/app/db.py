import json
import hashlib
import os
import re
import threading
import urllib.parse
from difflib import SequenceMatcher
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


_thread_local = threading.local()


def _create_connection():
    """Opens a fresh connection to PostgreSQL (if configured) or SQL Server Express."""
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


def get_connection():
    """Return a per-thread database connection.

    Each thread (e.g. an API worker thread or the Streamlit script thread) gets
    its own connection, reused across calls. This avoids sharing a single
    connection across threads, which is not safe for pyodbc/psycopg2 and caused
    500 errors under concurrent requests.
    """
    connection = getattr(_thread_local, "connection", None)
    if connection is not None:
        try:
            # Cheap liveness check; reuse if the connection is still healthy.
            cursor = connection.cursor()
            cursor.execute("SELECT 1")
            cursor.fetchall()
            return connection
        except Exception:
            try:
                connection.close()
            except Exception:
                pass
            _thread_local.connection = None

    connection = _create_connection()
    _thread_local.connection = connection
    return connection


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


def search_family_contributions(
    husband_name, current_place, receiver_id=None, *, allow_fuzzy=True
):
    """Find contribution totals using safely bound husband-name and place filters."""
    husband_name = husband_name.strip()
    current_place = current_place.strip()
    if not husband_name and not current_place:
        return []

    connection = get_connection()
    cursor = connection.cursor()
    name_pattern = f"%{husband_name}%"
    place_pattern = f"%{current_place}%"
    if is_postgres_mode():
        cursor.execute(
            """
            SELECT u.id, u.husband_name, u.wife_name, u.current_place,
                   COUNT(DISTINCT CASE WHEN je.entry_type = 'CONTRIBUTED'
                                       THEN je.transaction_id END) AS contribution_count,
                   COALESCE(SUM(CASE WHEN je.entry_type = 'CONTRIBUTED'
                                     THEN je.amount ELSE 0 END), 0) AS total_contributed
            FROM users u
            LEFT JOIN journal_entries je ON je.user_id = u.id
            WHERE u.is_active = TRUE
              AND (%s = '' OR u.husband_name ILIKE %s OR u.search_alias ILIKE %s)
              AND (%s = '' OR u.current_place ILIKE %s)
                            AND (%s IS NULL OR EXISTS (
                                    SELECT 1 FROM journal_entries received
                                    WHERE received.transaction_id = je.transaction_id
                                        AND received.user_id = %s
                                        AND received.entry_type = 'RECEIVED'
                            ))
            GROUP BY u.id, u.husband_name, u.wife_name, u.current_place
            ORDER BY u.husband_name;
            """,
                        (
                                husband_name, name_pattern, name_pattern, current_place, place_pattern,
                                receiver_id, receiver_id,
                        ),
        )
    else:
        cursor.execute(
            """
            SELECT u.id, u.husband_name, u.wife_name, u.current_place,
                   COUNT(DISTINCT CASE WHEN je.entry_type = 'CONTRIBUTED'
                                       THEN je.transaction_id END) AS contribution_count,
                   COALESCE(SUM(CASE WHEN je.entry_type = 'CONTRIBUTED'
                                     THEN je.amount ELSE 0 END), 0) AS total_contributed
            FROM dbo.users u
            LEFT JOIN dbo.journal_entries je ON je.user_id = u.id
            WHERE u.is_active = 1
              AND (? = '' OR u.husband_name LIKE ? OR u.search_alias LIKE ?)
              AND (? = '' OR u.current_place LIKE ?)
                            AND (? IS NULL OR EXISTS (
                                    SELECT 1 FROM dbo.journal_entries received
                                    WHERE received.transaction_id = je.transaction_id
                                        AND received.user_id = ?
                                        AND received.entry_type = 'RECEIVED'
                            ))
            GROUP BY u.id, u.husband_name, u.wife_name, u.current_place
            ORDER BY u.husband_name;
            """,
                        husband_name, name_pattern, name_pattern, current_place, place_pattern,
                        receiver_id, receiver_id,
        )
    columns = [column[0] for column in cursor.description]
    results = [dict(zip(columns, row)) for row in cursor.fetchall()]
    if results or not husband_name or not allow_fuzzy:
        return results

    if is_postgres_mode():
        cursor.execute(
            "SELECT husband_name FROM users WHERE is_active = TRUE"
        )
    else:
        cursor.execute(
            "SELECT husband_name FROM dbo.users WHERE is_active = 1"
        )
    candidate_names = [row[0] for row in cursor.fetchall() if row[0]]
    closest_name = max(
        candidate_names,
        key=lambda name: SequenceMatcher(None, husband_name, name).ratio(),
        default=None,
    )
    if closest_name is None:
        return []
    similarity = SequenceMatcher(None, husband_name, closest_name).ratio()
    if similarity < 0.72:
        return []
    return search_family_contributions(
        closest_name, current_place, receiver_id, allow_fuzzy=False
    )


def search_family_contributions_many(husband_names, current_place, receiver_id=None):
    """Combine contribution matches for several spoken names without duplicates."""
    combined = {}
    for husband_name in husband_names:
        for result in search_family_contributions(husband_name, current_place, receiver_id):
            combined[result["id"]] = result
    return sorted(combined.values(), key=lambda result: result["husband_name"])


def search_contributions_by_amount(amount, operator, receiver_id=None):
    """Return families with individual contributions matching an amount comparison."""
    sql_operators = {
        "eq": "=",
        "gt": ">",
        "gte": ">=",
        "lt": "<",
        "lte": "<=",
    }
    comparison = sql_operators.get(operator)
    if comparison is None:
        raise ValueError("Unsupported amount comparison.")

    connection = get_connection()
    cursor = connection.cursor()
    placeholder = "%s" if is_postgres_mode() else "?"
    table_prefix = "" if is_postgres_mode() else "dbo."
    cursor.execute(
        f"""
        SELECT u.id, u.husband_name, u.wife_name, u.current_place,
               COUNT(DISTINCT je.transaction_id) AS contribution_count,
               SUM(je.amount) AS total_contributed
        FROM {table_prefix}users u
        JOIN {table_prefix}journal_entries je ON je.user_id = u.id
        WHERE u.is_active = {"TRUE" if is_postgres_mode() else "1"}
          AND je.entry_type = 'CONTRIBUTED'
          AND je.amount {comparison} {placeholder}
                    AND ({placeholder} IS NULL OR EXISTS (
                            SELECT 1 FROM {table_prefix}journal_entries received
                            WHERE received.transaction_id = je.transaction_id
                                AND received.user_id = {placeholder}
                                AND received.entry_type = 'RECEIVED'
                    ))
        GROUP BY u.id, u.husband_name, u.wife_name, u.current_place
        ORDER BY u.husband_name;
        """,
                (amount, receiver_id, receiver_id),
    )
    columns = [column[0] for column in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


@st.cache_data(ttl=60)  # Cache for 60 seconds to avoid repeated DB queries during fast reruns
def get_active_families_for_search():
    """Return active family choices for the staff searchable name field."""
    connection = get_connection()
    cursor = connection.cursor()
    if is_postgres_mode():
        cursor.execute(
            """
                 SELECT id, husband_name, wife_name, husband_job, wife_job,
                     phone_number, native_place, current_place, place,
                     search_alias, others
            FROM users
            WHERE is_active = TRUE
            ORDER BY husband_name;
            """
        )
    else:
        cursor.execute(
            """
                 SELECT id, husband_name, wife_name, husband_job, wife_job,
                     phone_number, native_place, current_place, place,
                     search_alias, others
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


def get_all_transaction_partners(user_id):
    """
    Get all families this user has EVER transacted with (gave or received money).
    Returns list with phone_number, husband_name, id for sending notifications.
    """
    sql_mssql = """
        SELECT DISTINCT u.id, u.phone_number, u.husband_name
        FROM dbo.users u
        JOIN dbo.journal_entries je ON (
            (je.user_id = ? AND je.counterparty_id = u.id) OR
            (je.counterparty_id = ? AND je.user_id = u.id)
        )
        WHERE u.id != ? AND u.is_active = 1
        ORDER BY u.husband_name ASC
    """
    sql_pg = """
        SELECT DISTINCT u.id, u.phone_number, u.husband_name
        FROM users u
        JOIN journal_entries je ON (
            (je.user_id = %s AND je.counterparty_id = u.id) OR
            (je.counterparty_id = %s AND je.user_id = u.id)
        )
        WHERE u.id != %s AND u.is_active = TRUE
        ORDER BY u.husband_name ASC
    """
    return fetch_all(sql_mssql, sql_pg, user_id, user_id, user_id)


def get_family(user_id):
    """Fetch one family's full profile by their permanent id, or None if not found."""
    sql_mssql = """
         SELECT id, phone_number, native_place, current_place, husband_name, husband_job,
             wife_name, wife_job, place, others, notes, family_deity, email, search_alias, password_hash, is_active
        FROM dbo.users
        WHERE id = ?
    """
    sql_pg = """
         SELECT id, phone_number, native_place, current_place, husband_name, husband_job,
             wife_name, wife_job, place, others, notes, family_deity, email, search_alias, password_hash, is_active
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


@st.cache_data(ttl=60)  # Cache for 60 seconds - events don't change frequently
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


def create_family(phone_number, native_place, current_place, husband_name, husband_job, wife_name, wife_job, others, family_deity, email, search_alias, password, notes=""):
    """Insert a new family record and return its new permanent id."""
    connection = get_connection()
    cursor = connection.cursor()
    try:
        if is_postgres_mode():
            cursor.execute(
                """
                INSERT INTO users
                    (phone_number, native_place, current_place, husband_name, husband_job, wife_name, wife_job, place, others, notes, family_deity, email, search_alias, password_hash)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id;
                """,
                (
                    phone_number,
                    native_place or None,
                    current_place or None,
                    husband_name,
                    husband_job or None,
                    wife_name or None,
                    wife_job or None,
                    "",  # place: empty for now
                    others or None,
                    notes or None,
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
                    (phone_number, native_place, current_place, husband_name, husband_job, wife_name, wife_job, place, others, notes, family_deity, email, search_alias, password_hash)
                OUTPUT INSERTED.id
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    phone_number,
                    native_place or None,
                    current_place or None,
                    husband_name,
                    husband_job or None,
                    wife_name or None,
                    wife_job or None,
                    "",  # place: empty for now
                    others or None,
                    notes or None,
                    family_deity or None,
                    email or None,
                    search_alias or None,
                    hash_password(password),
                ),
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
    native_place="",
    current_place="",
    husband_job="",
    wife_name="",
    wife_job="",
    place="",
    others="",
    notes="",
    family_deity="",
    email="",
    search_alias="",
):
    """Update editable profile fields while keeping the login phone unchanged."""
    connection = get_connection()
    cursor = connection.cursor()
    try:
        if is_postgres_mode():
            cursor.execute(
                """
                UPDATE users
                SET native_place = %s, current_place = %s, husband_name = %s, husband_job = %s,
                    wife_name = %s, wife_job = %s, place = %s, others = %s, notes = %s,
                    family_deity = %s, email = %s, search_alias = %s, updated_at = NOW()
                WHERE id = %s AND is_active = TRUE
                """,
                (native_place or None, current_place or None, husband_name, husband_job or None,
                 wife_name or None, wife_job or None, place or None, others or None, notes or None,
                 family_deity or None, email or None, search_alias or None, user_id),
            )
        else:
            cursor.execute(
                """
                UPDATE dbo.users
                SET native_place = ?, current_place = ?, husband_name = ?, husband_job = ?,
                    wife_name = ?, wife_job = ?, place = ?, others = ?, notes = ?,
                    family_deity = ?, email = ?, search_alias = ?, updated_at = SYSDATETIME()
                WHERE id = ? AND is_active = 1
                """,
                native_place or None, current_place or None, husband_name, husband_job or None,
                wife_name or None, wife_job or None, place or None, others or None, notes or None,
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
            # Use EXEC for SQL Server instead of CALL syntax
            cursor.execute(
                "EXEC dbo.sp_ProcessContribution @ContributorId = ?, @ReceiverId = ?, @EventId = ?, @Amount = ?",
                (contributor_id, receiver_id, event_id, amount),
            )
        connection.commit()
        return True, "Contribution recorded successfully."
    except Exception as error:
        connection.rollback()
        return False, str(error)


def get_last_contribution(contributor_id, event_id):
    """Get the most recent contribution by a contributor for an event."""
    connection = get_connection()
    cursor = connection.cursor()
    try:
        if is_postgres_mode():
            sql = """
                SELECT je_id, je_amount, je_date
                FROM journal_entries
                WHERE je_contributor = %s AND je_event = %s AND is_active = TRUE
                ORDER BY je_date DESC
                LIMIT 1;
            """
            cursor.execute(sql, (contributor_id, event_id))
        else:
            sql = """
                SELECT TOP 1 je_id, je_amount, je_date
                FROM dbo.journal_entries
                WHERE je_contributor = ? AND je_event = ? AND is_active = 1
                ORDER BY je_date DESC;
            """
            cursor.execute(sql, (contributor_id, event_id))
        
        result = cursor.fetchone()
        if result:
            if is_postgres_mode():
                return {"id": result[0], "amount": result[1], "date": result[2]}
            else:
                return {"id": result[0], "amount": result[1], "date": result[2]}
        return None
    except Exception as error:
        return None


def delete_contribution(contribution_id):
    """Delete/undo a contribution by marking it as inactive."""
    connection = get_connection()
    cursor = connection.cursor()
    try:
        if is_postgres_mode():
            sql = "UPDATE journal_entries SET is_active = FALSE WHERE je_id = %s;"
            cursor.execute(sql, (contribution_id,))
        else:
            sql = "UPDATE dbo.journal_entries SET is_active = 0 WHERE je_id = ?;"
            cursor.execute(sql, (contribution_id,))
        
        connection.commit()
        return True, "Contribution undone successfully."
    except Exception as error:
        connection.rollback()
        return False, str(error)


def process_group_contribution(contributor_ids, receiver_id, event_id, amount):
    """
    Record multiple contributions from different families (group mode).
    All contributions are linked by the same group_id.
    Returns: (success, group_id or error_message)
    """
    connection = get_connection()
    cursor = connection.cursor()
    try:
        # Generate a unique group_id by creating one transaction entry first
        if is_postgres_mode():
            cursor.execute(
                "INSERT INTO transactions (description) VALUES (%s) RETURNING transaction_id;",
                (f"Group contribution to Family {receiver_id} - {len(contributor_ids)} families",),
            )
            group_id = cursor.fetchone()[0]
        else:
            cursor.execute(
                "INSERT INTO dbo.transactions (description) VALUES (?)",
                f"Group contribution to Family {receiver_id} - {len(contributor_ids)} families",
            )
            cursor.execute("SELECT CAST(SCOPE_IDENTITY() AS INT)")
            group_id = cursor.fetchone()[0]
        
        # Now record each contribution with the same group_id
        for contributor_id in contributor_ids:
            success, msg = process_contribution(contributor_id, receiver_id, event_id, amount, group_id)
            if not success:
                connection.rollback()
                return False, msg
        
        connection.commit()
        return True, group_id
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
                (event_name, event_date, event_place, event_location or None, host_user_id),
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
