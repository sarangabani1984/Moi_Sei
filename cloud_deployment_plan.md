# Moi Sei — Free Cloud Deployment Plan & Mobile Architecture

This document contains the complete blueprint and step-by-step roadmap for migrating the **Moi Sei** application from local development (SQL Server Express + local Streamlit) to a **100% Free Cloud Infrastructure** accessible from any smartphone or browser.

---

## 1. System Architecture

```mermaid
flowchart TD
    subgraph Users ["Mobile / Desktop Clients"]
        A["Admin / Receptionist"] -->|Opens Browser| B["Admin Streamlit App (app.py)"]
        C["Family Member"] -->|Opens Browser| D["Family Portal App (user_app.py)"]
    end

    subgraph CloudHosting ["Streamlit Community Cloud (FREE)"]
        B
        D
    end

    subgraph Database ["Supabase / Neon Postgres (FREE)"]
        DB[(MoiSei Postgres DB)]
        SP[Stored Procedures / Functions & Double-Entry Ledger]
    end

    subgraph External ["Messaging Service"]
        WA[Green API WhatsApp REST API]
    end

    B -->|SQL Queries via psycopg2| DB
    D -->|Read-only Queries| DB
    B -->|Sends Confirmation| WA
```

---

## 2. Tech Stack & Free Tier Breakdown

| Layer | Component | Cloud Free Tier Service | Cost |
| :--- | :--- | :--- | :--- |
| **Frontend & App Server** | Web UI & Backend Logic | **Streamlit Community Cloud** (`share.streamlit.io`) | **$0 / month** |
| **Database** | Double-Entry Ledger & Stored Procedures | **Supabase** (`supabase.com`) or **Neon Tech** (`neon.tech`) | **$0 / month** (500MB PostgreSQL) |
| **Messaging** | WhatsApp Confirmations | **Green API Developer Tier** (`green-api.com`) | **$0 / month** |
| **Source Control** | GitHub Repo | **GitHub** (`sarangabani1984/Moi_Sei`) | **$0 / month** |

---

## 3. Migration Roadmap (Step-by-Step)

### Step 1: Set Up Cloud PostgreSQL Database
1. Create a free account at [Supabase](https://supabase.com) or [Neon Tech](https://neon.tech).
2. Create a new database project named `MoiSei`.
3. Copy the database connection string:
   `postgresql://postgres:[PASSWORD]@[HOST]:5432/MoiSei`
4. Convert T-SQL (`backend.sql`) to PostgreSQL syntax (`psql` stored functions) and run in Supabase SQL Editor.

### Step 2: Push Latest Code to GitHub
Ensure all updated files (`app.py`, `user_app.py`, `db.py`, `notifications.py`, `requirements.txt`) are committed and pushed to `https://github.com/sarangabani1984/Moi_Sei`.

### Step 3: Deploy Frontend on Streamlit Community Cloud
1. Log in to [share.streamlit.io](https://share.streamlit.io) using GitHub.
2. Deploy App 1:
   - Repository: `sarangabani1984/Moi_Sei`
   - Main file path: `app.py`
   - Yields live Admin URL: `https://moisei-admin.streamlit.app`
3. Deploy App 2:
   - Repository: `sarangabani1984/Moi_Sei`
   - Main file path: `user_app.py`
   - Yields live Family Portal URL: `https://moisei-portal.streamlit.app`

### Step 4: Configure Cloud Secrets
In Streamlit Cloud settings $\rightarrow$ **Secrets**, paste your Green API credentials:

```toml
GREEN_API_ID_INSTANCE = "710722734735"
GREEN_API_TOKEN_INSTANCE = "7ddbc62cc97f48e6b0ff8c76025dc1f6f49904f3b7b7474fb2"
DEFAULT_COUNTRY_CODE = "+91"
POSTGRES_URL = "postgresql://postgres:password@db.xxx.supabase.co:5432/postgres"
```

---

## 4. Mobile Installation (Add to Home Screen)

For Android and iOS users to use **Moi Sei** like a native mobile app:
1. Open the Streamlit URL on Android Chrome or iPhone Safari.
2. Tap **Share / Options menu** $\rightarrow$ **"Add to Home Screen"**.
3. A "Moi Sei" app icon will appear on their phone home screen and launch full-screen.

---

## 5. PostgreSQL Schema Script (`backend_pg.sql` equivalent)

When migrating to Supabase/Neon, use PostgreSQL syntax:
- Replace `NVARCHAR` $\rightarrow$ `VARCHAR` or `TEXT`.
- Replace `IDENTITY(1,1)` $\rightarrow$ `SERIAL` or `BIGSERIAL`.
- Replace `DATETIME2` $\rightarrow$ `TIMESTAMPTZ`.
- Replace `SYSDATETIME()` $\rightarrow$ `NOW()`.
- Replace `BIT` $\rightarrow$ `BOOLEAN`.
- Replace T-SQL `CREATE PROCEDURE` $\rightarrow$ PostgreSQL `CREATE OR REPLACE FUNCTION ... RETURNS void AS $$ ... $$ LANGUAGE plpgsql;`.
