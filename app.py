# ==========================================
# IMPORTS
# ==========================================

from flask import Flask, render_template, request, Response, session, redirect, url_for, flash
from gemini_api import generate_form, analyze_feedback
from database import (
    create_database,
    save_form,
    get_form,
    save_response,
    get_responses,
    clean_responses,
    get_all_forms,
    update_form_db,
    count_total_responses,
    get_latest_responses,
    get_average_rating,
    get_question_statistics,
    get_rating_statistics,
    publish_form, 
    delete_form,
    create_user,
    get_user_by_email,
)
from openpyxl import Workbook
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv

load_dotenv()
import uuid
import json
import qrcode
import os
import re
import sqlite3

# ==========================================
# INITIALIZE FLASK APP
# ==========================================


app = Flask(__name__)


# ==========================================
# SECURITY CONFIGURATION
# ==========================================


app.secret_key = os.environ.get("SECRET_KEY")


if not app.secret_key:

    raise Exception("SECRET_KEY missing. Add it in environment variables.")


# Secure session cookies

app.config["SESSION_COOKIE_HTTPONLY"] = True

app.config["SESSION_COOKIE_SAMESITE"] = "Lax"


# For Render HTTPS
# enable this after deployment

# app.config["SESSION_COOKIE_SECURE"] = True


# ==========================================
# CREATE DATABASE
# ==========================================


create_database()


# ==========================================
# SECURITY HELPERS
# ==========================================


def login_required(function):
    """
    Protect routes that require login
    """

    def wrapper(*args, **kwargs):

        if "user_id" not in session:

            return redirect(url_for("login"))

        return function(*args, **kwargs)

    wrapper.__name__ = function.__name__

    return wrapper


def check_form_owner(form):
    """
    Check whether logged user owns form
    """

    if form is None:

        return False

    return form["user_id"] == session.get("user_id")


# ==========================================
# PASSWORD VALIDATION
# ==========================================


def validate_password(password):

    if len(password) < 8:

        return False

    if not re.search(r"[A-Z]", password):

        return False

    if not re.search(r"[0-9]", password):

        return False

    if not re.search(r"[@$!%*?&]", password):

        return False

    return True


# ==========================================
# AUTHENTICATION
# ==========================================


# ==========================================
# REGISTER
# ==========================================


@app.route("/register", methods=["GET", "POST"])
def register():

    error = None

    if request.method == "POST":

        name = request.form["name"]

        email = request.form["email"]

        password = request.form["password"]

        existing_user = get_user_by_email(email)

        if existing_user:

            error = "Email already registered. Please login or use another email."

            return render_template("register.html", error=error)

        hashed_password = generate_password_hash(password)

        create_user(name, email, hashed_password)

        return redirect(url_for("login"))

    return render_template("register.html", error=error)


# ==========================================
# LOGIN
# ==========================================


@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        email = request.form.get("email")

        password = request.form.get("password")

        user = get_user_by_email(email)

        if user and check_password_hash(user["password"], password):

            session.clear()

            session["user_id"] = user["id"]

            session["user_name"] = user["name"]

            return redirect(url_for("home"))

        return render_template("login.html", error="Invalid Email or Password")

    return render_template("login.html")


# ==========================================
# LOGOUT
# ==========================================


@app.route("/logout")
def logout():

    session.clear()

    return redirect(url_for("login"))


# ==========================================
# HOME PAGE
# ==========================================


@app.route("/")
@login_required
def home():

    return render_template("home.html")


# ==========================================
# MY FORMS
# ==========================================


@app.route("/myforms")
@login_required
def my_forms():

    forms = get_all_forms(session["user_id"])

    form_list = []

    for form in forms:

        responses = get_responses(form["form_id"])

        created_time = form["created_at"]

        if created_time:

            try:

                date_obj = datetime.strptime(created_time, "%Y-%m-%d %H:%M:%S")

                created_time = date_obj.strftime("%d %b %Y, %I:%M %p")

            except:

                pass

        form_list.append(
            {
                "form_id": form["form_id"],
                "title": form["title"],
                "description": form["description"],
                "created_at": created_time,
                "responses": len(responses),
                "status": form["status"] or "draft",
                "published_at": form["published_at"],
                "updated_at": form["updated_at"],
            }
        )

    return render_template("myforms.html", forms=form_list)
