# Deployment Guide — Ubuntu + Nginx + FastAPI + PostgreSQL

This guide covers production deployment of the Laetus movie recommendation system.

---

## 1. Nginx Reverse Proxy Configuration

Create or update your Nginx site config (e.g. `/etc/nginx/sites-available/laetus`):

```nginx
server {
    listen 80;
    server_name laetus.io.vn;

    # Redirect HTTP to HTTPS
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl http2;
    server_name laetus.io.vn;

    # SSL certificates (Let's Encrypt / Certbot)
    ssl_certificate     /etc/letsencrypt/live/laetus.io.vn/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/laetus.io.vn/privkey.pem;

    # ─── Frontend (static files built by Vite) ─────────────────────────
    location / {
        root /var/www/laetus/frontend/dist;
        try_files $uri $uri/ /index.html;
    }

    # ─── Backend API ───────────────────────────────────────────────────
    location /api/ {
        proxy_pass http://127.0.0.1:8000;

        # CRITICAL: These headers allow the backend to see the real
        # client IP instead of 127.0.0.1 (the proxy's own address).
        proxy_set_header Host              $host;
        proxy_set_header X-Real-IP         $remote_addr;
        proxy_set_header X-Forwarded-For   $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        proxy_read_timeout 300s;
        proxy_connect_timeout 75s;
    }

    # ─── Media files (posters, HLS streams) ────────────────────────────
    location /media/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host              $host;
        proxy_set_header X-Real-IP         $remote_addr;
        proxy_set_header X-Forwarded-For   $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # ─── Legacy uploads ────────────────────────────────────────────────
    location /uploads/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host              $host;
        proxy_set_header X-Real-IP         $remote_addr;
        proxy_set_header X-Forwarded-For   $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # ─── HLS streaming — increased buffer for video segments ──────────
    location ~* \.m3u8$ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        add_header Cache-Control "no-cache";
    }

    location ~* \.ts$ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        add_header Cache-Control "public, max-age=86400";
    }

    # ─── Upload size limit ─────────────────────────────────────────────
    client_max_body_size 2G;
}
```

After editing:

```bash
sudo nginx -t                  # Validate config syntax
sudo systemctl reload nginx    # Apply changes
```

> **Note**: The configuration above covers the main `laetus.io.vn` domain.
> If the production setup uses a separate `api.laetus.io.vn` subdomain for
> the backend (as configured in `frontend/.env.production`), a separate
> Nginx server block is required for that subdomain with its own SSL
> certificate and proxy rules. The `BACKEND_URL` environment variable
> must match whichever domain serves the API.


---

## 2. Backend Service (systemd)

Create `/etc/systemd/system/laetus-backend.service`:

```ini
[Unit]
Description=Laetus Backend (FastAPI + Uvicorn)
After=network.target postgresql.service

[Service]
Type=simple
User=www-data
Group=www-data
WorkingDirectory=/var/www/laetus/backend
Environment="PATH=/var/www/laetus/backend/venv/bin:/usr/local/bin:/usr/bin"
ExecStart=/var/www/laetus/backend/venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable laetus-backend
sudo systemctl start laetus-backend
```

> **Important**: uvicorn listens on `127.0.0.1` only — NOT `0.0.0.0`.
> This ensures all public traffic goes through Nginx, preventing
> X-Forwarded-For spoofing from direct connections.

---

## 3. Environment Variables

Copy `.env.example` to `.env` and set production values:

```bash
cp .env.example .env
nano .env
```

**Critical variables to set for production:**

| Variable | Example Value | Notes |
|----------|---------------|-------|
| `DATABASE_URL` | `postgresql://laetus_user:pass@localhost:5432/laetus_db` | Must be PostgreSQL |
| `SECRET_KEY` | `<random-64-char-string>` | Generate with `python -c "import secrets; print(secrets.token_hex(32))"` |
| `FRONTEND_URL` | `https://tltn.laetus.io.vn` | Used in email links — must match real domain |
| `BACKEND_URL` | `https://api.laetus.io.vn` | Used for media file URLs |
| `CORS_ORIGINS` | `https://laetus.io.vn` | Must include frontend domain |
| `SMTP_PASSWORD` | `<gmail-app-password>` | Required for emails to actually send |
| `SMTP_USER` | `noreply.tltn@gmail.com` | Gmail account |
| `SMTP_FROM_EMAIL` | `noreply.tltn@gmail.com` | From address |

