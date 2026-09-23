from flask import Flask, render_template, request, redirect, url_for, session, flash, Response, jsonify
import sqlite3
import csv
import io
from datetime import date, datetime
from werkzeug.security import generate_password_hash, check_password_hash
import os
import secrets

app = Flask(__name__)
app.secret_key = os.environ.get("MOODTRACKER_SECRET_KEY", secrets.token_hex(32))

# Protect session cookies when the app is deployed over HTTPS.
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=os.environ.get("SESSION_COOKIE_SECURE", "0") == "1",
)

DATABASE = os.environ.get("DATABASE_PATH", os.path.join(app.root_path, "mood_tracker.db"))

@app.after_request
def add_security_headers(response):
    """Add basic browser security headers to every response."""
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "SAMEORIGIN"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    return response



def get_db():
    """Open the SQLite database and return rows as dictionaries."""
    connection = sqlite3.connect(DATABASE)
    connection.row_factory = sqlite3.Row
    # Enforce foreign-key relationships so deleted accounts cannot leave orphaned records.
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def csrf_token():
    """Create and return a per-session CSRF token."""
    if "csrf_token" not in session:
        session["csrf_token"] = secrets.token_urlsafe(32)
    return session["csrf_token"]


def validate_csrf():
    """Validate the CSRF token sent by a POST form."""
    submitted = request.form.get("csrf_token", "")
    return secrets.compare_digest(submitted, session.get("csrf_token", ""))


app.jinja_env.globals["csrf_token"] = csrf_token


