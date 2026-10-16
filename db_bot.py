"""
Restaurant DB Bot
-----------------
Flow:
  1. User types a question in plain English
  2. We send (schema + question) to GPT -> it returns a SQL SELECT statement
  3. We run that SQL against our local SQLite database
  4. We send (question + raw results) back to GPT -> it returns a friendly answer
  5. Print the friendly answer

Three prompting strategies (from the research paper) are selectable:
  - zero_shot          : schema only, no examples
  - single_domain      : schema + one example Q&A pair (same domain)
  - multi_domain       : schema + two example Q&A pairs (different question types)
"""

import json
import os
import sqlite3
from openai import OpenAI

# ── Paths ──────────────────────────────────────────────────────────────────────
fdir = os.path.dirname(__file__)

def path(fname):
    return os.path.join(fdir, fname)

# ── SQLite Setup ───────────────────────────────────────────────────────────────
# We rebuild the DB fresh every run so the file stays in sync with the SQL files.
DB_PATH = path("restaurant.sqlite")
if os.path.exists(DB_PATH):
    os.remove(DB_PATH)

connection = sqlite3.connect(DB_PATH)
cursor = connection.cursor()

with open(path("setup.sql"))     as f: cursor.executescript(f.read())
with open(path("setupData.sql")) as f: cursor.executescript(f.read())

def run_sql(query: str):
    """Execute a SELECT query and return all rows as a list of tuples."""
    return cursor.execute(query).fetchall()

# ── OpenAI Setup ───────────────────────────────────────────────────────────────
with open(path("config.json")) as f:
    config = json.load(f)

client = OpenAI(api_key=config["openaiKey"])
model  = config.get("model", "gpt-4o-mini")

def ask_gpt(prompt: str) -> str:
    """Send a single prompt to GPT and return the text response."""
    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.choices[0].message.content

# ── Schema (used in every prompt so GPT knows the table structure) ─────────────
with open(path("setup.sql")) as f:
    SCHEMA = f.read()

# The core instruction we append to every SQL prompt.
# Note: we explicitly ask for COLLATE NOCASE on string comparisons so that
# questions like "chicken alfredo" still match "Chicken Alfredo" in the DB.
SQL_ONLY = (
    "Give me a SQLite SELECT statement that answers the question. "
    "Only respond with SQLite syntax — no explanation, no markdown code fences. "
    "When comparing text values use COLLATE NOCASE so the match is case-insensitive. "
    "If the question cannot be answered, respond with: SELECT 'N/A';"
)

# ── Prompting Strategies ───────────────────────────────────────────────────────
# Each strategy builds a different "prefix" that gets the question appended to it.
#
# ZERO-SHOT: Just the schema. GPT has to figure everything else out on its own.
# SINGLE-DOMAIN: Schema + one worked example (same restaurant domain).
# CROSS-DOMAIN: Schema + examples from a completely different database (a school).
#   The paper calls this cross-domain — the examples come from an unrelated domain
#   so GPT learns the SQL pattern without getting hints about the restaurant data.

STRATEGIES = {
    "zero_shot": (
        SCHEMA + "\n\n" + SQL_ONLY
    ),

    "single_domain": (
        SCHEMA
        + "\n\nExample:\n"
        + "Q: What is the most expensive item on the menu?\n"
        + "A: SELECT name, price FROM menu_item ORDER BY price DESC LIMIT 1;\n\n"
        + SQL_ONLY
    ),

    "cross_domain": (
        SCHEMA
        + "\n\nExamples (from a different database — a school database):\n"
        + "Q: Which students have the highest GPA?\n"
        + "A: SELECT name, gpa FROM student ORDER BY gpa DESC LIMIT 5;\n\n"
        + "Q: How many students are enrolled in each course?\n"
        + "A: SELECT c.title, COUNT(e.student_id) AS total "
        +    "FROM course c JOIN enrollment e ON c.course_id = e.course_id "
        +    "GROUP BY c.course_id ORDER BY total DESC;\n\n"
        + SQL_ONLY
    ),
}

# ── SQL Sanitizer ──────────────────────────────────────────────────────────────
def extract_sql(text: str) -> str:
    """
    GPT sometimes wraps its SQL in markdown fences like ```sql ... ```.
    This strips those markers so we get clean SQL we can actually run.
    """
    if "```" in text:
        parts = text.split("```", 1)
        after_fence = parts[1]
        # Skip the language label line (e.g. "sql\n")
        newline = after_fence.find("\n")
        if newline != -1:
            after_fence = after_fence[newline + 1:]
        text = after_fence.split("```")[0]
    return text.strip()

# ── Friendly Response Builder ──────────────────────────────────────────────────
def build_friendly_prompt(question: str, sql: str, raw_result: str) -> str:
    """
    We give GPT the original question, the SQL that was run, AND the raw data.
    Passing the SQL gives GPT context about what columns mean so it can give
    a smarter, more specific answer instead of a generic one.
    """
    return (
        f'A user asked: "{question}"\n'
        f"The following SQL was run against a restaurant database:\n{sql}\n"
        f"The raw result was: {raw_result}\n\n"
        "Please give a concise, friendly, plain-English answer using the actual "
        "data above. Do not suggest follow-up questions or add extra commentary."
    )

# ── Main Interactive Loop ──────────────────────────────────────────────────────
def main():
    print("\n🍽️  Restaurant DB Bot")
    print("=" * 50)
    print("I can answer questions about our restaurant's")
    print("menu, orders, staff, customers, and reviews.\n")

    # Let the user pick a strategy
    print("Prompting strategies:")
    print("  1 - zero_shot     (schema only)")
    print("  2 - single_domain (schema + 1 example, same domain)")
    print("  3 - cross_domain  (schema + 2 examples from a different database)")
    choice = input("\nPick a strategy [1/2/3] (default 1): ").strip()
    strategy_map = {"2": "single_domain", "3": "cross_domain"}
    strategy = strategy_map.get(choice, "zero_shot")
    print(f"\n✅ Using strategy: {strategy}\n")

    prompt_prefix = STRATEGIES[strategy]

    while True:
        question = input("Ask a question (or type 'quit' to exit):\n> ").strip()
        if question.lower() in ("quit", "exit", "q"):
            break
        if not question:
            continue

        print("\n⏳ Thinking...\n")

        # Step 1: Ask GPT for SQL
        sql_prompt = prompt_prefix + "\n\nQuestion: " + question
        sql = extract_sql(ask_gpt(sql_prompt))
        print(f"📋 SQL Generated:\n{sql}\n")

        # Step 2: Run the SQL against SQLite
        try:
            raw = str(run_sql(sql))
        except Exception as e:
            print(f"❌ SQL Error: {e}\n")
            continue
        print(f"📊 Raw Result:\n{raw}\n")

        # Step 3: Ask GPT to turn the raw data into a friendly response
        friendly_prompt = build_friendly_prompt(question, sql, raw)
        friendly = ask_gpt(friendly_prompt)
        print(f"💬 Answer:\n{friendly}\n")
        print("-" * 50 + "\n")

    cursor.close()
    connection.close()
    print("Goodbye! 👋")

if __name__ == "__main__":
    main()
