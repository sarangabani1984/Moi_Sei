-- SQL Server Migration Script
-- Adds new columns to the users table for Moi Sei app
-- Run this against your MoiSei database

-- Add new columns if they don't exist
ALTER TABLE dbo.users
ADD 
    native_place NVARCHAR(MAX) NULL,
    current_place NVARCHAR(MAX) NULL,
    wife_job NVARCHAR(MAX) NULL,
    others NVARCHAR(MAX) NULL;

-- Verify the columns were added
SELECT COLUMN_NAME, DATA_TYPE, IS_NULLABLE
FROM INFORMATION_SCHEMA.COLUMNS
WHERE TABLE_SCHEMA = 'dbo' AND TABLE_NAME = 'users'
ORDER BY ORDINAL_POSITION;
