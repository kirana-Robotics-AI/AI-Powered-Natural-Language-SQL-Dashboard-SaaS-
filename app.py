import streamlit as st
import pandas as pd
from sqlalchemy import create_engine, text, inspect
from main import ask_db
from auth import init_db, login_user, register_user
import plotly.express as px

# ================= CONFIG =================
st.set_page_config(page_title="AI SQL SaaS", layout="wide")
init_db()

# ================= SESSION =================
st.session_state.setdefault("logged_in", False)
st.session_state.setdefault("engine", None)
st.session_state.setdefault("uploaded_files", set())

# 🔥 Fixes for rerun + charts
st.session_state.setdefault("df", None)
st.session_state.setdefault("sql", None)
st.session_state.setdefault("error", None)
st.session_state.setdefault("chart_type", "Table")

# 🔥 NEW: uploader reset key
st.session_state.setdefault("uploader_key", 0)

# AUTO SQLITE
if st.session_state.engine is None:
    st.session_state.engine = create_engine("sqlite:///auto.db")

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
st.sidebar.title("⚙️ Database")

db_type = st.sidebar.selectbox("DB Type", ["Auto SQLite", "MySQL"])

if db_type == "MySQL":
    host = st.sidebar.text_input("Host")
    port = st.sidebar.text_input("Port", "3306")
    user = st.sidebar.text_input("User")
    password = st.sidebar.text_input("Password", type="password")
    db = st.sidebar.text_input("Database")

    if st.sidebar.button("Connect MySQL"):
        try:
            engine = create_engine(
                f"mysql+pymysql://{user}:{password}@{host}:{port}/{db}",
                pool_pre_ping=True,
                connect_args={"connect_timeout": 5}
            )
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))

            st.session_state.engine = engine
            st.success("✅ Connected to MySQL")
        except Exception as e:
            st.error(f"❌ Connection failed: {e}")

# ================= CSV LOADER =================
def load_csv(file):
    try:
        file.seek(0)
        df = pd.read_csv(file)
        if df.shape[1] == 0:
            raise ValueError("Empty columns")
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

# ================= CLEAR (FIXED) =================
if st.button("🧹 Clear Uploaded Files"):
    st.session_state.uploaded_files.clear()
    st.session_state.uploader_key += 1  # 🔥 reset uploader widget
    st.success("Uploads cleared")
    st.rerun()

# ================= UPLOADER (FIXED KEY) =================
files = st.file_uploader(
    "📂 Upload CSV Files",
    type=["csv"],
    accept_multiple_files=True,
    key=f"uploader_{st.session_state.uploader_key}"  # 🔥 important
)

# Show already uploaded
if st.session_state.uploaded_files:
    st.info(f"Uploaded tables: {list(st.session_state.uploaded_files)}")

# ================= PROCESS UPLOAD =================
if files:
    for f in files:
        if f.name in st.session_state.uploaded_files:
            continue

        try:
            df = load_csv(f)

            if df.empty:
                st.error(f"❌ {f.name} is empty")
                continue

            table_name = f.name.replace(".csv", "").replace(" ", "_").lower()

            df.to_sql(
                table_name,
                st.session_state.engine,
                index=False,
                if_exists="replace"
            )

            st.session_state.uploaded_files.add(f.name)
            st.success(f"✅ {table_name} uploaded")

        except Exception as e:
            st.error(f"❌ {f.name} failed: {str(e)}")

# ================= TABLE PREVIEW =================
inspector = inspect(st.session_state.engine)
tables = inspector.get_table_names()

if tables:
    st.subheader("📊 Preview Table")
    selected_table = st.selectbox("Select table", tables)

    if selected_table:
        df_preview = pd.read_sql(
            f"SELECT * FROM {selected_table} LIMIT 5",
            st.session_state.engine
        )
        st.dataframe(df_preview)

# ================= QUERY =================
st.subheader("💬 Ask your data")
query = st.text_input("Type your question")

if st.button("Run Query"):
    if not query.strip():
        st.warning("Enter a query")
        st.stop()

    df, sql, error = ask_db(query, st.session_state.engine)

    st.session_state.df = df
    st.session_state.sql = sql
    st.session_state.error = error

# ================= DISPLAY =================
if st.session_state.sql:

    with st.expander("🧠 Generated SQL"):
        st.code(st.session_state.sql)

    if st.session_state.error:
        st.error(st.session_state.error)
    else:
        df = st.session_state.df

        if df is None or df.empty:
            st.warning("No data")
        else:
            st.success("✅ Query executed")
            st.dataframe(df, use_container_width=True)

            numeric_cols = df.select_dtypes(include=['int64', 'float64']).columns.tolist()
            text_cols = df.select_dtypes(include=['object']).columns.tolist()

            chart = st.selectbox(
                "📈 Chart Type",
                ["Table", "Bar", "Line", "Pie"],
                key="chart_type"
            )

            if chart == "Bar" and numeric_cols and text_cols:
                st.plotly_chart(px.bar(df, x=text_cols[0], y=numeric_cols[0]))

            elif chart == "Line" and numeric_cols:
                st.plotly_chart(px.line(df, y=numeric_cols[0]))

            elif chart == "Pie" and numeric_cols and text_cols:
                st.plotly_chart(px.pie(df, names=text_cols[0], values=numeric_cols[0]))