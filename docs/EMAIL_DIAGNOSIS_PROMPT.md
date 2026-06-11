# ECL Platform — Email Sending: Full Diagnosis, Fix, and Verification

## Who You Are

You are a senior-level software engineer and platform architect with deep expertise in Python backends (FastAPI, Celery, SQLAlchemy), email delivery systems (SMTP, Gmail App Passwords, fastapi-mail), distributed task queues (Celery + Redis), and Next.js frontends (NextAuth, server actions). You also have strong operational instincts — you do not just write code that looks correct, you instrument it, run it, watch the logs, and confirm with your own eyes that it works.

Your job in this task is threefold: be a careful diagnostician, be a precise engineer who fixes what is broken without unnecessary changes to what works, and be a quality-obsessed verifier who does not call something done until the email actually arrives in the inbox (or a controlled test proves the full flow runs).

---

## The Problem

The ECL platform has a complete user registration and authentication system. When a new user signs up, the backend is supposed to send a verification email to their email address. The user is redirected to a "Check your email" page in the frontend. They never receive the email. There is no error shown to the user. The problem is invisible.

The project uses Google Gmail SMTP credentials configured in the backend environment. The frontend also has a "resend email" button with a 60-second countdown that triggers the resend endpoint. None of this is working — no email is ever delivered.

You need to find every single reason this is broken, fix all of them, add logging that makes the terminal clearly show whether emails succeed or fail, and then test and verify the full flow from account creation to email delivery.

### Important Clarification: Verification Email vs Welcome Email

Signup sends a **verification email** (template: verify_email.html) with a link to /verify-email?token=... — NOT a welcome email. The **welcome email** (template: welcome.html) with a dashboard link is sent only after onboarding is completed. If the user expects a welcome email at signup, they are looking for the wrong email — but if verification email also never arrives, the entire auth flow is blocked.

---

## Project Structure Overview

There are two separate sub-projects:

The backend is at ECL-Server. It is a Python FastAPI application using SQLAlchemy with async PostgreSQL (Neon), Celery with Redis as a broker and result backend, fastapi-mail for SMTP email sending, Jinja2 for HTML email templates, and structlog for logging.

The frontend is at ECL-Web. It is a Next.js 16 application using NextAuth v5 for session management, server actions for API calls, and Tailwind CSS with Radix UI components.

---

## Your First Task: Read and Understand Before You Touch Anything

Before making any changes, read every relevant file carefully. Do not assume you know what is in a file based on its name. Read the actual content. The files you must read and fully understand are listed below.

In ECL-Server, read these files:

The main application entry point at app/main.py to understand how FastAPI is initialized and what middleware and routers are registered.

The configuration file at app/config.py (NOT app/core/config.py — that path does not exist) to understand every SMTP-related setting, how it reads from environment variables, and what the defaults are.

The email sending utility at app/core/email.py to understand the send_email function, how fastapi-mail is configured, what the ConnectionConfig object looks like, and whether SUPPRESS_EMAIL_SEND is respected correctly.

The database session helper at app/database.py to understand that get_db commits AFTER the route handler returns — this matters because email tasks are dispatched before commit.

The Celery application setup at app/tasks/celery_app.py to understand the broker URL, result backend URL, task serializer, timezone, soft time limits, and whether CELERY_TASK_ALWAYS_EAGER is wired up correctly.

All email task definitions in app/tasks/email_tasks.py. Read every task function. Understand how the async inner function pattern works (tasks that wrap asyncio.run or a thread-pool fallback via _run), how exceptions are caught, what gets logged, and what retry logic exists.

The auth service at app/modules/auth/service.py. Focus specifically on the register_user function. Read the exact lines where the email verification token is created and where the Celery task is dispatched. Read the try-except wrapper around the task dispatch. Understand exactly what happens if Celery is unreachable or if the task fails.

The onboarding service at app/modules/onboarding/service.py to see when send_welcome_email is dispatched (after onboarding completion, not at signup).

The auth router at app/modules/auth/router.py to see the registration endpoint, the resend-verification endpoint, and the verify-email endpoint.

The environment file at .env to see the exact values of SMTP_HOST, SMTP_PORT, SMTP_USERNAME, SMTP_PASSWORD, SMTP_FROM_EMAIL, SMTP_FROM_NAME, SMTP_TLS, FRONTEND_URL, CELERY_TASK_ALWAYS_EAGER, SUPPRESS_EMAIL_SEND, and REDIS_CELERY_URL.

The verification email template at app/templates/verify_email.html to understand what context variables it expects and what the verification link looks like.

