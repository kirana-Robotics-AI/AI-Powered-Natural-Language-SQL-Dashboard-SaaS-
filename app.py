import streamlit as st
import pandas as pd
from sqlalchemy import create_engine, text, inspect
from main import ask_db
from auth import init_db, login_user, register_user
import plotly.express as px
import os

st.set_page_config(page_title="AI SQL SaaS", layout="wide")
init_db()

# SESSION
st.session_state.setdefault("logged_in", False)
st.session_state.setdefault("engine", None)
st.session_state.setdefault("df", None)
st.session_state.setdefault("sql", None)
st.session_state.setdefault("error", None)

# LOGIN
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

        if st.button("Create"):
            ok, msg = register_user(u, p)
            st.success(msg) if ok else st.error(msg)

    st.stop()

# SIDEBAR
st.sidebar.title("Database")

db_type = st.sidebar.selectbox("DB", ["MySQL", "SQLite"])

if db_type == "MySQL":
    host = st.sidebar.text_input("Host")
    port = st.sidebar.text_input("Port", "3306")
    user = st.sidebar.text_input("User")
    password = st.sidebar.text_input("Password", type="password")
    db = st.sidebar.text_input("Database")
else:
    path = st.sidebar.text_input("SQLite Path", "users.db")

def connect():
    try:
        if db_type == "MySQL":
            engine = create_engine(
                f"mysql+pymysql://{user}:{password}@{host}:{port}/{db}"
            )
        else:
            engine = create_engine(f"sqlite:///{path}")

        with engine.connect() as c:
            c.execute(text("SELECT 1"))

        st.session_state.engine = engine
        st.success("Connected")

    except Exception as e:
        st.error(f"Connection failed: {e}")

if st.sidebar.button("Connect"):
    connect()

# MAIN
st.title("🤖 AI SQL Dashboard")

# CSV UPLOAD
st.subheader("📂 Upload CSV")

file = st.file_uploader("Upload CSV", type=["csv"])

if file and st.session_state.engine:
    df = pd.read_csv(file)
    df.to_sql("user_data", st.session_state.engine, index=False, if_exists="replace")
    st.success("Data uploaded")
    st.dataframe(df.head())

# SHOW TABLES
if st.session_state.engine:
    insp = inspect(st.session_state.engine)
    tables = insp.get_table_names()

    if tables:
        table = st.selectbox("Preview Table", tables)
        if table:
            df_preview = pd.read_sql(f"SELECT * FROM {table} LIMIT 5", st.session_state.engine)
            st.dataframe(df_preview)

# QUERY
q = st.text_input("Ask your data")

if st.button("Run"):
    if not st.session_state.engine:
        st.warning("Connect DB")
        st.stop()

    df, sql, err = ask_db(q, st.session_state.engine)

    st.session_state.df = df
    st.session_state.sql = sql
    st.session_state.error = err

# DISPLAY
if st.session_state.sql:
    st.code(st.session_state.sql, language="sql")

    if st.session_state.error:
        st.error(st.session_state.error)
    else:
        df = st.session_state.df
        st.dataframe(df)

        num = df.select_dtypes(include=["int64", "float64"]).columns
        txt = df.select_dtypes(include=["object"]).columns

        chart = st.selectbox("Chart", ["Table", "Bar", "Line", "Pie"])

        if chart == "Bar" and len(num) and len(txt):
            st.plotly_chart(px.bar(df, x=txt[0], y=num[0]))

        elif chart == "Line" and len(num):
            st.plotly_chart(px.line(df, y=num[0]))

        elif chart == "Pie" and len(num) and len(txt):
            st.plotly_chart(px.pie(df, names=txt[0], values=num[0]))