# ==========================================
# PUBLISH FORM
# ==========================================
@app.route("/publish/<form_id>", methods=["POST"])
@login_required
def publish_form_route(form_id):

    form = get_form(form_id)

    if not check_form_owner(form):

        return "<h2>Unauthorized Access</h2>"

    if form["status"] == "published":

        flash("Form already published.", "info")

        return redirect(url_for("preview_form", form_id=form_id))

    # Publish in database
    publish_form(form_id)

    # Reload updated form
    form = get_form(form_id)

    # Public link
    share_link = url_for(
        "open_form",
        form_id=form_id,
        _external=True
    )

    # Create QR folder
    os.makedirs("static/qr", exist_ok=True)

    # Generate QR
    qr = qrcode.make(share_link)

    qr_path = os.path.join(
        "static",
        "qr",
        f"{form_id}.png"
    )

    qr.save(qr_path)

    flash("🎉 Form Published Successfully!", "success")

    return redirect(
        url_for(
            "preview_form",
            form_id=form_id
        )
    )
# ==========================================
# GENERATE AI FORM
# ==========================================


@app.route("/generate", methods=["POST"])
@login_required
def generate():

    prompt = request.form.get("prompt")

    if not prompt:

        return """
        <h3>
        Form description is required.
        </h3>
        """

    form = generate_form(prompt)

    if not form:

        return """
        <h3>
        Unable to generate form.
        </h3>
        """

    form_id = str(uuid.uuid4())[:8]

    save_form(form_id, form, session["user_id"])

    return redirect(
    url_for(
        "preview_form",
        form_id=form_id
    )
)
    
@app.route("/preview/<form_id>")
@login_required
def preview_form(form_id):

    form = get_form(form_id)

    if not form:
        return "<h2>Form Not Found</h2>"


    if not check_form_owner(form):

        return "<h2>Unauthorized Access</h2>"


    source = request.args.get(
        "source",
        "home"
    )


    share_link = url_for(
        "open_form",
        form_id=form_id,
        _external=True
    )


    qr_code_url = url_for(
        "static",
        filename=f"qr/{form_id}.png"
    )


    total_responses = count_total_responses(form_id)


    return render_template(
        "preview.html",
        form=form,
        form_id=form_id,
        share_link=share_link,
        qr_code_url=qr_code_url,
        total_responses=total_responses,
        source=source
    )

# ==========================================
# OPEN PUBLIC FORM
# ==========================================

@app.route("/form/<form_id>")
def open_form(form_id):

    form = get_form(form_id)

    if form is None:
        return "Form not found"

    if form["status"] != "published":

        return """
        <h2>
        This form is not published yet.
        </h2>
        """

    return render_template(
        "form.html",
        form=form,
        form_id=form_id
    )


# ==========================================
# SUBMIT FORM RESPONSE
# ==========================================


@app.route("/submit", methods=["POST"])
def submit():

    form_id = request.form.get("form_id")

    if not form_id:

        return """
        <h3>
        Invalid Form Submission
        </h3>
        """

    form = get_form(form_id)

    if form is None:

        return """
        <h3>
        Form does not exist.
        </h3>
        """

    answers = {}

    for key in request.form:

        if key == "form_id":

            continue

        values = request.form.getlist(key)

        if len(values) == 1:

            answers[key] = values[0]

        else:

            answers[key] = values

    save_response(form_id, answers)

    return render_template("thankyou.html")
# ==========================================
# VIEW RESPONSES DASHBOARD
# ==========================================


@app.route("/responses/<form_id>")
@login_required
def responses(form_id):

    form = get_form(form_id)

    if not check_form_owner(form):

        return """
        <h2>
        ❌ Unauthorized Access
        </h2>
        """
    source = request.args.get("source", "preview")
    response_data = get_responses(form_id)

    return render_template(
        "responses.html",
        form=form,
        form_id=form_id,
        responses=response_data,
        total_responses=len(response_data),
        source=source 
    )


# ==========================================
# ANALYTICS DASHBOARD
# ==========================================


