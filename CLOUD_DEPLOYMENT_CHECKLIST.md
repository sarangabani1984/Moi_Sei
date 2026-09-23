# ☁️ Moi Sei Cloud Deployment Checklist

**Status:** ✅ Ready for Cloud Deployment  
**Last Updated:** 2026-09-23  
**Target:** Streamlit Cloud + Supabase PostgreSQL

---

## 📋 Pre-Deployment Verification

### 1. ✅ Code Quality
- [x] Removed Tanglish feature code
- [x] Updated theme to professional dark (Navy + Teal)
- [x] All keyboard shortcuts working locally (Ctrl+S, Ctrl+D, Tab)
- [x] No console errors on localhost:8501

### 2. ✅ Credential Management (CRITICAL)
- [x] All `st.secrets.get()` → `_get_credential()` (checks env vars too)
- [x] `.streamlit/secrets.toml` is `.gitignore`'d ✓
- [x] Database connection uses `_get_secret_or_env()` ✓
- [x] WhatsApp credentials properly abstracted ✓
- [x] OpenAI key handling validated ✓

**Cloud-Safe:** YES - Will work with Streamlit Cloud Secrets dashboard

### 3. ✅ Database Configuration
- [x] `db.py` auto-detects PostgreSQL via `MOI_SEI_POSTGRES_URL`
- [x] Falls back to SQL Server if `POSTGRES_URL` env var not set
- [x] Connection pooling via threading.local
- [x] Supabase schema ready in `database/postgresql/backend_pg.sql`

**Cloud-Safe:** YES - Requires only env var on deployment

### 4. ✅ Streamlit Configuration
- [x] `config.toml` theme applied (Navy/Blue/Teal)
- [x] `headless = true` (compatible with Streamlit Cloud)
- [x] `port = 8501` (Streamlit Cloud default)
- [x] No hardcoded file paths

**Cloud-Safe:** YES

---

## 🚀 Pre-Push Checklist

Before pushing to GitHub:
- [ ] Run: `git status` — should show only `.streamlit/config.toml` and `src/app/app.py`
- [ ] Verify: `.streamlit/secrets.toml` is NOT listed
- [ ] Verify: No API keys/passwords visible in staged changes
- [ ] Run app locally: `streamlit run src/app/app.py` → Check theme loads
- [ ] Test: Ctrl+S (save), Ctrl+D (reset) shortcuts work
- [ ] Commit message: "feat: professional dark theme + cloud alignment (secrets, credentials)"

---

## ☁️ Streamlit Cloud Deployment Steps

### Step 1: Prepare Repository
```bash
git add .streamlit/config.toml src/app/app.py
git commit -m "feat: professional dark theme + cloud alignment (secrets, credentials)"
git push origin master
```

### Step 2: Create Streamlit Cloud App
1. Go to [share.streamlit.io](https://share.streamlit.io)
2. Click "Create app"
3. Select repo: `github.com/sarangabani1984/moi-sei` (or your repo)
4. Set **Main file path:** `src/app/app.py`
5. Click "Deploy"

### Step 3: Configure Secrets (CRITICAL)
After app deploys, configure secrets:
1. Go to app → Settings ⚙️ → Secrets
2. Add each secret as `KEY = value`:

```toml
# PostgreSQL (Supabase)
MOI_SEI_POSTGRES_URL = "postgresql://user:password@db.supabase.co:5432/postgres"

# WhatsApp
GREEN_API_ID_INSTANCE = "1234567890"
GREEN_API_TOKEN_INSTANCE = "your_token_here"

# AI
OPENAI_API_KEY = "sk-proj-..."

# Optional
DEFAULT_COUNTRY_CODE = "+91"
```

3. Click "Save & Rerun"

### Step 4: Test Cloud App
1. Navigate to app URL (e.g., `https://share.streamlit.io/sarangabani1984/moi-sei`)
2. Check:
   - [ ] Theme loads correctly (Navy background, Teal headers)
   - [ ] Login works (auto-authenticated)
   - [ ] Family form displays
   - [ ] Ctrl+S shortcut works (test in browser console)
   - [ ] Database connection works (form can load families)

---

## 🗄️ Database Setup (Supabase)

### Prerequisite: Create Supabase Project
1. Go to [supabase.com](https://supabase.com)
2. Create new project (region: closest to you)
3. Copy connection string: **Connection pooler** (not Direct)
4. Format: `postgresql://postgres:password@db.project.supabase.co:6543/postgres`

### Import Schema
```bash
# Get Supabase psql CLI connection
psql "postgresql://postgres:password@db.project.supabase.co:6543/postgres" \
  -f database/postgresql/backend_pg.sql
```

Or use Supabase SQL editor:
1. Go to Project → SQL Editor
2. Create new query
3. Copy contents of `database/postgresql/backend_pg.sql`
4. Run

---

## 📝 Environment Variables Reference

| Variable | Example | Required | Source |
|----------|---------|----------|--------|
| `MOI_SEI_POSTGRES_URL` | `postgresql://...` | YES (Cloud) | Supabase → Connection pooler |
| `GREEN_API_ID_INSTANCE` | `1234567890` | YES (WhatsApp) | [green-api.com](https://green-api.com) |
| `GREEN_API_TOKEN_INSTANCE` | `abcd1234...` | YES (WhatsApp) | [green-api.com](https://green-api.com) |
| `OPENAI_API_KEY` | `sk-proj-...` | NO (Optional) | [platform.openai.com](https://platform.openai.com) |
| `GROQ_API_KEY` | `gsk_...` | NO (Optional) | [console.groq.com](https://console.groq.com) |
| `DEFAULT_COUNTRY_CODE` | `+91` | NO (Default) | User preference |

---

## 🔐 Security Best Practices

✅ **Already Implemented:**
1. All API keys in `secrets.toml` (git-ignored)
2. Credential retrieval via `_get_credential()` (checks env vars first)
3. No hardcoded secrets in code
4. `.streamlit/secrets.toml` in `.gitignore`

✅ **Cloud Deployment:**
1. Use Streamlit Cloud Secrets dashboard (encrypted)
2. Never paste secrets into code or git
3. Rotate tokens regularly
4. Monitor usage (Green API, OpenAI)

---

## 🐛 Troubleshooting

| Issue | Solution |
|-------|----------|
| App won't start | Check Streamlit Cloud logs for errors |
| Database connection fails | Verify `MOI_SEI_POSTGRES_URL` in Secrets is correct |
| WhatsApp not sending | Verify `GREEN_API_ID_INSTANCE` and token in Secrets |
| Theme looks wrong | Clear browser cache, hard refresh (Ctrl+Shift+R) |
| Credentials not loading | Ensure Streamlit Cloud app has rerun after adding secrets |

---

## 📞 Support Resources

- **Streamlit Docs:** https://docs.streamlit.io
- **Streamlit Cloud:** https://docs.streamlit.io/streamlit-cloud
- **Supabase Docs:** https://supabase.com/docs
- **Green API:** https://green-api.com/docs
- **This Project:** Check `README.md` in root

---

✅ **Cloud alignment complete. Ready to push & deploy!**
