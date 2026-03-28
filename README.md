# PyRunner — Python Script Manager

A web app to **create, edit, delete and run Python scripts** via unique public URLs.

- **Authenticated admin** at `/admin/`
- **Public script runner** at `/<hash>/` — returns raw plain-text output
- **PostgreSQL** for persistent storage of users and scripts
- **Gunicorn** (gthread workers) behind Docker

---

## Stack

| Layer | Technology |
|-------|-----------|
| Runtime | Python 3.12 on Ubuntu 24.04 LTS x64 |
| Framework | Flask 3 |
| Database | PostgreSQL 16 |
| Server | Gunicorn (gthread workers) |
| Container | Docker + Docker Compose |

---

## Quick Start (Docker)

### 1. Configure credentials

```bash
cp .env.example .env
# Edit .env and set SECRET_KEY, ADMIN_USER, ADMIN_PASS
```

### 2. Build and run

```bash
docker compose up --build
```

App is now at **http://localhost:8000**

The admin user is created automatically on first boot using the values in `.env`.

---

## Usage

| URL | Description |
|-----|-------------|
| `/admin/login` | Sign in to the admin panel |
| `/admin/` | List all scripts |
| `/admin/create` | Create a new script |
| `/admin/edit/<hash>` | Edit an existing script |
| `/<hash>/` | Run a script — returns raw plain-text output |

---

## Writing Scripts

Scripts are written as a function body. Use `return` to produce the HTTP response:

```python
name = "world"
return f"Hello, {name}!"
```

Visiting `/<hash>/` returns:

```
Hello, world!
```

Imports work normally:

```python
import datetime
return datetime.date.today().isoformat()
```

Errors return a plain-text traceback with HTTP 500.

---

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `SECRET_KEY` | `change-me-in-production` | Flask session signing key |
| `DATABASE_URL` | `postgresql://pyrunner:pyrunner@db:5432/pyrunner` | PostgreSQL connection string |
| `ADMIN_USER` | `admin` | Admin username (used on first boot) |
| `ADMIN_PASS` | `admin123` | Admin password (used on first boot) |

---

## Production Tips

### Nginx reverse proxy

```nginx
server {
    listen 80;
    server_name mydomain.com.br;

    location / {
        proxy_pass         http://127.0.0.1:8000;
        proxy_set_header   Host $host;
        proxy_set_header   X-Real-IP $remote_addr;
        proxy_set_header   X-Forwarded-For $proxy_add_x_forwarded_for;
    }
}
```

### Stopping and restarting

```bash
docker compose down        # stop (data persists in postgres_data volume)
docker compose up -d       # restart in background
```

### Wiping the database

```bash
docker compose down -v     # removes containers AND the postgres_data volume
```

---

## License

Apache 2.0
