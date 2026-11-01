Job Board Platform built with **Django** and **Django REST Framework** for the
CodeAlpha Backend Development Internship (Task 4).

## Features
- **Employers** post, edit and close job listings, and manage applications
- **Candidates** upload resumes (PDF/DOC/DOCX, max 5 MB), apply for jobs and track their status
- **Job search filters:** keyword, location, job type, company, skills, salary range, ordering
- **Application status workflow:** applied, reviewing, shortlisted, rejected, hired, withdrawn
- **Notifications:** employers are notified of new applications and withdrawals; candidates are notified of every status change
- **Reports:** per-employer statistics and platform-wide statistics for admins
- **Admin panel** for user, job and application management
- Role-based permissions, token authentication, SQLite by default (PostgreSQL supported)
- 19 automated tests

## Database models
`EmployerProfile`, `CandidateProfile`, `Resume`, `Job`, `Application`, `Notification`
(Users are Django's built-in `User`; each user has one employer or candidate profile.)

## Project structure
```
JobBoard/
├── manage.py
├── requirements.txt
├── config/                  # settings, root urls, wsgi
└── jobs/
    ├── models.py
    ├── serializers.py
    ├── permissions.py       # IsEmployer / IsCandidate
    ├── views.py             # API logic
    ├── urls.py
    ├── admin.py
    ├── tests.py
    └── management/commands/seed_jobs.py
```

## Run locally
```bash
python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt
python manage.py migrate
python manage.py createsuperuser  # admin account for /admin/
python manage.py seed_jobs        # optional: demo_employer / demo12345 + 3 jobs
python manage.py runserver
```
API: http://127.0.0.1:8000/api/ | Admin: http://127.0.0.1:8000/admin/

Run tests: `python manage.py test`

PostgreSQL (optional): set `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`,
`POSTGRES_HOST`, `POSTGRES_PORT` before `migrate`.

## API reference
Send `Authorization: Token <token>` on authenticated requests.

| Method | Endpoint | Who | Description |
|---|---|---|---|
| POST | /api/auth/signup/ | anyone | Sign up with `role`: `employer` (needs `company_name`) or `candidate` (needs `full_name`) |
| POST | /api/auth/login/ | anyone | Returns token and role |
| GET | /api/jobs/ | anyone | Search active jobs (filters below) |
| GET | /api/jobs/{id}/ | anyone | Job details |
| POST | /api/jobs/ | employer | Post a job |
| PATCH/PUT/DELETE | /api/jobs/{id}/ | owner employer | Edit, close (`is_active: false`) or delete |
| GET | /api/my/jobs/ | employer | My jobs, including closed ones |
| GET | /api/jobs/{id}/applications/ | owner employer | Applicants (`?status=`) |
| POST | /api/resumes/ | candidate | Upload resume (multipart: `title`, `file`) |
| GET | /api/resumes/ | candidate | My resumes |
| DELETE | /api/resumes/{id}/ | candidate | Delete resume |
| POST | /api/jobs/{id}/apply/ | candidate | Apply (`resume` id optional, `cover_letter`) |
| GET | /api/applications/ | candidate | Track my applications (`?status=`) |
| GET | /api/applications/{id}/ | candidate | One application |
| DELETE | /api/applications/{id}/ | candidate | Withdraw application |
| PATCH | /api/applications/{id}/status/ | owner employer | Set `status` (reviewing, shortlisted, rejected, hired) and optional `note` |
| GET | /api/notifications/ | any user | My notifications (`?unread=true`) |
| POST | /api/notifications/read/ | any user | Mark all read |
| POST | /api/notifications/{id}/read/ | any user | Mark one read |
| GET | /api/stats/employer/ | employer | Job and application statistics |
| GET | /api/stats/admin/ | staff | Platform-wide statistics |

### Job search filters
`/api/jobs/?q=django&location=chattogram&job_type=full_time&skills=python,sql&company=acme&min_salary=30000&max_salary=80000&ordering=-created_at`

### Example flow
```bash
# 1. candidate signs up
curl -X POST http://127.0.0.1:8000/api/auth/signup/ -H "Content-Type: application/json" \
  -d '{"username":"sara","email":"s@x.com","password":"strongpass123","role":"candidate","full_name":"Sara Khan"}'

# 2. upload resume
curl -X POST http://127.0.0.1:8000/api/resumes/ -H "Authorization: Token CAND_TOKEN" \
  -F "title=My CV" -F "file=@cv.pdf"

# 3. apply
curl -X POST http://127.0.0.1:8000/api/jobs/1/apply/ -H "Authorization: Token CAND_TOKEN" \
  -H "Content-Type: application/json" -d '{"cover_letter":"I would love to join."}'

# 4. employer shortlists the candidate
curl -X PATCH http://127.0.0.1:8000/api/applications/1/status/ -H "Authorization: Token EMP_TOKEN" \
  -H "Content-Type: application/json" -d '{"status":"shortlisted","note":"Interview on Monday"}'
```

Errors return `{"error": "..."}` or field errors with 400 (invalid), 401 (not logged in),
403 (wrong role), 404 (not found or not yours) and 409 (already applied).
