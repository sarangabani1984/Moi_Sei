from db import get_connection

conn = get_connection()
cursor = conn.cursor()

# Find the user
cursor.execute("SELECT id, husband_name, phone_number FROM dbo.users WHERE phone_number = '7411346818'")
user = cursor.fetchone()

if user:
    user_id, name, phone = user
    print(f"Found user: ID={user_id}, Name={name}, Phone={phone}")
    
    # Delete the user and all related records
    try:
        # Get related transaction IDs to delete cascading entries
        cursor.execute("SELECT DISTINCT transaction_id FROM dbo.journal_entries WHERE user_id = ?", (user_id,))
        tx_ids = [row[0] for row in cursor.fetchall()]
        
        # First delete related journal entries
        cursor.execute("DELETE FROM dbo.journal_entries WHERE user_id = ?", (user_id,))
        print(f"  ✓ Deleted journal entries")
        
        # Delete related transactions
        if tx_ids:
            placeholders = ','.join(['?' for _ in tx_ids])
            cursor.execute(f"DELETE FROM dbo.transactions WHERE transaction_id IN ({placeholders})", tx_ids)
            print(f"  ✓ Deleted transactions")
        
        # Delete events hosted by this user
        cursor.execute("DELETE FROM dbo.event WHERE host_user_id = ?", (user_id,))
        print(f"  ✓ Deleted events")
        
        # Finally delete the user
        cursor.execute("DELETE FROM dbo.users WHERE id = ?", (user_id,))
        conn.commit()
        print(f"✅ User DELETED: {name} ({phone})")
    except Exception as e:
        conn.rollback()
        print(f"❌ Error: {e}")
else:
    print("❌ User not found with phone 7411346818")

cursor.close()
conn.close()
