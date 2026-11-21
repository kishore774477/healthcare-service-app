# Healthcare Service Application (HSA)

A web platform where patients register, log in securely, and book, view, cancel or reschedule appointments with healthcare providers. An admin approves and manages appointments and keeps track of provider schedules and availability.

Built for **21CSC303J – Software Engineering and Project Management** (SRM Institute of Science and Technology, Department of Computing Technologies) and aligned with **SDG 3: Good Health & Well-Being**.

## Features

| Sprint | User story | What's implemented |
|---|---|---|
| 1 | US01 Register | Username, email and password with confirmation. All fields are validated, emails must be unique, and passwords are hashed (Werkzeug). |
| 1 | US02 Login / logout | Flask-Login sessions, "remember me", and logout by POST protected with a CSRF token. |
| 1 | US03 Book appointment | Pick a provider and date, then choose from **live available slots**. Double-booking, past slots and non-working days are blocked. |
| 2 | US04 Manage / cancel | "My Appointments" page with cancel and a confirmation dialog. Patients can only touch their own appointments. |
| 2 | US05 History / upcoming | Upcoming and History tabs showing provider, date, time and status. |
| 2 | US06 Reminders | The dashboard highlights every appointment in the next 24 hours, and the navbar shows a badge. |
| 2 | US07 Reschedule | Move to a new free slot. Provider availability is checked again and a confirmation is shown. |
| 3 | US08 Admin management | Approve, cancel, reschedule, or mark appointments completed, with filters by status, provider and date. |
| 3 | US09 Schedule monitoring | Day-by-day slot grid per provider (free or booked plus utilisation). Add, edit, activate or deactivate providers and set their hours, slot length and working days. |

**Appointment statuses:** `Pending` (just booked) → `Confirmed` (admin approved) → `Completed`, or `Cancelled`. An active appointment whose time has passed shows as `Overdue`.

## Tech stack

- **Backend:** Python, Flask, Flask-Login, Flask-WTF (forms and CSRF), Flask-SQLAlchemy
- **Database:** SQLite (`instance/hsa.db`, created automatically)
- **Frontend:** Jinja2 templates, Bootstrap 5, Bootstrap Icons, a small vanilla-JS slot loader
- **Tests:** pytest (32 functional tests that cover every user story)

## Getting started

Requires Python 3.10+.

```bash
git clone https://github.com/kishore774477/healthcare-service-app.git
cd healthcare-service-app

python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate

pip install -r requirements.txt
python run.py
```

Open http://127.0.0.1:5000.

On first run the database is created and seeded with 5 providers and two demo accounts:

| Role | Username | Password |
|---|---|---|
| Admin | `admin` | `Admin@123` |
| Patient | `demo` | `Demo@1234` |

> Change these before deploying anywhere. Set `HSA_ADMIN_USERNAME`, `HSA_ADMIN_EMAIL` and `HSA_ADMIN_PASSWORD` before the first run, and always set a strong `SECRET_KEY`.

### Configuration (environment variables)

| Variable | Default | Purpose |
|---|---|---|
| `SECRET_KEY` | `dev-only-change-me` | Session signing key. **Set this in production.** |
| `DATABASE_URL` | `sqlite:///instance/hsa.db` | Any SQLAlchemy URL (for example PostgreSQL). |
| `HSA_ADMIN_USERNAME` / `HSA_ADMIN_EMAIL` / `HSA_ADMIN_PASSWORD` | `admin` / `admin@hsa.local` / `Admin@123` | Seeded admin account. |
| `HOST`, `PORT`, `FLASK_DEBUG` | `127.0.0.1`, `5000`, `1` | Dev server settings. |

To reset the database:

```bash
flask --app run init-db --reset
```

## Running tests

```bash
pytest
```

## Project structure

```
app/
  __init__.py      # app factory, template helpers, error pages, CLI
  models.py        # User, Provider, Appointment
  services.py      # slot generation, availability, reminders
  scheduling.py    # shared booking / reschedule logic + /api slots endpoint
  auth.py          # register, login, logout
  patient.py       # dashboard, book, my appointments, cancel, reschedule
  admin.py         # admin dashboard, appointments, schedule, providers
  forms.py         # Flask-WTF forms
  seed.py          # default admin, demo patient, providers
  templates/       # Jinja2 + Bootstrap pages
  static/          # CSS and slot-loading JS
tests/             # pytest functional tests
run.py             # entry point
```

## Security notes

- Passwords are stored only as salted hashes.
- Every form, including logout and the cancel and approve buttons, carries a CSRF token.
- Role checks: patients get `403` on admin pages and `404` on other patients' appointments.
- Login redirects only follow relative `next` URLs, which prevents open redirects.
- Session cookies are `HttpOnly` and `SameSite=Lax`.

## Future enhancements

Email/SMS reminders, teleconsultation, PostgreSQL/MySQL for larger deployments, analytics dashboards for appointment trends, and integration with wearable devices.

## Team

Lakshminarayanan K · Harish C · Kishore Kumar S · Srinithish S M. Guided by Dr. Arthi B.
