import streamlit as st
import pandas as pd
from sqlalchemy import create_engine, text, inspect
from main import ask_db
from auth import init_db, login_user, register_user
import plotly.express as px

# ================= CONFIG =================
st.set_page_config(page_title="AI SQL Dashboard", layout="wide")
init_db()

# ================= SESSION =================
st.session_state.setdefault("logged_in", False)
st.session_state.setdefault("engine", None)
st.session_state.setdefault("df", None)
st.session_state.setdefault("sql", None)
st.session_state.setdefault("error", None)
st.session_state.setdefault("chart", "Table")

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

# ================= DATABASE =================
st.sidebar.title("⚙️ Database")

db_type = st.sidebar.selectbox("DB Type", ["SQLite", "MySQL"])

if db_type == "SQLite":
    if st.session_state.engine is None:
        st.session_state.engine = create_engine(
            f"sqlite:///user_{st.session_state.username}.db"
        )
    st.sidebar.success("SQLite connected")

else:
    host = st.sidebar.text_input("Host")
    user = st.sidebar.text_input("User")
    password = st.sidebar.text_input("Password", type="password")
    db = st.sidebar.text_input("Database")

    if st.sidebar.button("Connect"):
        try:
            engine = create_engine(
                f"mysql+pymysql://{user}:{password}@{host}/{db}"
            )
            engine.connect()
            st.session_state.engine = engine
            st.success("Connected")
        except Exception as e:
            st.error(e)

# ================= LOGOUT =================
if st.sidebar.button("Logout"):
    st.session_state.clear()
    st.rerun()

# ================= SAFE CSV LOADER =================
def load_csv(file):
    encodings = ["utf-8", "latin1", "cp1252"]

    for enc in encodings:
        try:
            file.seek(0)
            return pd.read_csv(file, encoding=enc)
        except:
            continue

    raise ValueError("Unable to read CSV file (encoding issue)")

# ================= MAIN =================
st.title("🤖 AI SQL Dashboard")

# ================= UPLOAD =================
st.subheader("📂 Upload CSV")

files = st.file_uploader("Upload CSV files", type=["csv"], accept_multiple_files=True)

if files:
    for f in files:
        table = f.name.replace(".csv", "").lower()

        try:
            df = load_csv(f)

            with st.expander(f"Preview: {table}"):
                st.dataframe(df.head(), use_container_width=True)

            if st.button(f"Upload {table}", key=table):
                df.to_sql(table, st.session_state.engine, index=False, if_exists="replace")

                # 🔥 refresh connection
                st.session_state.engine.dispose()

                st.success(f"{table} uploaded")
                st.rerun()

        except Exception as e:
            st.error(f"{f.name} error: {e}")

# ================= TABLE MANAGER =================
st.subheader("🗂️ Tables")

inspector = inspect(st.session_state.engine)
tables = inspector.get_table_names()

if tables:
    cols = st.columns(2)

    for i, table in enumerate(tables):
        with cols[i % 2]:
            st.markdown(f"**📄 {table}**")

            if st.button("Delete", key=f"del_{table}"):
                try:
                    with st.session_state.engine.begin() as conn:
                        conn.execute(text(f"DROP TABLE `{table}`"))

                    # 🔥 refresh
                    st.session_state.engine.dispose()

                    st.success(f"{table} deleted")
                    st.rerun()

                except Exception as e:
                    st.error(e)

            df_preview = pd.read_sql(
                f"SELECT * FROM {table} LIMIT 5",
                st.session_state.engine
            )

            st.dataframe(df_preview, height=200, use_container_width=True)

# ================= QUERY =================
st.subheader("💬 Ask your data")

query = st.text_input("Type your question")

if st.button("Run Query"):
    if not query:
        st.warning("Enter a query")
    else:
        df, sql, error = ask_db(query, st.session_state.engine)
        st.session_state.df = df
        st.session_state.sql = sql
        st.session_state.error = error

# ================= RESULT =================
if st.session_state.sql:

    st.code(st.session_state.sql)

    if st.session_state.error:
        st.error(st.session_state.error)
    else:
        df = st.session_state.df

        if df is not None and not df.empty:
            st.dataframe(df, use_container_width=True)

            numeric = df.select_dtypes(include="number").columns
            text = df.select_dtypes(include="object").columns

            chart = st.selectbox(
                "Chart",
                ["Table", "Bar", "Line", "Pie"],
                key="chart"
            )

            if chart == "Bar" and len(numeric) and len(text):
                st.plotly_chart(px.bar(df, x=text[0], y=numeric[0]))

            elif chart == "Line" and len(numeric):
                st.plotly_chart(px.line(df, y=numeric[0]))

            elif chart == "Pie" and len(numeric) and len(text):
                st.plotly_chart(px.pie(df, names=text[0], values=numeric[0]))