import os
import uuid
import traceback
from functools import wraps
from datetime import datetime, timezone

from flask import (
    Flask, render_template, request, redirect, url_for,
    session, flash, abort, Response
)

from storage import make_storage

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "change-me-in-production-please")

# PostgreSQL URL (only used when DB_BACKEND=postgres)
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get(
    "DATABASE_URL",
    "postgresql://pyrunner:pyrunner@localhost:5432/pyrunner"
)
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

storage = make_storage()
storage.init_app(app)


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
    script = storage.get_script(script_hash)
    if not script:
        abort(404)

    # Wrap user code in a function so `return` works as the output value
    indented = "\n".join("    " + line for line in script["code"].splitlines())
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
        if storage.authenticate(username, password):
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
    return render_template("admin/index.html", scripts=storage.list_scripts())


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

        storage.create_script(name, description, code)
        flash(f'Script "{name}" created successfully.', "success")
        return redirect(url_for("admin_index"))

    return render_template("admin/edit.html", script=None, action="Create")


# ---------------------------------------------------------------------------
# Admin – edit
# ---------------------------------------------------------------------------
@app.route("/admin/edit/<script_hash>", methods=["GET", "POST"])
@login_required
def admin_edit(script_hash):
    script = storage.get_script(script_hash)
    if not script:
        abort(404)

    if request.method == "POST":
        name = request.form.get("name", script["name"]).strip()
        description = request.form.get("description", "").strip()
        code = request.form.get("code", "")
        storage.update_script(script_hash, name, description, code)
        flash(f'Script "{name}" updated.', "success")
        return redirect(url_for("admin_index"))

    return render_template("admin/edit.html", script=script, action="Edit")


# ---------------------------------------------------------------------------
# Admin – delete
# ---------------------------------------------------------------------------
@app.route("/admin/delete/<script_hash>", methods=["POST"])
@login_required
def admin_delete(script_hash):
    name = storage.delete_script(script_hash)
    if name:
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
