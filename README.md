# RentaPS5PO — sistem za rezervacije

## Šta radi
- Kupci ne moraju da naprave nalog.
- Ukupno 3 PS5 konzole.
- Rezervacije od 1 do 30 dana.
- Kupac bira datum preuzimanja i vraćanja.
- Rezervacija se automatski potvrđuje ako ima dovoljno slobodnih konzola.
- Provera dostupnosti pokriva ceo period i sprečava da se zauzme više od 3 konzole.
- Plaćanje pri preuzimanju.
- Pregled rezervacija na `/admin?key=TVOJA_LOZINKA`.

## 1. Instalacija na Windowsu
1. Instaliraj Python 3.11 ili noviji sa https://www.python.org/downloads/ . U instalaciji označi **Add Python to PATH**.
2. Raspakuj ZIP u folder, na primer `C:\RentaPS5PO`.
3. Otvori Command Prompt u tom folderu.
4. Pokreni ove komande jednu po jednu:

```bat
py -m venv .venv
.venv\Scripts\activate
py -m pip install -r requirements.txt
py app.py
```

5. Otvori `http://127.0.0.1:5000` u browseru. To radi na tvom računaru; kupci još ne mogu da pristupe sa interneta.

## 2. Promeni cene
U `app.py` pronađi:

```python
PRICES = {1: 2000, 3: 5000, 7: 9000, 30: 25000}
```

Promeni iznose u dinarima. To su samo primeri, ne preporuka za tvoju cenu.

Za trajanja koja nisu 1, 3, 7 ili 30 dana, trenutna formula koristi najbliži niži paket plus cenu za svaki dodatni dan po ceni paketa od 1 dana. Na primer, 4 dana = cena paketa za 3 dana + cena jednog dodatnog dana. Ako želiš drugačije pravilo, promeni funkciju `price_for_days()`.

## 3. Pregled rezervacija
Za admin pregled podesi promenljive okruženja pre pokretanja:

PowerShell:
```powershell
$env:ADMIN_PASSWORD="unesi-dugu-jaku-lozinku"
$env:SECRET_KEY="unesi-drugu-dugu-nasumicnu-vrednost"
py app.py
```

Otvori `http://127.0.0.1:5000/admin?key=unesi-dugu-jaku-lozinku`.

Ne šalji admin link kupcima. Pošto je lozinka u URL-u, ovo je samo osnovna zaštita; pre ozbiljnog javnog korišćenja preporučljivo je napraviti pravi login i HTTPS.

## 4. Kako dobiti javni link
Da bi kupci rezervisali preko interneta, aplikacija mora da bude postavljena na hosting koji podržava Python/Flask. Na primer, možeš istražiti PythonAnywhere ili drugi Python hosting. Prati njihova aktuelna uputstva za Flask/WSGI, otpremi `app.py` i `requirements.txt`, instaliraj Flask i podesi WSGI aplikaciju na `app:app`.

**Baza mora da se čuva na trajnom disku.** Podesi `DB_PATH` na trajni direktorijum hostinga. Nemoj koristiti privremeni disk koji se briše pri restartu/deploy-u, jer bi rezervacije mogle da nestanu. Za ozbiljniji rad sa više servera koristi PostgreSQL.

Pre nego što podeliš link:
1. Napravi probnu rezervaciju.
2. Pokušaj da rezervišeš četvrtu konzolu za isti period — mora biti odbijena.
3. Testiraj različite datume koji se preklapaju i koji se ne preklapaju.
4. Podesi jake `SECRET_KEY` i `ADMIN_PASSWORD` vrednosti.
5. Dodaj svoje uslove iznajmljivanja, pravila otkazivanja i obaveštenje o obradi imena i brojeva telefona.

## Ograničenja
- Potvrda se prikazuje na ekranu; ovaj kod ne šalje automatski SMS ili e-mail.
- Nema online plaćanja.
- Nema funkcije za otkazivanje ili izmenu rezervacije kupca.
- Potrebno je hosting okruženje sa trajnim čuvanjem baze za javnu upotrebu.
