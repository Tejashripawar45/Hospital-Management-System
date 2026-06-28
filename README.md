# Hospital Management System (HMS)

A local hospital management web app for doctor availability and patient appointment booking, with Google Calendar integration and a separate serverless email notification service.

## Features

- **Authentication** — Doctor and patient sign up / login with hashed passwords and role-based access
- **Doctor dashboard** — Create and manage personal availability slots; view bookings
- **Patient dashboard** — Browse doctors, view future unbooked slots, book appointments
- **Race-safe booking** — PostgreSQL row locking (`select_for_update`) prevents double-booking
- **Google Calendar** — OAuth2 flow; events created on both doctor and patient calendars after booking
- **Email notifications** — Serverless Python function (serverless-offline) for welcome and booking confirmation emails

## Tech Stack

| Layer | Technology |
|-------|------------|
| Backend | Django 6 |
| Database | PostgreSQL |
| Auth | Django session auth |
| Calendar | Google Calendar API + OAuth2 |
| Email service | Serverless Framework + serverless-offline |

## Project Structure

```
TASK1/
├── hms/                    # Django app (models, views, templates)
├── hms_project/            # Django project settings
├── email_service/          # Serverless email function
│   ├── handler.py
│   └── serverless.yml
├── manage.py
├── requirements.txt
└── .env                    # Copy from .env.example
```

## Prerequisites

- Python 3.11+
- Node.js 18+ (for serverless-offline)
- PostgreSQL running locally
- (Optional) Google Cloud OAuth credentials for Calendar
- (Optional) Gmail SMTP app password for real emails

## Setup

### 1. Database

Create a PostgreSQL database:

```sql
CREATE DATABASE hms;
```

### 2. Django backend

```powershell
cd TASK1
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
# Edit .env with your credentials

python manage.py migrate
python manage.py runserver
```

App runs at **http://localhost:8000**

### 3. Serverless email service

In a second terminal:

```powershell
cd email_service
npm install
npm start
```

Service runs at **http://localhost:3000/dev/send-email**

Without SMTP credentials, emails are printed to the serverless terminal (still satisfies local demo).

### 4. Google Calendar (optional)

1. Create a project in [Google Cloud Console](https://console.cloud.google.com/)
2. Enable the **Google Calendar API**
3. Create OAuth 2.0 credentials (Web application)
4. Add redirect URI: `http://localhost:8000/accounts/google/callback/`
5. Put `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET` in `.env`
6. After login, click **Link Google Calendar** in the navbar

## Demo Flow

1. Start PostgreSQL, Django (`runserver`), and serverless (`npm start`)
2. Sign up as a **doctor** → welcome email logged in serverless terminal
3. Create availability slots on the doctor dashboard
4. Sign up as a **patient** (use a different browser or incognito)
5. Select the doctor, pick a slot, book → confirmation email + calendar events (if linked)

## Design Decision: Handling Concurrent Slot Booking

### The problem

Two patients can click "Book" on the same availability slot at nearly the same time. Without coordination, both requests might read `is_booked=False` and both succeed — a classic lost-update race condition.

### Approaches considered

**Approach A — Application-level check only**  
Read the slot, verify `is_booked` is false, then save. Simple, but under concurrent requests two transactions can both pass the check before either commits.

**Approach B — Database row lock with `select_for_update()`**  
Wrap booking in `transaction.atomic()`, lock the slot row with `SELECT … FOR UPDATE`, re-check availability inside the lock, then mark booked and create the booking in the same transaction.

**Approach C — Optimistic locking with a version field**  
Add a `version` column; update only if version matches. Works, but adds schema complexity and requires retry logic in the view.

### What I chose and why

I chose **Approach B** (`select_for_update` inside `transaction.atomic()`).

PostgreSQL already serializes row-level locks — the second patient blocks until the first transaction commits, then sees `is_booked=True` and gets a clear error. This is minimal code, uses the database as the source of truth, and pairs naturally with the existing `is_booked` flag and `OneToOneField` on `Booking`. Optimistic locking would be better at very high scale with low contention, but for a local HMS demo with real correctness requirements, pessimistic locking is simpler and guarantees no double booking without retry loops.

Relevant code in `hms/views.py` → `book_slot_view`.

## API: Email Service

`POST http://localhost:3000/dev/send-email`

```json
{
  "trigger_type": "SIGNUP_WELCOME",
  "recipient": "user@example.com",
  "data": {
    "username": "jane",
    "role": "patient",
    "full_name": "Jane Doe"
  }
}
```

Supported triggers: `SIGNUP_WELCOME`, `BOOKING_CONFIRMATION`

## License

Built for a shortlisting task — local development only.
