import streamlit as st
import pandas as pd
from sqlalchemy import create_engine, text, inspect
from main import ask_db
from auth import init_db, login_user, register_user
import plotly.express as px
import os

# ================= CONFIG =================
st.set_page_config(page_title="AI SQL SaaS", layout="wide")
init_db()

# ================= SESSION =================
st.session_state.setdefault("logged_in", False)
st.session_state.setdefault("engine", None)
st.session_state.setdefault("db_type", "SQLite")
st.session_state.setdefault("uploaded_files", set())
st.session_state.setdefault("uploader_key", 0)

st.session_state.setdefault("df", None)
st.session_state.setdefault("sql", None)
st.session_state.setdefault("error", None)
st.session_state.setdefault("chart_type", "Table")

# ================= LOGIN =================
if not st.session_state.logged_in:
    st.title("🔐 Login")

    tab1, tab2 = st.tabs(["Login", "Register"])

    with tab1:
        u = st.text_input("Username")
        p = st.text_input("Password", type="password")

        if st.button("Login"):
            ok, msg = login_user(u, p)
            if ok:
                st.session_state.logged_in = True
                st.session_state.username = u
                st.rerun()
            else:
                st.error(msg)

    with tab2:
        u = st.text_input("New Username")
        p = st.text_input("New Password", type="password")

        if st.button("Create Account"):
            ok, msg = register_user(u, p)
            if ok:
                st.success(msg)
            else:
                st.error(msg)

    st.stop()

# ================= SIDEBAR =================
st.sidebar.title("⚙️ Database Settings")

db_type = st.sidebar.selectbox("DB Type", ["SQLite (Auto)", "MySQL"])

# ================= SQLITE (PER USER) =================
if db_type == "SQLite (Auto)":
    st.session_state.db_type = "sqlite"

    if st.session_state.engine is None:
        db_name = f"user_{st.session_state.username}.db"
        st.session_state.db_path = db_name
        st.session_state.engine = create_engine(f"sqlite:///{db_name}")

    st.sidebar.success("Using private SQLite DB")

# ================= MYSQL =================
else:
    st.session_state.db_type = "mysql"

    host = st.sidebar.text_input("Host")
    port = st.sidebar.text_input("Port", "3306")
    user = st.sidebar.text_input("User")
    password = st.sidebar.text_input("Password", type="password")
    db = st.sidebar.text_input("Database")

    if st.sidebar.button("Connect MySQL"):
        try:
            engine = create_engine(
                f"mysql+pymysql://{user}:{password}@{host}:{port}/{db}",
                pool_pre_ping=True
            )

            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))

            st.session_state.engine = engine
            st.success("✅ Connected to MySQL")

        except Exception as e:
            st.error(f"❌ {e}")

# ================= LOGOUT =================
if st.sidebar.button("🚪 Logout"):

    # 🔥 Only delete SQLite DB
    if st.session_state.get("db_type") == "sqlite":
        db_path = st.session_state.get("db_path")

        if db_path and os.path.exists(db_path):
            os.remove(db_path)

    st.session_state.clear()
    st.rerun()

# ================= CSV LOADER =================
def load_csv(file):
    try:
        file.seek(0)
        df = pd.read_csv(file)
        if df.shape[1] == 0:
            raise ValueError("Empty")
        return df
    except:
        try:
            file.seek(0)
            return pd.read_csv(file, delimiter=";")
        except:
            file.seek(0)
            return pd.read_csv(file, encoding="latin1")

# ================= MAIN =================
st.title("🤖 AI SQL Dashboard")

# ================= CLEAR =================
if st.button("🧹 Clear Uploaded Files"):
    st.session_state.uploaded_files.clear()
    st.session_state.uploader_key += 1
    st.rerun()

# ================= UPLOADER =================
files = st.file_uploader(
    "📂 Upload CSV",
    type=["csv"],
    accept_multiple_files=True,
    key=f"uploader_{st.session_state.uploader_key}"
)

if files:
    for f in files:
        if f.name in st.session_state.uploaded_files:
            continue

        try:
            df = load_csv(f)

            table = f.name.replace(".csv", "").lower()

            df.to_sql(table, st.session_state.engine, index=False, if_exists="replace")

            st.session_state.uploaded_files.add(f.name)
            st.success(f"{table} uploaded")

        except Exception as e:
            st.error(f"{f.name} failed: {e}")

# ================= TABLE PREVIEW =================
inspector = inspect(st.session_state.engine)
tables = inspector.get_table_names()

if tables:
    table = st.selectbox("Preview Table", tables)

    if table:
        df_preview = pd.read_sql(
            f"SELECT * FROM {table} LIMIT 5",
            st.session_state.engine
        )
        st.dataframe(df_preview)

# ================= QUERY =================
query = st.text_input("Ask your database")

if st.button("Run Query"):

    df, sql, error = ask_db(query, st.session_state.engine)

    st.session_state.df = df
    st.session_state.sql = sql
    st.session_state.error = error

# ================= DISPLAY =================
if st.session_state.sql:

    st.code(st.session_state.sql)

    if st.session_state.error:
        st.error(st.session_state.error)
    else:
        df = st.session_state.df

        if df is not None:
            st.dataframe(df)

            num = df.select_dtypes(include=['int64','float64']).columns
            txt = df.select_dtypes(include=['object']).columns

            chart = st.selectbox(
                "Chart",
                ["Table","Bar","Line","Pie"],
                key="chart_type"
            )

            if chart == "Bar" and len(num) and len(txt):
                st.plotly_chart(px.bar(df, x=txt[0], y=num[0]))

            elif chart == "Line" and len(num):
                st.plotly_chart(px.line(df, y=num[0]))

            elif chart == "Pie" and len(num) and len(txt):
                st.plotly_chart(px.pie(df, names=txt[0], values=num[0]))