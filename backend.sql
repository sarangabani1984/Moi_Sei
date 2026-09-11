-- ============================================================================
-- DOUBLE-ENTRY LEDGER SYSTEM - SQL SERVER (T-SQL) SCHEMA & PROCEDURES
-- Description: Sets up users, event dimensions, transaction headers, 
--              and atomic double-entry journal entries for contributions.
-- ============================================================================

-- ----------------------------------------------------------------------------
-- STEP 1: DROP EXISTING TABLES (Optional: Un-comment for clean resets)
-- ----------------------------------------------------------------------------
/*
IF OBJECT_ID('journal_entries', 'U') IS NOT NULL DROP TABLE journal_entries;
IF OBJECT_ID('transactions', 'U') IS NOT NULL DROP TABLE transactions;
IF OBJECT_ID('event', 'U') IS NOT NULL DROP TABLE event;
IF OBJECT_ID('users', 'U') IS NOT NULL DROP TABLE users;
IF OBJECT_ID('sp_ProcessContribution', 'P') IS NOT NULL DROP PROCEDURE sp_ProcessContribution;
*/

-- ----------------------------------------------------------------------------
-- STEP 2: CREATE TABLES
-- ----------------------------------------------------------------------------

-- 1. Users Table: Stores family profiles and login information
CREATE TABLE users (
    id INT IDENTITY(1,1) PRIMARY KEY,
    husband_name NVARCHAR(150) NOT NULL,
    wife_name NVARCHAR(150) NULL,
    husband_job NVARCHAR(150) NULL,
    phone_number NVARCHAR(30) NOT NULL,
    place NVARCHAR(150) NULL,
    family_deity NVARCHAR(150) NULL,
    email NVARCHAR(254) NULL,
    created_at DATETIME2 NOT NULL CONSTRAINT DF_users_created_at DEFAULT (SYSDATETIME()),
    updated_at DATETIME2 NOT NULL CONSTRAINT DF_users_updated_at DEFAULT (SYSDATETIME()),
    is_active BIT NOT NULL CONSTRAINT DF_users_is_active DEFAULT (1),
    CONSTRAINT UQ_users_phone_number UNIQUE (phone_number)
);

-- 2. Event Table: Stores each function, occasion, or contribution event
CREATE TABLE event (
    event_id INT IDENTITY(101,1) PRIMARY KEY,
    event_name NVARCHAR(200) NOT NULL,
    event_date DATE NOT NULL,
    event_place NVARCHAR(200) NULL,
    event_location NVARCHAR(300) NULL,
    -- The single family authorized to receive contributions for this event.
    -- Locked in by the first contribution processed for the event.
    host_user_id INT NULL,
    is_active BIT NOT NULL CONSTRAINT DF_event_is_active DEFAULT (1),
    created_at DATETIME2 NOT NULL CONSTRAINT DF_event_created_at DEFAULT (SYSDATETIME()),
    updated_at DATETIME2 NOT NULL CONSTRAINT DF_event_updated_at DEFAULT (SYSDATETIME()),
    CONSTRAINT FK_event_host_user FOREIGN KEY (host_user_id) REFERENCES users(id)
);

-- 3. Transactions Table: High-level parent record for each financial event
CREATE TABLE transactions (
    transaction_id INT IDENTITY(1,1) PRIMARY KEY,
    description NVARCHAR(255) NULL,
    created_at DATETIME2 NOT NULL CONSTRAINT DF_transactions_created_at DEFAULT (SYSDATETIME()),
    transaction_date DATE NOT NULL CONSTRAINT DF_transactions_transaction_date DEFAULT (CONVERT(DATE, SYSDATETIME()))
);

-- 4. Journal Entries Table: Stores contributed and received amounts
CREATE TABLE journal_entries (
    journal_entry_id INT IDENTITY(1,1) PRIMARY KEY,
    transaction_id INT NOT NULL,
    user_id INT NOT NULL,
    event_id INT NOT NULL,
    entry_type VARCHAR(12) NOT NULL,
    amount DECIMAL(12,2) NOT NULL,
    
    -- Integrity Constraints
    CONSTRAINT CK_journal_entries_entry_type CHECK (entry_type IN ('CONTRIBUTED', 'RECEIVED')),
    CONSTRAINT CK_journal_entries_amount CHECK (amount > 0),
    
    -- Foreign Key Relationships
    CONSTRAINT FK_journal_entries_transactions FOREIGN KEY (transaction_id) 
        REFERENCES transactions(transaction_id) ON DELETE CASCADE,
    CONSTRAINT FK_journal_entries_users FOREIGN KEY (user_id) 
        REFERENCES users(id),
    CONSTRAINT FK_journal_entries_events FOREIGN KEY (event_id) 
        REFERENCES event(event_id)
);
GO

-- ----------------------------------------------------------------------------
-- STEP 3: INSERT SEED / TEST DATA
-- ----------------------------------------------------------------------------

-- Synthetic test families. Replace these records with real family details later.
INSERT INTO users
    (husband_name, wife_name, husband_job, phone_number, place, family_deity, email)
