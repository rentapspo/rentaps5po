import os
import sqlite3
from datetime import date, datetime, timedelta
from flask import Flask, request, redirect, url_for, render_template_string, flash, abort

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "change-this-before-publishing")
DB_PATH = os.environ.get("DB_PATH", os.path.join(os.path.dirname(__file__), "bookings.sqlite3"))

TOTAL_CONSOLES = 3
MAX_DAYS = 30

# Primer cena u RSD — promeni ove iznose pre objavljivanja.
PRICES = {1: 2000, 3: 5000, 7: 9000, 30: 25000}


def connect_db():
    conn = sqlite3.connect(DB_PATH, timeout=20)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with connect_db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS bookings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                customer_name TEXT NOT NULL,
                phone TEXT NOT NULL,
                quantity INTEGER NOT NULL,
                pickup_date TEXT NOT NULL,
                return_date TEXT NOT NULL,
                rental_days INTEGER NOT NULL,
                total_price INTEGER NOT NULL,
                created_at TEXT NOT NULL
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS dates_idx ON bookings(pickup_date, return_date)")


def price_for_days(days):
    # Za 1, 3, 7 i 30 dana koristi tačno definisanu cenu.
    # Za ostale dužine: najbliži niži paket + cena za svaki dodatni dan po ceni 1 dana.
    if days in PRICES:
        return PRICES[days]
    lower = max(d for d in PRICES if d < days)
    return PRICES[lower] + (days - lower) * PRICES[1]


def peak_occupied(conn, start_date, end_date):
    """Najveći broj zauzetih konzola u bilo kom delu [start_date, end_date)."""
    rows = conn.execute(
        "SELECT pickup_date, return_date, quantity FROM bookings "
        "WHERE pickup_date < ? AND return_date > ?",
        (end_date.isoformat(), start_date.isoformat())
    ).fetchall()

    events = {start_date: 0, end_date: 0}
    for row in rows:
        start = max(start_date, date.fromisoformat(row["pickup_date"]))
        end = min(end_date, date.fromisoformat(row["return_date"]))
        if start < end:
            events[start] = events.get(start, 0) + row["quantity"]
            events[end] = events.get(end, 0) - row["quantity"]

    occupied = peak = 0
    for day in sorted(events):
        occupied += events[day]
        if day < end_date:
            peak = max(peak, occupied)
    return peak


