from sqlalchemy import text, inspect
import pandas as pd
from openai import OpenAI
import os
import re

# ================= OPENAI =================
api_key = os.getenv("OPENAI_API_KEY")
client = OpenAI(api_key=api_key) if api_key else None

# ================= SCHEMA =================
def get_schema(engine):
    inspector = inspect(engine)
    schema = ""

    for table in inspector.get_table_names():
        schema += f"\nTable: {table}\nColumns:\n"

        for col in inspector.get_columns(table):
            schema += f"- {col['name']} ({col['type']})\n"

        # Include foreign keys (helps JOIN)
        for fk in inspector.get_foreign_keys(table):
            schema += f"FK: {fk['constrained_columns']} -> {fk['referred_table']}.{fk['referred_columns']}\n"

    return schema


# ================= CLEAN SQL =================
def clean_sql(sql):
    if not sql:
        return None

    sql = sql.replace("```sql", "").replace("```", "").strip()
    match = re.search(r"(select .*?)(;|$)", sql, re.IGNORECASE | re.DOTALL)
    return match.group(1).strip() if match else None


# ================= VALIDATE =================
def validate_sql(sql):
    if not sql.lower().startswith("select"):
        return False, "Only SELECT queries allowed"
    return True, None


# ================= LIMIT =================
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

Rules:
- Return ONLY SQL
- No explanation
- Must start with SELECT
- Use JOIN when needed
- Use schema correctly

Schema:
{schema}

Question:
{question}
"""

    res = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}]
    )

    return clean_sql(res.choices[0].message.content)


# ================= EXECUTE =================
def execute_sql(engine, sql):
    try:
        with engine.connect() as conn:
            result = conn.execute(text(sql))
            df = pd.DataFrame(result.fetchall(), columns=result.keys())
        return df, None
    except Exception as e:
        return None, str(e)


# ================= MAIN =================
def ask_db(question, engine):
    if not client:
        return None, None, "❌ OPENAI_API_KEY missing"

    schema = get_schema(engine)
    sql = generate_sql(question, schema)

    if not sql:
        return None, None, "SQL generation failed"

    valid, msg = validate_sql(sql)
    if not valid:
        return None, sql, msg

    sql = ensure_limit(sql)

    df, err = execute_sql(engine, sql)

    return df, sql, err