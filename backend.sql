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
    password_hash NVARCHAR(255) NULL,
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
    event_place NVARCHAR(200) NOT NULL,
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

-- ============================================================================
-- sp_ProcessContribution
-- ----------------------------------------------------------------------------
-- PURPOSE:
--   Records one contribution from a contributor family to a receiver family
--   for a specific event. This is the only way money movement is written to
--   the database, so every business rule is enforced here in one place.
--
-- PARAMETERS:
--   @ContributorId  Permanent id (users.id) of the family giving the amount.
--   @ReceiverId     Permanent id (users.id) of the family getting the amount.
--   @EventId        The event this contribution belongs to (event.event_id).
--   @Amount         The amount being contributed. Must be greater than zero.
--
-- VALIDATION RULES (checked before anything is written):
--   1. Contributor and Receiver must be two different families.
--   2. Amount must be a positive number.
--   3. Contributor must exist and be active (is_active = 1).
--   4. Receiver must exist and be active (is_active = 1).
--   5. Event must exist and be active.
--   6. One event can only ever have ONE receiver (the "host"):
--        - If the event has no host yet, this contribution's @ReceiverId
--          becomes the permanent host for that event (locked in below).
--        - If the event already has a host, @ReceiverId must match it,
--          otherwise the contribution is rejected.
--
-- WHAT IT WRITES (only if all validations pass):
--   1. One row in `transactions`  -> the parent receipt for this contribution.
--   2. One row in `journal_entries` with entry_type = 'CONTRIBUTED'
--      for the contributor (money going out).
--   3. One row in `journal_entries` with entry_type = 'RECEIVED'
--      for the receiver (money coming in).
--   All three writes happen inside one SQL transaction: if anything fails,
--   everything is rolled back so no half-saved contribution is ever left
--   behind.
-- ============================================================================
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
-- Every procedure below only ever returns data that belongs to, or directly
-- involves, the @UserId that is passed in. No procedure here lets one family
-- browse another family's private records except through a shared
-- transaction they were both part of.

-- ============================================================================
-- sp_GetFamilyByPhone
-- ----------------------------------------------------------------------------
-- PURPOSE:
--   Used for login. Converts a phone number typed by the user into that
--   family's permanent id (users.id). The phone number can change over time;
--   the id it resolves to never does, so history is never lost.
--
-- PARAMETERS:
--   @PhoneNumber  The phone number typed on the login screen.
--
-- RETURNS:
--   Zero rows if no active family has that phone number.
--   One row with (id, husband_name, wife_name, phone_number) if found.
--   The caller (db.py) then fetches the full profile using that id.
-- ============================================================================
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

-- ============================================================================
-- sp_GetMyContributions
-- ----------------------------------------------------------------------------
-- PURPOSE:
--   Answers: "What have I given, and to whom?"
--   Returns every contribution the logged-in family has made, together with
--   the full profile of the family that received it and the event it was
--   for, so the screen never needs a second lookup.
--
-- PARAMETERS:
--   @UserId  Permanent id (users.id) of the logged-in family.
--
-- HOW IT WORKS:
--   Every contribution creates TWO journal_entries rows that share the same
--   transaction_id: one 'CONTRIBUTED' row (the giver) and one 'RECEIVED' row
--   (the getter). This procedure starts from the caller's own 'CONTRIBUTED'
--   rows, then joins back to the matching 'RECEIVED' row on the same
--   transaction to pull out who the receiver was.
--
-- RETURNS (one row per contribution, newest first):
--   transaction_id, transaction_date,
--   receiver_id, receiver_husband_name, receiver_wife_name,
--   receiver_husband_job, receiver_phone_number, receiver_place,
--   receiver_family_deity, receiver_email,
--   event_id, event_name, event_date, event_place, event_location,
--   amount
-- ============================================================================
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

-- ============================================================================
-- sp_GetMyReceivedContributions
-- ----------------------------------------------------------------------------
-- PURPOSE:
--   Answers: "What have I received, and from whom?"
--   The mirror image of sp_GetMyContributions: starts from the caller's own
--   'RECEIVED' rows and joins back to the matching 'CONTRIBUTED' row on the
--   same transaction to pull out the full profile of whoever gave the money.
--
-- PARAMETERS:
--   @UserId  Permanent id (users.id) of the logged-in family.
--
-- RETURNS (one row per amount received, newest first):
--   transaction_id, transaction_date,
--   contributor_id, contributor_husband_name, contributor_wife_name,
--   contributor_husband_job, contributor_phone_number, contributor_place,
--   contributor_family_deity, contributor_email,
--   event_id, event_name, event_date, event_place, event_location,
--   amount
-- ============================================================================
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

-- ============================================================================
-- sp_GetMyPartnerHistory
-- ----------------------------------------------------------------------------
-- PURPOSE:
--   Answers: "Across every event, family by family, am I ahead or behind?"
--   The same two families can exchange money more than once, in either
--   direction, across many different events over time (this is the "Moi Sei"
--   reciprocity custom: what you give at someone's function, they are
--   expected to return at yours). This procedure collapses all of that
--   history into one summary row per counterpart family.
--
-- PARAMETERS:
--   @UserId  Permanent id (users.id) of the logged-in family.
--
-- HOW IT WORKS:
--   1. The tx_pairs CTE pairs up every transaction's 'CONTRIBUTED' row with
--      its matching 'RECEIVED' row, keeping only transactions where the
--      caller was on either side (as contributor or as receiver).
--   2. The outer query groups those pairs by the *other* family involved,
--      and sums how much the caller gave them vs. received from them.
--
-- RETURNS (one row per counterpart family, largest net_difference first):
--   other_user_id, other_husband_name, other_wife_name, other_phone_number,
--   total_given       -> everything the caller has given this family
--   total_received    -> everything the caller has received from this family
--   net_difference    -> total_given - total_received
--                        (positive = caller has given more than received;
--                         negative = caller has received more than given)
--   transaction_count, last_transaction_date
-- ============================================================================
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

-- ============================================================================
-- sp_GetMyPartnerTransactions
-- ----------------------------------------------------------------------------
-- PURPOSE:
--   Drill-down for sp_GetMyPartnerHistory. Answers: "Show me exactly what
--   happened between me and this ONE specific family, in the order it
--   happened, so I can see the back-and-forth (e.g. I paid, then they paid
--   me back, then I paid again)."
--
-- PARAMETERS:
--   @UserId       Permanent id (users.id) of the logged-in family.
--   @OtherUserId  Permanent id (users.id) of the one counterpart family to
--                 show the timeline for (chosen by the user from the
--                 sp_GetMyPartnerHistory list).
--
-- HOW IT WORKS:
--   1. The tx_pairs CTE finds every transaction that happened directly
--      between exactly these two families, in either direction.
--   2. Each row is labelled 'You Paid' or 'You Received' from @UserId's
--      point of view.
--   3. A running SUM() window function keeps a rolling net balance across
--      the rows, ordered by date: it goes up when @UserId paid, and down
--      when @UserId received, so the sign at each row shows who was ahead
--      at that point in time.
--
-- RETURNS (one row per transaction, oldest first):
--   transaction_id, transaction_date, event_id, event_name,
--   direction                 -> 'You Paid' or 'You Received'
--   amount                    -> this transaction's amount
--   running_net_difference    -> cumulative balance after this transaction
--                                (positive = @UserId is ahead so far)
-- ============================================================================
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