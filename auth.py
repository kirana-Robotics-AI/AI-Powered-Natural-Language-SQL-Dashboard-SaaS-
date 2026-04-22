import sqlite3
import hashlib
import os

# ✅ Use absolute safe path
DB_FILE = os.path.join(os.getcwd(), "users.db")


# =========================
# SAFE CONNECTION
# =========================
def get_connection():
    return sqlite3.connect(DB_FILE, check_same_thread=False)


# =========================
# INIT DB (SAFE)
# =========================
def init_db():
    try:
        conn = get_connection()
        c = conn.cursor()

        c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE,
            password TEXT
        )
        """)

        conn.commit()
        conn.close()

    except Exception as e:
        print(f"DB INIT ERROR: {e}")


# =========================
# HASH PASSWORD
# =========================
def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()


# =========================
# REGISTER USER
# =========================
def register_user(username, password):
    try:
        conn = get_connection()
        c = conn.cursor()

        c.execute(
            "INSERT INTO users (username, password) VALUES (?, ?)",
            (username, hash_password(password))
        )

        conn.commit()
        conn.close()

        return True, "Account created successfully"

    except sqlite3.IntegrityError:
        return False, "Username already exists"

    except Exception as e:
        return False, str(e)


# =========================
# LOGIN USER
# =========================
def login_user(username, password):
    try:
        conn = get_connection()
        c = conn.cursor()

        c.execute(
            "SELECT * FROM users WHERE username=? AND password=?",
            (username, hash_password(password))
        )

        user = c.fetchone()
        conn.close()

        if user:
            return True, user
        else:
            return False, "Invalid username or password"

    except Exception as e:
        return False, str(e)