# 📁 Moi Sei Project Structure Guide

After reorganization, the project is now **clean and organized** by purpose. Here's what goes where:

---

## 🎯 Quick Reference

| Folder | Purpose | Files |
|--------|---------|-------|
| **`src/app/`** | Production code (runs the app) | `app.py`, `user_app.py`, `db.py`, `notifications.py`, etc. |
| **`config/`** | Configuration & dependencies | `requirements.txt`, `.streamlit/` (settings, secrets) |
| **`database/`** | Database migrations & schema | `sql-server/` (local), `postgresql/` (cloud) |
| **`docs/`** | All documentation | Guides, deployment, setup, tutorials |
| **`scripts/`** | One-off utility scripts | Testing, data fixes, imports |
| **`archive/`** | Legacy & reference files | Old plans, exports, docs |
| **`flutter_app/`** | Mobile app (separate project) | Keep as-is |
| **`api/`** | FastAPI experimental backend | Keep as-is |

---

## 📋 Detailed Breakdown

### 🎯 `src/app/` — Production Code (THE MAIN APP)
**Run this folder when deploying to cloud or running locally**

```
src/app/
├── app.py                  ← ADMIN PANEL (main file to run: streamlit run app.py)
├── user_app.py             ← FAMILY PORTAL (run: streamlit run user_app.py)
├── db.py                   ← DATABASE LAYER (auto-detects SQL Server or Postgres)
├── notifications.py        ← WhatsApp integration (sends confirmations)
├── voice_app.py            ← Voice-based data entry (experimental)
└── voice_ai.py             ← AI voice processing (experimental)
```

**When to use:** Daily development & production deployment
**How to run locally:**
```powershell
cd src/app
streamlit run app.py       # Admin panel on http://localhost:8501
streamlit run user_app.py  # Family portal on http://localhost:8502 (different terminal)
```

---

### ⚙️ `config/` — Settings & Dependencies

```
config/
└── requirements.txt        ← All Python packages (pip install -r config/requirements.txt)
.streamlit/                 ← Streamlit configuration
├── config.toml            ← App theme & UI settings
└── secrets.template.toml  ← Secrets template (copy & fill locally)
```

**When to use:** Setting up environment, managing dependencies
**Key files:**
- `requirements.txt` → Lists all dependencies (install with: `pip install -r config/requirements.txt`)
- `.streamlit/config.toml` → Streamlit UI theme (colors, layout)
- `.streamlit/secrets.template.toml` → Shows what secrets are needed

**⚠️ IMPORTANT:** `.streamlit/secrets.toml` is in `.gitignore` — never commit!

---

### 🗄️ `database/` — Database Schemas & Migrations

```
database/
├── sql-server/             ← LOCAL development (SQL Server Express)
│   ├── backend.sql         ← Main schema (create tables)
│   └── ALTER_USERS_ADD_NEW_FIELDS.sql  ← Add notes column
│
└── postgresql/             ← CLOUD deployment (Supabase)
    ├── supabase_schema_complete.sql    ← Full schema for Supabase
    ├── backend_pg.sql      ← PostgreSQL version of schema
    └── cloud_auth_migration.sql        ← Additional cloud migrations
```

**When to use:** Database setup & migrations

**For Local Development (SQL Server):**
1. Run: `backend.sql` (creates tables)
2. Run: `ALTER_USERS_ADD_NEW_FIELDS.sql` (adds notes column)

**For Cloud Deployment (Supabase):**
1. Create Supabase account → New project
2. Go to SQL Editor → Paste `supabase_schema_complete.sql` → Run
3. Then run: `cloud_auth_migration.sql`

---

### 📚 `docs/` — All Documentation

```
docs/
├── README.md                          ← Project overview (for GitHub)
├── CLOUD_DEPLOYMENT.md               ← STEP-BY-STEP cloud deployment guide
├── CLOUD_READINESS_CHECKLIST.md      ← Code audit (everything is cloud-ready)
├── GITHUB_SETUP.md                   ← GitHub push instructions
├── VOICE_AI_SETUP.md                 ← Voice feature setup
├── FLUTTER_GUIDE.md                  ← Flutter mobile app guide
└── learning_roadmap.md               ← Learning materials & roadmap
```

**When to use:** Setup, deployment, learning

**Quick Start:**
1. First time? → Read `README.md`
2. Going to cloud? → Follow `CLOUD_DEPLOYMENT.md`
3. Pushing to GitHub? → Use `GITHUB_SETUP.md`
4. Setting up voice? → See `VOICE_AI_SETUP.md`

---

### 🔧 `scripts/` — Utility & Testing Scripts (ONE-OFF USE)