The welcome email template at app/templates/welcome.html to understand what context variables it expects and what the dashboard link looks like.

The base email template at app/templates/base_email.html to understand the email layout.

The Makefile to understand what commands exist to start the server, the Celery worker, and Redis.

The Docker configuration in the docker directory to understand how Redis is run and on what port (6380, not default 6379).

The pyproject.toml to understand all dependencies including which version of fastapi-mail, celery, and redis-py are installed.

The test configuration at tests/conftest.py to understand how tests override the email settings (CELERY_TASK_ALWAYS_EAGER=true and SUPPRESS_EMAIL_SEND=true — tests never hit real SMTP).

In ECL-Web, read these files:

The signup page at src/app/(auth)/sign-up/page.tsx and the SignUpForm component at src/components/auth/SignUpForm.tsx to understand the form fields and submit logic.

The server actions file at src/app/actions/auth.ts to understand signUpAction, resendVerificationAction, and verifyEmailAction — specifically what API endpoints they call, what request bodies they send, and how they handle errors.

The verify email pending page at src/app/(auth)/verify-email-pending/page.tsx and the VerifyEmailPendingForm component at src/components/auth/VerifyEmailPendingForm.tsx to understand what the user sees after signup.

The ResendCountdown component at src/components/auth/ResendCountdown.tsx to understand the resend button behavior.

The VerifyEmailHandler component that handles the token link click.

The TermsCheckbox component — Radix Checkbox may not populate FormData for server actions.

The middleware at middleware.ts and src/lib/auth.config.ts to understand how unverified users are redirected.

The environment file at .env.local to verify BACKEND_URL points to the correct backend URL.

---

## Your Second Task: Diagnose Every Failure Point

After reading all files, you must identify and document every failure point in the system. You are looking for failures at every layer.

At the infrastructure layer, determine whether Redis is running. The Celery broker in the backend uses Redis. If Redis is not running, every single email task dispatch silently fails. The try-except around the dispatch only logs a warning and lets registration succeed — the user never gets an email and never knows why. Check whether Redis is configured to run on port 6380 (not the default 6379). Check whether Docker or a local Redis instance is used and whether it is actually running. Determine what command starts it and whether it is being started as part of the development workflow.

At the Celery layer, determine whether the Celery worker is running as a separate process. The FastAPI server does not execute Celery tasks — it only enqueues them. A separate Celery worker process must be running, consuming the queue from Redis, and executing the tasks. If the worker is not running, tasks accumulate in Redis (or are dropped if Redis is also down) and no emails are sent. Check whether the Makefile has a command to start the worker. Check whether there is any documentation about running the worker during development. Determine whether CELERY_TASK_ALWAYS_EAGER is set to false in development — if it were true, tasks would run synchronously in the same process without needing a separate worker, which is useful for local testing.

At the task execution layer, examine how the email tasks handle async code inside Celery tasks. Celery tasks are synchronous by default but the inner send_email function is async. Determine whether the pattern used (_run with asyncio.run or thread pool fallback) is correct and compatible with the installed versions of Celery and Python. A common failure is that async tasks are structured incorrectly and raise exceptions that are silently caught.

At the database commit layer, examine whether email tasks are dispatched before the user row is committed to the database. register_user calls send_verification_email.delay before the route handler returns, but get_db only commits after the handler completes. The task retries 3 times at 2-second intervals if the user is not found, but this race can still cause failures especially in eager mode.

At the SMTP layer, examine the Gmail configuration. Gmail SMTP requires either an App Password (when 2-Step Verification is enabled) or specific configuration. The app password in the environment must be a 16-character password generated specifically from Google's app password management page, not the Gmail account's regular password. Determine whether SMTP_TLS=true with port 587 is the correct fastapi-mail configuration for Gmail's STARTTLS behavior. Understand the difference between STARTTLS (port 587) and SSL/TLS (port 465) and whether fastapi-mail's ConnectionConfig USE_TLS and MAIL_STARTTLS fields are being set correctly. MAIL_STARTTLS=True and MAIL_SSL_TLS=False is correct for port 587.

At the template layer, determine whether the verify_url being constructed in the email task is valid. It should produce a URL like http://localhost:3000/verify-email?token=the-raw-token-string. Verify that FRONTEND_URL in the .env matches the URL where the frontend is actually running. Verify that the /verify-email route exists in the Next.js app and that the VerifyEmailHandler component correctly extracts the token from the query string and calls the backend.

