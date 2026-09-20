# Moi Sei Learning Roadmap

A beginner-friendly plan for understanding the Moi Sei project step by step.

## How to Use This Roadmap

- Follow the steps in order.
- Do not try to understand every file at once.
- For each step, read a small section, run the app, and change one small thing.
- Keep a notebook with three questions for every function:
  - What information comes in?
  - What does the function do?
  - What comes out?

## Preferred Teaching Method

- Teach one small code section at a time instead of explaining the whole project at once.
- Explain every important line in simple beginner-friendly language.
- Use a layman analogy before introducing technical terms.
  - Example: a variable is a labeled box; a function is a reusable machine; a dictionary is a form with named fields.
- Show the real code location and explain what happens before and after that code.
- Always describe the flow as:
  - What information comes in?
  - What decision or action happens?
  - What information goes out?
- Connect each code concept to a real Moi Sei example such as a family, event, contribution, login, or receipt.
- Use small tables, short flow diagrams, and simple examples when they clarify the idea.
- Separate local SQL Server behavior from cloud Supabase behavior whenever both exist.
- Explain errors by identifying:
  - What the error means in plain language.
  - Which code path caused it.
  - The smallest safe fix.
  - How to test that the fix worked.
- After each lesson, give one small practice exercise that can be run locally.
- Do not move to the next section until the current flow is understandable.
- Prefer questions such as “What comes in?”, “What changes?”, and “What comes out?” to help build independent debugging skills.

## Phase 1: Python Foundations

- Learn variables.
  - Example: `name = "Sarangabani"` stores a value in a labeled box.
  - Practice with names, phone numbers, amounts, and dates.

- Learn strings.
  - Strings are text inside quotes.
  - Practice `.strip()`, `.lower()`, and f-strings such as `f"Hello {name}"`.

- Learn numbers and type conversion.
  - Understand `int`, `float`, and `str`.
  - Practice converting an amount typed into a form into a number.

- Learn lists and dictionaries.
  - A list is like a row of items.
  - A dictionary is like a form with named fields:
    `{"name": "Sarangabani", "phone": "7411346811"}`.

- Learn `if`, `elif`, and `else`.
  - These are decision points: if the phone exists, show the family; otherwise, ask to register it.

- Learn loops.
  - A loop repeats an action for every row, family, or contribution.

- Learn functions.
  - A function is a reusable machine: give it inputs, it performs a task, and it returns a result.
  - Start with small functions in `app.py`, such as `format_family()` and `format_event()`.

- Learn exceptions.
  - `try` means attempt an operation.
  - `except` means show a useful message if the operation fails.
  - Study the database connection error handling in `app.py` and `db.py`.

## Phase 2: Understand Streamlit

- Learn that Streamlit runs a Python script from top to bottom whenever a widget changes.

- Study `st.title`, `st.caption`, `st.write`, and `st.subheader`.
  - These display information on the page.

- Study `st.text_input`, `st.number_input`, `st.date_input`, and `st.button`.
  - These collect information from the user.

- Study `st.session_state`.
  - It is like a small backpack that keeps values between Streamlit reruns.
  - Moi Sei uses it to remember the selected contributor, receiver, and event.

- Study forms and tabs.
  - Forms group inputs together.
  - Tabs separate the family portal into upcoming events, hosted events, and history.

- Run the local apps:
  - Admin: `python -m streamlit run app.py --server.port 8509`
  - Family portal: `python -m streamlit run user_app.py --server.port 8508`

## Phase 3: Learn the Project Files

- Start with `app.py`.
  - This is the staff/admin user interface.
  - Trace the screen from top to bottom.
  - Understand admin login, phone lookup, event lookup, verification, contribution save, WhatsApp notification, and printable receipt.

- Then study `user_app.py`.
  - This is the family portal.
  - Understand family login, password setup, contribution history, received history, partner history, event scheduling, event updates, and upcoming events.

- Then study `db.py`.
  - This is the database access layer.
  - The UI should ask `db.py` for data instead of writing SQL everywhere.
  - Learn `get_connection()` first.
  - Then learn lookup functions such as `get_family_by_phone()` and `get_event()`.
  - Then learn write functions such as `create_family()`, `process_contribution()`, and `create_event_by_host()`.
  - Finally learn `get_upcoming_partner_events()`.

- Then study `notifications.py`.
  - This sends WhatsApp messages through Green API.
  - Follow the path: format phone number, build message, send HTTP request, read response, show success or error.

- Then study `.streamlit/secrets.toml`.
  - Secrets are configuration values such as database URLs, admin password, and Green API credentials.
  - Never commit this file to GitHub.
  - Study `.streamlit/secrets.toml.example` for the safe template.