---

## 4. Production Smoke Test Checklist

After deploying, run through these checks:

### 4.1 — Restart backend and check logs

```bash
sudo systemctl restart laetus-backend
sudo journalctl -u laetus-backend -f --no-pager -n 50
```

Look for:
- ✅ `SMTP configured: host=smtp.gmail.com port=465 from=...`
- ✅ No import errors or startup crashes

### 4.2 — Create a test account

1. Open `https://tltn.laetus.io.vn/register` in browser
2. Register with a real email you can check
3. Verify:
   - ✅ Registration succeeds (201 response)
   - ✅ Welcome email arrives in inbox
   - ✅ Email says "Laetus" (not "Mov-Sug")
   - ✅ "Start Watching" button links to `https://tltn.laetus.io.vn` (not localhost)

### 4.3 — Request password reset

1. Open `https://tltn.laetus.io.vn/forgot-password`
2. Enter the test email
3. Verify:
   - ✅ Response says "If that email is registered, a reset link has been sent."
   - ✅ Reset email arrives
   - ✅ Email says "Laetus Account Security" (not "Mov-Sug")
   - ✅ Reset link points to `https://tltn.laetus.io.vn/reset-password?token=...`

### 4.4 — Reset password and login

1. Click the reset link in the email
2. Enter a new password meeting complexity requirements
3. Verify:
   - ✅ Reset succeeds
   - ✅ Can login with new password
   - ✅ Old password no longer works

### 4.5 — Check IP tracking in PostgreSQL

```bash
sudo -u postgres psql -d laetus_db
```

```sql
-- Check last login IP for a user
SELECT email, last_login_ip, last_login_at, failed_login_attempts
FROM users
WHERE email = 'your-test@email.com';
```

Verify:
- ✅ `last_login_ip` is your real public IP (not `127.0.0.1`)
- ✅ `last_login_at` is recent
- ✅ `failed_login_attempts` is 0 after successful login

### 4.6 — Check IP from admin Security Audit page

1. Login as admin
2. Navigate to `https://tltn.laetus.io.vn/admin/security`
3. Verify:
   - ✅ IP column shows real client IPs
   - ✅ Location column resolves (via client-side geolocation)
   - ✅ No `127.0.0.1` or `::1` entries for real users

### 4.7 — Test failed login tracking

1. Try logging in with wrong password 3 times
2. Check PostgreSQL:

```sql
SELECT email, failed_login_attempts, status
FROM users
WHERE email = 'your-test@email.com';
```

- ✅ `failed_login_attempts` increments
- ✅ After 5 failures, `status` becomes `'suspect'`
- ✅ Successful login resets both fields

### 4.8 — Confirm frontend build uses production API

```bash
cat /var/www/laetus/frontend/dist/assets/*.js | grep -o 'https://[^"]*api[^"]*' | head -3
```

- ✅ API calls point to production backend URL
- ✅ No `localhost:8000` references in built JS

---

## 5. Troubleshooting

### Emails not sending

```bash
sudo journalctl -u laetus-backend --no-pager | grep -i "smtp\|mail\|email"
```

If you see `SMTP NOT configured (missing: SMTP_PASSWORD)`:
- Set `SMTP_PASSWORD` in `.env` to your Gmail App Password
- Restart backend: `sudo systemctl restart laetus-backend`

### IP showing as 127.0.0.1

Check Nginx config has these headers:
```bash
grep -A5 "proxy_pass" /etc/nginx/sites-available/laetus
```

Must include:
```
proxy_set_header X-Real-IP $remote_addr;
proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
```

### Reset link points to localhost

Set `FRONTEND_URL` in `.env`:
```
FRONTEND_URL=https://tltn.laetus.io.vn
```
Restart backend after changing.
