-- ============================================================================
-- DOUBLE-ENTRY LEDGER SYSTEM - POSTGRESQL (SUPABASE / NEON / CLOUD) SCHEMA
-- Description: Sets up users, event dimensions, transaction headers, 
--              and atomic double-entry journal entries for contributions.
-- ============================================================================

-- ----------------------------------------------------------------------------
-- STEP 1: DROP EXISTING TABLES & FUNCTIONS (Clean resets)
-- ----------------------------------------------------------------------------
DROP TABLE IF EXISTS journal_entries CASCADE;
DROP TABLE IF EXISTS transactions CASCADE;
DROP TABLE IF EXISTS event CASCADE;
DROP TABLE IF EXISTS users CASCADE;

-- ----------------------------------------------------------------------------
-- STEP 2: CREATE TABLES
-- ----------------------------------------------------------------------------

-- 1. Users Table: Stores family profiles and login information
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    husband_name VARCHAR(150) NOT NULL,
    wife_name VARCHAR(150) NULL,
    husband_job VARCHAR(150) NULL,
    phone_number VARCHAR(30) NOT NULL CONSTRAINT UQ_users_phone_number UNIQUE,
    place VARCHAR(150) NULL,
    family_deity VARCHAR(150) NULL,
    email VARCHAR(254) NULL,
    password_hash VARCHAR(255) NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    is_active BOOLEAN NOT NULL DEFAULT TRUE
);