At the logging layer, determine whether there is any visible indication in the FastAPI server logs or the Celery worker logs when an email is successfully dispatched, when a task is picked up, when SMTP connection is attempted, or when a send fails. If the logging produces no visible output for email events, the developer has no way to know whether anything is happening.

At the frontend layer, determine whether resendVerificationAction swallows all errors and always returns success. Determine whether clicking the verification link without an active session causes a redirect to sign-in instead of onboarding.

---

## Your Third Task: Fix Everything

After diagnosing every failure point, fix all of them. Here is what must be fixed or added, organized by area. Apply judgment — if something is already working correctly, do not change it. Only fix what is broken.

Regarding the Celery and Redis infrastructure: if Redis and the Celery worker need to be started manually, add this clearly to the Makefile so there is a single command developers run to start the full development stack including the FastAPI server, the Celery worker, and Redis. If Docker is used for Redis, ensure the docker-compose file correctly maps port 6380. If CELERY_TASK_ALWAYS_EAGER is not set in the development .env and there is no Celery worker running, consider setting it to true for local development so emails execute synchronously and do not require a separate worker process — but only do this if it will not break other functionality.

Regarding dispatch timing: defer email task dispatch until after the database transaction commits. Use an after_commit hook on the SQLAlchemy session so send_verification_email.delay runs only after the user row is visible to the Celery worker.

Regarding the email sending code in app/core/email.py: the send_email function must log clearly at every important moment. When it starts attempting to send, log the recipient address, the template name, and the subject. When the ConnectionConfig is created, log the SMTP host and port. When the send succeeds, log a clear success message including the recipient. When the send fails, log the full exception with exc_info=True, the SMTP host, and the recipient. This logging must appear in the terminal so a developer watching the Celery worker logs can see exactly what is happening. Do not swallow exceptions silently.

Regarding the Gmail SMTP configuration: verify that the fastapi-mail ConnectionConfig is set up correctly for Gmail. For port 587 with STARTTLS, the ConnectionConfig must have MAIL_STARTTLS=True and MAIL_SSL_TLS=False. For port 465 with SSL, it must have MAIL_STARTTLS=False and MAIL_SSL_TLS=True. These are mutually exclusive. Fix this explicitly to match the Gmail SMTP requirements for port 587.

Regarding exception handling in email_tasks.py: the current pattern catches all exceptions at the end and logs a warning. This means an SMTP authentication failure, a connection timeout, and a template rendering error all produce identical silent failures. Update the exception handling to distinguish between categories of errors: connection errors and SMTP auth errors should be logged as critical errors with full details; template errors should be logged differently; retry logic should be applied to transient network errors but not to auth errors (since retrying an auth error 3 times is useless and produces noise). Log success when email sends.

Regarding the async pattern in Celery tasks: if the inner async function pattern is causing issues, ensure _run is called correctly. Verify this is not interfering with the event loop.

Regarding the email templates: verify that the verify_email.html template correctly renders the verify_url context variable as a clickable link. Verify that the welcome.html template correctly renders the dashboard_url. Verify that the base template does not have broken CSS or layout that might cause email clients to reject the message. The links in the templates must be fully constructed with the FRONTEND_URL prefix.

Regarding the resend verification endpoint: the resend endpoint in the backend (POST /api/v1/auth/resend-verification) must also dispatch the email task after commit and log clearly. Verify it is using the same task dispatch pattern and that it also benefits from any fixes made to the task dispatch and logging.

Regarding the frontend verify-email-pending page: the card says "Check your email" and shows the user's email address. This is correct. Ensure the email address is displayed clearly and that the resend button is functional. Fix resendVerificationAction to surface errors. Fix TermsCheckbox to submit terms value in FormData. Fix VerifyEmailHandler to handle verification without an active session by redirecting to sign-in with a verified query param.

---

## Your Fourth Task: Add a Smoke Test

Create a test or test script that can be run from the terminal to verify that the full email sending pipeline is working without requiring a full signup flow.

This test should do one or more of the following: directly call the send_email function with a real test email address and verify it succeeds (this requires SMTP credentials to actually work), or mock the SMTP connection and verify that the Jinja2 template renders correctly and produces a valid HTML email with the correct verify_url, or create a Celery task test that sets CELERY_TASK_ALWAYS_EAGER=true and SUPPRESS_EMAIL_SEND=false and verifies the task executes without exceptions.

The test should be placed in the tests directory with a name like test_email_smoke.py. It should be runnable with pytest. Add a comment at the top explaining what environment variables must be set for the real SMTP version to work.

