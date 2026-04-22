from sqlalchemy import text, inspect
import pandas as pd
from openai import OpenAI
import os

# =========================
# INIT OPENAI (SAFE)
# =========================
api_key = os.getenv("OPENAI_API_KEY")

client = None
if api_key:
    client = OpenAI(api_key=api_key)

# =========================
# CACHE SCHEMA
# =========================
_schema_cache = {}

def get_schema(engine):
    global _schema_cache

    engine_id = str(engine.url)

    if engine_id in _schema_cache:
        return _schema_cache[engine_id]

    try:
        inspector = inspect(engine)
        schema = ""

        for table in inspector.get_table_names():
            schema += f"\nTable: {table}\nColumns:\n"

            for col in inspector.get_columns(table):
                schema += f"- {col['name']} ({col['type']})\n"

        _schema_cache[engine_id] = schema
        return schema

    except Exception as e:
        return f"Schema error: {str(e)}"


# =========================
# CLEAN SQL
# =========================
def clean_sql(sql):
    if not sql:
        return None

    sql = sql.replace("```sql", "").replace("```", "").strip()

    lines = sql.split("\n")
    clean_lines = [l for l in lines if not l.strip().startswith("--")]

    sql = " ".join(clean_lines)

    if ";" in sql:
        sql = sql.split(";")[0]

    return sql.strip()


# =========================
# VALIDATE SQL
# =========================
def validate_sql(sql):
    if not sql.lower().startswith("select"):
        return False, "Only SELECT queries allowed"
    return True, None


# =========================
# ENSURE LIMIT
# =========================
def ensure_limit(sql):
    if "limit" not in sql.lower():
        return sql + " LIMIT 10"
    return sql


# =========================
# GENERATE SQL
# =========================
def generate_sql(question, schema):
    if client is None:
        return None

    prompt = f"""
You are an expert SQL engineer.

DATABASE SCHEMA:
{schema}

RULES:
- Use ONLY schema
- Only SELECT queries
- Add LIMIT 10

Question:
{question}

Return ONLY SQL.
"""

    try:
        res = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}]
        )
        return clean_sql(res.choices[0].message.content)

    except Exception:
        return None


# =========================
# FIX SQL
# =========================
def fix_sql(error, bad_sql, schema):
    if client is None:
        return None

    prompt = f"""
Fix SQL.

SCHEMA:
{schema}

ERROR:
{error}

SQL:
{bad_sql}

Return ONLY SQL.
"""

    try:
        res = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}]
        )
        return clean_sql(res.choices[0].message.content)

    except:
        return None


# =========================
# EXECUTE SQL
# =========================
def execute_sql(engine, sql):
    try:
        with engine.connect() as conn:
            result = conn.execute(text(sql))
            rows = result.fetchall()
            cols = result.keys()

        return pd.DataFrame(rows, columns=cols), None

    except Exception as e:
        return None, str(e)


# =========================
# MAIN PIPELINE
# =========================
def ask_db(question, engine):

    if client is None:
        return None, None, "OPENAI_API_KEY not set"

    schema = get_schema(engine)

    sql = generate_sql(question, schema)
    if not sql:
        return None, None, "SQL generation failed"

    valid, msg = validate_sql(sql)
    if not valid:
        return None, sql, msg

    sql = ensure_limit(sql)

    df, error = execute_sql(engine, sql)

    if df is not None:
        return df, sql, None

    fixed_sql = fix_sql(error, sql, schema)

    if fixed_sql:
        df, error2 = execute_sql(engine, ensure_limit(fixed_sql))
        if df is not None:
            return df, fixed_sql, None
        return None, fixed_sql, error2

    return None, sql, error