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
ALTER SEQUENCE event_event_id_seq RESTART WITH 101;

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

INSERT INTO event (event_name, event_date, event_place, event_location)
VALUES
    ('Test Family Function 2026', '2026-10-10', 'Test Mandapam 1', 'Test Location 1'),
    ('Test Education Support 2026', '2026-11-15', 'Test Hall 2', 'Test Location 2'),
    ('Test Medical Help 2026', '2026-12-05', 'Test Community Hall 3', 'Test Location 3'),
    ('Test Festival Gathering 2027', '2027-01-14', 'Test Temple Hall 4', 'Test Location 4'),
    ('Test Welfare Meeting 2027', '2027-02-20', 'Test Mandapam 5', 'Test Location 5');

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
