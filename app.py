import streamlit as st
import os
import pandas as pd
from sqlalchemy import create_engine, text
from main import ask_db
from auth import init_db, login_user, register_user
import plotly.express as px

# ================= CONFIG =================
st.set_page_config(page_title="AI SQL SaaS", layout="wide")
init_db()

# ================= SESSION =================
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

if "engine" not in st.session_state:
    st.session_state.engine = None

if "df" not in st.session_state:
    st.session_state.df = None

if "sql" not in st.session_state:
    st.session_state.sql = None

if "error" not in st.session_state:
    st.session_state.error = None

# ================= LOGIN =================
if not st.session_state.logged_in:
    st.title("🔐 Login")

    tab1, tab2 = st.tabs(["Login", "Register"])

    with tab1:
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")

        if st.button("Login"):
            success, result = login_user(username, password)

            if success:
                st.session_state.logged_in = True
                st.success("Login successful")
                st.rerun()
            else:
                st.error(result)

    with tab2:
        new_user = st.text_input("New Username")
        new_pass = st.text_input("New Password", type="password")

        if st.button("Create Account"):
            success, msg = register_user(new_user, new_pass)

            if success:
                st.success(msg)
            else:
                st.error(msg)

    st.stop()

# ================= SIDEBAR =================
st.sidebar.title("⚙️ Database Connection")

db_type = st.sidebar.selectbox("DB Type", ["MySQL", "SQLite"])

if db_type == "MySQL":
    host = st.sidebar.text_input("Host")
    user = st.sidebar.text_input("User")
    password = st.sidebar.text_input("Password", type="password")
    db = st.sidebar.text_input("Database Name")
else:
    sqlite_path = st.sidebar.text_input("SQLite file path")

def connect_db():
    try:
        if db_type == "MySQL":
            engine = create_engine(f"mysql+pymysql://{user}:{password}@{host}/{db}")
        else:
            engine = create_engine(f"sqlite:///{sqlite_path}")

        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))

        st.session_state.engine = engine
        st.success("✅ Connected successfully")

    except Exception as e:
        st.error(f"❌ Connection failed: {str(e)}")

if st.sidebar.button("Connect"):
    connect_db()

# ================= MAIN =================
st.title("🤖 AI SQL Dashboard")

query = st.text_input("Ask your database")

if st.button("Run Query"):

    if not st.session_state.engine:
        st.warning("Connect database first")
        st.stop()

    if not query.strip():
        st.warning("Enter a query")
        st.stop()

    with st.spinner("Processing..."):
        df, sql, error = ask_db(query, st.session_state.engine)

    st.session_state.df = df
    st.session_state.sql = sql
    st.session_state.error = error

# ================= DISPLAY =================
if st.session_state.sql:

    with st.expander("Generated SQL"):
        st.code(st.session_state.sql)

    if st.session_state.error:
        st.error(st.session_state.error)
        st.stop()

    df = st.session_state.df

    if df is None or df.empty:
        st.warning("No data")
        st.stop()

    st.success("Done")

    chart_type = st.selectbox("View", ["Table", "Bar", "Line", "Pie"])

    if chart_type == "Table":
        st.dataframe(df)

    elif chart_type == "Bar":
        num = df.select_dtypes(include=['int64','float64']).columns
        txt = df.select_dtypes(include=['object']).columns

        if len(num) and len(txt):
            st.plotly_chart(px.bar(df, x=txt[0], y=num[0]))

    elif chart_type == "Line":
        num = df.select_dtypes(include=['int64','float64']).columns
        if len(num):
            st.plotly_chart(px.line(df, y=num[0]))

    elif chart_type == "Pie":
        num = df.select_dtypes(include=['int64','float64']).columns
        txt = df.select_dtypes(include=['object']).columns

        if len(num) and len(txt):
            st.plotly_chart(px.pie(df, names=txt[0], values=num[0]))