If you create a test that exercises real SMTP, add a pytest mark like @pytest.mark.smtp that allows it to be skipped by default and run explicitly when testing the live email flow: pytest tests/test_email_smoke.py -m smtp.

---

## Your Fifth Task: Verify End-to-End

After making all fixes, verify the entire flow manually using the terminal and browser.

Start all required services. This means Redis, the Celery worker, and the FastAPI server must all be running simultaneously. Check the Makefile for the correct commands. Run make up for infrastructure, uvicorn for the API, and make worker for Celery.

Register a new account through the frontend at http://localhost:3000/sign-up. Use a real email address that you can check. Watch the FastAPI server terminal — you should see log output for the registration endpoint and for the Celery task dispatch. Watch the Celery worker terminal — you should see the task being picked up, the SMTP connection attempt, and either a success log or a detailed failure log.

If the email arrives, click the verification link. Confirm you land on /setup/onboarding. Confirm the onboarding wizard loads. Confirm you can complete it and reach /dashboard. After onboarding completion, confirm the welcome email is sent.

If the email does not arrive, the Celery worker terminal must now show a clear error message explaining exactly why. Fix that error and repeat.

Do not report this task as complete until you have either received an email in the inbox or produced clear terminal evidence that the SMTP send is succeeding (for example, by checking the Celery worker output for a success log line with the recipient address).

---

## Your Sixth Task: Update Logging Across the Auth Flow

Add terminal-visible logging for the following events in ECL-Server, using the existing structlog-based logging pattern already in the codebase:

When a Celery email task is dispatched from the auth service, log the event name email_task_dispatched, the task name (for example send_verification_email), and the user ID.

When a Celery email task starts executing (inside the task function), log the task name, the user ID, and the recipient email address.

When the SMTP send_email call succeeds, log a success event with the recipient, subject, and template name.

When the SMTP send_email call fails, log a failure event with the full exception details, the recipient, and the subject.

When a task is retried, log the retry attempt number and the reason.

When a task exhausts all retries and gives up, log a critical failure event so the developer knows this email will never be sent.

These logs should appear in the standard output so they are visible in the terminal where the Celery worker is running. Do not add logs that require a separate logging service or file — stdout is sufficient for now.

---

## Your Seventh Task: Document the Development Startup Sequence

After all fixes are in place, update the ECL-Server README or the Makefile comments (whichever is more appropriate) to document the exact commands a developer must run to start the full development stack including the database, Redis, Celery worker, and FastAPI server. Make this startup sequence obvious so no developer ever loses emails in development because they forgot to start the Celery worker.

---

## Constraints and Rules

Do not change the database schema unless it is directly required to fix the email sending problem. Do not change the frontend authentication flow unless fixing resend UX, TermsCheckbox, or verify-without-session. Do not change the NextAuth configuration beyond what is needed for verify-without-session. Do not change the onboarding wizard. Do not add features that are not directly related to making email sending work correctly.

Do not add comments that explain what the code does. Only add comments where the reasoning would be non-obvious to a future developer — for example, if a specific fastapi-mail configuration field has a non-obvious requirement.

Do not use bare except clauses. Be specific about the exception types you are catching.

Preserve the existing pattern of using structlog for logging. Do not introduce a different logging library.

Do not commit changes. Leave the changes in the working tree for the developer to review.

---

## Summary of Files You Are Likely to Modify

In ECL-Server: app/core/email.py is almost certainly being modified for better logging and correct ConnectionConfig. app/config.py may need a correction if the SMTP TLS field does not map correctly to fastapi-mail. app/tasks/email_tasks.py needs better exception handling and logging. app/tasks/celery_app.py may need the CELERY_TASK_ALWAYS_EAGER setting wired in for development ease. app/modules/auth/service.py may need better logging around the task dispatch and after_commit dispatch. app/core/db_hooks.py may be new for after_commit callbacks. The Makefile needs a clear development startup command. Possibly a new tests/test_email_smoke.py file.

In ECL-Web: possibly src/app/actions/auth.ts if the resend or verify actions have bugs. src/components/auth/TermsCheckbox.tsx for FormData fix. src/components/auth/VerifyEmailHandler.tsx for no-session case. No other frontend files should need changes since the signup and redirect flow is already correct.

---

## Starting Point

Begin by reading all the files listed in the first task. Do not skip files. Read them in full. After reading, write a short internal summary of what you found at each failure layer (infrastructure, Celery, SMTP, template, logging). Then begin the fixes in order of most likely to least likely cause. After each fix, explain what you changed and why.

Run the server, watch the logs, and iterate until the email arrives or until the logs produce a clear, actionable error message for every remaining issue.
