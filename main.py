from sqlalchemy import text, inspect
import pandas as pd
from openai import OpenAI
import os

# =========================
# LAZY OPENAI CLIENT (FIX)
# =========================
_client = None

def get_client():
    global _client
    if _client is None:
        api_key = os.getenv("OPENAI_API_KEY")

        if not api_key:
            raise ValueError("OPENAI_API_KEY not set")

        _client = OpenAI(api_key=api_key)

    return _client


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
    sql_lower = sql.lower()

    if not sql_lower.startswith("select"):
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
# GENERATE SQL (SAFE)
# =========================
def generate_sql(question, schema):
    prompt = f"""
You are an expert SQL engineer.

DATABASE SCHEMA:
{schema}

STRICT RULES:
- Use ONLY tables and columns from schema
- NEVER guess column names
- Only SELECT queries
- Use proper joins
- Add LIMIT 10 unless aggregation

Question:
{question}

Return ONLY SQL.
"""

    try:
        client = get_client()

        res = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}]
        )

        sql = res.choices[0].message.content.strip()
        return clean_sql(sql)

    except Exception as e:
        return None


# =========================
# FIX SQL
# =========================
def fix_sql(error, bad_sql, schema):
    prompt = f"""
Fix this SQL query.

SCHEMA:
{schema}

ERROR:
{error}

BAD SQL:
{bad_sql}

RULES:
- Use only schema columns
- Only SELECT
- Correct joins
- Return valid SQL

Return ONLY SQL.
"""

    try:
        client = get_client()

        res = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}]
        )

        sql = res.choices[0].message.content.strip()
        return clean_sql(sql)

    except Exception as e:
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

        df = pd.DataFrame(rows, columns=cols)

        return df, None

    except Exception as e:
        return None, str(e)


# =========================
# MAIN PIPELINE
# =========================
def ask_db(question, engine):
    try:
        schema = get_schema(engine)

        # STEP 1: Generate SQL
        sql = generate_sql(question, schema)

        if not sql:
            return None, None, "Failed to generate SQL"

        # STEP 2: Validate
        valid, msg = validate_sql(sql)
        if not valid:
            return None, sql, msg

        # STEP 3: Ensure LIMIT
        sql = ensure_limit(sql)

        # STEP 4: Execute
        df, error = execute_sql(engine, sql)

        if df is not None:
            return df, sql, None

        # STEP 5: Fix SQL
        fixed_sql = fix_sql(error, sql, schema)

        if fixed_sql:
            valid, msg = validate_sql(fixed_sql)
            if not valid:
                return None, fixed_sql, msg

            fixed_sql = ensure_limit(fixed_sql)

            df, error2 = execute_sql(engine, fixed_sql)

            if df is not None:
                return df, fixed_sql, None

            return None, fixed_sql, error2

        return None, sql, error

    except Exception as e:
        return None, None, str(e)