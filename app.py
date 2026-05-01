import streamlit as st
import pandas as pd
from sqlalchemy import create_engine, text, inspect
from main import ask_db
from auth import init_db, login_user, register_user
import plotly.express as px
import chardet

# ================= CONFIG =================
st.set_page_config(page_title="AI SQL SaaS", layout="wide")

# Init auth DB
init_db()

# ================= SESSION =================
st.session_state.setdefault("logged_in", False)
st.session_state.setdefault("engine", None)

# ================= AUTO SQLITE (NO DB NEEDED) =================
if st.session_state.engine is None:
    st.session_state.engine = create_engine("sqlite:///auto.db")

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

            # Test connection
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))

            st.session_state.engine = engine
            st.success("✅ Connected to MySQL")

        except Exception as e:
            st.error(f"❌ Connection failed: {e}")

# ================= SAFE CSV LOADER =================
def load_csv(file):
    try:
        raw = file.read()
        encoding = chardet.detect(raw)["encoding"]
        file.seek(0)
        return pd.read_csv(file, encoding=encoding)
    except:
        file.seek(0)
        return pd.read_csv(file, encoding="latin1")

# ================= MAIN =================
st.title("🤖 AI SQL Dashboard")

# ================= CSV UPLOAD =================
st.subheader("📂 Upload CSV Files")

files = st.file_uploader(
    "Upload CSV files",
    type=["csv"],
    accept_multiple_files=True
)

if files:
    for f in files:
        try:
            df = load_csv(f)

            table_name = f.name.replace(".csv", "").replace(" ", "_").lower()

            df.to_sql(
                table_name,
                st.session_state.engine,
                index=False,
                if_exists="replace"
            )

            st.success(f"✅ {table_name} uploaded")

        except Exception as e:
            st.error(f"❌ {f.name} failed: {str(e)}")

# ================= SHOW TABLES =================
inspector = inspect(st.session_state.engine)
tables = inspector.get_table_names()

if tables:
    st.subheader("📊 Table Preview")

    selected_table = st.selectbox("Select Table", tables)

    if selected_table:
        df_preview = pd.read_sql(
            f"SELECT * FROM {selected_table} LIMIT 5",
            st.session_state.engine
        )
        st.dataframe(df_preview)

# ================= QUERY =================
st.subheader("💬 Ask Your Data")

query = st.text_input("Type your question")

if st.button("Run Query"):

    if not query.strip():
        st.warning("Please enter a question")
        st.stop()

    with st.spinner("Generating SQL & fetching data..."):
        df, sql, error = ask_db(query, st.session_state.engine)

    if sql:
        with st.expander("🧠 Generated SQL"):
            st.code(sql, language="sql")

    if error:
        st.error(error)
    else:
        if df is None or df.empty:
            st.warning("No data found")
        else:
            st.success("✅ Query executed")

            st.dataframe(df, use_container_width=True)

            # ================= CHARTS =================
            numeric_cols = df.select_dtypes(include=['int64', 'float64']).columns.tolist()
            text_cols = df.select_dtypes(include=['object']).columns.tolist()

            chart_type = st.selectbox(
                "📈 Choose Chart",
                ["Table", "Bar", "Line", "Pie"]
            )

            if chart_type == "Bar" and numeric_cols and text_cols:
                fig = px.bar(df, x=text_cols[0], y=numeric_cols[0])
                st.plotly_chart(fig, use_container_width=True)

            elif chart_type == "Line" and numeric_cols:
                fig = px.line(df, y=numeric_cols[0])
                st.plotly_chart(fig, use_container_width=True)

            elif chart_type == "Pie" and numeric_cols and text_cols:
                fig = px.pie(df, names=text_cols[0], values=numeric_cols[0])
                st.plotly_chart(fig, use_container_width=True)