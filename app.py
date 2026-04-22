import streamlit as st
import pandas as pd
import os
from sqlalchemy import create_engine, text
from main import ask_db
from auth import init_db, login_user, register_user
import plotly.express as px

# ================= SAFE APP WRAPPER =================
try:

    # ================= CONFIG =================
    st.set_page_config(page_title="AI SQL SaaS", layout="wide")

    # ================= SAFE DB INIT =================
    try:
        init_db()
    except Exception as e:
        st.error(f"⚠️ DB Init Failed: {e}")

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
                engine = create_engine(
                    f"mysql+pymysql://{user}:{password}@{host}/{db}"
                )
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

    if st.sidebar.button("Reset"):
        st.session_state.engine = None
        st.rerun()

    if st.sidebar.button("Logout"):
        st.session_state.clear()
        st.rerun()

    # ================= MAIN =================
    st.title("🤖 AI SQL Dashboard")

    query = st.text_input("Ask your database")

    # ================= RUN QUERY =================
    if st.button("Run Query"):

        if not st.session_state.engine:
            st.warning("Connect database first")
            st.stop()

        if not query.strip():
            st.warning("Please enter a query")
            st.stop()

        with st.spinner("Generating SQL & fetching data..."):
            df, sql, error = ask_db(query, st.session_state.engine)

        st.session_state.df = df
        st.session_state.sql = sql
        st.session_state.error = error

    # ================= DISPLAY =================
    if st.session_state.sql:

        with st.expander("🧠 View Generated SQL"):
            st.code(st.session_state.sql, language="sql")

        if st.session_state.error:
            st.error(st.session_state.error)
            st.stop()

        df = st.session_state.df

        if df is None or df.empty:
            st.warning("No data found")
            st.stop()

        st.success("✅ Query executed successfully")

        st.markdown(
            """
            <style>
            .dataframe th, .dataframe td {
                text-align: center !important;
            }
            </style>
            """,
            unsafe_allow_html=True
        )

        numeric_cols = df.select_dtypes(include=['int64', 'float64']).columns.tolist()
        text_cols = df.select_dtypes(include=['object']).columns.tolist()

        chart_type = st.selectbox(
            "Choose view",
            ["Table", "Bar", "Line", "Pie"]
        )

        if chart_type == "Table":
            st.dataframe(df, use_container_width=True)

        elif chart_type == "Bar":
            if numeric_cols and text_cols:
                fig = px.bar(df, x=text_cols[0], y=numeric_cols[0])
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.warning("Need text + numeric column")

        elif chart_type == "Line":
            if numeric_cols:
                fig = px.line(df, y=numeric_cols[0])
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.warning("Need numeric column")

        elif chart_type == "Pie":
            if numeric_cols and text_cols:
                fig = px.pie(df, names=text_cols[0], values=numeric_cols[0])
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.warning("Need text + numeric column")

# ================= GLOBAL ERROR CATCH =================
except Exception as e:
    st.error(f"🚨 App crashed: {str(e)}")