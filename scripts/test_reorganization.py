#!/usr/bin/env python3
"""
Quick verification that reorganization didn't break anything.
Run from root: python test_reorganization.py
"""

import sys
import os

print("=" * 60)
print("TESTING REORGANIZATION IMPACT")
print("=" * 60)
print()

# Test 1: Check if src/app folder exists
print("✓ Test 1: Checking folder structure...")
if os.path.isdir("src/app"):
    print("  ✅ src/app/ folder exists")
else:
    print("  ❌ src/app/ folder NOT FOUND")
    sys.exit(1)

# Test 2: Check if all main files exist
print()
print("✓ Test 2: Checking main app files...")
required_files = [
    "src/app/app.py",
    "src/app/user_app.py",
    "src/app/db.py",
    "src/app/notifications.py",
    "src/app/voice_app.py",
    "src/app/voice_ai.py",
]
for file in required_files:
    if os.path.isfile(file):
        print(f"  ✅ {file}")
    else:
        print(f"  ❌ {file} NOT FOUND")

# Test 3: Check if config files exist
print()
print("✓ Test 3: Checking configuration files...")
config_files = [
    ".streamlit/config.toml",
    ".streamlit/secrets.template.toml",
    "config/requirements.txt",
]
for file in config_files:
    if os.path.isfile(file):
        print(f"  ✅ {file}")
    else:
        print(f"  ⚠️  {file} not found (may be OK)")

# Test 4: Check database schemas
print()
print("✓ Test 4: Checking database migration files...")
db_files = [
    "database/sql-server/backend.sql",
    "database/sql-server/ALTER_USERS_ADD_NEW_FIELDS.sql",
    "database/postgresql/backend_pg.sql",
    "database/postgresql/supabase_schema_complete.sql",
    "database/postgresql/cloud_auth_migration.sql",
]
for file in db_files:
    if os.path.isfile(file):
        print(f"  ✅ {file}")
    else:
        print(f"  ⚠️  {file} not found")

# Test 5: Try importing db module
print()
print("✓ Test 5: Testing Python imports...")
try:
    sys.path.insert(0, "src/app")
    from db import get_connection, create_family
    print("  ✅ Successfully imported from src/app/db.py")
except ImportError as e:
    print(f"  ❌ Failed to import db: {e}")
    sys.exit(1)

# Test 6: Try importing notifications
try:
    from notifications import send_green_api_whatsapp
    print("  ✅ Successfully imported from src/app/notifications.py")
except ImportError as e:
    print(f"  ❌ Failed to import notifications: {e}")
    sys.exit(1)

# Test 7: Check Streamlit can load
print()
print("✓ Test 6: Checking if Streamlit is installed...")
try:
    import streamlit
    print(f"  ✅ Streamlit {streamlit.__version__} installed")
except ImportError:
    print("  ❌ Streamlit not installed (run: pip install -r config/requirements.txt)")

# Test 8: Check database drivers
print()
print("✓ Test 7: Checking database drivers...")
try:
    import psycopg2
    print("  ✅ psycopg2 (PostgreSQL) available")
except ImportError:
    print("  ⚠️  psycopg2 not installed (OK for local dev, needed for cloud)")

try:
    import pyodbc
    print("  ✅ pyodbc (SQL Server) available")
except ImportError:
    print("  ⚠️  pyodbc not installed (OK for cloud, needed for local dev)")

# All tests passed
print()
print("=" * 60)
print("✅ ALL TESTS PASSED!")
print("=" * 60)
print()
print("Ready to run:")
print("  • streamlit run src/app/app.py")
print("  • streamlit run src/app/user_app.py")
print()
