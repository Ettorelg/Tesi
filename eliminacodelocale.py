import sqlite3
from flask import Flask, render_template, request, redirect, session

app = Flask(__name__)
app.secret_key = "supersecretkey"
class Database:
    def __init__(self, db_name="eliminacode.db"):
        self.db_name = db_name  # Mantiene solo il nome del database

    def connect(self):
        """Apre una connessione al database e restituisce cursor e connessione."""
        conn = sqlite3.connect(self.db_name, check_same_thread=False)
        conn.execute("PRAGMA journal_mode=WAL")  # Abilita Write-Ahead Logging per ridurre i lock
        cursor = conn.cursor()
        return conn, cursor

    def execute_query(self, query, params=(), commit=False):
        """Esegue una query su una nuova connessione e la chiude subito dopo l'uso."""
        conn, cursor = self.connect()
        cursor.execute(query, params)
        if commit:
            conn.commit()
        result = cursor.fetchall()
        conn.close()  # Assicura la chiusura della connessione per evitare blocchi
        return result

    def get_licenze_utente(self, user_id):
        """Recupera le licenze attive di un utente."""
        query = "SELECT tipo, data_scadenza FROM licenze WHERE id_utente = ?"
        result = self.execute_query(query, (user_id,))
        return {row[0]: row[1] for row in result}

    def crea_tabelle(self):
        """Crea le tabelle nel database se non esistono."""
        self.cursor.execute('''CREATE TABLE IF NOT EXISTS utenti (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            admin BOOLEAN,
            ragione_sociale TEXT,
            indirizzo TEXT,
            citta TEXT,
            cap TEXT,
            partita_iva TEXT,
            telefono TEXT,
            email TEXT
        )''')

        self.cursor.execute('''CREATE TABLE IF NOT EXISTS licenze (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            id_utente INTEGER,
            tipo TEXT NOT NULL,
            data_scadenza TEXT NOT NULL,
            FOREIGN KEY(id_utente) REFERENCES utenti(id)
        )''')

        self.conn.commit()

    def chiudi_connessione(self):
        """Chiude la connessione con il database."""
        self.conn.close()

@app.route("/login", methods=["GET", "POST"])
def login():
    """Gestisce il login e il reindirizzamento in base al ruolo dell'utente."""
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        db = Database()
        result = db.execute_query("SELECT id, username, admin FROM utenti WHERE username = ? AND password = ?",
                                  (username, password))

        if result:
            user_id, username, is_admin = result[0]  # Estrai i dati dalla query
            session["user_id"] = user_id
            session["username"] = username
            session["is_admin"] = is_admin
            return redirect("/dashboard_admin") if is_admin else redirect("/dashboard_utente")
        else:
            return "Login fallito! Username o password errati."

    return render_template("login.html")

@app.route("/logout")
def logout():
    """Effettua il logout e reindirizza al login."""
    session.clear()
    return redirect("/login")

@app.route("/dashboard_admin")
def dashboard_admin():
    """Mostra la dashboard per gli amministratori con le licenze attive."""
    if not session.get("is_admin"):
        return redirect("/login")

    db = Database()
    
    # Recupera tutti gli utenti
    utenti = db.execute_query("SELECT * FROM utenti")

    # Recupera tutte le licenze associate agli utenti
    licenze_raw = db.execute_query("SELECT id_utente, tipo, data_scadenza FROM licenze")
    
    licenze = {}
    for id_utente, tipo, scadenza in licenze_raw:
        if id_utente not in licenze:
            licenze[id_utente] = []
        licenze[id_utente].append((tipo, scadenza))

    return render_template("dashboard_admin.html", utenti=utenti, licenze=licenze)

@app.route("/dashboard_utente")
def dashboard_utente():
    """Mostra la dashboard per gli utenti normali."""
    if not session.get("user_id"):
        return redirect("/login")
    return "<h2>Benvenuto nella Dashboard Utente</h2><a href='/logout'>Logout</a>"
