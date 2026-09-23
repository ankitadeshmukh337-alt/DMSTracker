# MoodTracker

Daily Mood and Stress Check-in Tracker.

## Complete flow

Register
→ Login
→ Daily Mood & Stress Check-in
→ Store data in SQLite
→ Personalized student response
→ Stress solution
→ Daily Solution Mode
→ Check-in History
→ Friendly AI Assistant
→ Logout

## Run on Windows PowerShell

```powershell
py -m venv venv
venv\Scripts\activate
python -m pip install -r requirements.txt
python app.py
```

Open:

```text
http://127.0.0.1:5000
```

## Important

The AI Assistant in this project is a local rule-based assistant. It does not require an API key.

For a real deployment, add proper authentication, authorization, HTTPS, secure secret management, privacy controls, consent, and professional mental-health support escalation.


## Account and data-control features

- Delete one individual check-in.
- Delete all check-in history.
- Permanently delete the student account.
- Account deletion also removes related check-ins and assistant conversation history.
- Passwords are hashed with Werkzeug.
- SQL statements use parameterized values.
- Each authenticated query is restricted to the current user ID.
- Session cookies use HttpOnly and SameSite=Lax settings.

## Recommended production security

Before deploying this project publicly:

1. Replace the example Flask secret key with a long random secret stored in an environment variable.
2. Use HTTPS and enable `SESSION_COOKIE_SECURE = True`.
3. Add CSRF protection (for example, Flask-WTF) to all state-changing forms.
4. Do not expose the SQLite database file publicly.
5. Add proper role-based access control if a staff/admin dashboard is added.
6. Define a privacy/retention policy and collect only the information the project actually needs.
7. For a real healthcare deployment, use appropriate legal, security, consent, and professional-support requirements.


## Final state-level presentation build

### Local run
```powershell
py -m venv venv
venv\Scripts\activate
python -m pip install -r requirements.txt
python app.py
```

Open `http://127.0.0.1:5000`.

### Important
- The local development server uses normal HTTP, so `SESSION_COOKIE_SECURE` defaults to `0`.
- On an HTTPS deployment, set `SESSION_COOKIE_SECURE=1`.
- Set `MOODTRACKER_SECRET_KEY` in production to a long random secret.
- SQLite is suitable for a classroom/demo deployment. For production-scale use, move the database to a managed database.
- Sensor readings are educational data and must not be treated as medical diagnosis.
