# PyRunner — Python Script Manager

A web app to **create, edit, delete and run Python scripts** via unique public URLs.

- 🔒 **Authenticated admin** at `/admin/`
- ▶️ **Public script runner** at `/<hash>/`
- 🚀 **Gunicorn-ready** out of the box

---

## Quick Start

### 1. Install dependencies

```bash
python -m venv .venv
source .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Set environment variables

```bash
export SECRET_KEY="your-random-secret-key-here"
export ADMIN_USER="admin"
export ADMIN_PASS="your-secure-password"
```

Or create a `.env` file and load it with `python-dotenv`.

### 3. Run with Gunicorn

```bash
gunicorn -c gunicorn.conf.py app:app
```

App is now at **http://localhost:8000**

### 4. Development mode (Flask built-in server)

```bash
python app.py
```

---

## Usage

| URL | Description |
|-----|-------------|
| `/admin/login` | Sign in to the admin panel |
| `/admin/` | List all scripts |
| `/admin/create` | Create a new script |
| `/admin/edit/<hash>` | Edit an existing script |
| `/<hash>/` | Run a script publicly |

---

## Production Tips

### With Nginx (recommended)

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

### Persistent storage

The default app uses an in-memory dict — **scripts are lost on restart**.  
For production, swap `SCRIPTS = {}` in `app.py` with a SQLite or Postgres database using SQLAlchemy or similar.

### Systemd service

```ini
[Unit]
Description=PyRunner
After=network.target

[Service]
User=www-data
WorkingDirectory=/path/to/python-web-script
Environment="SECRET_KEY=changeme"
Environment="ADMIN_USER=admin"
Environment="ADMIN_PASS=changeme"
ExecStart=/path/to/.venv/bin/gunicorn -c gunicorn.conf.py app:app
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

---

## License

Apache 2.0