@app.route("/aggiungi_utente", methods=["GET", "POST"])
def aggiungi_utente():
    """Permette di aggiungere un nuovo utente dalla Dashboard Admin."""
    if not session.get("is_admin"):
        return redirect("/login")

    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        admin = 1 if "admin" in request.form else 0
        ragione_sociale = request.form["ragione_sociale"]
        indirizzo = request.form["indirizzo"]
        citta = request.form["citta"]
        cap = request.form["cap"]
        partita_iva = request.form["partita_iva"]
        telefono = request.form["telefono"]
        email = request.form["email"]

        db = Database()

        try:
            db.execute_query('''
                INSERT INTO utenti (username, password, admin, ragione_sociale, indirizzo, citta, cap, partita_iva, telefono, email)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (username, password, admin, ragione_sociale, indirizzo, citta, cap, partita_iva, telefono, email), commit=True)

            return redirect("/dashboard_admin")

        except sqlite3.IntegrityError:
            return "Errore: Username già esistente. Riprova con un altro nome."

    return render_template("aggiungi_utente.html")

from datetime import datetime, timedelta

@app.route("/gestisci_licenze/<int:user_id>", methods=["GET", "POST"])
def gestisci_licenze(user_id):
    """Gestisce attivazione, disattivazione e modifica delle licenze di un utente, compresi reparti e file per eliminacode."""
    if not session.get("is_admin"):
        return redirect("/login")

    db = Database()

    # Licenze disponibili
    licenze_disponibili = ["eliminacode", "prenotazioni", "ordini"]

    # Licenze attive dell'utente
    licenze_attuali = db.get_licenze_utente(user_id)

    if request.method == "POST":
        # Gestione delle licenze
        if "licenze" in request.form:
            licenze_selezionate = request.form.getlist("licenze")

            # Rimuove licenze non selezionate
            for licenza in list(licenze_attuali.keys()):
                if licenza not in licenze_selezionate:
                    db.execute_query("DELETE FROM licenze WHERE id_utente = ? AND tipo = ?", (user_id, licenza), commit=True)
                    del licenze_attuali[licenza]

            # Aggiunge nuove licenze con scadenza di 1 anno
            for licenza in licenze_selezionate:
                if licenza not in licenze_attuali:
                    scadenza = (datetime.today() + timedelta(days=365)).strftime("%Y-%m-%d")
                    db.execute_query("INSERT INTO licenze (id_utente, tipo, data_scadenza) VALUES (?, ?, ?)",
                                     (user_id, licenza, scadenza), commit=True)
                    licenze_attuali[licenza] = scadenza

            # Aggiorna le scadenze
            for licenza in licenze_attuali:
                if f"scadenza_{licenza}" in request.form:
                    nuova_scadenza = request.form[f"scadenza_{licenza}"]
                    db.execute_query("UPDATE licenze SET data_scadenza = ? WHERE id_utente = ? AND tipo = ?",
                                     (nuova_scadenza, user_id, licenza), commit=True)
                    licenze_attuali[licenza] = nuova_scadenza

        # Gestione dei reparti
        elif "nuovo_reparto" in request.form:
            if "eliminacode" in licenze_attuali:
                licenza_id = db.execute_query("SELECT id FROM licenze WHERE id_utente = ? AND tipo = 'eliminacode'",
                                              (user_id,))
                if licenza_id:
                    nuovo_reparto = request.form["nuovo_reparto"].strip()
                    db.execute_query("INSERT INTO reparti (nome, id_licenza) VALUES (?, ?)",
                                     (nuovo_reparto, licenza_id[0][0]), commit=True)

        elif "elimina_reparto" in request.form:
            reparto_id = request.form["elimina_reparto"]
            db.execute_query("DELETE FROM reparti WHERE id = ?", (reparto_id,), commit=True)

        # Gestione delle file (code)
        elif "nuova_fila" in request.form:
            reparto_id = request.form.get("reparto_id")  # Ottiene il reparto_id dal form
            nuova_fila = request.form.get("nuova_fila").strip()
            if nuova_fila and reparto_id:
                db.execute_query("INSERT INTO file_reparto (nome, id_reparto) VALUES (?, ?)",
                                 (nuova_fila, reparto_id), commit=True)

        elif "elimina_file" in request.form:
            file_id = request.form["elimina_file"]
            db.execute_query("DELETE FROM file_reparto WHERE id = ?", (file_id,), commit=True)

        return redirect(f"/gestisci_licenze/{user_id}")

    # Recupera reparti e file SOLO se l'utente ha eliminacode
    reparti = []
    file_reparto = {}
    if "eliminacode" in licenze_attuali:
        reparti = db.execute_query("SELECT id, nome FROM reparti WHERE id_licenza = "
                                   "(SELECT id FROM licenze WHERE id_utente = ? AND tipo = 'eliminacode')",
                                   (user_id,))
        for reparto_id, reparto_nome in reparti:
            file_reparto[reparto_id] = db.execute_query("SELECT id, nome FROM file_reparto WHERE id_reparto = ?",
                                                         (reparto_id,))

    return render_template("gestisci_licenze.html", user_id=user_id, licenze_disponibili=licenze_disponibili,
                           licenze_attuali=licenze_attuali, reparti=reparti, file_reparto=file_reparto)

if __name__ == "__main__":
    app.run(debug=True)
