from sqlalchemy import text, inspect
import pandas as pd
from openai import OpenAI
import os

# ================= SAFE OPENAI =================
_client = None

def get_client():
    global _client

    if _client:
        return _client

    api_key = os.getenv("OPENAI_API_KEY")

    if not api_key:
        return None  # don't crash

    try:
        _client = OpenAI(api_key=api_key)
        return _client
    except Exception:
        return None


# ================= SCHEMA CACHE =================
_schema_cache = {}

def get_schema(engine):
    try:
        inspector = inspect(engine)
        schema = ""

        for table in inspector.get_table_names():
            schema += f"\nTable: {table}\nColumns:\n"
            for col in inspector.get_columns(table):
                schema += f"- {col['name']} ({col['type']})\n"

        return schema

    except Exception as e:
        return f"Schema error: {str(e)}"


# ================= SQL HELPERS =================
def clean_sql(sql):
    if not sql:
        return None

    sql = sql.replace("```sql", "").replace("```", "").strip()
    lines = [l for l in sql.split("\n") if not l.strip().startswith("--")]
    sql = " ".join(lines)

    if ";" in sql:
        sql = sql.split(";")[0]

    return sql.strip()


def validate_sql(sql):
    if not sql:
        return False, "No SQL generated"

    if not sql.lower().startswith("select"):
        return False, "Only SELECT allowed"

    return True, None


def ensure_limit(sql):
    if "limit" not in sql.lower():
        return sql + " LIMIT 10"
    return sql


# ================= GENERATE SQL =================
def generate_sql(question, schema):
    client = get_client()
    if not client:
        return None

    prompt = f"""
    You are an SQL expert.

    SCHEMA:
    {schema}

    RULES:
    - Only SELECT
    - Use correct tables
    - LIMIT 10

    Question: {question}
    """

    try:
        res = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}]
        )
        return clean_sql(res.choices[0].message.content)

    except Exception:
        return None


def fix_sql(error, bad_sql, schema):
    client = get_client()
    if not client:
        return None

    try:
        res = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{
                "role": "user",
                "content": f"Fix SQL:\n{bad_sql}\nError:{error}\nSchema:{schema}"
            }]
        )
        return clean_sql(res.choices[0].message.content)

    except Exception:
        return None


# ================= EXECUTE =================
def execute_sql(engine, sql):
    try:
        with engine.connect() as conn:
            result = conn.execute(text(sql))
            rows = result.fetchall()
            cols = result.keys()

        return pd.DataFrame(rows, columns=cols), None

    except Exception as e:
        return None, str(e)


# ================= MAIN =================
def ask_db(question, engine):
    schema = get_schema(engine)

    sql = generate_sql(question, schema)
    if not sql:
        return None, None, "OpenAI not configured"

    valid, msg = validate_sql(sql)
    if not valid:
        return None, sql, msg

    sql = ensure_limit(sql)

    df, err = execute_sql(engine, sql)
    if df is not None:
        return df, sql, None

    fixed = fix_sql(err, sql, schema)
    if fixed:
        df, err2 = execute_sql(engine, ensure_limit(fixed))
        if df is not None:
            return df, fixed, None

    return None, sql, err