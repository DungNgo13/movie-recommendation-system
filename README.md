# 🎬 Movie Streaming & Recommendation System

## 📌 Project Overview
A full-stack, production-quality movie streaming web application engineered with a centralized content-based recommendation system. The platform elegantly handles multi-tiered user authentication, allowing users to autonomously build watch histories, save favorites, and receive personalized localized recommendations while granting elevated staff privileges to manage film catalogs and observe aggregated system logs.

---

## 🚀 Features

### 👤 User Features
- **Secure Authentication:** Handled via stateless JWT tokens; no rogue memory storage. Clean register-to-login transitions mapping strictly to RBAC.
- **Dynamic Catalog:** Paginated movie browsing containing high-res posters, descriptions, and dynamic sorting matrices (A-Z, Release Dates).
- **Favorites & History:** Asynchronous, persistent user tracking of `Continue Watching` states mapped natively inside the persistent store.
- **Live Search Filtering:** Real-time cascading UI input filtering traversing titles seamlessly.
- **Rating Matrix:** Interactive star-rating evaluations securely mapping back to backend aggregators.

### 🛡️ Admin Features (Elevated JWTs)
- **Advanced Dashboard Metrics:** Low-overhead live-aggregation arrays outputting holistic system statistics (Totals for Users, Movies, Favorites, Logs).
- **Action Auditing Ecosystem:** Persistent `AdminAuditLog` tracking all role mutations, and specific catalog alterations synchronously preventing untracked system creep.
- **Robust RBAC Guardrails:** Built-in core logic preventing self-deprecating actions that could inadvertently strip the system's "last remaining admin".
- **Dynamic User Management:** Deep inline user mutation forms with instant React-state hydration arrays mapping backend changes back to the client immediately.
- **Scalable Movie CRUD Control:** Intuitive creation portals mapping generic film metrics against core REST architecture with robust safety deletions.

### 🤖 Recommendation System
The built-in engine leverages a robust **Content-Based Filtering** algorithm processed responsively at the client tier.
- **Scoring Profile:** Identifies thematic correlations using keyword extractions (e.g. `title` substring overlays omitting explicit syntax stop-words).
- **Release Proximity Weighting:** Adds aggressive heuristic bonuses for films released sequentially within identical or neighboring calendar years.
- **Cold-Start Handling:** Naturally cascades gracefully defaulting back to the newest, globally top-rated feature pools without breaking the UX sequence if history is null.
- *(Note: In highly-scaled production topologies containing >10,000 films traversing TF-IDF/Cosine Similarity NLP arrays, this filtering array must migrate to the Vector backend database queries).*

---

## 🧠 Tech Stack

### Frontend Architecture
- **React 19** + **TypeScript**
- **Vite** — HMR Build tooling with minimal-footprint asset rendering.
- **React Router v7** — Core declarative sub-routing hierarchies (`ProtectedAdminRoutes`).
- **Vitest** — High velocity Unit/Integration boundaries.

### Backend Infrastructure
- **FastAPI** — High-performance Async Python REST backbone.
- **SQLAlchemy** — Deeply-integrated Pythonic ORM.
- **PostgreSQL / SQLite** — Agnostic dialect databases wrapped securely inside SQLAlchemy schemas.
- **Pydantic** — Bullet-proof serializing type validations explicitly rejecting loosely shaped frontend injections.
- **JWT (Passlib/Bcrypt)** — Cryptographically salted stateless authing mechanisms.

---

## ⚙️ How to Run Project

### Prerequisites
- **Node.js** >= 18.x
- **Python** >= 3.10
- **PostgreSQL** or **SQLite** (Default fallback for seamless Dev mode).

### 1. Backend Engine
```bash
cd backend
python -m venv venv
# Activate VENV (Windows: venv\Scripts\activate, Unix: source venv/bin/activate)

pip install -r requirements.txt
python -m uvicorn app.main:app --reload
```
*API Base Path executes live on **http://localhost:8000** with dynamic Swagger UI mounted natively at **http://localhost:8000/docs**.*

### 2. Frontend Terminal
```bash
cd frontend
npm install
npm run dev
```
*The React compiler resolves strictly and hosts the web interface live at **http://localhost:5173**.*

---

## 👑 Admin Account Setup

By default, the API shields the manual creation of Administrator boundaries within the frontend registration portals. Assuming normal operations during a first-time local setup:
```bash
cd backend

# Option 1: Execute the native Database Seeding function included within the package:
python -m app.seed
# This creates a baseline dataset alongside an administrative bypass.

# Option 2: Elevating via custom CLI script if packaged:
# Execute target CLI commands or directly inject value 'admin' via standard DB management schemas inside the `users` table for the target UUID.
```

---

## 📡 API Overview (Brief)

| Endpoint Prefix | Description | Auth Scope |
| :--- | :--- | :--- |
| **`/api/v1/auth/*`** | Handles stateless JWT Bearer token generation, decoding `me`, and native `register` routes. | `Public` / `User` |
| **`/api/v1/movies/*`** | Core RESTful movie aggregators handling Paginated `GET` requests spanning the entire catalog and specific `UUID` lookup endpoints. | `Public` |
| **`/api/v1/favorites/*`** | Synchronized state tracking resolving user-bound movie `UUIDs` across persistent storage states. | `User` |
| **`/api/v1/admin/*`** | Sensitive multi-table aggregates containing endpoints for User Role mutations (`PATCH`), system configurations, and Audit Logs. | `Admin` |

---

## 📸 Screenshots

| View Type | Placeholder Image |
| :--- | :--- |
| **Homepage Layout** | `![Homepage Overview](/assets/home_overview_placeholder.png)` |
| **Admin Dashboard** | `![Admin Dashboard Metrics](/assets/admin_dashboard_placeholder.png)` |
| **Recommendations** | `![Recommendation Sequence](/assets/recommendation_engine_placeholder.png)` |

---

## ⚠️ Known Limitations
- **Memory Scaling Bound:** Currently, `get_all_users` on the backend explicitly enforces a `.limit(100)` throttle to completely circumvent RAM bloat or 503 gateway timeouts, bypassing the current lack of dedicated `skip/limit` pagination implementations on the Admin User Table grid.
- **Client-Side Heavy Search Arrays:** The generic keyword algorithm runs via React `useMemo` inline computations rendering UI blocks instantly, but theoretically incurs main-thread degradation limits above extremely heavy 100kb payload returns.
- **Race Condition Mitigations:** Explicit `setTimeout` delays securely decouple `<ProtectedRoute>` aggressive kicks during Admin logouts, circumventing hard crashes inherently present in React Router sub-trees unmounting asynchronously against Context States.
