-- ============================================================================
-- MOI SEI — Supabase PostgreSQL Schema (Complete)
-- ============================================================================
-- For Supabase SQL Editor: Copy this entire file and run it.
-- This creates the complete schema with all tables and stored procedures
-- needed for the Moi Sei application.
--
-- DO NOT include this in cloud_auth_migration.sql (run AFTER backend_pg.sql)
-- ============================================================================

-- ============================================================================
-- USERS TABLE (Family Profiles)
-- ============================================================================
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    phone_number VARCHAR(20) NOT NULL UNIQUE,
    husband_name VARCHAR(100) NOT NULL,
    wife_name VARCHAR(100) NOT NULL,
    native_place VARCHAR(100),
    current_place VARCHAR(100),
    husband_job VARCHAR(100),
    wife_job VARCHAR(100),
    others VARCHAR(100),
    family_deity VARCHAR(100),
    notes TEXT,
    password_hash VARCHAR(255),
    email VARCHAR(100),
    search_alias VARCHAR(200),
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_users_phone ON users(phone_number);
CREATE INDEX IF NOT EXISTS idx_users_husband_name ON users(husband_name);
CREATE INDEX IF NOT EXISTS idx_users_is_active ON users(is_active);

-- ============================================================================
-- EVENTS TABLE (Collection Events)
-- ============================================================================
CREATE TABLE IF NOT EXISTS events (
    event_id SERIAL PRIMARY KEY,
    event_name VARCHAR(200) NOT NULL,
    event_date DATE NOT NULL,
    event_place VARCHAR(100),
    host_user_id INTEGER REFERENCES users(id),
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_events_date ON events(event_date);
CREATE INDEX IF NOT EXISTS idx_events_host ON events(host_user_id);
CREATE INDEX IF NOT EXISTS idx_events_is_active ON events(is_active);

-- ============================================================================
-- JOURNAL ENTRIES TABLE (Double-Entry Ledger - Contributions)
-- ============================================================================
CREATE TABLE IF NOT EXISTS journal_entries (
    je_id SERIAL PRIMARY KEY,
    je_contributor INTEGER NOT NULL REFERENCES users(id),
    je_receiver INTEGER NOT NULL REFERENCES users(id),
    je_event INTEGER NOT NULL REFERENCES events(event_id),
    je_amount DECIMAL(10, 2) NOT NULL,
    je_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_active BOOLEAN DEFAULT TRUE,
    CONSTRAINT check_different_users CHECK (je_contributor != je_receiver)
);

CREATE INDEX IF NOT EXISTS idx_journal_contributor ON journal_entries(je_contributor);
CREATE INDEX IF NOT EXISTS idx_journal_receiver ON journal_entries(je_receiver);
CREATE INDEX IF NOT EXISTS idx_journal_event ON journal_entries(je_event);
CREATE INDEX IF NOT EXISTS idx_journal_date ON journal_entries(je_date);
CREATE INDEX IF NOT EXISTS idx_journal_is_active ON journal_entries(is_active);

-- ============================================================================
-- DENOMINATION TRACKING TABLE (New - for staff collection analytics)
-- ============================================================================
CREATE TABLE IF NOT EXISTS denomination_tracking (
    id SERIAL PRIMARY KEY,
    je_id INTEGER REFERENCES journal_entries(je_id) ON DELETE CASCADE,
    denomination INTEGER NOT NULL, -- 1000, 500, 200, 100, 50, 20, 10
    count INTEGER NOT NULL DEFAULT 1,
    recorded_by VARCHAR(100), -- Staff name who recorded
    recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_denom_je ON denomination_tracking(je_id);
CREATE INDEX IF NOT EXISTS idx_denom_recorded_by ON denomination_tracking(recorded_by);

-- ============================================================================
-- STAFF SESSION TRACKING TABLE (New - for multi-staff events)
-- ============================================================================
CREATE TABLE IF NOT EXISTS staff_sessions (
    session_id SERIAL PRIMARY KEY,
    event_id INTEGER NOT NULL REFERENCES events(event_id),
    staff_name VARCHAR(100) NOT NULL,
    total_collected DECIMAL(10, 2) DEFAULT 0,
    family_count INTEGER DEFAULT 0,
    session_start TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    session_end TIMESTAMP,
    is_active BOOLEAN DEFAULT TRUE
);

CREATE INDEX IF NOT EXISTS idx_staff_event ON staff_sessions(event_id);
CREATE INDEX IF NOT EXISTS idx_staff_name ON staff_sessions(staff_name);
CREATE INDEX IF NOT EXISTS idx_staff_active ON staff_sessions(is_active);

-- ============================================================================
-- STORED PROCEDURE: Process Contribution (Double-Entry Ledger)
-- ============================================================================
CREATE OR REPLACE FUNCTION sp_ProcessContribution(
    p_contributor_id INTEGER,
    p_receiver_id INTEGER,
    p_event_id INTEGER,
    p_amount DECIMAL
)
RETURNS INTEGER AS $$
DECLARE
    v_je_id INTEGER;
BEGIN
    -- Insert into journal_entries (double-entry ledger)
    INSERT INTO journal_entries (je_contributor, je_receiver, je_event, je_amount, is_active)
    VALUES (p_contributor_id, p_receiver_id, p_event_id, p_amount, TRUE)
    RETURNING je_id INTO v_je_id;
    
    RETURN v_je_id;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- FUNCTION: Get Event Collections (for sidebar summary)
-- ============================================================================
CREATE OR REPLACE FUNCTION get_event_collection_summary(p_event_id INTEGER)
RETURNS TABLE(
    total_collected DECIMAL,
    family_count BIGINT,
    contributors TEXT
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        COALESCE(SUM(je_amount), 0::DECIMAL) as total_collected,
        COUNT(DISTINCT je_contributor) as family_count,
        STRING_AGG(DISTINCT u.husband_name, ', ') as contributors
    FROM journal_entries je
    LEFT JOIN users u ON je.je_contributor = u.id
    WHERE je.je_event = p_event_id AND je.is_active = TRUE;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- FUNCTION: Get Staff Collection Summary
-- ============================================================================
CREATE OR REPLACE FUNCTION get_staff_collection(p_event_id INTEGER, p_staff_name VARCHAR)
RETURNS TABLE(
    staff_name VARCHAR,
    total_collected DECIMAL,
    family_count BIGINT
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        ss.staff_name,
        COALESCE(ss.total_collected, 0::DECIMAL) as total_collected,
        COALESCE(ss.family_count, 0::BIGINT) as family_count
    FROM staff_sessions ss
    WHERE ss.event_id = p_event_id 
      AND ss.staff_name = p_staff_name
      AND ss.is_active = TRUE;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- FUNCTION: Undo Last Contribution
-- ============================================================================
CREATE OR REPLACE FUNCTION undo_contribution(p_je_id INTEGER)
RETURNS BOOLEAN AS $$
BEGIN
    UPDATE journal_entries
    SET is_active = FALSE
    WHERE je_id = p_je_id;
    
    RETURN TRUE;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- VIEW: Event Summary (for analytics)
-- ============================================================================
CREATE OR REPLACE VIEW event_summary AS
SELECT
    e.event_id,
    e.event_name,
    e.event_date,
    COUNT(DISTINCT j.je_contributor) as total_families,
    COUNT(DISTINCT j.je_receiver) as receivers,
    SUM(j.je_amount) as total_collected,
    MAX(j.je_date) as last_contribution
FROM events e
LEFT JOIN journal_entries j ON e.event_id = j.je_event AND j.is_active = TRUE
GROUP BY e.event_id, e.event_name, e.event_date
ORDER BY e.event_date DESC;

-- ============================================================================
-- VIEW: Family Transaction History
-- ============================================================================
CREATE OR REPLACE VIEW family_transactions AS
SELECT
    j.je_id,
    u.phone_number,
    u.husband_name as family_name,
    j.je_amount as amount_contributed,
    r.husband_name as receiver_name,
    e.event_name,
    e.event_date,
    j.je_date as contribution_date
FROM journal_entries j
LEFT JOIN users u ON j.je_contributor = u.id
LEFT JOIN users r ON j.je_receiver = r.id
LEFT JOIN events e ON j.je_event = e.event_id
WHERE j.is_active = TRUE
ORDER BY j.je_date DESC;

-- ============================================================================
-- INSERT SAMPLE DATA (Optional - for testing)
-- ============================================================================
-- Uncomment these lines to populate test data

/*
-- Insert test users
INSERT INTO users (phone_number, husband_name, wife_name, native_place, current_place, husband_job, wife_job, family_deity, notes)
VALUES 
    ('9876543210', 'Suresh', 'Priya', 'Hosur', 'Trichy', 'IT', 'Teacher', 'Ganesha', 'Test family 1'),
    ('8765432109', 'Rajesh', 'Kavya', 'Salem', 'Bangalore', 'Engineer', 'Nurse', 'Murugan', 'Test family 2'),
    ('7654321098', 'Kumar', 'Deepa', 'Vellore', 'Coimbatore', 'Business', 'Housewife', 'Durga', 'Test family 3');

-- Insert test events
INSERT INTO events (event_name, event_date, event_place, host_user_id)
VALUES 
    ('Wedding Contribution', CURRENT_DATE, 'Chennai', 1),
    ('Temple Festival', CURRENT_DATE + INTERVAL '7 days', 'Trichy', 2);

-- Insert test contributions
INSERT INTO journal_entries (je_contributor, je_receiver, je_event, je_amount)
VALUES 
    (2, 1, 1, 1000.00),
    (3, 1, 1, 750.00);
*/

-- ============================================================================
-- GRANT PERMISSIONS (for Supabase authentication)
-- ============================================================================
-- If using Row Level Security (RLS), add policies here
-- For now, the app uses password-based auth

GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO authenticated;
GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA public TO authenticated;

-- ============================================================================
-- END OF SCHEMA
-- ============================================================================