PAGE = r"""<!doctype html>
<html lang="sr"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>RentaPS5PO — Rezervacija</title>
<style>
*{box-sizing:border-box}body{margin:0;background:#f3f4f6;color:#171717;font-family:Arial,sans-serif}
main{max-width:720px;margin:24px auto;padding:22px;background:white;border-radius:16px;box-shadow:0 5px 24px #0001}
.brand{font-size:13px;color:#555;letter-spacing:.08em}h1{margin:8px 0}
p{line-height:1.5;color:#444}label{display:block;font-weight:bold;margin:15px 0 6px}
input,select,button{width:100%;padding:12px;border:1px solid #cbd0d8;border-radius:9px;font-size:16px}
button{margin-top:18px;background:#111827;color:white;font-weight:bold;cursor:pointer;border:0}
.notice{padding:12px;border-radius:9px;margin:12px 0;background:#eff6ff}.error{background:#fff0f0;color:#8a1717}
.prices{display:grid;grid-template-columns:repeat(2,1fr);gap:8px;margin:16px 0}
.prices div{background:#f6f6f7;padding:12px;border-radius:9px}.small{font-size:13px;color:#555;line-height:1.5}
@media(min-width:560px){.prices{grid-template-columns:repeat(4,1fr)}}
</style></head><body><main>
<div class="brand">@rentaps5po</div><h1>Rezerviši PS5</h1>
<p>Izaberi datum preuzimanja i vraćanja. Rezervacija se automatski potvrđuje samo ako ima dovoljno slobodnih konzola tokom celog perioda.</p>
<div class="prices">{% for d,p in prices.items() %}<div><b>{{d}} {{'dan' if d == 1 else 'dana'}}</b><br>{{"{:,}".format(p).replace(",", ".")}} RSD</div>{% endfor %}</div>
{% with messages=get_flashed_messages(with_categories=true) %}{% for category,message in messages %}<div class="notice {{category}}">{{message}}</div>{% endfor %}{% endwith %}
<form method="post" action="{{url_for('book')}}">
<label for="customer_name">Ime i prezime</label><input id="customer_name" name="customer_name" maxlength="100" autocomplete="name" required>
<label for="phone">Broj telefona</label><input id="phone" name="phone" type="tel" maxlength="40" placeholder="+381..." autocomplete="tel" required>
<label for="pickup_date">Datum preuzimanja</label><input id="pickup_date" name="pickup_date" type="date" min="{{today}}" required>
<label for="return_date">Datum vraćanja</label><input id="return_date" name="return_date" type="date" min="{{tomorrow}}" required>
<label for="quantity">Broj konzola</label><select id="quantity" name="quantity"><option value="1">1 PS5 konzola</option><option value="2">2 PS5 konzole</option><option value="3">3 PS5 konzole</option></select>
<div id="estimate" class="notice">Izaberi datume da vidiš cenu.</div>
<button type="submit">Potvrdi rezervaciju</button>
</form>
<p class="small">Plaćanje se vrši pri preuzimanju. Datum vraćanja je dan kada se konzola vraća i ne računa se kao dodatni dan najma. Sačuvaj broj rezervacije.</p>
</main>
<script>
const pickup=document.getElementById('pickup_date'), ret=document.getElementById('return_date'), estimate=document.getElementById('estimate');
const prices={{prices|tojson}};
function iso(d){return d.getFullYear()+'-'+String(d.getMonth()+1).padStart(2,'0')+'-'+String(d.getDate()).padStart(2,'0')}
function getPrice(days){
  if(prices[days]!==undefined)return Number(prices[days]);
  const tiers=Object.keys(prices).map(Number).sort((a,b)=>a-b);
  const lower=Math.max(...tiers.filter(t=>t<days));
  return Number(prices[lower])+(days-lower)*Number(prices[1]);
}
function update(){
  if(!pickup.value||!ret.value){estimate.textContent='Izaberi datume da vidiš cenu.';return}
  const a=new Date(pickup.value+'T12:00:00'), b=new Date(ret.value+'T12:00:00');
  const days=Math.round((b-a)/86400000);
  if(days<1){estimate.textContent='Datum vraćanja mora biti posle preuzimanja.';return}
  if(days>30){estimate.textContent='Najduži najam je 30 dana.';return}
  estimate.textContent='Trajanje: '+days+' dana. Cena po jednoj konzoli: '+getPrice(days).toLocaleString('sr-RS')+' RSD.';
}
pickup.addEventListener('change',()=>{
  if(pickup.value){
    const d=new Date(pickup.value+'T12:00:00');d.setDate(d.getDate()+1);ret.min=iso(d);
    if(ret.value&&ret.value<ret.min)ret.value=ret.min;
  }
  update();
});
ret.addEventListener('change',update);
</script></body></html>"""

CONFIRM = r"""<!doctype html><html lang="sr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Rezervacija potvrđena</title><style>body{font-family:Arial,sans-serif;background:#f3f4f6;padding:18px;color:#171717}.card{max-width:650px;margin:20px auto;background:white;padding:24px;border-radius:16px}.ok{background:#eaf8ef;padding:12px;border-radius:9px}a{color:#111827}</style></head>
<body><div class="card"><h1>Rezervacija potvrđena!</h1><p class="ok">Rezervacija je automatski potvrđena. Plaćanje se vrši pri preuzimanju.</p>
<p><b>Broj rezervacije:</b> {{booking_id}}</p><p><b>Ime:</b> {{customer_name}}</p>
<p><b>Period:</b> {{pickup}} — {{return_date}} ({{days}} dana)</p><p><b>Broj konzola:</b> {{quantity}}</p>
<p><b>Ukupno za plaćanje:</b> {{"{:,}".format(total).replace(",", ".")}} RSD</p>
<p>Sačuvaj broj rezervacije. Za izmene kontaktiraj @rentaps5po.</p><a href="{{url_for('home')}}">Nazad na rezervacije</a></div></body></html>"""


@app.get("/")
def home():
    today = date.today()
    return render_template_string(PAGE, prices=PRICES, today=today.isoformat(),
                                  tomorrow=(today + timedelta(days=1)).isoformat())


