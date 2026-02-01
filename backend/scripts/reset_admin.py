import os
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), "../"))
from app.services.auth.passwords import hash_password
from app.db.pg import get_conn
from app.config.settings import settings

def reset_admin():
    email = settings.bootstrap_admin_email
    password = settings.bootstrap_admin_password.get_secret_value()
    print(f"Resetting password for {email} to {password}...")
    
    conn = get_conn()
    with conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE users SET password_hash=%s WHERE email=%s", (hash_password(password), email))
            if cur.rowcount == 0:
                print("User not found, creating...")
                cur.execute("INSERT INTO users(email, password_hash, role) VALUES (%s,%s,'admin')", (email, hash_password(password)))
            else:
                print("Password updated.")
    conn.close()

if __name__ == "__main__":
    reset_admin()