from sqlalchemy import text, inspect
import pandas as pd
from openai import OpenAI
import os
import re

api_key = os.getenv("OPENAI_API_KEY")
client = OpenAI(api_key=api_key) if api_key else None

_schema_cache = {}

def get_schema(engine):
    engine_id = str(engine.url)

    if engine_id in _schema_cache:
        return _schema_cache[engine_id]

    inspector = inspect(engine)
    schema = ""

    for table in inspector.get_table_names():
        schema += f"\nTable: {table}\nColumns:\n"
        for col in inspector.get_columns(table):
            schema += f"- {col['name']} ({col['type']})\n"

    _schema_cache[engine_id] = schema
    return schema


def clean_sql(sql):
    if not sql:
        return None

    sql = sql.replace("```sql", "").replace("```", "").strip()
    match = re.search(r"(select .*?)(;|$)", sql, re.IGNORECASE | re.DOTALL)

    return match.group(1).strip() if match else None


def validate_sql(sql):
    return (sql.lower().startswith("select"), "Only SELECT allowed")


def ensure_limit(sql):
    return sql if "limit" in sql.lower() else sql + " LIMIT 10"


def generate_sql(question, schema):
    if not client:
        return None

    prompt = f"""
Return ONLY SQL.

SCHEMA:
{schema}

QUESTION:
{question}
"""

    res = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}]
    )

    return clean_sql(res.choices[0].message.content)


def execute_sql(engine, sql):
    try:
        with engine.connect() as conn:
            result = conn.execute(text(sql))
            df = pd.DataFrame(result.fetchall(), columns=result.keys())
        return df, None
    except Exception as e:
        return None, str(e)


def ask_db(question, engine):
    if not client:
        return None, None, "❌ API key missing"

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