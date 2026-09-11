# Moi Sei — Process Flow

## Overall picture

```mermaid
flowchart TD
    A["Admin / Reception<br>app.py"] -->|"reads and writes data"| C["db.py<br>(the helper that talks to the database)"]
    B["Family Member<br>user_app.py"] -->|"only reads their own data"| C
    C -->|"runs safe, pre-approved steps"| D[("SQL Server Database<br>MoiSei")]
```

**In plain words:** There are two screens people use — one for staff, one for families. Neither screen talks to the database directly. Both go through one helper file (`db.py`), which is the only thing allowed to open the database.

---

## Flow 1: Staff records a contribution (`app.py`)

```mermaid
flowchart TD
    A["Staff types:<br>Contributor phone, Receiver phone, Event ID, Amount"] --> B["Click 'Check Details'"]
    B --> C{"Are both families<br>found in the system?"}
    C -->|"No"| D["Show a form to add<br>the missing family"]
    D --> E["Staff fills in the new<br>family's details and saves"]
    E --> C
    C -->|"Yes"| F["Show contributor, receiver,<br>and event details on screen"]
    F --> G["Staff checks it looks correct"]
    G --> H["Click 'Submit Contribution'"]
    H --> I["Database saves the record safely"]
    I --> J["Screen shows 'Success'"]
```

---

## Flow 2: Family checks their own history (`user_app.py`)

```mermaid
flowchart TD
    A["Family types their<br>phone number"] --> B["Click 'View My Records'"]
    B --> C{"Is this phone number<br>registered?"}
    C -->|"No"| D["Show error message"]
    C -->|"Yes"| E["Show their family name"]
    E --> F["Table 1: What I contributed<br>(and to whom)"]
    E --> G["Table 2: What I received<br>(and from whom)"]
    E --> H["Table 3: Totals with each family<br>across every event"]
    H --> I["Pick one family from a list"]
    I --> J["Table 4: Full history with just<br>that one family, in date order"]
```

---

## Why a changed phone number is safe

```mermaid
flowchart LR
    A["Family's permanent ID<br>e.g. ID = 2"] --> B["All history is<br>linked to this ID"]
    C["Phone number"] -->|"only used to find the ID"| A
    C -->|"can be changed anytime"| C2["New phone number"]
    C2 --> A
```

**In plain words:** The ID never changes. The phone number is just a way to look up the ID — like a nickname. Changing the nickname doesn't erase or move any history, because the history is stored against the ID, not the phone number.

---

## Files in this project

| File | Purpose |
|---|---|
| `backend.sql` | SQL Server schema and stored procedures (source-of-truth setup script) |
| `db.py` | Shared database helper — the only file that talks to SQL Server |
| `app.py` | Admin / Reception Streamlit app — records contributions, can add new families |
| `user_app.py` | Family Portal Streamlit app — read-only, shows only the logged-in family's own history |
