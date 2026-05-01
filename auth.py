import sqlite3
import hashlib
import os

DB_FILE = os.path.join(os.getcwd(), "users.db")

def get_conn():
    return sqlite3.connect(DB_FILE, check_same_thread=False)

def init_db():
    conn = get_conn()
    conn.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE,
        password TEXT
    )
    """)
    conn.commit()
    conn.close()

def hash_pass(p):
    return hashlib.sha256(p.encode()).hexdigest()

def register_user(u, p):
    try:
        conn = get_conn()
        conn.execute("INSERT INTO users VALUES (NULL, ?, ?)", (u, hash_pass(p)))
        conn.commit()
        return True, "Account created"
    except:
        return False, "Username exists"

def login_user(u, p):
    conn = get_conn()
    user = conn.execute(
        "SELECT * FROM users WHERE username=? AND password=?",
        (u, hash_pass(p))
    ).fetchone()

    return (True, user) if user else (False, "Invalid credentials")