import sqlite3
import hashlib

DB_FILE = "users.db"

def init_db():
    conn = sqlite3.connect(DB_FILE)
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


def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()


# ✅ FIXED REGISTER (returns tuple)
def register_user(username, password):
    try:
        conn = sqlite3.connect(DB_FILE)
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


# ✅ FIXED LOGIN (returns tuple)
def login_user(username, password):
    conn = sqlite3.connect(DB_FILE)
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