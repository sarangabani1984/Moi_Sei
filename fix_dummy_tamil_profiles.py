# -*- coding: utf-8 -*-
"""Restore Tamil text for the local 10-record dummy family dataset."""

import pyodbc

PROFILES = [
    ("9000000003", "சரவணன்", "லட்சுமி", "விவசாயி", "உசிலம்பட்டி", "கருப்பண்ணசாமி"),
    ("9000000004", "முருகன்", "கலையரசி", "கட்டிட ஒப்பந்ததாரர்", "மதுரை", "மீனாட்சி அம்மன்"),
    ("9000000006", "ராஜ்குமார்", "சுமதி", "மின்சார தொழிலாளர்", "தேனி", "முருகன்"),
    ("9000000008", "பாபு சத்யா", "ரம்யா", "கடை உரிமையாளர்", "உசிலம்பட்டி", "அய்யனார்"),
    ("9000000010", "கணேசன்", "சத்யா", "பொறியாளர்", "கல்லாத்து", "நல்ல குரும்பன்"),
]

connection = pyodbc.connect(
    r"DRIVER={ODBC Driver 18 for SQL Server};"
    r"SERVER=JNPR-WIN-MPRZ09\SQLEXPRESS;"
    r"DATABASE=MoiSei;"
    r"Trusted_Connection=yes;"
    r"TrustServerCertificate=yes;"
)
cursor = connection.cursor()

for phone, husband, wife, job, place, deity in PROFILES:
    cursor.execute(
        """
        UPDATE dbo.users
        SET husband_name = ?, wife_name = ?, husband_job = ?, place = ?, family_deity = ?
        WHERE phone_number = ?
        """,
        husband,
        wife,
        job,
        place,
        deity,
        phone,
    )

connection.commit()
cursor.execute(
    "SELECT id, husband_name, wife_name, place, search_alias FROM dbo.users ORDER BY id"
)
for row in cursor.fetchall():
    print(row)

connection.close()
print("Tamil dummy profiles restored successfully.")
