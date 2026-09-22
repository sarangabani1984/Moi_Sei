# 🛕 Moi Sei — Family Contribution Tracking System

A modern, full-featured **admin panel** and **family portal** for managing family contributions during events (weddings, temple festivals, religious ceremonies, etc.). Built with Streamlit, PostgreSQL, and WhatsApp integration.

**Live Demo:** `[Your Streamlit Cloud URL will appear here after deployment]`

---

## ✨ Features

### 👨‍💼 Admin Panel (`app.py`)
- **Family Registration** – Capture phone, spouse names, occupations, hometown, deity, notes
- **Contribution Recording** – Record contributions with denomination breakdown (₹1000, ₹500, ₹200, ₹100, ₹50, ₹20, ₹10)
- **Multi-Staff Tracking** – Assign collections to individual staff members (Suresh, Sarang, etc.)
  - Real-time per-staff totals in sidebar
  - Staff lock after first contribution (prevents accidental switching)
  - Change Staff confirmation dialog
- **Collection Summary** – Live sidebar showing:
  - Total collected (event-wise)
  - Number of families contributed
  - Per-staff breakdown with denomination counts
- **Undo Feature** – Recover from mistaken contributions (with confirmation)
- **WhatsApp Notifications** – Send auto-confirmations via Green API
- **Keyboard Shortcuts** – Ctrl+S to save, Tab to auto-load pasted details
- **Tamil Localization** – Field labels in Tamil (போன், குறிப்பு, குலதெய்வம், etc.)

### 👨‍👩‍👧‍👦 Family Portal (`user_app.py`)
- View profile (name, phone, occupation, hometown)
- See contribution history
- Event-wise transaction summary
- Read-only access (view only, no editing)

### 🗄️ Database
- **Supabase PostgreSQL** (cloud) or **SQL Server Express** (local)
- Automatic dual-mode detection via environment variables
- Double-entry ledger for financial integrity
- Staff session tracking
- Denomination analytics

---

## 📦 Tech Stack

| Layer | Technology | Why |
|-------|-----------|-----|
| **Frontend** | Streamlit >=1.30.0 | Simple, fast Python UI; no JavaScript needed |
| **Database (Local)** | SQL Server Express | Pre-existing; tested |
| **Database (Cloud)** | Supabase PostgreSQL | Free tier, serverless, included full-text search |
| **Messaging** | Green API WhatsApp | Free tier, tested, reliable |
| **Auth** | PBKDF2 Password Hashing | Secure, simple (no external OAuth needed) |
| **Deployment** | Streamlit Community Cloud | Free tier, Git-based deployment |

---

## 🚀 Quick Start

