# Moi Sei API

This is the first API slice for the future Flutter family portal.

## Local setup

From the repository root:

```powershell
python -m pip install -r api/requirements.txt
python -m uvicorn api.main:app --reload --port 8000
```

Check the API:

```text
http://localhost:8000/health
http://localhost:8000/docs
```

The API uses the same `db.py` abstraction as the Streamlit apps:

- Without `MOI_SEI_POSTGRES_URL`, it uses local SQL Server.
- With `MOI_SEI_POSTGRES_URL`, it uses Supabase PostgreSQL.

Set the PostgreSQL URL as an environment variable when testing against Supabase. Never commit the real URL or database password.

## Flutter connection

The Android emulator reaches the computer running the API through `10.0.2.2`:

```powershell
flutter run --dart-define=MOI_SEI_API_URL=http://10.0.2.2:8000
```

For a physical phone, use the computer's local network address instead, for example:

```powershell
flutter run --dart-define=MOI_SEI_API_URL=http://192.168.1.33:8000
```
