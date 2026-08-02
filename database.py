# ==========================================
# DATABASE CONFIGURATION
# ==========================================

import sqlite3
import json
import os

# Always use the same database file
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

DATABASE = os.path.join(BASE_DIR, "database.db")


# ==========================================
# Database Connection
# ==========================================


def get_connection():

    conn = sqlite3.connect(DATABASE, check_same_thread=False)

    conn.row_factory = sqlite3.Row

    return conn


# ==========================================
# Create Database Tables
# ==========================================


def create_database():

    conn = get_connection()

    cursor = conn.cursor()

    # -----------------------------
    # Users Table
    # -----------------------------

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users(

        id INTEGER PRIMARY KEY AUTOINCREMENT,

        name TEXT NOT NULL,

        email TEXT UNIQUE NOT NULL,

        password TEXT NOT NULL,

        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP

    )
    """)

    # -----------------------------
    # Forms Table
    # -----------------------------

    cursor.execute("""
 CREATE TABLE IF NOT EXISTS forms(

    id INTEGER PRIMARY KEY AUTOINCREMENT,

    form_id TEXT UNIQUE NOT NULL,

    user_id INTEGER NOT NULL,

    title TEXT NOT NULL,

    description TEXT,

    questions TEXT NOT NULL,

    status TEXT DEFAULT 'draft',

    published_at TIMESTAMP,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY(user_id)
    REFERENCES users(id)
    ON DELETE CASCADE

)
    """)
    # ==========================================
    # Upgrade forms table (only runs once)
    # ==========================================

    cursor.execute("PRAGMA table_info(forms)")
    columns = [column[1] for column in cursor.fetchall()]

    if "status" not in columns:
        cursor.execute("ALTER TABLE forms ADD COLUMN status TEXT DEFAULT 'draft'")

    if "published_at" not in columns:
        cursor.execute("ALTER TABLE forms ADD COLUMN published_at TIMESTAMP")

    if "updated_at" not in columns:
        cursor.execute(
        "ALTER TABLE forms ADD COLUMN updated_at TIMESTAMP"
    )

    # -----------------------------
    # Responses Table
    # -----------------------------

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS responses(

        id INTEGER PRIMARY KEY AUTOINCREMENT,

        form_id TEXT NOT NULL,

        answers TEXT NOT NULL,

        submitted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

        FOREIGN KEY(form_id)
        REFERENCES forms(form_id)
        ON DELETE CASCADE

    )
    """)

    conn.commit()

    conn.close()
    # ==========================================


# USER AUTHENTICATION
# ==========================================


def create_user(name, email, password):

    conn = get_connection()

    cursor = conn.cursor()

    try:

        cursor.execute(
            """
            INSERT INTO users(
                name,
                email,
                password
            )

            VALUES(?,?,?)
            """,
            (name, email, password),
        )

        conn.commit()

        user_id = cursor.lastrowid

    except sqlite3.IntegrityError:

        user_id = None

    finally:

        conn.close()

    return user_id


def get_user_by_email(email):

    conn = get_connection()

    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT *

        FROM users

        WHERE email=?

        """,
        (email,),
    )

    user = cursor.fetchone()

    conn.close()

    return user


# ==========================================
# SAVE FORM
# ==========================================


def save_form(form_id, form, user_id):

    conn = get_connection()

    cursor = conn.cursor()

    cursor.execute(
        """
       INSERT INTO forms(

    form_id,

    user_id,

    title,

    description,

    questions,

    status

)

VALUES(?,?,?,?,?,?)
        """,
        (
            form_id,
            user_id,
            form["title"],
            form["description"],
            json.dumps(form["questions"]),
            "draft",
        ),
    )

    conn.commit()

    conn.close()


# ==========================================
# LOAD FORM
# ==========================================


def get_form(form_id):

    conn = get_connection()

    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT *

        FROM forms

        WHERE form_id=?

        """,
        (form_id,),
    )

    row = cursor.fetchone()

    conn.close()

    if row is None:

        return None

    return {
        "form_id": row["form_id"],
        "user_id": row["user_id"],
        "title": row["title"],
        "description": row["description"],
        "questions": json.loads(row["questions"]),
        "status": row["status"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
        "published_at": row["published_at"],
    }


# ==========================================
# GET ALL USER FORMS
# ==========================================


def get_all_forms(user_id):

    conn = get_connection()

    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT *

        FROM forms

        WHERE user_id=?

        ORDER BY created_at DESC

        """,
        (user_id,),
    )

    forms = cursor.fetchall()

    conn.close()

    return forms


# ==========================================
# SAVE RESPONSE
# ==========================================


def save_response(form_id, answers):

    conn = get_connection()

    cursor = conn.cursor()

    cursor.execute(
        """
        INSERT INTO responses(

            form_id,

            answers

        )

        VALUES(?,?)

        """,
        (form_id, json.dumps(answers)),
    )

    conn.commit()

    conn.close()


# ==========================================
# GET RESPONSES
# ==========================================


def get_responses(form_id):

    conn = get_connection()

    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT answers, submitted_at

        FROM responses

        WHERE form_id=?

        ORDER BY submitted_at DESC

        """,
        (form_id,),
    )

    rows = cursor.fetchall()

    conn.close()

    responses = []

    for row in rows:

        responses.append(
            {"answers": json.loads(row["answers"]), "submitted_at": row["submitted_at"]}
        )

    return responses