@app.post("/book")
def book():
    name = request.form.get("customer_name", "").strip()
    phone = request.form.get("phone", "").strip()
    try:
        pickup = date.fromisoformat(request.form.get("pickup_date", ""))
        return_date = date.fromisoformat(request.form.get("return_date", ""))
        quantity = int(request.form.get("quantity", "1"))
    except (ValueError, TypeError):
        flash("Proveri datume i broj konzola.", "error")
        return redirect(url_for("home"))

    days = (return_date - pickup).days
    if not name or not phone:
        flash("Unesi ime i broj telefona.", "error")
        return redirect(url_for("home"))
    if pickup < date.today():
        flash("Datum preuzimanja ne može biti u prošlosti.", "error")
        return redirect(url_for("home"))
    if days < 1 or days > MAX_DAYS:
        flash("Najam mora trajati od 1 do 30 dana.", "error")
        return redirect(url_for("home"))
    if quantity < 1 or quantity > TOTAL_CONSOLES:
        flash("Možeš rezervisati od 1 do 3 konzole.", "error")
        return redirect(url_for("home"))

    total = price_for_days(days) * quantity
    conn = connect_db()
    try:
        # Zaključava upis dok se proverava dostupnost i čuva rezervacija.
        conn.execute("BEGIN IMMEDIATE")
        peak = peak_occupied(conn, pickup, return_date)
        if peak + quantity > TOTAL_CONSOLES:
            conn.rollback()
            free = max(0, TOTAL_CONSOLES - peak)
            flash(f"Nema dovoljno slobodnih konzola za ceo period. Najviše {free} je slobodno.", "error")
            return redirect(url_for("home"))
        cur = conn.execute(
            """INSERT INTO bookings
            (customer_name, phone, quantity, pickup_date, return_date, rental_days, total_price, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (name, phone, quantity, pickup.isoformat(), return_date.isoformat(), days, total,
             datetime.now().isoformat(timespec="seconds"))
        )
        booking_id = cur.lastrowid
        conn.commit()
    except sqlite3.Error:
        conn.rollback()
        app.logger.exception("Database error")
        flash("Došlo je do greške. Pokušaj ponovo.", "error")
        return redirect(url_for("home"))
    finally:
        conn.close()

    return render_template_string(CONFIRM, booking_id=booking_id, customer_name=name,
                                  pickup=pickup.isoformat(), return_date=return_date.isoformat(),
                                  days=days, quantity=quantity, total=total)


@app.get("/admin")
def admin():
    # Osnovna zaštita za lični pregled rezervacija. Podesi ADMIN_PASSWORD u hostingu.
    password = os.environ.get("ADMIN_PASSWORD")
    if not password:
        abort(503, "Admin pregled nije uključen. Podesi ADMIN_PASSWORD.")
    if request.args.get("key", "") != password:
        abort(403)
    with connect_db() as conn:
        rows = conn.execute("SELECT * FROM bookings ORDER BY pickup_date, id").fetchall()
    return render_template_string("""<!doctype html><html lang="sr"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>RentaPS5PO — Rezervacije</title><style>body{font-family:Arial;padding:16px}div{overflow-x:auto}table{border-collapse:collapse}th,td{padding:8px;border-bottom:1px solid #ddd;text-align:left;white-space:nowrap}</style>
<h1>Rezervacije</h1><div><table><tr><th>ID</th><th>Ime</th><th>Telefon</th><th>Komada</th><th>Preuzimanje</th><th>Vraćanje</th><th>Dana</th><th>Ukupno RSD</th></tr>
{% for r in rows %}<tr><td>{{r['id']}}</td><td>{{r['customer_name']}}</td><td>{{r['phone']}}</td><td>{{r['quantity']}}</td><td>{{r['pickup_date']}}</td><td>{{r['return_date']}}</td><td>{{r['rental_days']}}</td><td>{{r['total_price']}}</td></tr>{% endfor %}
</table></div></html>""", rows=rows)


@app.get("/health")
def health():
    return {"status": "ok"}


init_db()

if __name__ == "__main__":
    # Lokalno testiranje; za javni link postavi aplikaciju na hosting.
    app.run(debug=True, port=5000)