```
scripts/
├── test_api_key.py                   ← Test OpenAI/LiteLLM API
├── test_litellm.py                   ← LiteLLM integration tests
├── delete_user.py                    ← Database utility (delete a family)
├── fix_dummy_tamil_profiles.py       ← Data cleanup script
├── fix_imported_tamil_profiles.py    ← Data migration tool
└── import_excel_contributions.py     ← Bulk import from Excel
```

**When to use:** Testing, data fixes, bulk operations (NOT for production daily use)

**Example:**
```powershell
cd scripts
python test_api_key.py        # Test WhatsApp API
python delete_user.py          # Delete a user from DB
```

---

### 📦 `archive/` — Legacy & Reference Files

```
archive/
├── cloud_deployment_plan.md    ← Old deployment plan (superseded by CLOUD_DEPLOYMENT.md)
├── conversation_log.md         ← Old chat logs
├── process_flow.md             ← Legacy workflow docs
├── chat_moi.json               ← Old chat export
└── Moi_Sei.docx                ← Word document (reference)
```

**When to use:** Rarely — only for reference or if you need historical context

**Note:** These are kept for archival purposes. If you don't need them, delete them.

---

### 📱 `flutter_app/` & 🔌 `api/` — Keep Separate

```
flutter_app/                   ← Flutter mobile app (iOS/Android)
api/                           ← FastAPI backend (experimental)
```

**These are separate sub-projects.** Keep them organized as they are.

---

## 🚀 Common Tasks & Where to Find Files

| Task | File Location |
|------|----------------|
| **Run admin panel** | `src/app/app.py` |
| **Run family portal** | `src/app/user_app.py` |
| **Check database logic** | `src/app/db.py` |
| **Install dependencies** | `config/requirements.txt` → `pip install -r config/requirements.txt` |
| **Setup Streamlit config** | `.streamlit/config.toml` |
| **Add API secrets locally** | `.streamlit/secrets.toml` (create from `.streamlit/secrets.template.toml`) |
| **Create local database** | `database/sql-server/` files |
| **Create cloud database** | `database/postgresql/supabase_schema_complete.sql` |
| **Deploy to cloud** | Follow `docs/CLOUD_DEPLOYMENT.md` |
| **Push to GitHub** | Follow `docs/GITHUB_SETUP.md` |
| **Test WhatsApp API** | `scripts/test_api_key.py` |
| **Bulk import data** | `scripts/import_excel_contributions.py` |

---

## 📊 File Count Summary

| Folder | Count | Type |
|--------|-------|------|
| `src/app/` | 6 files | Python app code |
| `config/` | 1 file | Config |
| `database/sql-server/` | 2 files | SQL migrations |
| `database/postgresql/` | 3 files | SQL migrations |
| `docs/` | 7 files | Markdown docs |
| `scripts/` | 6 files | Python utilities |
| `archive/` | 5 files | Legacy files |
| **TOTAL** | **30 files** | Clean & organized |

---

## 🎯 Navigation Tips

### If you want to...

**...run the app locally:**
```powershell
# Terminal 1: Admin panel
cd src/app
streamlit run app.py

# Terminal 2: Family portal
cd src/app
streamlit run user_app.py
```

**...see what to install:**
```powershell
cat config/requirements.txt
```

**...set up local database:**
```powershell
# Run SQL Server scripts in Management Studio
database/sql-server/backend.sql
database/sql-server/ALTER_USERS_ADD_NEW_FIELDS.sql
```

**...deploy to cloud:**
```powershell
# Follow step-by-step guide
cat docs/CLOUD_DEPLOYMENT.md
```

**...push to GitHub:**
```powershell
# Follow step-by-step guide
cat docs/GITHUB_SETUP.md
```

---

## ✨ Organization Benefits

✅ **Clear separation** → Know instantly what's for dev, cloud, docs, scripts  
✅ **Easy to navigate** → Find files faster  
✅ **GitHub-friendly** → Clean folder structure for teams  
✅ **Deployment-ready** → Organized files mean fewer mistakes  
✅ **Maintenance** → Legacy files don't clutter root directory  

---

## 🔄 If You Add New Files

Follow this guide:

| File Type | Goes In |
|-----------|---------|
| Python app code | `src/app/` |
| Database migration | `database/sql-server/` or `database/postgresql/` |
| Documentation | `docs/` |
| Testing script | `scripts/` |
| Config file | `config/` |
| Old/unused files | `archive/` |

---

## 📞 Questions?

- **"Where's the main code?"** → `src/app/app.py`
- **"How do I run it?"** → `streamlit run src/app/app.py`
- **"Where's the database setup?"** → `database/`
- **"How do I deploy?"** → `docs/CLOUD_DEPLOYMENT.md`
- **"Where's my requirements?"** → `config/requirements.txt`

---

**Last Updated:** September 2026  
**Status:** ✅ Clean, organized, production-ready