@app.route("/analytics/<form_id>")
@login_required
def analytics(form_id):

    form = get_form(form_id)

    if not check_form_owner(form):

        return """
        <h2>
        ❌ Unauthorized Access
        </h2>
        """
    source = request.args.get("source", "preview")
    all_responses = get_responses(form_id)

    cleaned_responses = clean_responses(all_responses)

    latest_responses = get_latest_responses(form_id)

    total_responses = count_total_responses(form_id)

    average_rating = get_average_rating(form_id)

    if average_rating is None:

        average_rating = 0

    question_statistics = get_question_statistics(form_id)

    rating_statistics = get_rating_statistics(form_id)

    # AI Analysis

    try:

        ai_summary = analyze_feedback(form, cleaned_responses)

    except Exception:

        ai_summary = {}

    # Default AI Response Structure

    ai_summary.setdefault("sentiment", {"positive": 0, "neutral": 0, "negative": 0})

    ai_summary.setdefault("strengths", [])

    ai_summary.setdefault("issues", [])

    ai_summary.setdefault("recommendations", [])

    ai_summary.setdefault("summary", "No AI summary available.")

    if latest_responses:

        latest_submission = latest_responses[0]["submitted_at"]

    else:

        latest_submission = "No Responses Yet"

    return render_template(
    "analytics.html",
    form=form,
    form_id=form_id,
    responses=latest_responses,
    total_responses=total_responses,
    average_rating=average_rating,
    latest_submission=latest_submission,
    question_statistics=question_statistics,
    rating_statistics=rating_statistics,
    ai_summary=ai_summary,
    source=source
)
# ==========================================
# EXPORT CSV
# ==========================================


@app.route("/export/csv/<form_id>")
@login_required
def export_csv(form_id):

    form = get_form(form_id)

    if not check_form_owner(form):

        return """
        <h2>
        ❌ Unauthorized Access
        </h2>
        """

    responses = get_responses(form_id)

    if not responses:

        return """
        <h3>
        No responses available.
        </h3>
        """

    headers = list(responses[0]["answers"].keys())

    def generate_csv():

        yield ",".join(headers) + "\n"

        for response in responses:

            row = []

            for key in headers:

                value = response["answers"].get(key, "")

                if isinstance(value, list):

                    value = ", ".join(value)

                row.append(f'"{value}"')

            yield ",".join(row) + "\n"

    return Response(
        generate_csv(),
        mimetype="text/csv",
        headers={
            "Content-Disposition": f"attachment; filename={form_id}_responses.csv"
        },
    )


# ==========================================
# EXPORT EXCEL
# ==========================================


@app.route("/export/excel/<form_id>")
@login_required
def export_excel(form_id):

    form = get_form(form_id)

    if not check_form_owner(form):

        return """
        <h2>
        ❌ Unauthorized Access
        </h2>
        """

    responses = get_responses(form_id)

    if not responses:

        return """
        <h3>
        No responses available.
        </h3>
        """

    workbook = Workbook()

    sheet = workbook.active

    sheet.title = "Responses"

    headers = list(responses[0]["answers"].keys())

    sheet.append(headers)

    for response in responses:

        row = []

        for header in headers:

            value = response["answers"].get(header, "")

            if isinstance(value, list):

                value = ", ".join(value)

            row.append(value)

        sheet.append(row)

    filename = f"{form_id}_responses.xlsx"

    workbook.save(filename)

    return Response(
        open(filename, "rb").read(),
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


# ==========================================
# EDIT FORM
# ==========================================
@app.route("/edit/<form_id>")
@login_required
def edit_form(form_id):

    form = get_form(form_id)

    if not form:
        return """
        <h2>
        ❌ Form Not Found
        </h2>
        """

    if not check_form_owner(form):

        return """
        <h2>
        ❌ Unauthorized Access
        </h2>
        """


    source = request.args.get(
        "source",
        "home"
    )


    return render_template(
        "edit_form.html",
        form=form,
        form_id=form_id,
        source=source
    )

# ==========================================
# UPDATE FORM
# ==========================================


@app.route("/update/<form_id>", methods=["POST"])
@login_required
def update_form(form_id):

    form = get_form(form_id)

    if not check_form_owner(form):

        return """
        <h2>
        ❌ Unauthorized Access
        </h2>
        """

    form["title"] = request.form.get("title", "")

    form["description"] = request.form.get("description", "")

    questions_json = request.form.get("questions")

    if questions_json:

        form["questions"] = json.loads(questions_json)

    update_form_db(form_id, form)

    return redirect(url_for("edit_form", form_id=form_id))


# ==========================================
# DELETE FORM
# ==========================================


@app.route("/delete/<form_id>", methods=["POST"])
@login_required
def delete_form_route(form_id):

    form = get_form(form_id)

    if not check_form_owner(form):

        return """
        <h2>
        ❌ Unauthorized Access
        </h2>
        """

    delete_form(form_id)

    return redirect(url_for("my_forms"))


# ==========================================
# RUN APPLICATION
# ==========================================


if __name__ == "__main__":

    app.run(debug=False)
