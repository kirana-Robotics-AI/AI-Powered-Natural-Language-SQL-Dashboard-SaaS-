import streamlit as st
import pandas as pd
from sqlalchemy import create_engine, text, inspect
from main import ask_db
from auth import init_db, login_user, register_user
import plotly.express as px

st.set_page_config(page_title="AI SQL SaaS", layout="wide")
init_db()

# ================= SESSION =================
st.session_state.setdefault("logged_in", False)
st.session_state.setdefault("engine", None)

# AUTO DB
if st.session_state.engine is None:
    st.session_state.engine = create_engine("sqlite:///auto.db")

# ================= LOGIN =================
if not st.session_state.logged_in:
    st.title("Login")

    tab1, tab2 = st.tabs(["Login", "Register"])

    with tab1:
        u = st.text_input("Username")
        p = st.text_input("Password", type="password")

        if st.button("Login"):
            ok, msg = login_user(u, p)
            if ok:
                st.session_state.logged_in = True
                st.rerun()
            else:
                st.error(msg)

    with tab2:
        u = st.text_input("New Username")
        p = st.text_input("New Password", type="password")

        if st.button("Create Account"):
            ok, msg = register_user(u, p)
            st.success(msg) if ok else st.error(msg)

    st.stop()

# ================= SIDEBAR =================
st.sidebar.title("Database")

db_type = st.sidebar.selectbox("DB Type", ["Auto SQLite", "MySQL"])

if db_type == "MySQL":
    host = st.sidebar.text_input("Host")
    port = st.sidebar.text_input("Port", "3306")
    user = st.sidebar.text_input("User")
    password = st.sidebar.text_input("Password", type="password")
    db = st.sidebar.text_input("Database")

    if st.sidebar.button("Connect"):
        try:
            engine = create_engine(
                f"mysql+pymysql://{user}:{password}@{host}:{port}/{db}"
            )
            engine.connect()
            st.session_state.engine = engine
            st.success("Connected to MySQL")
        except Exception as e:
            st.error(e)

# ================= SAFE CSV LOADER =================
def load_csv(file):
    try:
        file.seek(0)

        # Try normal CSV
        df = pd.read_csv(file)

        if df.shape[1] == 0:
            raise ValueError("Empty columns")

        return df

    except:
        try:
            file.seek(0)
            # Try semicolon delimiter
            df = pd.read_csv(file, delimiter=";")

            if df.shape[1] == 0:
                raise ValueError("Still empty")

            return df

        except:
            try:
                file.seek(0)
                # Try latin encoding
                return pd.read_csv(file, encoding="latin1")

            except Exception as e:
                raise Exception(f"Unreadable file: {str(e)}")

# ================= MAIN =================
st.title("AI SQL Dashboard")

# CSV Upload
files = st.file_uploader("Upload CSV", type=["csv"], accept_multiple_files=True)

if files:
    for f in files:
        try:
            df = load_csv(f)
            table = f.name.replace(".csv", "").lower()

            df.to_sql(table, st.session_state.engine, index=False, if_exists="replace")

            st.success(f"{table} uploaded")

        except Exception as e:
            st.error(f"{f.name} failed: {e}")

# Preview
inspector = inspect(st.session_state.engine)
tables = inspector.get_table_names()

if tables:
    table = st.selectbox("Preview Table", tables)

    if table:
        df = pd.read_sql(f"SELECT * FROM {table} LIMIT 5", st.session_state.engine)
        st.dataframe(df)

# Query
query = st.text_input("Ask your database")

if st.button("Run"):
    df, sql, err = ask_db(query, st.session_state.engine)

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