VALUES
    ('Test Husband 1', 'Test Wife 1', 'Test Occupation 1', '9000000001', 'Test Place 1', 'Test Deity 1', 'family1@example.test'),
    ('Test Husband 2', 'Test Wife 2', 'Test Occupation 2', '9000000002', 'Test Place 2', 'Test Deity 2', 'family2@example.test'),
    ('Test Husband 3', 'Test Wife 3', 'Test Occupation 3', '9000000003', 'Test Place 3', 'Test Deity 3', 'family3@example.test'),
    ('Test Husband 4', 'Test Wife 4', 'Test Occupation 4', '9000000004', 'Test Place 4', 'Test Deity 4', 'family4@example.test'),
    ('Test Husband 5', 'Test Wife 5', 'Test Occupation 5', '9000000005', 'Test Place 5', 'Test Deity 5', 'family5@example.test');

-- Synthetic test events. Replace these records with real event details later.
INSERT INTO event
    (event_name, event_date, event_place, event_location)
VALUES
    ('Test Family Function 2026', '2026-10-10', 'Test Mandapam 1', 'Test Location 1'),
    ('Test Education Support 2026', '2026-11-15', 'Test Hall 2', 'Test Location 2'),
    ('Test Medical Help 2026', '2026-12-05', 'Test Community Hall 3', 'Test Location 3'),
    ('Test Festival Gathering 2027', '2027-01-14', 'Test Temple Hall 4', 'Test Location 4'),
    ('Test Welfare Meeting 2027', '2027-02-20', 'Test Mandapam 5', 'Test Location 5');
GO

-- ----------------------------------------------------------------------------
-- STEP 4: CREATE STORED PROCEDURE FOR ATOMIC CONTRIBUTIONS
-- ----------------------------------------------------------------------------

CREATE PROCEDURE sp_ProcessContribution
    @ContributorId INT,
    @ReceiverId INT,
    @EventId INT,
    @Amount DECIMAL(12,2)
AS
BEGIN
    SET NOCOUNT ON;

    -- Validation 1: Prevent self-transfers
    IF @ContributorId = @ReceiverId
    BEGIN
        RAISERROR('Contributor and Receiver cannot be the same user.', 16, 1);
        RETURN;
    END

    -- Validation 2: Ensure valid positive transfer amount
    IF @Amount <= 0
    BEGIN
        RAISERROR('Contribution amount must be greater than zero.', 16, 1);
        RETURN;
    END

    -- Validation 3: Ensure both families exist and are active
    IF NOT EXISTS (SELECT 1 FROM users WHERE id = @ContributorId AND is_active = 1)
    BEGIN
        RAISERROR('Contributor User ID does not exist.', 16, 1);
        RETURN;
    END

    IF NOT EXISTS (SELECT 1 FROM users WHERE id = @ReceiverId AND is_active = 1)
    BEGIN
        RAISERROR('Receiver User ID does not exist.', 16, 1);
        RETURN;
    END

    -- Validation 4: One event can have only one receiver (the host).
    DECLARE @HostUserId INT;
    SELECT @HostUserId = host_user_id FROM event WHERE event_id = @EventId AND is_active = 1;

    IF @HostUserId IS NULL AND NOT EXISTS (SELECT 1 FROM event WHERE event_id = @EventId AND is_active = 1)
    BEGIN
        RAISERROR('Event ID does not exist or is inactive.', 16, 1);
        RETURN;
    END

    IF @HostUserId IS NOT NULL AND @HostUserId <> @ReceiverId
    BEGIN
        RAISERROR('This event already has a different receiver (host) assigned. Only one receiver is allowed per event.', 16, 1);
        RETURN;
    END

    -- Execute Double-Entry Booking safely within a Transaction
    BEGIN TRANSACTION;
    BEGIN TRY
        DECLARE @NewTxId INT;

        -- 1. Lock in the receiver as the event host on its first contribution.
        IF @HostUserId IS NULL
        BEGIN
            UPDATE event SET host_user_id = @ReceiverId, updated_at = SYSDATETIME() WHERE event_id = @EventId;
        END

        -- 2. Create Transaction Header
        INSERT INTO transactions (description)
        VALUES ('Contribution from User ' + CAST(@ContributorId AS VARCHAR) + ' to User ' + CAST(@ReceiverId AS VARCHAR));

        SET @NewTxId = CONVERT(INT, SCOPE_IDENTITY());

        -- 3. Record the contribution from the contributor
        INSERT INTO journal_entries (transaction_id, user_id, event_id, entry_type, amount)
        VALUES (@NewTxId, @ContributorId, @EventId, 'CONTRIBUTED', @Amount);

        -- 4. Record the amount received by the receiver
        INSERT INTO journal_entries (transaction_id, user_id, event_id, entry_type, amount)
        VALUES (@NewTxId, @ReceiverId, @EventId, 'RECEIVED', @Amount);

        -- Finalize Changes
        COMMIT TRANSACTION;
        PRINT 'Contribution completed successfully!';
    END TRY
    BEGIN CATCH
        -- Rollback on any internal failure
        IF @@TRANCOUNT > 0
            ROLLBACK TRANSACTION;

        DECLARE @ErrorMessage NVARCHAR(4000) = ERROR_MESSAGE();
        RAISERROR(@ErrorMessage, 16, 1);
    END CATCH
