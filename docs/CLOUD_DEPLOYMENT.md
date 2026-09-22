# 🚀 Moi Sei — Cloud Deployment Guide (Supabase + Streamlit Cloud + GitHub)

## Overview
This guide walks you through deploying Moi Sei to **100% free cloud infrastructure**:
- **Database:** Supabase PostgreSQL (free tier: 500MB)
- **Frontend:** Streamlit Community Cloud (free tier)
- **Messaging:** Green API WhatsApp (free tier: test mode)
- **Source Control:** GitHub

---

## 📋 Pre-Deployment Checklist

### ✅ Local Machine
- [x] Code tested locally with SQL Server (app.py, user_app.py)
- [x] All features working (staff login, collection tracking, undo)
- [x] `.streamlit/secrets.toml` is in `.gitignore` (never commit secrets!)
- [ ] Git repo initialized and ready to push

### ✅ Accounts Created (Free)
- [ ] **Supabase Account** → https://supabase.com (sign in with GitHub)
- [ ] **Streamlit Cloud Account** → https://share.streamlit.io (sign in with GitHub)
- [ ] **Green API Account** (Optional) → https://green-api.com

---

## 🗄️ STEP 1: Set Up Supabase PostgreSQL Database

### 1.1 Create Supabase Project
1. Go to **https://supabase.com** → Click "Start Your Project"
2. Sign in with GitHub (easier for linking later)
3. Click **"New Project"**
   - **Project Name:** `moi-sei`
   - **Database Password:** Create a strong password (save it!)
   - **Region:** Choose closest to you
   - Click **"Create new project"** (takes 1-2 minutes)

### 1.2 Get Connection String
1. After project is created, go to **Settings** → **Database**
2. Copy the **Connection String** (looks like):
   ```
   postgresql://postgres:[password]@[host]:[port]/postgres?sslmode=require
   ```
3. Save this — you'll need it for Streamlit Cloud secrets

### 1.3 Create Database Schema in Supabase

1. Open Supabase dashboard → **SQL Editor** (left sidebar)
2. Click **"New Query"**
3. Copy & paste the content from `backend_pg.sql` (local file)
4. Click **"Run"**

**What this creates:**
- `users` table (family profiles)
- `journal_entries` table (double-entry ledger for contributions)
- `events` table (event records)
- Stored procedures for processing contributions

### 1.4 Run Cloud-Specific Migrations

1. In SQL Editor, click **"New Query"**
2. Paste content from `cloud_auth_migration.sql`:
   ```sql
   ALTER TABLE users
   ADD COLUMN IF NOT EXISTS password_hash VARCHAR(255);
   ALTER TABLE users
   ADD COLUMN IF NOT EXISTS search_alias VARCHAR(200);
   ALTER TABLE users
   ADD COLUMN IF NOT EXISTS notes TEXT;
   ```
3. Click **"Run"**

✅ **Database is ready!**

---

## 🐙 STEP 2: Push Code to GitHub

### 2.1 Initialize Git (if not already done)
```powershell
cd "c:\Users\sarangs\OneDrive - Hewlett Packard Enterprise\All_VS_Code\Moi_Sei"
git init
git add .
git commit -m "Initial commit: Admin panel with staff tracking, collection summary, undo feature"
```

### 2.2 Check `.gitignore` (⚠️ CRITICAL)
Ensure `.gitignore` has:
```
.streamlit/secrets.toml
.env
.venv/
__pycache__/
*.pyc
.git/
Moi_Sei.docx
chat_moi.json
```

**Verify secrets are NOT committed:**
```powershell
git status
# Should NOT show: .streamlit/secrets.toml
```

### 2.3 Create GitHub Repository