def init_db():
    """Create all tables required by the application."""
    connection = get_db()

    # Store student registration and login information.
    connection.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    """)

    # Store every daily mood and stress check-in.
    connection.execute("""
        CREATE TABLE IF NOT EXISTS checkins (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            mood INTEGER NOT NULL,
            stress INTEGER NOT NULL,
            note TEXT,
            advice TEXT,
            solution TEXT,
            checkin_date TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)

    # Store conversations with the friendly AI assistant.
    connection.execute("""
        CREATE TABLE IF NOT EXISTS assistant_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            sender TEXT NOT NULL,
            message TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)

    
    connection.execute("""
        CREATE TABLE IF NOT EXISTS sensor_readings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            heart_rate REAL,
            spo2 REAL,
            temperature REAL,
            created_at TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
    """)

    # Store a hashed token for trusted Java/ESP32 sensor devices.
    connection.execute("""
        CREATE TABLE IF NOT EXISTS sensor_devices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            token_hash TEXT UNIQUE NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
    """)

    connection.commit()
    connection.close()


def require_login():
    """Return True when a student is logged in."""
    return "user_id" in session


def get_solution(stress, mood):
    """
    Generate a simple supportive response and practical solution.
    This is a local rule-based assistant, so no external API key is required.
    """
    if stress >= 5:
        advice = "Your stress level is very high today. Please slow down and give yourself a short break."
        solution = (
            "1. Take 5 slow breaths.\n"
            "2. Drink some water.\n"
            "3. Step away from study/work for 10 minutes.\n"
            "4. Break your biggest task into one small next step.\n"
            "5. If this level continues, talk to a trusted person or appropriate college support."
        )
    elif stress == 4:
        advice = "Your stress is high. You do not need to solve everything at once."
        solution = (
            "1. Take a 10-minute screen break.\n"
            "2. Write down your top 3 tasks.\n"
            "3. Finish only the first small task.\n"
            "4. Try a short walk or breathing exercise.\n"
            "5. Check in again tomorrow."
        )
    elif stress == 3:
        advice = "Your stress is moderate. A little structure can help you feel more in control."
        solution = (
            "1. Choose one priority for the next hour.\n"
            "2. Study/work for 25 minutes and rest for 5 minutes.\n"
            "3. Keep water nearby.\n"
            "4. Avoid multitasking."
        )
    else:
        advice = "Your stress level looks manageable today. Keep protecting the habits that help you."
        solution = (
            "1. Keep your normal routine.\n"
            "2. Take regular short breaks.\n"
            "3. Get enough sleep.\n"
            "4. Make time for one activity you enjoy."
        )

    if mood <= 2:
        advice += " Your mood is also low, so be gentle with yourself today."

    return advice, solution


def assistant_reply(message, user_id):
    """
    Return a friendly local AI-style response using the student's recent data.
    It is intentionally supportive and does not claim to diagnose any condition.
    """
    connection = get_db()
    latest = connection.execute("""
        SELECT mood, stress, note, checkin_date
        FROM checkins
        WHERE user_id = ?
        ORDER BY id DESC
        LIMIT 1
    """, (user_id,)).fetchone()
    connection.close()

    text = message.lower()

    if any(word in text for word in ["hello", "hi", "hey", "namaste"]):
        return "Hi! 🌿 I am here with you. You can tell me how your day is going, or ask for a simple stress-management idea."

    if any(word in text for word in ["stress", "stressed", "tension", "pressure"]):
        if latest:
            _, solution = get_solution(latest["stress"], latest["mood"])
            return (
                f"I hear you. Your latest recorded stress level is {latest['stress']}/5. "
                "Let's keep it simple today.\n\n" + solution
            )
        return "Let's start with one small step: take 5 slow breaths, drink some water, and choose only one task to focus on."

    if any(word in text for word in ["sad", "unhappy", "low", "bad mood"]):
        return (
            "I am sorry your day feels heavy. 💚 You do not have to fix everything immediately. "
            "Try a short break, talk to someone you trust, and choose one small thing that feels manageable."
        )

    if any(word in text for word in ["study", "exam", "exam stress", "college"]):
        return (
            "For study stress, try the 25–5 method: focus for 25 minutes, then take a 5-minute break. "
            "Start with the easiest important task so you can build momentum."
        )

    if any(word in text for word in ["sleep", "tired", "fatigue"]):
        return (
            "If you are tired, protect your rest. 🌙 Try reducing screen time before sleep and keep a consistent sleep routine."
        )

    if any(word in text for word in ["thank", "thanks"]):
        return "You are welcome! 💚 One small positive step is enough for today."

    if latest:
        return (
            f"I am listening. Your latest check-in was mood {latest['mood']}/5 and "
            f"stress {latest['stress']}/5. Tell me what is bothering you, and we can break it into a small next step."
        )

    return (
        "I am here to help. 🌿 You can tell me about your stress, mood, studies, sleep, "
        "or simply say what happened today."
    )


@app.route("/")
def home():
    """Send visitors to registration or the student dashboard."""
    if require_login():
        return redirect(url_for("dashboard"))
    return redirect(url_for("register"))


@app.route("/register", methods=["GET", "POST"])
def register():
    """Create a new student account."""
    if require_login():
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        if not validate_csrf():
            flash("Security check failed. Please try again.", "error")
            return render_template("register.html")

        username = request.form["username"].strip()
        email = request.form["email"].strip().lower()
        password = request.form["password"]
        confirm_password = request.form["confirm_password"]

        if not username or not email or not password:
            flash("Please fill in all fields.", "error")
            return render_template("register.html")

        if len(username) < 3:
            flash("Username must contain at least 3 characters.", "error")
            return render_template("register.html")

        if len(password) < 6:
            flash("Password must contain at least 6 characters.", "error")
            return render_template("register.html")

        if password != confirm_password:
            flash("Passwords do not match.", "error")
            return render_template("register.html")

        connection = get_db()

        existing = connection.execute(
            "SELECT id FROM users WHERE username = ? OR email = ?",
            (username, email)
        ).fetchone()

        if existing:
            connection.close()
            flash("Username or email is already registered.", "error")
            return render_template("register.html")

        # Hash the password before storing it in the database.
        password_hash = generate_password_hash(password)

        connection.execute("""
            INSERT INTO users (username, email, password, created_at)
            VALUES (?, ?, ?, ?)
        """, (
            username,
            email,
            password_hash,
            datetime.now().isoformat(timespec="seconds")
        ))

        connection.commit()
        connection.close()

        flash("Registration successful. Please login.", "success")
        return redirect(url_for("login"))

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    """Authenticate a registered student."""
    if require_login():
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        if not validate_csrf():
            flash("Security check failed. Please try again.", "error")
            return render_template("login.html")

        username_or_email = request.form["username_or_email"].strip().lower()
        password = request.form["password"]

        connection = get_db()

        user = connection.execute("""
            SELECT * FROM users
            WHERE lower(username) = ? OR lower(email) = ?
        """, (username_or_email, username_or_email)).fetchone()

        connection.close()

        if user and check_password_hash(user["password"], password):
            session["user_id"] = user["id"]
            session["username"] = user["username"]
            session["email"] = user["email"]
            return redirect(url_for("dashboard"))

        flash("Invalid username/email or password.", "error")

    return render_template("login.html")


@app.route("/dashboard")
def dashboard():
    """Show the main daily mood and stress dashboard."""
    if not require_login():
        return redirect(url_for("login"))

    connection = get_db()

    # Fetch the latest personal check-in for the summary section.
    latest = connection.execute("""
        SELECT * FROM checkins
        WHERE user_id = ?
        ORDER BY id DESC
        LIMIT 1
    """, (session["user_id"],)).fetchone()

    # Fetch the last seven check-ins for the weekly trend section.
    weekly_rows = connection.execute("""
        SELECT checkin_date, mood, stress
        FROM checkins
        WHERE user_id = ?
        ORDER BY checkin_date DESC, id DESC
        LIMIT 7
    """, (session["user_id"],)).fetchall()

    # Get the most recent sensor reading for the dashboard status card.
    latest_sensor = connection.execute("""
        SELECT heart_rate, spo2, temperature, created_at
        FROM sensor_readings
        WHERE user_id = ?
        ORDER BY id DESC
        LIMIT 1
    """, (session["user_id"],)).fetchone()

    # Count personal check-ins for the dashboard.
    checkin_count = connection.execute("""
        SELECT COUNT(*) AS total
        FROM checkins
        WHERE user_id = ?
    """, (session["user_id"],)).fetchone()["total"]

    connection.close()

    # Reverse the rows so the chart reads from oldest to newest.
    weekly = list(reversed(weekly_rows))

    # Detect whether the student has had high stress for three recent check-ins.
    high_stress_streak = False
    if len(weekly_rows) >= 3:
        high_stress_streak = all(row["stress"] >= 4 for row in weekly_rows[:3])

    return render_template(
        "dashboard.html",
        latest=latest,
        weekly=weekly,
        latest_sensor=latest_sensor,
        checkin_count=checkin_count,
        high_stress_streak=high_stress_streak
    )


@app.route("/checkin", methods=["POST"])
def checkin():
    """Store today's mood and stress and immediately generate feedback."""
    if not require_login():
        return redirect(url_for("login"))

    if not validate_csrf():
        flash("Security check failed. Please try again.", "error")
        return redirect(url_for("dashboard"))

    mood = int(request.form["mood"])
    stress = int(request.form["stress"])

    if mood not in range(1, 6) or stress not in range(1, 6):
        flash("Invalid mood or stress value.", "error")
        return redirect(url_for("dashboard"))
    note = request.form.get("note", "").strip()

    advice, solution = get_solution(stress, mood)

    connection = get_db()
    connection.execute("""
        INSERT INTO checkins
        (user_id, mood, stress, note, advice, solution, checkin_date, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        session["user_id"],
        mood,
        stress,
        note,
        advice,
        solution,
        date.today().isoformat(),
        datetime.now().isoformat(timespec="seconds")
    ))
    connection.commit()
    connection.close()

    flash("Today's check-in is saved. Your personal response is ready.", "success")
    return redirect(url_for("response_page"))


@app.route("/response")
def response_page():
    """Show the latest personalized response and solution."""
    if not require_login():
        return redirect(url_for("login"))

    connection = get_db()
    latest = connection.execute("""
        SELECT * FROM checkins
        WHERE user_id = ?
        ORDER BY id DESC
        LIMIT 1
    """, (session["user_id"],)).fetchone()
    connection.close()

    return render_template("response.html", latest=latest)


@app.route("/history")
def history():
    """Show all check-in history for the logged-in student."""
    if not require_login():
        return redirect(url_for("login"))

    connection = get_db()
    records = connection.execute("""
        SELECT * FROM checkins
        WHERE user_id = ?
        ORDER BY checkin_date DESC, id DESC
    """, (session["user_id"],)).fetchall()
    connection.close()

    return render_template("history.html", records=records)


@app.route("/daily-mode")
def daily_mode():
    """Show a simple daily action plan based on the latest check-in."""
    if not require_login():
        return redirect(url_for("login"))

    connection = get_db()
    latest = connection.execute("""
        SELECT * FROM checkins
        WHERE user_id = ?
        ORDER BY id DESC
        LIMIT 1
    """, (session["user_id"],)).fetchone()
    connection.close()

    if latest:
        _, solution = get_solution(latest["stress"], latest["mood"])
        daily_steps = solution.split("\n")
    else:
        daily_steps = [
            "1. Take 5 slow breaths.",
            "2. Drink water.",
            "3. Choose one important task.",
            "4. Take regular short breaks.",
            "5. Check in again tomorrow."
        ]

    return render_template(
        "daily_mode.html",
        latest=latest,
        daily_steps=daily_steps
    )


@app.route("/assistant", methods=["GET", "POST"])
def assistant():
    """Provide a friendly local AI-style assistant and store the conversation."""
    if not require_login():
        return redirect(url_for("login"))

    if request.method == "POST":
        if not validate_csrf():
            flash("Security check failed. Please try again.", "error")
            return redirect(url_for("assistant"))

        message = request.form["message"].strip()

        if message:
            reply = assistant_reply(message, session["user_id"])

            connection = get_db()

            # Store both sides of the conversation.
            connection.execute("""
                INSERT INTO assistant_messages
                (user_id, sender, message, created_at)
                VALUES (?, ?, ?, ?)
            """, (
                session["user_id"],
                "student",
                message,
                datetime.now().isoformat(timespec="seconds")
            ))

            connection.execute("""
                INSERT INTO assistant_messages
                (user_id, sender, message, created_at)
                VALUES (?, ?, ?, ?)
            """, (
                session["user_id"],
                "assistant",
                reply,
                datetime.now().isoformat(timespec="seconds")
            ))

            connection.commit()
            connection.close()

    connection = get_db()
    messages = connection.execute("""
        SELECT * FROM assistant_messages
        WHERE user_id = ?
        ORDER BY id ASC
    """, (session["user_id"],)).fetchall()
    connection.close()

    return render_template("assistant.html", messages=messages)



@app.route("/delete-checkin/<int:checkin_id>", methods=["POST"])
def delete_checkin(checkin_id):
    """Delete only a check-in owned by the currently logged-in student."""
    if not require_login():
        return redirect(url_for("login"))

    if not validate_csrf():
        flash("Security check failed. Please try again.", "error")
        return redirect(url_for("history"))

    connection = get_db()

    # The user_id condition prevents one student from deleting another student's data.
    connection.execute(
        "DELETE FROM checkins WHERE id = ? AND user_id = ?",
        (checkin_id, session["user_id"])
    )
    connection.commit()
    connection.close()

    flash("Selected check-in deleted.", "success")
    return redirect(url_for("history"))


@app.route("/clear-history", methods=["POST"])
def clear_history():
    """Delete all check-ins and assistant messages for the current student."""
    if not require_login():
        return redirect(url_for("login"))

    if not validate_csrf():
        flash("Security check failed. Please try again.", "error")
        return redirect(url_for("history"))

    connection = get_db()
    connection.execute(
        "DELETE FROM assistant_messages WHERE user_id = ?",
        (session["user_id"],)
    )
    connection.execute(
        "DELETE FROM checkins WHERE user_id = ?",
        (session["user_id"],)
    )
    connection.commit()
    connection.close()

    flash("Your mood history and assistant history were deleted.", "success")
    return redirect(url_for("history"))


@app.route("/export-data")
def export_data():
    """Export only the logged-in student's own check-in data as CSV."""
    if not require_login():
        return redirect(url_for("login"))

    connection = get_db()
    records = connection.execute("""
        SELECT checkin_date, mood, stress, note, advice, solution
        FROM checkins
        WHERE user_id = ?
        ORDER BY checkin_date DESC, id DESC
    """, (session["user_id"],)).fetchall()
    connection.close()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["date", "mood", "stress", "note", "response", "solution"])

    for record in records:
        writer.writerow([
            record["checkin_date"],
            record["mood"],
            record["stress"],
            record["note"] or "",
            record["advice"] or "",
            record["solution"] or ""
        ])

    response = Response(output.getvalue(), mimetype="text/csv")
    response.headers["Content-Disposition"] = "attachment; filename=moodtracker_my_data.csv"
    return response


@app.route("/account")
def account():
    """Show the current student's account and privacy information."""
    if not require_login():
        return redirect(url_for("login"))

    connection = get_db()

    user = connection.execute(
        "SELECT username, email, created_at FROM users WHERE id = ?",
        (session["user_id"],)
    ).fetchone()

    checkin_count = connection.execute(
        "SELECT COUNT(*) AS total FROM checkins WHERE user_id = ?",
        (session["user_id"],)
    ).fetchone()["total"]

    assistant_count = connection.execute(
        "SELECT COUNT(*) AS total FROM assistant_messages WHERE user_id = ?",
        (session["user_id"],)
    ).fetchone()["total"]

    device = connection.execute(
        "SELECT created_at FROM sensor_devices WHERE user_id = ? ORDER BY id DESC LIMIT 1",
        (session["user_id"],)
    ).fetchone()

    connection.close()

    # Show a newly generated token only on the immediate account page.
    new_device_token = session.pop("new_device_token", None)

    return render_template(
        "account.html",
        user=user,
        checkin_count=checkin_count,
        assistant_count=assistant_count,
        device=device,
        new_device_token=new_device_token
    )


@app.route("/delete-account", methods=["POST"])
def delete_account():
    """Permanently delete the current student's account and all related data."""
    if not require_login():
        return redirect(url_for("login"))

    if not validate_csrf():
        flash("Security check failed. Please try again.", "error")
        return redirect(url_for("dashboard"))

    confirmation = request.form.get("confirmation", "").strip().upper()

    if confirmation != "DELETE":
        flash('Type DELETE to permanently remove your account and data.', "error")
        return redirect(url_for("dashboard"))

    user_id = session["user_id"]

    connection = get_db()

    # Delete dependent records first, then delete the student account.
    connection.execute(
        "DELETE FROM assistant_messages WHERE user_id = ?",
        (user_id,)
    )
    connection.execute(
        "DELETE FROM checkins WHERE user_id = ?",
        (user_id,)
    )
    connection.execute(
        "DELETE FROM sensor_devices WHERE user_id = ?",
        (user_id,)
    )
    connection.execute(
        "DELETE FROM users WHERE id = ?",
        (user_id,)
    )

    connection.commit()
    connection.close()

    # Remove all login/session information after account deletion.
    session.clear()

    flash("Your account and stored MoodTracker data have been permanently deleted.", "success")
    return redirect(url_for("register"))



@app.route("/generate-device-token", methods=["POST"])
def generate_device_token():
    """Create a new token for one trusted Java/ESP32 sensor device."""
    if not require_login():
        return redirect(url_for("login"))

    if not validate_csrf():
        flash("Security check failed. Please try again.", "error")
        return redirect(url_for("account"))

    # Generate a strong random token and store only its hash in SQLite.
    raw_token = secrets.token_urlsafe(32)
    token_hash = generate_password_hash(raw_token)

    connection = get_db()
    connection.execute("DELETE FROM sensor_devices WHERE user_id = ?", (session["user_id"],))
    connection.execute(
        "INSERT INTO sensor_devices (user_id, token_hash, created_at) VALUES (?, ?, ?)",
        (session["user_id"], token_hash, datetime.now().isoformat(timespec="seconds"))
    )
    connection.commit()
    connection.close()

    # Keep the raw token in the session only long enough to display it once.
    session["new_device_token"] = raw_token
    flash("New sensor device token generated. Copy it into your Java client or ESP32 code.", "success")
    return redirect(url_for("account"))


def get_sensor_user_id():
    """Return the owner user ID for a browser session or a trusted device token."""
    if require_login():
        return session["user_id"]

    supplied_token = request.headers.get("X-Device-Token", "").strip()
    if not supplied_token:
        return None

    connection = get_db()
    devices = connection.execute(
        "SELECT user_id, token_hash FROM sensor_devices"
    ).fetchall()
    connection.close()

    # Compare the supplied token against hashed tokens without exposing user passwords.
    for device in devices:
        if check_password_hash(device["token_hash"], supplied_token):
            return device["user_id"]

    return None


@app.route("/api/sensor-data", methods=["POST"])
def sensor_data():
    """Receive sensor readings from a logged-in browser, Java client, or ESP32 device."""
    user_id = get_sensor_user_id()
    if user_id is None:
        return jsonify({"success": False, "message": "Valid login or sensor device token required"}), 401

    payload = request.get_json(silent=True) or {}

    # Validate incoming values before saving them.
    try:
        heart_rate = float(payload["heart_rate"]) if payload.get("heart_rate") is not None else None
        spo2 = float(payload["spo2"]) if payload.get("spo2") is not None else None
        temperature = float(payload["temperature"]) if payload.get("temperature") is not None else None
    except (TypeError, ValueError):
        return jsonify({"success": False, "message": "Invalid sensor values"}), 400

    if heart_rate is None and spo2 is None and temperature is None:
        return jsonify({"success": False, "message": "At least one sensor value is required"}), 400

    # Reject clearly impossible values to reduce accidental bad readings.
    if heart_rate is not None and not 20 <= heart_rate <= 250:
        return jsonify({"success": False, "message": "Heart rate is outside the accepted range"}), 400
    if spo2 is not None and not 50 <= spo2 <= 100:
        return jsonify({"success": False, "message": "SpO2 is outside the accepted range"}), 400
    if temperature is not None and not 20 <= temperature <= 50:
        return jsonify({"success": False, "message": "Temperature is outside the accepted range"}), 400

    connection = get_db()
    connection.execute(
        """INSERT INTO sensor_readings
           (user_id, heart_rate, spo2, temperature, created_at)
           VALUES (?, ?, ?, ?, datetime('now'))""",
        (user_id, heart_rate, spo2, temperature)
    )
    connection.commit()
    connection.close()

    return jsonify({"success": True, "message": "Sensor data stored safely"})




@app.route("/api/simulate-sensor", methods=["POST"])
def simulate_sensor():
    """Generate a realistic demo reading for software-only sensor validation."""
    if not require_login():
        return jsonify({"success": False, "message": "Login required"}), 401
    if not validate_csrf():
        return jsonify({"success": False, "message": "Security check failed"}), 403

    import random
    # Simulated values are for demonstration/testing only, not medical measurements.
    heart_rate = round(random.uniform(65, 88), 1)
    spo2 = round(random.uniform(96.5, 99.5), 1)
    temperature = round(random.uniform(36.3, 37.2), 1)

    connection = get_db()
    connection.execute(
        """INSERT INTO sensor_readings
           (user_id, heart_rate, spo2, temperature, created_at)
           VALUES (?, ?, ?, ?, datetime('now'))""",
        (session["user_id"], heart_rate, spo2, temperature)
    )
    connection.commit()
    connection.close()

    return jsonify({
        "success": True,
        "heart_rate": heart_rate,
        "spo2": spo2,
        "temperature": temperature,
        "message": "Simulated sensor reading stored successfully"
    })


@app.route("/api/sensor-test", methods=["POST"])
def sensor_test():
    """Store safe demo sensor values for local/project demonstration."""
    if not require_login():
        return jsonify({"success": False, "message": "Login required"}), 401

    if not validate_csrf():
        return jsonify({"success": False, "message": "Security check failed"}), 403

    # These values are demonstration readings only, not real medical measurements.
    heart_rate = 72.0
    spo2 = 98.0
    temperature = 36.7

    connection = get_db()
    connection.execute(
        """INSERT INTO sensor_readings
           (user_id, heart_rate, spo2, temperature, created_at)
           VALUES (?, ?, ?, ?, datetime('now'))""",
        (session["user_id"], heart_rate, spo2, temperature)
    )
    connection.commit()
    connection.close()

    return jsonify({
        "success": True,
        "message": "Demo sensor reading added",
        "heart_rate": heart_rate,
        "spo2": spo2,
        "temperature": temperature
    })


@app.route("/sensor")
def sensor():
    """Display recent sensor readings for the logged-in student."""
    if not require_login():
        return redirect(url_for("login"))

    connection = get_db()
    readings = connection.execute(
        """SELECT heart_rate, spo2, temperature, created_at
           FROM sensor_readings
           WHERE user_id = ?
           ORDER BY id DESC LIMIT 20""",
        (session["user_id"],)
    ).fetchall()
    connection.close()

    return render_template("sensor.html", readings=readings)

@app.route("/logout")
def logout():
    """Log out the current student."""
    session.clear()
    flash("You have been logged out.", "success")
    return redirect(url_for("login"))


with app.app_context():
    init_db()


if __name__ == "__main__":
    # Debug mode is useful locally. Disable debug mode in production.
    app.run(debug=True)
