import os
import uuid
import traceback
from functools import wraps
from datetime import datetime, timezone

from flask import (
    Flask, render_template, request, redirect, url_for,
    session, flash, abort, Response
)
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "change-me-in-production-please")
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get(
    "DATABASE_URL",
    "postgresql://pyrunner:pyrunner@localhost:5432/pyrunner"
)
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------
class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)

    def set_password(self, password: str):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)


class Script(db.Model):
    __tablename__ = "scripts"

    id = db.Column(db.Integer, primary_key=True)
    hash = db.Column(db.String(32), unique=True, nullable=False, index=True)
    name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, default="")
    code = db.Column(db.Text, nullable=False, default="")
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    def to_dict(self):
        return {
            "hash": self.hash,
            "name": self.name,
            "description": self.description,
            "code": self.code,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M UTC"),
        }


# ---------------------------------------------------------------------------
# Auth helpers
# ---------------------------------------------------------------------------
def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("logged_in"):
            flash("Please log in to access the admin panel.", "warning")
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated


# ---------------------------------------------------------------------------
# Public: run a script by hash
# ---------------------------------------------------------------------------
@app.route("/<script_hash>/")
def run_script(script_hash):
    script = Script.query.filter_by(hash=script_hash).first()
    if not script:
        abort(404)

    # Wrap user code in a function so `return` works as the output value
    indented = "\n".join("    " + line for line in script.code.splitlines())
    wrapped = f"def _main():\n{indented or '    pass'}\n\n_result = _main()\n"

    try:
        namespace: dict = {}
        exec(wrapped, namespace)  # noqa: S102
        output = namespace.get("_result", "")
        status = 200
    except Exception:
        output = traceback.format_exc()
        status = 500

    return Response(str(output) if output is not None else "", status=status,
                    mimetype="text/plain; charset=utf-8")


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------
@app.route("/admin/login", methods=["GET", "POST"])
def login():
    if session.get("logged_in"):
        return redirect(url_for("admin_index"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            session["logged_in"] = True
            session["username"] = username
            flash("Welcome back!", "success")
            return redirect(url_for("admin_index"))
        flash("Invalid credentials.", "error")

    return render_template("login.html")


@app.route("/admin/logout")
def logout():
    session.clear()
    flash("Logged out.", "info")
    return redirect(url_for("login"))


# ---------------------------------------------------------------------------
# Admin – list
# ---------------------------------------------------------------------------
@app.route("/admin/")
@login_required
def admin_index():
    scripts = Script.query.order_by(Script.created_at.desc()).all()
    return render_template("admin/index.html", scripts=[s.to_dict() for s in scripts])


# ---------------------------------------------------------------------------
# Admin – create
# ---------------------------------------------------------------------------
@app.route("/admin/create", methods=["GET", "POST"])
@login_required
def admin_create():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        description = request.form.get("description", "").strip()
        code = request.form.get("code", "")

        if not name:
            flash("Script name is required.", "error")
            return render_template("admin/edit.html", script=None, action="Create")

        script = Script(
            hash=uuid.uuid4().hex[:12],
            name=name,
            description=description,
            code=code,
        )
        db.session.add(script)
        db.session.commit()
        flash(f'Script "{name}" created successfully.', "success")
        return redirect(url_for("admin_index"))

    return render_template("admin/edit.html", script=None, action="Create")


# ---------------------------------------------------------------------------
# Admin – edit
# ---------------------------------------------------------------------------
@app.route("/admin/edit/<script_hash>", methods=["GET", "POST"])
@login_required
def admin_edit(script_hash):
    script = Script.query.filter_by(hash=script_hash).first_or_404()

    if request.method == "POST":
        script.name = request.form.get("name", script.name).strip()
        script.description = request.form.get("description", "").strip()
        script.code = request.form.get("code", "")
        db.session.commit()
        flash(f'Script "{script.name}" updated.', "success")
        return redirect(url_for("admin_index"))

    return render_template("admin/edit.html", script=script.to_dict(), action="Edit")


# ---------------------------------------------------------------------------
# Admin – delete
# ---------------------------------------------------------------------------
@app.route("/admin/delete/<script_hash>", methods=["POST"])
@login_required
def admin_delete(script_hash):
    script = Script.query.filter_by(hash=script_hash).first()
    if script:
        name = script.name
        db.session.delete(script)
        db.session.commit()
        flash(f'Script "{name}" deleted.', "success")
    return redirect(url_for("admin_index"))


# ---------------------------------------------------------------------------
# 404
# ---------------------------------------------------------------------------
@app.errorhandler(404)
def not_found(e):
    return render_template("404.html"), 404


if __name__ == "__main__":
    app.run(debug=True)
