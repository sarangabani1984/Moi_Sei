# 🐙 GitHub Setup & Push Guide

Quick step-by-step to push Moi Sei code to GitHub and prepare for cloud deployment.

---

## Step 1: Verify `.gitignore` Exists

Run in PowerShell (in your Moi Sei folder):

```powershell
cd "c:\Users\sarangs\OneDrive - Hewlett Packard Enterprise\All_VS_Code\Moi_Sei"
Test-Path .gitignore
```

**Expected output:** `True`

If `.gitignore` doesn't exist, check its contents:

```powershell
Get-Content .gitignore
```

**Should contain:**
```
.streamlit/secrets.toml
.env
.venv/
__pycache__/
*.pyc
```

---

## Step 2: Check Git Status

Verify no secrets are staged for commit:

```powershell
git status
```

**What you should NOT see in output:**
- `.streamlit/secrets.toml`
- `.env`

**What you SHOULD see:**
- Untracked files: All `.py`, `.md`, `.sql`, `.txt`, `requirements.txt`

---

## Step 3: Stage All Code Files

```powershell
git add .
```

Verify nothing dangerous is staged:

```powershell
git diff --cached --name-only | Where-Object { $_ -match "secrets|\.env|\.venv" }
```

**Expected output:** (blank/nothing)

---

## Step 4: Create Initial Commit

```powershell
git commit -m "Initial commit: Moi Sei Admin Panel v1.0 with staff tracking, collection summary, undo, and cloud deployment ready"
```

**Expected output:**
```
[main (root-commit) abc123] Initial commit: Moi Sei Admin Panel v1.0 ...
 XX files changed, XXXX insertions(+)
 create mode 100644 app.py
 create mode 100644 user_app.py
 create mode 100644 db.py
 ...
```

---

## Step 5: Create GitHub Repository

1. Open **https://github.com/new** in browser
2. Fill in:
   - **Repository name:** `moi-sei` (or `Moi_Sei`)
   - **Description:** "Family Contribution Tracking System - Admin Panel & Family Portal with WhatsApp Integration"
   - **Public** (checked) — needed for free Streamlit Cloud hosting
   - **Skip** "Initialize with README" (we already have one)
   - **Skip** ".gitignore template" (we already have .gitignore)
3. Click **"Create repository"**

**You'll see a page with:**
```
…or push an existing repository from the command line
git remote add origin https://github.com/sarangabani1984/moi-sei.git
git branch -M main
git push -u origin main
```

Copy this (you'll need it next)

---

## Step 6: Connect Local Repo to GitHub

Run these commands (replace with YOUR GitHub username if different):

```powershell
# Add GitHub as remote
git remote add origin https://github.com/sarangabani1984/moi-sei.git

# Rename default branch to 'main' (if not already)
git branch -M main

# Push code to GitHub
git push -u origin main
```

**Expected output:**
```
Enumerating objects: XX, done.
Counting objects: 100% (XX/XX), done.
Delta compression using up to XX threads.
Compressing objects: 100% (XX/XX), done.
Writing objects: 100% (XX/XX), 1.23 MiB | 5.67 MiB/s, done.
Total XX (delta XX), reused XX (delta 0), pack-reused 0
remote: Resolving deltas: 100% (XX/XX), done.
To https://github.com/sarangabani1984/moi-sei.git
 * [new branch]      main -> main
Branch 'main' is set up to track remote branch 'main' from 'origin'.
```

---

## Step 7: Verify on GitHub

1. Open **https://github.com/sarangabani1984/moi-sei** in browser
2. You should see:
   - All files listed (app.py, user_app.py, db.py, requirements.txt, etc.)
   - README.md displayed
   - No `.streamlit/secrets.toml` file (good! It's in .gitignore)
   - Branch: `main`

---

## Step 8: Get Repository URL for Streamlit Cloud

Copy this URL (you'll need it when deploying):

```
https://github.com/sarangabani1984/moi-sei
```

Or via command line:

```powershell
git config --get remote.origin.url
```

---

## Subsequent Updates (After Changes)

Whenever you update code locally:

```powershell
# See what changed
git status

# Stage changes
git add .

# Commit with message
git commit -m "Update: Describe what changed"

# Push to GitHub
git push
```

---

## Useful Commands Reference

```powershell
# Check current branch
git branch

# See commit history
git log --oneline

# See all remotes
git remote -v

# Undo last commit (keep changes)
git reset HEAD~1

# Remove file from tracking (but keep locally)
git rm --cached .streamlit/secrets.toml
```

---

## Next Steps

After successful push to GitHub:

1. ✅ Go to **[CLOUD_DEPLOYMENT.md](CLOUD_DEPLOYMENT.md)**
2. ✅ Create Supabase project (Step 1)
3. ✅ Deploy to Streamlit Cloud (Step 3, uses this GitHub repo)
4. ✅ Add secrets in Streamlit Cloud dashboard
5. ✅ Test live app!

---

## Troubleshooting

### "fatal: not a git repository"
```powershell
# Reinitialize
git init
git add .
git commit -m "Initial commit"
```

### "Permission denied (publickey)"
- Add SSH key to GitHub: https://github.com/settings/ssh/new
- Or use HTTPS with Personal Access Token: https://github.com/settings/tokens

### "Changes not pushed"
```powershell
# Check if remote exists
git remote -v

# If not, add it
git remote add origin https://github.com/sarangabani1984/moi-sei.git

# Try push again
git push -u origin main
```

### ".gitignore not working"
```powershell
# Remove file from tracking
git rm --cached .streamlit/secrets.toml

# Reapply .gitignore
git add .gitignore
git commit -m "Fix: Update .gitignore to exclude secrets"
git push
```

---

**Status:** Ready for GitHub! 🚀
