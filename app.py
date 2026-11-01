import os, sqlite3
from datetime import datetime
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, session, flash

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "change-this-before-publishing")
DB = os.path.join(os.path.dirname(__file__), "reservations.db")

PRICES = {
    1: {1: 1800, 2: 2000}, 2: {1: 3000, 2: 3400},
    3: {1: 4600, 2: 5200}, 4: {1: 5900, 2: 6600},
    5: {1: 7100, 2: 8000}, 7: {1: 9500, 2: 10800},
    14: {1: 15500, 2: 18000}, 30: {1: 20000, 2: 23500}
}

def connect():
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    return c

def init_db():
    with connect() as c:
        c.execute("""CREATE TABLE IF NOT EXISTS reservations (
            id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL,
            phone TEXT NOT NULL, days INTEGER NOT NULL, controllers INTEGER NOT NULL,
            start_date TEXT NOT NULL, address TEXT NOT NULL, note TEXT,
            price INTEGER NOT NULL, status TEXT NOT NULL DEFAULT 'Nova',
            created TEXT NOT NULL)""")

def admin_only(fn):
    @wraps(fn)
    def wrapped(*args, **kwargs):
        if not session.get("admin"):
            return redirect(url_for("login"))
        return fn(*args, **kwargs)
    return wrapped

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/reserve", methods=["POST"])
def reserve():
    name = request.form.get("name", "").strip()
    phone = request.form.get("phone", "").strip()
    address = request.form.get("address", "").strip()
    note = request.form.get("note", "").strip()
    try:
        days = int(request.form.get("days", "0"))
        controllers = int(request.form.get("controllers", "0"))
        start_date = request.form.get("start_date", "")
        price = PRICES[days][controllers]
    except (ValueError, KeyError):
        flash("Izaberi ispravno trajanje i broj džojstika.", "error")
        return redirect(url_for("home") + "#rezervacija")
    if not all([name, phone, address, start_date]):
        flash("Popuni sva obavezna polja.", "error")
        return redirect(url_for("home") + "#rezervacija")
    with connect() as c:
        c.execute("""INSERT INTO reservations
        (name,phone,days,controllers,start_date,address,note,price,created)
        VALUES (?,?,?,?,?,?,?,?,?)""",
        (name, phone, days, controllers, start_date, address, note, price,
         datetime.now().strftime("%Y-%m-%d %H:%M")))
    flash("Rezervacija je poslata! Sačekaj potvrdu.", "success")
    return redirect(url_for("home") + "#rezervacija")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        admin_password = os.environ.get("ADMIN_PASSWORD")
        if admin_password and request.form.get("password") == admin_password:
            session["admin"] = True
            return redirect(url_for("admin"))
        flash("Lozinka nije podešena ili nije ispravna.", "error")
    return render_template("login.html")

@app.route("/admin")
@admin_only
def admin():
    with connect() as c:
        rows = c.execute("SELECT * FROM reservations ORDER BY id DESC").fetchall()
    return render_template("admin.html", reservations=rows)

@app.route("/admin/status/<int:rid>", methods=["POST"])
@admin_only
def status(rid):
    value = request.form.get("status")
    if value in ("Nova", "Potvrđena", "Završena", "Otkazana"):
        with connect() as c:
            c.execute("UPDATE reservations SET status=? WHERE id=?", (value, rid))
    return redirect(url_for("admin"))

@app.route("/admin/delete/<int:rid>", methods=["POST"])
@admin_only
def delete(rid):
    with connect() as c:
        c.execute("DELETE FROM reservations WHERE id=?", (rid,))
    return redirect(url_for("admin"))

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("home"))

init_db()
if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)
