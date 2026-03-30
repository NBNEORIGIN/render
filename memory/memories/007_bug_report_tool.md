# Bug report tool — email via IONOS SMTP
Tags: bug report email smtp ionos modal
Date: 2026-03-30

## Feature

A "🐛 Report a Bug" button in the top-right corner of the header opens a modal.
Users fill in: their name, what they were doing, and what went wrong.
On submit, an email is sent to toby@nbnesigns.com and gabby@nbnesigns.com.

## Implementation

Frontend: modal in `templates/index.html`, JS `submitBugReport()` posts to `/api/bug-report`.

Backend: `/api/bug-report` in `app.py`:
- Uses Python's built-in `smtplib` (no extra dependency)
- STARTTLS on port 587
- Sender identity from session (`session['user_email']`) included in body
- Subject: `[Render] Bug report from <name>`

SMTP config via env vars:
- `SMTP_HOST` = smtp.ionos.co.uk
- `SMTP_PORT` = 587
- `SMTP_USER` = toby@nbnesigns.com
- `SMTP_PASSWORD` = (IONOS account password)

Recipients hardcoded in `config.BUG_REPORT_RECIPIENTS`:
```python
BUG_REPORT_RECIPIENTS = ["toby@nbnesigns.com", "gabby@nbnesigns.com"]
```
