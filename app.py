import streamlit as st
import pandas as pd
from sqlalchemy import create_engine, text, inspect
from main import ask_db
from auth import init_db, login_user, register_user
import plotly.express as px

st.set_page_config(page_title="AI SQL SaaS", layout="wide")
init_db()

# SESSION
st.session_state.setdefault("logged_in", False)
st.session_state.setdefault("engine", None)

# AUTO SQLITE (🔥 NO DB REQUIRED)
if st.session_state.engine is None:
    st.session_state.engine = create_engine("sqlite:///auto.db")

# LOGIN
if not st.session_state.logged_in:
    st.title("Login")

    t1, t2 = st.tabs(["Login", "Register"])

    with t1:
        u = st.text_input("User")
        p = st.text_input("Pass", type="password")

        if st.button("Login"):
            ok, msg = login_user(u, p)
            if ok:
                st.session_state.logged_in = True
                st.rerun()
            else:
                st.error(msg)

    with t2:
        u = st.text_input("New User")
        p = st.text_input("New Pass", type="password")

        if st.button("Create"):
            ok, msg = register_user(u, p)
            st.success(msg) if ok else st.error(msg)

    st.stop()

# SIDEBAR DB
st.sidebar.title("Database")

db_type = st.sidebar.selectbox("DB", ["Auto SQLite", "MySQL"])

if db_type == "MySQL":
    host = st.sidebar.text_input("Host")
    port = st.sidebar.text_input("Port", "3306")
    user = st.sidebar.text_input("User")
    password = st.sidebar.text_input("Password", type="password")
    db = st.sidebar.text_input("DB")

    if st.sidebar.button("Connect MySQL"):
        try:
            engine = create_engine(
                f"mysql+pymysql://{user}:{password}@{host}:{port}/{db}"
            )
            engine.connect()
            st.session_state.engine = engine
            st.success("Connected")
        except Exception as e:
            st.error(e)

# MAIN
st.title("AI SQL Dashboard")

# MULTI CSV UPLOAD
st.subheader("Upload CSV")

files = st.file_uploader(
    "Upload CSV files",
    type=["csv"],
    accept_multiple_files=True
)

if files:
    for f in files:
        df = pd.read_csv(f)
        name = f.name.replace(".csv", "").lower()

        df.to_sql(name, st.session_state.engine, index=False, if_exists="replace")
        st.success(f"{name} uploaded")

# SHOW TABLES
insp = inspect(st.session_state.engine)
tables = insp.get_table_names()

if tables:
    table = st.selectbox("Preview", tables)

    if table:
        df = pd.read_sql(f"SELECT * FROM {table} LIMIT 5", st.session_state.engine)
        st.dataframe(df)

# QUERY
q = st.text_input("Ask your data")

if st.button("Run"):
    df, sql, err = ask_db(q, st.session_state.engine)

    st.code(sql or "No SQL")

    if err:
        st.error(err)
    else:
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