# ==========================================
# UPDATE FORM
# ==========================================


def update_form_db(form_id, form):

    conn = get_connection()

    cursor = conn.cursor()

    cursor.execute(
    """
    UPDATE forms

SET
    title=?,
    description=?,
    questions=?,
    updated_at=CURRENT_TIMESTAMP

WHERE form_id=?
    """,
    (
        form["title"],
        form["description"],
        json.dumps(form["questions"]),
        form_id,
    ),
)
    conn.commit()

    conn.close()

# ==========================================
# PUBLISH FORM
# ==========================================

def publish_form(form_id):

    conn = get_connection()

    cursor = conn.cursor()

    cursor.execute(
        """
        UPDATE forms

        SET

            status='published',

            published_at=CURRENT_TIMESTAMP,

            updated_at=CURRENT_TIMESTAMP

        WHERE form_id=?

        """,
        (form_id,)
    )

    conn.commit()

    conn.close()
# ==========================================
# UNPUBLISH FORM
# ==========================================

def unpublish_form(form_id):

    conn = get_connection()

    cursor = conn.cursor()

    cursor.execute(
        """
        UPDATE forms

        SET

            status='draft',

            published_at=NULL,

            updated_at=CURRENT_TIMESTAMP

        WHERE form_id=?

        """,
        (form_id,)
    )

    conn.commit()

    conn.close()
# ==========================================
# DELETE FORM
# ==========================================


def delete_form(form_id):

    conn = get_connection()

    cursor = conn.cursor()

    # Delete responses first

    cursor.execute(
        """
        DELETE FROM responses

        WHERE form_id=?

        """,
        (form_id,),
    )

    # Delete form

    cursor.execute(
        """
        DELETE FROM forms

        WHERE form_id=?

        """,
        (form_id,),
    )

    conn.commit()

    conn.close()
    # ==========================================


# COUNT TOTAL RESPONSES
# ==========================================


def count_total_responses(form_id):

    responses = get_responses(form_id)

    return len(responses)


# ==========================================
# GET LATEST RESPONSES
# ==========================================


def get_latest_responses(form_id, limit=5):

    responses = get_responses(form_id)

    return responses[:limit]


# ==========================================
# QUESTION STATISTICS
# ==========================================


def get_question_statistics(form_id):

    form = get_form(form_id)

    responses = get_responses(form_id)

    statistics = {}

    if form is None:

        return statistics

    # Create question structure

    for question in form["questions"]:

        statistics[question["label"]] = {}

    # Count answers

    for response in responses:

        answers = response["answers"]

        for question, answer in answers.items():

            if question not in statistics:

                statistics[question] = {}

            # Checkbox answers

            if isinstance(answer, list):

                for option in answer:

                    option = str(option).strip()

                    if option:

                        statistics[question][option] = (
                            statistics[question].get(option, 0) + 1
                        )

            else:

                answer = str(answer).strip()

                if answer:

                    statistics[question][answer] = (
                        statistics[question].get(answer, 0) + 1
                    )

    return statistics


# ==========================================
# AVERAGE RATING
# ==========================================


def get_average_rating(form_id):

    form = get_form(form_id)

    responses = get_responses(form_id)

    if form is None:

        return 0.0

    rating_questions = []

    for question in form["questions"]:

        if question["type"] == "rating":

            rating_questions.append(question["label"])

    if not rating_questions:

        return 0.0

    total = 0

    count = 0

    for response in responses:

        answers = response["answers"]

        for label in rating_questions:

            if label in answers:

                try:

                    total += float(answers[label])

                    count += 1

                except:

                    pass

    if count == 0:

        return 0.0

    return round(total / count, 1)


# ==========================================
# RATING STATISTICS
# ==========================================


def get_rating_statistics(form_id):

    form = get_form(form_id)

    responses = get_responses(form_id)

    result = {}

    if form is None:

        return result

    for question in form["questions"]:

        if question["type"] != "rating":

            continue

        label = question["label"]

        ratings = []

        for response in responses:

            answers = response["answers"]

            if label in answers:

                try:

                    ratings.append(int(answers[label]))

                except:

                    pass

        if ratings:

            result[label] = {
                "average": round(sum(ratings) / len(ratings), 1),
                "highest": max(ratings),
                "lowest": min(ratings),
                "count": len(ratings),
            }

    return result


# ==========================================
# GET FORM RESPONSES
# ==========================================


def get_form_responses(form_id):

    conn = get_connection()

    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT answers

        FROM responses

        WHERE form_id=?

        """,
        (form_id,),
    )

    data = cursor.fetchall()

    conn.close()

    return data


# ==========================================
# CLEAN RESPONSES FOR AI ANALYSIS
# ==========================================


def clean_responses(responses):

    cleaned = []

    for response in responses:

        answers = response["answers"]

        valid = False

        for value in answers.values():

            if value:

                value = str(value).strip()

                if value.lower() not in ["", "select rating", "none", "null"]:

                    valid = True

                    break

        if valid:

            cleaned.append(response)

    return cleaned


# ==========================================
# DATABASE HEALTH CHECK
# ==========================================


def check_database():

    try:

        conn = get_connection()

        cursor = conn.cursor()

        cursor.execute("SELECT 1")

        conn.close()

        return True

    except Exception:

        return False