## Phase 4: Understand the Database Design

- Read `backend.sql` for local SQL Server.
- Read `backend_pg.sql` for cloud PostgreSQL.
- Understand the four main tables:
  - `users`: one row per family.
  - `event`: one row per function or occasion.
  - `transactions`: one parent receipt per contribution.
  - `journal_entries`: two accounting rows per contribution.

- Understand primary keys.
  - A primary key is the permanent ID card for a row.
  - `users.id` identifies a family permanently, even if the phone number changes.

- Understand foreign keys.
  - A foreign key connects a row to another table.
  - `journal_entries.user_id` points to `users.id`.

- Understand constraints.
  - `NOT NULL`: a value is required.
  - `UNIQUE`: duplicate values are rejected.
  - `CHECK`: a condition must be true.
  - `DEFAULT`: SQL fills a value automatically.

- Understand the event host rule.
  - The first receiver for an event becomes the event host.
  - Later contributions for the same event must use the same receiver.

## Phase 5: Trace One Complete Contribution

- Start in `app.py` when staff clicks `Check Details`.
- `get_family_by_phone()` searches for the contributor and receiver.
- `get_event()` checks that the event exists.
- `st.session_state` remembers the verified details.
- Staff clicks `Submit Contribution`.
- `process_contribution()` in `db.py` calls the database procedure.
- `sp_ProcessContribution` validates:
  - contributor and receiver are different;
  - amount is positive;
  - both families are active;
  - event exists and is active;
  - contribution date is not before event date;
  - event has only one receiver.
- SQL creates one `transactions` row.
- SQL creates two `journal_entries` rows:
  - `CONTRIBUTED` for the giver;
  - `RECEIVED` for the receiver.
- `notifications.py` sends the WhatsApp receipt.
- `app.py` displays success and the print receipt.

## Phase 6: Understand One Example

Suppose Family 6 gives Rs. 5,000 to Family 2 for Event 101.

- `users` contains Family 6 and Family 2.
- `event` contains Event 101.
- `transactions` gets one new parent row.
- `journal_entries` gets:
  - Family 6, Event 101, `CONTRIBUTED`, Rs. 5,000.
  - Family 2, Event 101, `RECEIVED`, Rs. 5,000.
- Family 6 sees the payment under `My Contributions`.
- Family 2 sees it under `My Received Contributions`.

## Phase 7: Understand Reciprocity Reports

- Read `sp_GetMyContributions`.
  - It answers: “What did I give, and to whom?”

- Read `sp_GetMyReceivedContributions`.
  - It answers: “What did I receive, and from whom?”

- Read `sp_GetMyPartnerHistory`.
  - It groups all exchanges with one family.
  - It calculates total given, total received, and net difference.

- Read `sp_GetMyPartnerTransactions`.
  - It displays the chronological back-and-forth timeline.
  - The running net increases when you pay and decreases when you receive.

- Read `get_upcoming_partner_events()` in `db.py`.
  - It finds future events hosted by families you have exchanged contributions with.
  - It calculates what that host previously contributed to you and what you contributed to the host.

## Phase 8: Security Understanding

- Admin password protects the staff page.
- Family passwords protect the family portal.
- Family passwords are stored as hashes, not plain text.
- The family portal must only query the logged-in family’s records.
- A family may edit only its own hosted events.
- Secrets must remain outside GitHub.
- Do not use real family information in test data.

## Phase 9: Practice Exercises

- Change the page title and observe the result.
- Add a temporary `st.write()` to display a variable.
- Change the test amount and observe the database result.
- Add a new test family locally.
- Try a duplicate phone number and read the error.
- Try a negative amount and observe the validation.
- Try recording a contribution for a future event and observe the date rule.
- Schedule an upcoming event as a host.
- Sign in as a partner and find that upcoming event.
- Update the event date and confirm the partner sees the new date.
- Read the SQL query that produces each screen and explain each `JOIN` in plain language.

## Phase 10: Cloud Understanding

- Local mode uses SQL Server Express.
- Cloud mode uses Supabase PostgreSQL.
- `db.py` chooses PostgreSQL when `MOI_SEI_POSTGRES_URL` exists.
- Streamlit Cloud runs `app.py` and `user_app.py` as separate apps.
- Each cloud app needs its own Streamlit Secrets configuration.
- `backend_pg.sql` creates the cloud database structure.
- `cloud_auth_migration.sql` adds password support without deleting cloud data.
- Never rerun a destructive reset script on production data.

## Recommended Learning Habit

- Study one function per day.
- Draw the input and output on paper.
- Run one small test after reading it.
- Explain the function aloud in your own words.
- Only then move to the next function.