1. Go to **https://github.com/new**
2. **Repository name:** `moi-sei` (or `Moi_Sei`)
3. **Description:** "Family Contribution Tracking System - Admin & Family Portal"
4. **Public** (for free Streamlit Cloud hosting)
5. **Skip** "Initialize with README" (we'll add it)
6. Click **"Create repository"**

### 2.4 Connect Local Repo to GitHub

```powershell
git remote add origin https://github.com/sarangabani1984/moi-sei.git
git branch -M main
git push -u origin main
```

✅ **Code is on GitHub!**

---

## 🎯 STEP 3: Deploy to Streamlit Cloud

### 3.1 Link Streamlit Cloud to GitHub

1. Go to **https://share.streamlit.io**
2. Click **"New app"**
3. Sign in with GitHub (if prompted)
4. Select:
   - **Repository:** `sarangabani1984/moi-sei`
   - **Branch:** `main`
   - **Main file path:** `app.py` (admin panel)
   - Click **"Deploy"**

Streamlit will build & deploy (takes 2-3 minutes)

### 3.2 Add Secrets in Streamlit Cloud

1. After deployment, click the **"⋯"** (three dots) → **"Settings"**
2. Go to **"Secrets"** tab
3. Paste your secrets (DO NOT include `.streamlit/` — just the contents):
   ```
   MOI_SEI_POSTGRES_URL = "postgresql://postgres:[password]@[host]:[port]/postgres?sslmode=require"
   
   GREEN_API_ID_INSTANCE = "your_id_instance"
   GREEN_API_TOKEN_INSTANCE = "your_token_instance"
   ```
4. Click **"Save"**

✅ **Admin panel deployed!**

### 3.3 Deploy Family Portal (user_app.py) - OPTIONAL

1. Go back to Streamlit Cloud → **"New app"**
2. Same repo, but change:
   - **Main file path:** `user_app.py`
3. Deploy
4. Add same secrets in Settings → Secrets

✅ **Family portal deployed!**

---

## 📝 Supabase Schema Reference

### Tables Created by `backend_pg.sql`

#### `users` table
```sql
Column Name       | Type         | Purpose
------------------|--------------|---------
id                | int (PK)     | Unique family ID
phone_number      | varchar(20)  | Contact phone
husband_name      | varchar(100) | Husband's name
wife_name         | varchar(100) | Wife's name
native_place      | varchar(100) | Hometown
current_place     | varchar(100) | Current location
husband_job       | varchar(100) | Occupation
wife_job          | varchar(100) | Spouse occupation
family_deity      | varchar(100) | Kuladeivam
notes             | text         | Kurrippu (remarks)
password_hash     | varchar(255) | Login password (hashed)
search_alias      | varchar(200) | Search nickname
email             | varchar(100) | Email (optional)
is_active         | boolean      | Active status
created_at        | timestamp    | Registration date
```

#### `journal_entries` table (Double-Entry Ledger)
```sql
Column Name       | Type         | Purpose
------------------|--------------|---------
je_id             | int (PK)     | Transaction ID
je_contributor    | int (FK)     | Contributing family
je_receiver       | int (FK)     | Receiving family (host)
je_event          | int (FK)     | Event ID
je_amount         | decimal      | Amount contributed
je_date           | timestamp    | Contribution date
is_active         | boolean      | Not deleted (undo support)
```

#### `events` table
```sql
Column Name       | Type         | Purpose
------------------|--------------|---------
event_id          | int (PK)     | Unique event ID
event_name        | varchar(200) | Event name
event_date        | date         | Event date
event_place       | varchar(100) | Location
host_user_id      | int (FK)     | Host family
is_active         | boolean      | Active status
```

---

## 🔄 Local → Cloud Switching

The code **automatically detects** which database to use:

**Local (SQL Server):**
- No `MOI_SEI_POSTGRES_URL` secret → Uses SQL Server

**Cloud (Supabase):**
- `MOI_SEI_POSTGRES_URL` set → Uses PostgreSQL

No code changes needed!

---

## ✅ Post-Deployment Verification

### 1. Test Admin Panel (app.py)
- [ ] Login works (auto-authenticates)
- [ ] Can add new family
- [ ] Can record contribution with denominations
- [ ] Staff lock works (after first save)
- [ ] Collection summary updates in sidebar
- [ ] Undo feature works

### 2. Test Family Portal (user_app.py)
- [ ] Login with family phone number
- [ ] Can view profile
- [ ] Can see contribution history
- [ ] Read-only (can't edit)

### 3. Test WhatsApp Notifications
- [ ] Enter Green API test credentials
- [ ] Send test WhatsApp message
- [ ] Verify message delivered

---

## 🛠️ Troubleshooting

### "Database connection failed"
**Solution:**
1. Check Supabase connection string in Streamlit Cloud secrets
2. Verify `sslmode=require` is in the URL
3. Check firewall isn't blocking (Supabase allows all IPs by default)

### "psycopg2 not found"
**Solution:**
- Already in `requirements.txt` ✅
- Streamlit Cloud auto-installs dependencies

### "Password hashing errors"
**Solution:**
- Password hashing is automatic (Python's `hashlib`)
- No additional setup needed

### "Schema tables don't exist"
**Solution:**
1. Verify you ran `backend_pg.sql` in Supabase SQL Editor
2. Check the query result for errors
3. Re-run if needed

---

## 📊 Key Configuration Summary

| Environment | Database | Connection Method | Secrets Location |
|-------------|----------|-------------------|------------------|
| **Local Dev** | SQL Server Express | Direct OS auth | `.streamlit/secrets.toml` |
| **Streamlit Cloud** | Supabase Postgres | Connection string | Streamlit Cloud UI |
| **Code** | Supports both | Auto-detection via env vars | `db.py` handles switching |

---

## 🎯 What's Next?

1. ✅ **Phase 1 (DONE):** Admin panel with staff tracking + collection summary + undo
2. ⏳ **Phase 2 (Next):**
   - User portal updates (show transaction history)
   - Analytics dashboard (reports by event/staff/month)
   - Data import/export tools

3. ⏳ **Phase 3 (Future):**
   - Flutter mobile app (iOS/Android)
   - Advanced reporting (Power BI integration)
   - Scheduled batch notifications

---

## 💬 Support

For issues, check:
1. `.streamlit/config.toml` (Streamlit settings)
2. `db.py` (database logic)
3. `requirements.txt` (dependencies)
4. Supabase docs: https://supabase.com/docs

---

**Happy deploying! 🚀**
