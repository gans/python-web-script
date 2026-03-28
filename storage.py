"""
Storage backends for PyRunner.

Select via environment variable:
  DB_BACKEND=postgres   (default) — requires DATABASE_URL
  DB_BACKEND=filesystem           — requires FS_DATA_PATH
"""

import json
import os
import uuid
from abc import ABC, abstractmethod
from datetime import datetime, timezone

import bcrypt


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def _verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode(), password_hash.encode())


def _now_str() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


# ---------------------------------------------------------------------------
# Abstract interface
# ---------------------------------------------------------------------------

class BaseStorage(ABC):

    @abstractmethod
    def init_app(self, app) -> None:
        """Called once at startup: create tables / files and seed admin user."""

    @abstractmethod
    def get_user(self, username: str) -> dict | None:
        """Return user dict {username, password_hash} or None."""

    @abstractmethod
    def create_user(self, username: str, password: str) -> None:
        """Create a new user with a bcrypt-hashed password."""

    def authenticate(self, username: str, password: str) -> bool:
        user = self.get_user(username)
        if not user:
            return False
        return _verify_password(password, user["password_hash"])

    @abstractmethod
    def list_scripts(self) -> list[dict]:
        """Return all scripts sorted newest-first."""

    @abstractmethod
    def get_script(self, script_hash: str) -> dict | None:
        """Return script dict or None."""

    @abstractmethod
    def create_script(self, name: str, description: str, code: str) -> dict:
        """Persist a new script and return its dict."""

    @abstractmethod
    def update_script(self, script_hash: str, name: str, description: str, code: str) -> dict | None:
        """Update an existing script. Returns updated dict or None if not found."""

    @abstractmethod
    def delete_script(self, script_hash: str) -> str | None:
        """Delete a script. Returns its name or None if not found."""


# ---------------------------------------------------------------------------
# PostgreSQL backend (SQLAlchemy)
# ---------------------------------------------------------------------------

class PostgresStorage(BaseStorage):

    def __init__(self, app=None):
        from flask_sqlalchemy import SQLAlchemy
        self.db = SQLAlchemy()
        self._define_models()
        if app:
            self.init_app(app)

    def _define_models(self):
        db = self.db

        class User(db.Model):
            __tablename__ = "users"
            id = db.Column(db.Integer, primary_key=True)
            username = db.Column(db.String(80), unique=True, nullable=False)
            password_hash = db.Column(db.String(256), nullable=False)

        class Script(db.Model):
            __tablename__ = "scripts"
            id = db.Column(db.Integer, primary_key=True)
            hash = db.Column(db.String(32), unique=True, nullable=False, index=True)
            name = db.Column(db.String(200), nullable=False)
            description = db.Column(db.Text, default="")
            code = db.Column(db.Text, nullable=False, default="")
            created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

        self.User = User
        self.Script = Script

    def init_app(self, app) -> None:
        self.db.init_app(app)
        with app.app_context():
            self.db.create_all()
            admin_user = os.environ.get("ADMIN_USER", "admin")
            admin_pass = os.environ.get("ADMIN_PASS", "admin123")
            if not self.get_user(admin_user):
                self.create_user(admin_user, admin_pass)
                print(f"[storage] Created admin user: {admin_user}")
            else:
                print(f"[storage] Admin user already exists: {admin_user}")

    def get_user(self, username: str) -> dict | None:
        u = self.User.query.filter_by(username=username).first()
        if not u:
            return None
        return {"username": u.username, "password_hash": u.password_hash}

    def create_user(self, username: str, password: str) -> None:
        u = self.User(username=username, password_hash=_hash_password(password))
        self.db.session.add(u)
        self.db.session.commit()

    def list_scripts(self) -> list[dict]:
        rows = self.Script.query.order_by(self.Script.created_at.desc()).all()
        return [self._row_to_dict(r) for r in rows]

    def get_script(self, script_hash: str) -> dict | None:
        row = self.Script.query.filter_by(hash=script_hash).first()
        return self._row_to_dict(row) if row else None

    def create_script(self, name: str, description: str, code: str) -> dict:
        row = self.Script(
            hash=uuid.uuid4().hex[:12],
            name=name,
            description=description,
            code=code,
        )
        self.db.session.add(row)
        self.db.session.commit()
        return self._row_to_dict(row)

    def update_script(self, script_hash: str, name: str, description: str, code: str) -> dict | None:
        row = self.Script.query.filter_by(hash=script_hash).first()
        if not row:
            return None
        row.name = name
        row.description = description
        row.code = code
        self.db.session.commit()
        return self._row_to_dict(row)

    def delete_script(self, script_hash: str) -> str | None:
        row = self.Script.query.filter_by(hash=script_hash).first()
        if not row:
            return None
        name = row.name
        self.db.session.delete(row)
        self.db.session.commit()
        return name

    @staticmethod
    def _row_to_dict(row) -> dict:
        return {
            "hash": row.hash,
            "name": row.name,
            "description": row.description,
            "code": row.code,
            "created_at": row.created_at.strftime("%Y-%m-%d %H:%M UTC"),
        }