END;
GO

-- ----------------------------------------------------------------------------
-- STEP 5: PRIVATE FAMILY REPORT PROCEDURES
-- ----------------------------------------------------------------------------

-- Login lookup: the phone number maps to the permanent family ID.
CREATE PROCEDURE sp_GetFamilyByPhone
    @PhoneNumber NVARCHAR(30)
AS
BEGIN
    SET NOCOUNT ON;

    SELECT id, husband_name, wife_name, phone_number
    FROM users
    WHERE phone_number = @PhoneNumber
      AND is_active = 1;
END;
GO

-- Show only the logged-in family's own contributions, including receiver details.
CREATE PROCEDURE sp_GetMyContributions
    @UserId INT
AS
BEGIN
    SET NOCOUNT ON;

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
    WHERE contributed.user_id = @UserId
      AND contributed.entry_type = 'CONTRIBUTED'
    ORDER BY t.transaction_date DESC, t.transaction_id DESC;
END;
GO

-- Show only what the logged-in family received, including contributor details.
CREATE PROCEDURE sp_GetMyReceivedContributions
    @UserId INT
AS
BEGIN
    SET NOCOUNT ON;

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
    WHERE received.user_id = @UserId
      AND received.entry_type = 'RECEIVED'
    ORDER BY t.transaction_date DESC, t.transaction_id DESC;
END;
GO

-- Show the running give-and-take history with each family the user has ever
-- exchanged with, combined across all events (the "Moi Sei" reciprocity view).
CREATE PROCEDURE sp_GetMyPartnerHistory
    @UserId INT
AS
BEGIN
    SET NOCOUNT ON;

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
          AND (c.user_id = @UserId OR r.user_id = @UserId)
    )
    SELECT
        other.id AS other_user_id,
        other.husband_name AS other_husband_name,
        other.wife_name AS other_wife_name,
        other.phone_number AS other_phone_number,
        SUM(CASE WHEN tp.contributor_id = @UserId THEN tp.amount ELSE 0 END) AS total_given,
        SUM(CASE WHEN tp.receiver_id = @UserId THEN tp.amount ELSE 0 END) AS total_received,
        SUM(CASE WHEN tp.contributor_id = @UserId THEN tp.amount ELSE 0 END)
            - SUM(CASE WHEN tp.receiver_id = @UserId THEN tp.amount ELSE 0 END) AS net_difference,
        COUNT(*) AS transaction_count,
        MAX(tp.transaction_date) AS last_transaction_date
    FROM tx_pairs tp
    JOIN users other
        ON other.id = CASE WHEN tp.contributor_id = @UserId THEN tp.receiver_id ELSE tp.contributor_id END
    GROUP BY other.id, other.husband_name, other.wife_name, other.phone_number
    ORDER BY net_difference DESC;
END;
GO

-- Show the chronological transaction-by-transaction timeline between the
-- logged-in family and one specific counterpart, with a running net balance.
CREATE PROCEDURE sp_GetMyPartnerTransactions
    @UserId INT,
    @OtherUserId INT
AS
BEGIN
    SET NOCOUNT ON;

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
                (c.user_id = @UserId AND r.user_id = @OtherUserId)
             OR (c.user_id = @OtherUserId AND r.user_id = @UserId)
          )
    )
    SELECT
        transaction_id,
        transaction_date,
        event_id,
        event_name,
        CASE WHEN contributor_id = @UserId THEN 'You Paid' ELSE 'You Received' END AS direction,
        amount,
        SUM(CASE WHEN contributor_id = @UserId THEN amount ELSE -amount END)
            OVER (ORDER BY transaction_date, transaction_id
                  ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS running_net_difference
    FROM tx_pairs
    ORDER BY transaction_date, transaction_id;
END;
GO

-- ----------------------------------------------------------------------------
-- STEP 6: VERIFICATION & AUDIT QUERIES
-- ----------------------------------------------------------------------------

/* 
-- Example Execution Call:
EXEC sp_ProcessContribution 
    @ContributorId = 1, 
    @ReceiverId = 2, 
    @EventId = 101, 
    @Amount = 50.00;

-- Audit Query: Check Family Details
SELECT id, husband_name, wife_name, phone_number, is_active FROM users;

-- Audit Query: Detailed Double-Entry Journal Ledger
SELECT 
    je.journal_entry_id AS entry_id,
    t.transaction_id AS tx_id,
    u.husband_name,
    u.wife_name,
    e.event_name,
    je.entry_type,
    je.amount,
    t.created_at
FROM journal_entries je
JOIN transactions t ON je.transaction_id = t.transaction_id
JOIN users u ON je.user_id = u.id
    JOIN event e ON je.event_id = e.event_id
ORDER BY je.journal_entry_id ASC;
*/