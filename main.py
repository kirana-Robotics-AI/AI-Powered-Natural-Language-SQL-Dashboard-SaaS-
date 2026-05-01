from sqlalchemy import text, inspect
import pandas as pd
from openai import OpenAI
import os
import re

# ================= OPENAI =================
api_key = os.getenv("OPENAI_API_KEY")
client = OpenAI(api_key=api_key) if api_key else None

# ================= SCHEMA CACHE =================
_schema_cache = {}

def get_schema(engine):
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


# ================= CLEAN SQL =================
def clean_sql(sql):
    if not sql:
        return None

    sql = sql.replace("```sql", "").replace("```", "").strip()

    # Extract SELECT query only
    match = re.search(r"(select .*?)(;|$)", sql, re.IGNORECASE | re.DOTALL)
    if match:
        sql = match.group(1)

    return sql.strip()


# ================= VALIDATE SQL =================
def validate_sql(sql):
    if not sql.lower().strip().startswith("select"):
        return False, "Only SELECT queries allowed"
    return True, None


# ================= ENSURE LIMIT =================
def ensure_limit(sql):
    if "limit" not in sql.lower():
        return sql + " LIMIT 10"
    return sql


# ================= GENERATE SQL =================
def generate_sql(question, schema):
    if not client:
        return None

    prompt = f"""
You are an expert SQL generator.

STRICT RULES:
- Return ONLY SQL
- Must start with SELECT
- No explanation
- Use only tables in schema

SCHEMA:
{schema}

QUESTION:
{question}
"""

    try:
        res = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "Return ONLY SQL."},
                {"role": "user", "content": prompt}
            ]
        )

        sql = res.choices[0].message.content.strip()
        return clean_sql(sql)

    except Exception:
        return None


# ================= EXECUTE SQL =================
def execute_sql(engine, sql):
    try:
        with engine.connect() as conn:
            result = conn.execute(text(sql))
            rows = result.fetchall()
            cols = result.keys()

        df = pd.DataFrame(rows, columns=cols)
        return df, None

    except Exception as e:
        return None, str(e)


# ================= MAIN =================
def ask_db(question, engine):

    if not client:
        return None, None, "❌ OPENAI_API_KEY not set"

    schema = get_schema(engine)

    sql = generate_sql(question, schema)
    if not sql:
        return None, None, "❌ Failed to generate SQL"

    valid, msg = validate_sql(sql)
    if not valid:
        return None, sql, msg

    sql = ensure_limit(sql)

    df, error = execute_sql(engine, sql)

    if df is not None:
        return df, sql, None

    return None, sql, error