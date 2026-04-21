import streamlit as st
import pandas as pd
from sqlalchemy import create_engine, text
from main import ask_db
from auth import init_db, register_user, login_user
import plotly.express as px

# ================= CONFIG =================
st.set_page_config(page_title="AI SQL SaaS", layout="wide")

# ================= INIT =================
init_db()

# ================= SESSION =================
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "engine" not in st.session_state:
    st.session_state.engine = None
if "user" not in st.session_state:
    st.session_state.user = None

# ================= LOGIN =================
if not st.session_state.logged_in:
    st.title("🔐 Login")

    tab1, tab2 = st.tabs(["Login", "Register"])

    # -------- LOGIN --------
    with tab1:
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")

        if st.button("Login"):
            result = login_user(username, password)

            # SAFETY CHECK (prevents unpack error)
            if isinstance(result, tuple) and len(result) == 2:
                success, data = result

                if success:
                    st.session_state.logged_in = True
                    st.session_state.user = username
                    st.rerun()
                else:
                    st.error(data)
            else:
                st.error("Auth system error: invalid return format")

    # -------- REGISTER --------
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
st.sidebar.title(f"👤 {st.session_state.user}")

db_type = st.sidebar.selectbox("Database Type", ["MySQL", "SQLite"])

if db_type == "MySQL":
    host = st.sidebar.text_input("Host")
    user = st.sidebar.text_input("User")
    password = st.sidebar.text_input("Password", type="password")
    db_name = st.sidebar.text_input("Database Name")
else:
    sqlite_path = st.sidebar.text_input("SQLite file path")

# ================= CONNECT =================
def connect_db():
    try:
        if db_type == "MySQL":
            engine = create_engine(
                f"mysql+pymysql://{user}:{password}@{host}/{db_name}"
            )
        else:
            engine = create_engine(f"sqlite:///{sqlite_path}")

        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))

        st.session_state.engine = engine
        st.sidebar.success("Connected successfully")

    except Exception as e:
        st.sidebar.error(str(e))


if st.sidebar.button("Connect"):
    connect_db()

if st.sidebar.button("Reset Connection"):
    st.session_state.engine = None
    st.rerun()

if st.sidebar.button("Logout"):
    st.session_state.clear()
    st.rerun()

# ================= MAIN =================
st.title("🤖 AI SQL Dashboard")

question = st.text_input("Ask your database")

# ================= RUN =================
if st.button("Run Query"):

    if not st.session_state.engine:
        st.warning("Connect database first")
        st.stop()

    if not question.strip():
        st.warning("Enter a question")
        st.stop()

    df, sql, error = ask_db(question, st.session_state.engine)

    # -------- SQL (HIDDEN) --------
    with st.expander("🧠 View Generated SQL"):
        st.code(sql, language="sql")

    # -------- ERROR --------
    if error:
        st.error(error)
        st.stop()

    # -------- EMPTY --------
    if df is None or df.empty:
        st.warning("No data found")
        st.stop()

    st.success("Query executed successfully")

    # -------- TABLE --------
    st.dataframe(df, use_container_width=True)

    # -------- CLEAN DATA --------
    df = df.dropna()

    numeric_cols = df.select_dtypes(include=['int64', 'float64']).columns.tolist()
    text_cols = df.select_dtypes(include=['object']).columns.tolist()

    # -------- BAR CHART --------
    if text_cols and numeric_cols:
        df_sorted = df.sort_values(by=numeric_cols[0], ascending=False)

        fig_bar = px.bar(
            df_sorted,
            x=text_cols[0],
            y=numeric_cols[0],
            title="Bar Chart"
        )
        st.plotly_chart(fig_bar, use_container_width=True)

    # -------- LINE CHART --------
    if numeric_cols:
        fig_line = px.line(
            df,
            y=numeric_cols[0],
            title="Line Chart"
        )
        st.plotly_chart(fig_line, use_container_width=True)

    # -------- PIE CHART --------
    if text_cols and numeric_cols:
        fig_pie = px.pie(
            df,
            names=text_cols[0],
            values=numeric_cols[0],
            title="Pie Chart"
        )
        st.plotly_chart(fig_pie, use_container_width=True)