### Prerequisites
- **Python 3.9+**
- **Git**
- **Free Accounts:**
  - Supabase (https://supabase.com)
  - Streamlit Cloud (https://share.streamlit.io)
  - Green API (https://green-api.com) — optional, for WhatsApp

### Local Development (5 minutes)

1. **Clone the repository**
   ```bash
   git clone https://github.com/sarangabani1984/moi-sei.git
   cd moi-sei
   ```

2. **Create virtual environment**
   ```bash
   python -m venv .venv
   # Windows
   .venv\Scripts\activate
   # macOS/Linux
   source .venv/bin/activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure secrets (LOCAL ONLY)**
   - Copy `.streamlit/secrets.template.toml` → `.streamlit/secrets.toml`
   - Fill in your local SQL Server details (or Supabase connection string)
   - ⚠️ **Never commit `secrets.toml` to GitHub** (already in `.gitignore`)

5. **Run admin panel**
   ```bash
   streamlit run app.py
   ```
   Visits http://localhost:8501 automatically

6. **Run family portal (in another terminal)**
   ```bash
   streamlit run user_app.py -- --server.port=8502
   ```
   Visit http://localhost:8502

---

## ☁️ Cloud Deployment (10 minutes)

Full step-by-step guide in **[CLOUD_DEPLOYMENT.md](CLOUD_DEPLOYMENT.md)**

**Quick summary:**
1. Set up **Supabase PostgreSQL** database
2. Push code to **GitHub**
3. Deploy admin panel to **Streamlit Cloud** (link GitHub repo)
4. Add secrets in Streamlit Cloud dashboard
5. Done! App runs at `https://share.streamlit.io/[your-username]/moi-sei`

---

## 📁 Project Structure

```
moi-sei/
├── app.py                          # Admin panel (staff collection tracking)
├── user_app.py                     # Family portal (read-only)
├── db.py                           # Database layer (auto-switches SQL Server ↔ Postgres)
├── notifications.py                # WhatsApp integration
├── voice_app.py                    # Voice-based data entry (optional)
├── voice_ai.py                     # AI voice processing (optional)
├── requirements.txt                # Python dependencies
├── .streamlit/
│   ├── config.toml                 # Streamlit UI settings
│   └── secrets.template.toml       # Secrets template (copy & fill locally)
├── .gitignore                      # Excludes secrets, venv, cache
├── README.md                       # This file
├── CLOUD_DEPLOYMENT.md             # Detailed deployment guide
├── supabase_schema_complete.sql    # PostgreSQL schema for Supabase
├── cloud_auth_migration.sql        # Additional cloud-specific migrations
├── backend_pg.sql                  # Original PostgreSQL schema
├── backend.sql                     # Original SQL Server schema
└── api/
    └── main.py                     # FastAPI backend (experimental)
```

---

## 🔌 Database Modes

### Local Development (SQL Server Express)
```python
# db.py auto-detects this configuration:
MOI_SEI_SQL_SERVER = "JNPR-WIN-MPRZ09\SQLEXPRESS"
MOI_SEI_SQL_DATABASE = "MoiSei"
```
- Run locally on Windows
- No internet required
- Full pyodbc driver support

### Cloud Deployment (Supabase PostgreSQL)
```python
# Set this environment variable or Streamlit secret:
MOI_SEI_POSTGRES_URL = "postgresql://user:password@host:port/database?sslmode=require"
```
- Accessible from anywhere
- Free tier: 500MB storage
- All features supported

**The code automatically detects which mode to use based on available environment variables. No code changes needed!**

---

## 👤 User Roles

| Role | Access | Features |
|------|--------|----------|
| **Admin (Suresh/Sarang)** | Full | Record contributions, multi-staff tracking, undo, WhatsApp |
| **Family Member** | Read-only | View profile, see transaction history |
| **Guest** | View-only | See event summary (future feature) |

---

## 🎯 Core Workflows

### Workflow 1: Recording a Contribution
1. Admin opens **app.py**
2. Selects or creates family from dropdown
3. Enters contribution amount
4. Selects denomination(s) (e.g., 1×₹1000 + 1×₹500)
5. Press **Ctrl+S** → Contribution saved
6. Sidebar updates with staff total + family count
7. WhatsApp confirmation sent (optional)

### Workflow 2: Multi-Staff Event Tracking
1. **Event Start:** Staff selects their name (e.g., "suresh")
2. **After First Contribution:** Staff name locks with 🔒 indicator
3. **Can Switch Staffs:** Requires confirmation ("Change Staff? Y/N")
4. **Sidebar Summary:**
   - Total collected: ₹50,000
   - suresh: ₹30,000 (40 families, ₹1000: 20, ₹500: 20)
   - sarang: ₹20,000 (30 families, ₹1000: 15, ₹500: 10)

### Workflow 3: Undo a Wrong Entry
1. Admin sees mistake (e.g., wrong amount or family)
2. Clicks **↩️ Undo Last Entry**
3. Confirms deletion dialog
4. Contribution marked as inactive (recoverable)
5. Staff total refreshes

### Workflow 4: Family Checking History
1. Family member opens **user_app.py**
2. Logs in with phone number
3. Sees:
   - Profile (husband, wife, hometown, etc.)
   - All contributions made
   - Event-wise summary
   - Transaction dates

---

## 🔐 Security Features

- **Password Hashing:** PBKDF2-SHA256 with 200k iterations (industry standard)
- **SSL/TLS:** All cloud connections encrypted
- **Secrets Management:**
  - Local: `.streamlit/secrets.toml` (in `.gitignore`)
  - Cloud: Streamlit Cloud secrets panel (never visible in logs)
- **Session State:** Streamlit session isolation (no cross-user data leakage)
- **Read-Only Portal:** Family portal cannot modify data
- **Staff Lock:** Prevents accidental data mixing between staff

---

## 📊 Analytics & Reporting

Built-in views (SQL):
- `event_summary` – Total families, receivers, amount per event
- `family_transactions` – Transaction history for family portal
- `denomination_tracking` – Breakdown of notes used per event

Future: Power BI dashboards, monthly reports, family-wise analytics

---

## 📝 Configuration

### Streamlit Settings (`.streamlit/config.toml`)
```toml
[theme]
primaryColor = "#FF6B35"
backgroundColor = "#FFFBF0"
secondaryBackgroundColor = "#FFE66D"

[client]
showErrorDetails = false
toolbarMode = "minimal"
```

### Environment Variables

**Local (Windows):**
```env
MOI_SEI_SQL_SERVER=JNPR-WIN-MPRZ09\SQLEXPRESS
MOI_SEI_SQL_DATABASE=MoiSei
```

**Cloud (Streamlit Cloud Secrets):**
```env
MOI_SEI_POSTGRES_URL=postgresql://user:password@host:port/database?sslmode=require
GREEN_API_ID_INSTANCE=your_id_instance
GREEN_API_TOKEN_INSTANCE=your_token_instance
```

---

## 🐛 Troubleshooting

### "Cannot connect to database"
- **Local:** Ensure SQL Server Express is running (`services.msc`)
- **Cloud:** Check Supabase connection string in Streamlit Cloud secrets
- Verify firewall isn't blocking port 5432 (PostgreSQL)

### "psycopg2 not found"
- Already in `requirements.txt`
- On Streamlit Cloud, it auto-installs
- Local: `pip install psycopg2-binary`

### "WhatsApp message not sending"
- Check Green API credentials in `.streamlit/secrets.toml`
- Verify phone number format (include country code, e.g., +919876543210)
- Test credentials in Green API dashboard first

### "Streamlit session state errors"
- Clear browser cache → F5 refresh
- Restart Streamlit: Press `C` in terminal, then re-run

---

## 📚 Documentation

- **[CLOUD_DEPLOYMENT.md](CLOUD_DEPLOYMENT.md)** – Full step-by-step cloud setup guide
- **[supabase_schema_complete.sql](supabase_schema_complete.sql)** – Complete PostgreSQL schema with stored procedures
- **[cloud_auth_migration.sql](cloud_auth_migration.sql)** – Cloud-specific database migrations
- **[VOICE_AI_SETUP.md](VOICE_AI_SETUP.md)** – Voice-based data entry (experimental)
- **[FLUTTER_GUIDE.md](FLUTTER_GUIDE.md)** – Mobile app setup (in progress)

---

## 🤝 Contributing

Found a bug or have a feature idea?
1. Fork the repo
2. Create a feature branch (`git checkout -b feature/your-idea`)
3. Commit changes (`git commit -m "Add: your feature"`)
4. Push to branch (`git push origin feature/your-idea`)
5. Open a Pull Request

---

## 📞 Support

- **Email:** sarangabani2026@gmail.com
- **GitHub Issues:** [moi-sei/issues](https://github.com/sarangabani1984/moi-sei/issues)
- **WhatsApp:** Test mode via Green API dashboard

---

## 📄 License

MIT License — Feel free to use, modify, and distribute this project.

---

## 🙏 Acknowledgments

- **Streamlit** – Fast, simple Python UI framework
- **Supabase** – PostgreSQL hosting and backend services
- **Green API** – WhatsApp integration
- **Family & Community** – The reason we built this!

---

**Version:** 1.0.0 (Admin Panel + Staff Tracking + Cloud-Ready)  
**Last Updated:** January 2025  
**Status:** Production-Ready ✅

---

### Quick Links

- 🎬 **[Deploy to Streamlit Cloud](CLOUD_DEPLOYMENT.md#-step-3-deploy-to-streamlit-cloud)**
- 🗄️ **[Set Up Supabase](CLOUD_DEPLOYMENT.md#-step-1-set-up-supabase-postgresql-database)**
- 📤 **[Push to GitHub](CLOUD_DEPLOYMENT.md#-step-2-push-code-to-github)**
- ❓ **[Troubleshooting](TROUBLESHOOTING.md)**

---

*Made with ❤️ for family and community*