-- 2. Event Table: Stores each function, occasion, or contribution event
CREATE TABLE event (
    event_id SERIAL PRIMARY KEY,
    event_name VARCHAR(200) NOT NULL,
    event_date DATE NOT NULL,
    event_place VARCHAR(200) NOT NULL,
    event_location VARCHAR(300) NULL,
    host_user_id INT NULL REFERENCES users(id),
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 3. Transactions Table: High-level parent record for each financial event
CREATE TABLE transactions (
    transaction_id SERIAL PRIMARY KEY,
    description VARCHAR(255) NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    transaction_date DATE NOT NULL DEFAULT CURRENT_DATE
);

-- 4. Journal Entries Table: Stores contributed and received amounts
CREATE TABLE journal_entries (
    journal_entry_id SERIAL PRIMARY KEY,
    transaction_id INT NOT NULL REFERENCES transactions(transaction_id) ON DELETE CASCADE,
    user_id INT NOT NULL REFERENCES users(id),
    event_id INT NOT NULL REFERENCES event(event_id),
    entry_type VARCHAR(12) NOT NULL CONSTRAINT CK_journal_entries_entry_type CHECK (entry_type IN ('CONTRIBUTED', 'RECEIVED')),
    amount DECIMAL(12,2) NOT NULL CONSTRAINT CK_journal_entries_amount CHECK (amount > 0)
);

-- ----------------------------------------------------------------------------
-- STEP 3: INSERT SEED DATA
-- ----------------------------------------------------------------------------

INSERT INTO users (husband_name, wife_name, husband_job, phone_number, place, family_deity, email)
VALUES
    ('Test Husband 1', 'Test Wife 1', 'Test Occupation 1', '9000000001', 'Test Place 1', 'Test Deity 1', 'family1@example.test'),
    ('Test Husband 2', 'Test Wife 2', 'Test Occupation 2', '9000000002', 'Test Place 2', 'Test Deity 2', 'family2@example.test'),
    ('Test Husband 3', 'Test Wife 3', 'Test Occupation 3', '9000000003', 'Test Place 3', 'Test Deity 3', 'family3@example.test'),
    ('Test Husband 4', 'Test Wife 4', 'Test Occupation 4', '9000000004', 'Test Place 4', 'Test Deity 4', 'family4@example.test'),
    ('Test Husband 5', 'Test Wife 5', 'Test Occupation 5', '9000000005', 'Test Place 5', 'Test Deity 5', 'family5@example.test');

INSERT INTO event (event_id, event_name, event_date, event_place, event_location)
VALUES
    (101, 'Test Family Function 2026', '2026-10-10', 'Test Mandapam 1', 'Test Location 1'),
    (102, 'Test Education Support 2026', '2026-11-15', 'Test Hall 2', 'Test Location 2'),
    (103, 'Test Medical Help 2026', '2026-12-05', 'Test Community Hall 3', 'Test Location 3'),
    (104, 'Test Festival Gathering 2027', '2027-01-14', 'Test Temple Hall 4', 'Test Location 4'),
    (105, 'Test Welfare Meeting 2027', '2027-02-20', 'Test Mandapam 5', 'Test Location 5');

ALTER SEQUENCE event_event_id_seq RESTART WITH 106;

-- ----------------------------------------------------------------------------
-- STEP 4: FUNCTION FOR ATOMIC CONTRIBUTIONS
-- ----------------------------------------------------------------------------

CREATE OR REPLACE FUNCTION sp_ProcessContribution(
    p_contributor_id INT,
    p_receiver_id INT,
    p_event_id INT,
    p_amount DECIMAL(12,2)
)
RETURNS VOID AS $$
DECLARE
    v_host_user_id INT;
    v_new_tx_id INT;
BEGIN
    -- Validation 1: Prevent self-transfers
    IF p_contributor_id = p_receiver_id THEN
        RAISE EXCEPTION 'Contributor and Receiver cannot be the same user.';
    END IF;

    -- Validation 2: Ensure valid positive transfer amount
    IF p_amount <= 0 THEN
        RAISE EXCEPTION 'Contribution amount must be greater than zero.';
    END IF;

    -- Validation 3: Ensure both families exist and are active
    IF NOT EXISTS (SELECT 1 FROM users WHERE id = p_contributor_id AND is_active = TRUE) THEN
        RAISE EXCEPTION 'Contributor User ID does not exist.';
    END IF;

    IF NOT EXISTS (SELECT 1 FROM users WHERE id = p_receiver_id AND is_active = TRUE) THEN
        RAISE EXCEPTION 'Receiver User ID does not exist.';
    END IF;

    -- Validation 4: One event can have only one receiver (the host).
    SELECT host_user_id INTO v_host_user_id FROM event WHERE event_id = p_event_id AND is_active = TRUE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Event ID does not exist or is inactive.';
    END IF;

    IF v_host_user_id IS NOT NULL AND v_host_user_id <> p_receiver_id THEN
        RAISE EXCEPTION 'This event already has a different receiver (host) assigned. Only one receiver is allowed per event.';
    END IF;

    -- 1. Lock in receiver as event host on first contribution
    IF v_host_user_id IS NULL THEN
        UPDATE event SET host_user_id = p_receiver_id, updated_at = NOW() WHERE event_id = p_event_id;
    END IF;

    -- 2. Create Transaction Header
    INSERT INTO transactions (description)
    VALUES ('Contribution from User ' || p_contributor_id || ' to User ' || p_receiver_id)
    RETURNING transaction_id INTO v_new_tx_id;

    -- 3. Record contribution from contributor
    INSERT INTO journal_entries (transaction_id, user_id, event_id, entry_type, amount)
    VALUES (v_new_tx_id, p_contributor_id, p_event_id, 'CONTRIBUTED', p_amount);

    -- 4. Record amount received by receiver
    INSERT INTO journal_entries (transaction_id, user_id, event_id, entry_type, amount)
    VALUES (v_new_tx_id, p_receiver_id, p_event_id, 'RECEIVED', p_amount);

END;
$$ LANGUAGE plpgsql;

-- ----------------------------------------------------------------------------
-- STEP 5: REPORT FUNCTIONS
-- ----------------------------------------------------------------------------

CREATE OR REPLACE FUNCTION sp_GetFamilyByPhone(p_phone_number VARCHAR)
RETURNS TABLE (
    id INT,
    husband_name VARCHAR,
    wife_name VARCHAR,
    phone_number VARCHAR
) AS $$
BEGIN
    RETURN QUERY
    SELECT u.id, u.husband_name, u.wife_name, u.phone_number
    FROM users u
    WHERE u.phone_number = p_phone_number
      AND u.is_active = TRUE;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION sp_GetMyContributions(p_user_id INT)
RETURNS TABLE (
    transaction_id INT,
    transaction_date DATE,
    receiver_id INT,
    receiver_husband_name VARCHAR,
    receiver_wife_name VARCHAR,
    receiver_husband_job VARCHAR,
    receiver_phone_number VARCHAR,
    receiver_place VARCHAR,
    receiver_family_deity VARCHAR,
    receiver_email VARCHAR,
    event_id INT,
    event_name VARCHAR,
    event_date DATE,
    event_place VARCHAR,
    event_location VARCHAR,
    amount DECIMAL(12,2)
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        t.transaction_id,
        t.transaction_date,
        receiver.id AS receiver_id,
        receiver.husband_name AS receiver_husband_name,
        receiver.wife_name AS receiver_wife_name,
        receiver.husband_job AS receiver_husband_job,
        receiver.phone_number AS receiver_phone_number,
        receiver.place AS receiver_place,
        receiver.family_deity AS receiver_family_deity,
        receiver.email AS receiver_email,
        e.event_id,
        e.event_name,
        e.event_date,
        e.event_place,
        e.event_location,
        contributed.amount
    FROM journal_entries contributed
    JOIN journal_entries received
        ON received.transaction_id = contributed.transaction_id
       AND received.entry_type = 'RECEIVED'
    JOIN transactions t ON t.transaction_id = contributed.transaction_id
    JOIN users receiver ON receiver.id = received.user_id
    JOIN event e ON e.event_id = contributed.event_id
    WHERE contributed.user_id = p_user_id
      AND contributed.entry_type = 'CONTRIBUTED'
    ORDER BY t.transaction_date DESC, t.transaction_id DESC;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION sp_GetMyReceivedContributions(p_user_id INT)
RETURNS TABLE (
    transaction_id INT,
    transaction_date DATE,
    contributor_id INT,
    contributor_husband_name VARCHAR,
    contributor_wife_name VARCHAR,
    contributor_husband_job VARCHAR,
    contributor_phone_number VARCHAR,
    contributor_place VARCHAR,
    contributor_family_deity VARCHAR,
    contributor_email VARCHAR,
    event_id INT,
    event_name VARCHAR,
    event_date DATE,
    event_place VARCHAR,
    event_location VARCHAR,
    amount DECIMAL(12,2)
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        t.transaction_id,
        t.transaction_date,
        contributor.id AS contributor_id,
        contributor.husband_name AS contributor_husband_name,
        contributor.wife_name AS contributor_wife_name,
        contributor.husband_job AS contributor_husband_job,
        contributor.phone_number AS contributor_phone_number,
        contributor.place AS contributor_place,
        contributor.family_deity AS contributor_family_deity,
        contributor.email AS contributor_email,
        e.event_id,
        e.event_name,
        e.event_date,
        e.event_place,
        e.event_location,
        contributed.amount
    FROM journal_entries received
    JOIN journal_entries contributed
        ON contributed.transaction_id = received.transaction_id
       AND contributed.entry_type = 'CONTRIBUTED'
    JOIN transactions t ON t.transaction_id = received.transaction_id
    JOIN users contributor ON contributor.id = contributed.user_id
    JOIN event e ON e.event_id = received.event_id
    WHERE received.user_id = p_user_id
      AND received.entry_type = 'RECEIVED'
    ORDER BY t.transaction_date DESC, t.transaction_id DESC;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION sp_GetMyPartnerHistory(p_user_id INT)
RETURNS TABLE (
    other_user_id INT,
    other_husband_name VARCHAR,
    other_wife_name VARCHAR,
    other_phone_number VARCHAR,
    total_given NUMERIC,
    total_received NUMERIC,
    net_difference NUMERIC,
    transaction_count BIGINT,
    last_transaction_date DATE
) AS $$
BEGIN
    RETURN QUERY
    WITH tx_pairs AS (
        SELECT
            c.transaction_id,
            c.user_id AS contributor_id,
            r.user_id AS receiver_id,
            c.event_id,
            c.amount,
            t.transaction_date
        FROM journal_entries c
        JOIN journal_entries r
            ON r.transaction_id = c.transaction_id
           AND r.entry_type = 'RECEIVED'
        JOIN transactions t ON t.transaction_id = c.transaction_id
        WHERE c.entry_type = 'CONTRIBUTED'
          AND (c.user_id = p_user_id OR r.user_id = p_user_id)
    )
    SELECT
        other.id AS other_user_id,
        other.husband_name AS other_husband_name,
        other.wife_name AS other_wife_name,
        other.phone_number AS other_phone_number,
        SUM(CASE WHEN tp.contributor_id = p_user_id THEN tp.amount ELSE 0 END) AS total_given,
        SUM(CASE WHEN tp.receiver_id = p_user_id THEN tp.amount ELSE 0 END) AS total_received,
        SUM(CASE WHEN tp.contributor_id = p_user_id THEN tp.amount ELSE 0 END)
            - SUM(CASE WHEN tp.receiver_id = p_user_id THEN tp.amount ELSE 0 END) AS net_difference,
        COUNT(*) AS transaction_count,
        MAX(tp.transaction_date) AS last_transaction_date
    FROM tx_pairs tp
    JOIN users other
        ON other.id = CASE WHEN tp.contributor_id = p_user_id THEN tp.receiver_id ELSE tp.contributor_id END
    GROUP BY other.id, other.husband_name, other.wife_name, other.phone_number
    ORDER BY net_difference DESC;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION sp_GetMyPartnerTransactions(p_user_id INT, p_other_user_id INT)
RETURNS TABLE (
    transaction_id INT,
    transaction_date DATE,
    event_id INT,
    event_name VARCHAR,
    direction TEXT,
    amount DECIMAL(12,2),
    running_net_difference NUMERIC
) AS $$
BEGIN
    RETURN QUERY
    WITH tx_pairs AS (
        SELECT
            c.transaction_id,
            t.transaction_date,
            c.event_id,
            e.event_name,
            c.user_id AS contributor_id,
            r.user_id AS receiver_id,
            c.amount
        FROM journal_entries c
        JOIN journal_entries r
            ON r.transaction_id = c.transaction_id
           AND r.entry_type = 'RECEIVED'
        JOIN transactions t ON t.transaction_id = c.transaction_id
        JOIN event e ON e.event_id = c.event_id
        WHERE c.entry_type = 'CONTRIBUTED'
          AND (
                (c.user_id = p_user_id AND r.user_id = p_other_user_id)
             OR (c.user_id = p_other_user_id AND r.user_id = p_user_id)
          )
    )
    SELECT
        tp.transaction_id,
        tp.transaction_date,
        tp.event_id,
        tp.event_name,
        CASE WHEN tp.contributor_id = p_user_id THEN 'You Paid' ELSE 'You Received' END AS direction,
        tp.amount,
        SUM(CASE WHEN tp.contributor_id = p_user_id THEN tp.amount ELSE -tp.amount END)
            OVER (ORDER BY tp.transaction_date, tp.transaction_id
                  ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS running_net_difference
    FROM tx_pairs tp
    ORDER BY tp.transaction_date, tp.transaction_id;
END;
$$ LANGUAGE plpgsql;
