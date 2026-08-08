# BursaTrack

BursaTrack is a dividend portfolio tracker for Bursa Malaysia (the Malaysian stock exchange). It tracks what stocks you own, what you actually paid for them (including brokerage fees), and the dividends you've received — and shows you your true dividend yield.

This README explains **how the project works**, aimed at someone who is new to software engineering and wants to understand how Python is used to build a real web application. It's written so you can read a paragraph here, then go open the file it points to and see the real code for yourself. Two parts: the **Backend** first (it's the foundation everything else depends on), then the **Frontend**.

If you just want to run the project, see [Running this project locally](#running-this-project-locally) at the bottom.

---

## Backend

The backend is a Python program that runs on a server. It never draws anything on screen — its only job is to store data permanently and answer questions about it when asked. "Answering questions" happens over the internet using **HTTP**, the same protocol your browser uses to load web pages. A backend that answers HTTP questions with structured data (rather than a webpage) is usually called an **API** (Application Programming Interface).

Concretely: when you click "Log In" on BursaTrack, the browser sends an HTTP request like `POST /auth/login` with your email and password. The backend checks the password, and sends back an HTTP response — some JSON data (`{"user": {...}}`) plus a status code (`200` for success, `401` for wrong password). The backend never knows or cares what the button looked like; it only deals with requests and responses.

### The big picture: how one request flows through this backend

Take a concrete example — loading your dashboard. Here's the exact path a request takes, top to bottom:

1. Your browser sends `GET /api/v1/portfolio/dashboard`.
2. [`backend/app/main.py`](backend/app/main.py) is where the FastAPI application is created and where every URL is connected ("routed") to the Python code that should handle it.
3. That URL is handled by a function in [`backend/app/portfolio/router.py`](backend/app/portfolio/router.py) (search for `get_dashboard`). This file is the **HTTP layer** — it only deals with "what did the request ask for, what status code / JSON do I send back."
4. The router function doesn't contain any real logic itself — it calls into [`backend/app/portfolio/service.py`](backend/app/portfolio/service.py), the **business logic layer**. This is where the actual rules live: "add up all this user's positions," "compute their all-in cost," etc.
5. The service layer reads and writes data through **models** — Python classes that represent database tables, defined in files like [`backend/app/portfolio/models.py`](backend/app/portfolio/models.py). It never writes raw SQL; it works with Python objects, and a library called SQLAlchemy translates that into SQL behind the scenes.
6. The result flows back up: service → router → turned into JSON → sent back to the browser as the HTTP response.

This **router → service → models** pattern repeats for almost everything the backend does. Once you recognize it in one file, you'll recognize it everywhere.

### Key models — the "nouns" of the app

A **model** here means a Python class that represents one row of one database table — literally "the shape of the data." Every model in this project lives in a `models.py` file and inherits from `Base` ([`backend/app/database.py`](backend/app/database.py)), which is what tells SQLAlchemy "this class is a database table."

These are the models that make up the actual product:

| Model | File | What it represents in plain English |
|---|---|---|
| `User` | [`app/auth/models.py`](backend/app/auth/models.py) | One person's account — email, a *hashed* password (the real password is never stored, see below), whether their email is verified, and which subscription state they're in (`trial`, `active`, etc). |
| `BrokerConfig` | [`app/portfolio/models.py`](backend/app/portfolio/models.py) | A brokerage firm's fee structure (e.g. "Maybank charges 0.1% per trade, minimum RM8"). Used to calculate what you actually paid, not just the share price. |
| `Portfolio` | [`app/portfolio/models.py`](backend/app/portfolio/models.py) | One per user — basically a folder that holds all of that user's `Position`s. |
| `Position` | [`app/portfolio/models.py`](backend/app/portfolio/models.py) | One stock you own, e.g. "I hold CIMB shares." Has a `stock_code`, a `category_tag`, and belongs to a `Portfolio`. |
| `Lot` | [`app/portfolio/models.py`](backend/app/portfolio/models.py) | One *purchase event* of a `Position`. If you bought CIMB shares on three separate occasions, that's three `Lot` rows under one `Position` — each with its own share count, price, and fees. This is what makes "true all-in cost" possible. |
| `DividendTranche` | [`app/portfolio/models.py`](backend/app/portfolio/models.py) | One dividend payment you received for a `Position` — amount per share, how many shares qualified, and the payment date. |
| `PriceSnapshot` | [`app/pricing/models.py`](backend/app/pricing/models.py) | A stock's price on a given day — either fetched automatically or entered manually when the automatic fetch fails. |
| `AuditLog` / `SystemConfig` | [`app/admin/models.py`](backend/app/admin/models.py) | Internal bookkeeping, not user-facing data. `AuditLog` records "who did what, when" (for security). `SystemConfig` stores small settings (like a price-alert threshold) that can change without redeploying code. |

The relationships chain together like this:

```
User → Portfolio → Position → Lot            (a purchase)
                             → DividendTranche (a payment received)
```

One user has one portfolio; one portfolio has many positions; one position has many lots and many dividend tranches. This "one thing has many of another thing" relationship is expressed with a foreign key — e.g. open [`app/portfolio/models.py`](backend/app/portfolio/models.py) and look at `Lot.position_id`: it's a column that stores *which* `Position` this lot belongs to.

### The technology: FastAPI

[FastAPI](https://fastapi.tiangolo.com/) is the Python framework this backend is built on. Here's what it actually gives you, with real examples from this codebase:

**1. It turns Python type hints into automatic request validation.**
Look at [`backend/app/auth/schemas.py`](backend/app/auth/schemas.py) — `RegisterRequest` is a small class describing exactly what a registration request must look like: an `email` that's a valid email address, a `password` that's 8–128 characters. These are called **Pydantic schemas** (a different concept from the SQLAlchemy *models* above — schemas describe the shape of data going in/out over HTTP; models describe a database table). If a request doesn't match, FastAPI rejects it automatically, before your own code ever runs.

**2. Routes connect a URL + HTTP method to a Python function.**
Open [`backend/app/auth/router.py`](backend/app/auth/router.py) and find:
```python
@router.post("/register", response_model=AuthResponse, status_code=201)
async def register(payload: RegisterRequest, ...):
```
The `@router.post("/register", ...)` line is a **decorator** — it tells FastAPI "when a `POST /register` request arrives, call this function." `payload: RegisterRequest` means FastAPI will automatically parse the incoming JSON into a validated `RegisterRequest` object and hand it to you — you never manually parse JSON anywhere in this codebase.

**3. `async`/`await` let the server handle many requests at once without blocking.**
Every route function here is declared `async def`. In plain terms: while one request is waiting on something slow (like a database query), Python can go work on a *different* request instead of just sitting idle. You'll see `await db.execute(...)` throughout [`backend/app/portfolio/service.py`](backend/app/portfolio/service.py) — that `await` is the "pause here, but let other work happen" point.

**4. Dependency Injection (`Depends`) supplies things a route needs, automatically.**
Look at [`backend/app/auth/dependencies.py`](backend/app/auth/dependencies.py)'s `get_current_user` function. It reads the session cookie, checks it's a valid login, and returns the logged-in `User`. Any route that needs to know "who is calling this?" just writes `current_user: User = Depends(get_current_user)` in its function signature — FastAPI runs `get_current_user` first and hands the result in. The same pattern supplies a database connection everywhere via `db: AsyncSession = Depends(get_db)` (defined in [`backend/app/database.py`](backend/app/database.py)). This is why you'll never see a route function that fetches its own DB connection or manually re-checks a cookie — it's handled once, centrally, and reused everywhere.

**5. SQLAlchemy is the ORM (Object-Relational Mapper) — it turns Python objects into SQL.**
An ORM lets you write `select(Position).where(Position.portfolio_id == portfolio.id)` in Python instead of writing raw SQL (`SELECT * FROM positions WHERE portfolio_id = ...`). Every model file (`models.py`) defines what a table looks like; [`backend/app/portfolio/service.py`](backend/app/portfolio/service.py) is full of real, working examples of querying with it.

**6. Alembic tracks how the database schema changes over time.**
Every time a model changes (a new column, a new table), a small Python script describing that change is added to [`backend/alembic/versions/`](backend/alembic/versions/). Running `alembic upgrade head` applies every change in order — this is how the database structure itself is version-controlled, the same way the code is version-controlled with git.

**7. Configuration lives in environment variables, not in the code.**
[`backend/app/config.py`](backend/app/config.py) defines a `Settings` class — things like the database connection string or secret keys are read from the environment (see [`backend/.env.example`](backend/.env.example) for the full list) rather than hardcoded, so the same code can run locally, in tests, and in production with different values.

**8. Tests live in `backend/tests/`, one file per feature area.**
E.g. [`backend/tests/test_auth_login.py`](backend/tests/test_auth_login.py) tests the login endpoint end-to-end — it makes a real (simulated) HTTP request and checks the real response, without needing a browser or a real database. Run them with `uv run pytest` from `backend/`.

### Suggested reading order

If you want to trace one real feature start to finish, read these in order:
1. [`backend/app/main.py`](backend/app/main.py) — the entry point; see how everything gets wired together.
2. [`backend/app/auth/models.py`](backend/app/auth/models.py) — the `User` table.
3. [`backend/app/auth/schemas.py`](backend/app/auth/schemas.py) — what a register/login request must look like.
4. [`backend/app/auth/router.py`](backend/app/auth/router.py) — the actual `/auth/*` endpoints.
5. [`backend/app/auth/service.py`](backend/app/auth/service.py) — the real logic (hashing passwords, creating a session).
6. [`backend/app/database.py`](backend/app/database.py) and [`backend/app/config.py`](backend/app/config.py) — how the database connection and settings are set up.

---

## Frontend

The frontend is the part that runs in *your browser*, not on the server — it's what you actually see and click on. It's built with **Next.js** (a framework built on top of React) and **TypeScript** (JavaScript with type-checking added, similar in spirit to the type hints FastAPI uses on the backend).

### How it's organized

- [`frontend/src/app/`](frontend/src/app/) — Next.js's "App Router": **each folder is one URL**. [`app/dashboard/page.tsx`](frontend/src/app/dashboard/page.tsx) is the `/dashboard` page, [`app/login/page.tsx`](frontend/src/app/login/page.tsx) is `/login`. [`app/positions/[id]/page.tsx`](frontend/src/app/positions/%5Bid%5D/page.tsx) uses square brackets to mean "this part of the URL is a variable" — it handles any URL like `/positions/abc-123`.
- [`frontend/src/components/`](frontend/src/components/) — reusable pieces of *UI* (buttons, dialogs, forms) shared across multiple pages.
- [`frontend/src/hooks/`](frontend/src/hooks/) — reusable pieces of *logic*. In React, a "hook" is a function starting with `use` that a component calls to get data or behavior — e.g. [`hooks/useDashboard.ts`](frontend/src/hooks/useDashboard.ts) fetches the portfolio data and keeps it current.
- [`frontend/src/lib/`](frontend/src/lib/) — plain helper code with no UI in it: [`lib/api.ts`](frontend/src/lib/api.ts) (talks to the backend), [`lib/auth-context.tsx`](frontend/src/lib/auth-context.tsx) (tracks login state app-wide), plus calculators and form validators.

### How the frontend talks to the backend

Every piece of real data on screen came from an HTTP request to the FastAPI backend described above. [`lib/api.ts`](frontend/src/lib/api.ts) is the one place that actually calls `fetch()` — every other file goes through it, so things like "always send the session cookie" or "handle an error response consistently" only need to be written once.

A concrete example, start to finish: [`hooks/useDashboard.ts`](frontend/src/hooks/useDashboard.ts) calls `apiFetch("/api/v1/portfolio/dashboard")` — the exact same endpoint traced through the backend section above. It uses a library called **SWR** ("stale-while-revalidate") to cache that data and automatically re-fetch it when useful (e.g. when you switch back to the browser tab). [`app/dashboard/page.tsx`](frontend/src/app/dashboard/page.tsx) then calls `useDashboard()` and renders whatever comes back — it never calls `fetch` directly itself.

### Staying logged in

[`lib/auth-context.tsx`](frontend/src/lib/auth-context.tsx) wraps the entire app and keeps track of "is someone logged in right now," including silently refreshing the session in the background before it expires. [`components/auth/AuthGate.tsx`](frontend/src/components/auth/AuthGate.tsx) is used on pages that require a login — it blocks the page from rendering until that check has actually completed.

### Suggested reading order

1. [`frontend/src/app/layout.tsx`](frontend/src/app/layout.tsx) — the root layout every page shares.
2. [`frontend/src/lib/auth-context.tsx`](frontend/src/lib/auth-context.tsx) — how login state is tracked.
3. [`frontend/src/app/login/page.tsx`](frontend/src/app/login/page.tsx) and [`components/auth/LoginForm.tsx`](frontend/src/components/auth/LoginForm.tsx) — a real page + the form it renders.
4. [`frontend/src/lib/api.ts`](frontend/src/lib/api.ts) — the one place HTTP requests actually happen.
5. [`frontend/src/app/dashboard/page.tsx`](frontend/src/app/dashboard/page.tsx) and [`frontend/src/hooks/useDashboard.ts`](frontend/src/hooks/useDashboard.ts) — a full page fetching and rendering real backend data.

---

## Running this project locally

The whole stack (backend + frontend + database) runs via Docker Compose:

```bash
cp backend/.env.example backend/.env      # then fill in the values described inside
cp frontend/.env.example frontend/.env.local
docker compose up
```

Frontend: http://localhost:3000 · Backend: http://localhost:8000 · Backend health check: http://localhost:8000/health
