import streamlit as st
import os
import traceback
import pandas as pd
from sqlalchemy import create_engine, text
from main import ask_db
from auth import init_db, login_user, register_user
import plotly.express as px

# Required for Railway
os.environ["STREAMLIT_SERVER_HEADLESS"] = "true"

# ================= CONFIG =================
st.set_page_config(page_title="AI SQL SaaS", layout="wide")

# SAFE DB INIT
if "db_init" not in st.session_state:
    try:
        init_db()
        st.session_state.db_init = True
    except Exception as e:
        st.error(f"DB Init Error: {e}")

# ================= SESSION =================
st.session_state.setdefault("logged_in", False)
st.session_state.setdefault("engine", None)
st.session_state.setdefault("df", None)
st.session_state.setdefault("sql", None)
st.session_state.setdefault("error", None)

try:

    # ================= LOGIN =================
    if not st.session_state.logged_in:
        st.title("🔐 Login")

        tab1, tab2 = st.tabs(["Login", "Register"])

        with tab1:
            u = st.text_input("Username")
            p = st.text_input("Password", type="password")

            if st.button("Login"):
                ok, res = login_user(u, p)
                if ok:
                    st.session_state.logged_in = True
                    st.rerun()
                else:
                    st.error(res)

        with tab2:
            u = st.text_input("New Username")
            p = st.text_input("New Password", type="password")

            if st.button("Register"):
                ok, msg = register_user(u, p)
                if ok:
                    st.success(msg)
                else:
                    st.error(msg)

        st.stop()

    # ================= DB =================
    st.sidebar.title("Database")

    db_type = st.sidebar.selectbox("DB", ["SQLite", "MySQL"])

    if db_type == "SQLite":
        path = st.sidebar.text_input("Path", "test.db")
    else:
        host = st.sidebar.text_input("Host")
        user = st.sidebar.text_input("User")
        pw = st.sidebar.text_input("Password", type="password")
        db = st.sidebar.text_input("DB")

    if st.sidebar.button("Connect"):
        try:
            if db_type == "SQLite":
                engine = create_engine(f"sqlite:///{path}")
            else:
                engine = create_engine(f"mysql+pymysql://{user}:{pw}@{host}/{db}")

            with engine.connect() as c:
                c.execute(text("SELECT 1"))

            st.session_state.engine = engine
            st.success("Connected")

        except Exception as e:
            st.error(str(e))

    # ================= MAIN =================
    st.title("AI SQL Dashboard")

    q = st.text_input("Ask your database")

    if st.button("Run"):
        if not st.session_state.engine:
            st.warning("Connect DB")
            st.stop()

        df, sql, err = ask_db(q, st.session_state.engine)

        st.session_state.df = df
        st.session_state.sql = sql
        st.session_state.error = err

    if st.session_state.sql:
        st.code(st.session_state.sql)

        if st.session_state.error:
            st.error(st.session_state.error)
        else:
            df = st.session_state.df
            if df is not None and not df.empty:
                st.dataframe(df)

except Exception:
    st.error("App crashed")
    st.code(traceback.format_exc())