# ---------------------------------------------------------------------------
# Filesystem backend (JSON files)
# ---------------------------------------------------------------------------

class FilesystemStorage(BaseStorage):
    """
    Stores data as two JSON files inside FS_DATA_PATH:
      users.json   — list of {username, password_hash}
      scripts.json — list of script dicts
    """

    def __init__(self, data_path: str):
        self.data_path = data_path
        self._users_file = os.path.join(data_path, "users.json")
        self._scripts_file = os.path.join(data_path, "scripts.json")
        try:
            from filelock import FileLock
            self._users_lock = FileLock(self._users_file + ".lock")
            self._scripts_lock = FileLock(self._scripts_file + ".lock")
        except ImportError:
            raise RuntimeError("filesystem backend requires 'filelock': pip install filelock")

    def init_app(self, app) -> None:
        os.makedirs(self.data_path, exist_ok=True)
        if not os.path.exists(self._users_file):
            self._write_json(self._users_file, [])
        if not os.path.exists(self._scripts_file):
            self._write_json(self._scripts_file, [])

        admin_user = os.environ.get("ADMIN_USER", "admin")
        admin_pass = os.environ.get("ADMIN_PASS", "admin123")
        if not self.get_user(admin_user):
            self.create_user(admin_user, admin_pass)
            print(f"[storage] Created admin user: {admin_user}")
        else:
            print(f"[storage] Admin user already exists: {admin_user}")

    # --- users ---

    def get_user(self, username: str) -> dict | None:
        users = self._read_json(self._users_file)
        return next((u for u in users if u["username"] == username), None)

    def create_user(self, username: str, password: str) -> None:
        with self._users_lock:
            users = self._read_json(self._users_file)
            users.append({"username": username, "password_hash": _hash_password(password)})
            self._write_json(self._users_file, users)

    # --- scripts ---

    def list_scripts(self) -> list[dict]:
        scripts = self._read_json(self._scripts_file)
        return sorted(scripts, key=lambda s: s["created_at"], reverse=True)

    def get_script(self, script_hash: str) -> dict | None:
        scripts = self._read_json(self._scripts_file)
        return next((s for s in scripts if s["hash"] == script_hash), None)

    def create_script(self, name: str, description: str, code: str) -> dict:
        script = {
            "hash": uuid.uuid4().hex[:12],
            "name": name,
            "description": description,
            "code": code,
            "created_at": _now_str(),
        }
        with self._scripts_lock:
            scripts = self._read_json(self._scripts_file)
            scripts.append(script)
            self._write_json(self._scripts_file, scripts)
        return script

    def update_script(self, script_hash: str, name: str, description: str, code: str) -> dict | None:
        with self._scripts_lock:
            scripts = self._read_json(self._scripts_file)
            for s in scripts:
                if s["hash"] == script_hash:
                    s["name"] = name
                    s["description"] = description
                    s["code"] = code
                    self._write_json(self._scripts_file, scripts)
                    return s
        return None

    def delete_script(self, script_hash: str) -> str | None:
        with self._scripts_lock:
            scripts = self._read_json(self._scripts_file)
            for i, s in enumerate(scripts):
                if s["hash"] == script_hash:
                    name = s["name"]
                    scripts.pop(i)
                    self._write_json(self._scripts_file, scripts)
                    return name
        return None

    # --- helpers ---

    @staticmethod
    def _read_json(path: str) -> list:
        try:
            with open(path) as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return []

    @staticmethod
    def _write_json(path: str, data: list) -> None:
        with open(path, "w") as f:
            json.dump(data, f, indent=2)


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

def make_storage() -> BaseStorage:
    backend = os.environ.get("DB_BACKEND", "postgres").lower()
    if backend == "filesystem":
        data_path = os.environ.get("FS_DATA_PATH", "./data")
        print(f"[storage] Using filesystem backend at: {data_path}")
        return FilesystemStorage(data_path)
    else:
        print("[storage] Using PostgreSQL backend")
        return PostgresStorage()
