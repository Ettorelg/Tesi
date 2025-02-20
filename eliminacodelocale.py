from flask import Flask, render_template, jsonify, request, session, redirect, url_for
from flask_cors import CORS
import pyttsx3  # Libreria per la sintesi vocale
import threading  # Per evitare blocchi nell'esecuzione
from flask_sqlalchemy import SQLAlchemy  # Gestione database utenti
from flask_bcrypt import Bcrypt  # Per la gestione delle password
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user

# Creazione dell'app Flask
app = Flask(__name__)
app.secret_key = "supersegreto"  # Chiave segreta per la gestione delle sessioni
CORS(app)  # Abilita CORS per gestire richieste da altri domini
bcrypt = Bcrypt(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"

# Configurazione database SQLite
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///eliminacode.db'
db = SQLAlchemy(app)

# Inizializzazione delle code
numero_cliente = 0  # Numerazione per i clienti in coda
numero_chiamato = 0  # Ultimo numero chiamato

def inizializza_sintesi_vocale():
    """Crea e configura un nuovo motore di sintesi vocale."""
    engine = pyttsx3.init()
    engine.setProperty('rate', 120)  # Imposta una velocità più lenta della voce
    return engine

def parla_numero(numero):
    """Pronuncia il numero chiamato in un thread separato per evitare blocchi."""
    def speak():
        engine = inizializza_sintesi_vocale()
        engine.say(f"Numero {numero} allo sportello")
        engine.runAndWait()
        
    threading.Thread(target=speak, daemon=True).start()

# Definizione del modello Utente
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(150), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)
    sportello_nome = db.Column(db.String(150), nullable=True)
    sportello_numero = db.Column(db.Integer, nullable=True)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Creazione del database e dell'utente admin
with app.app_context():
    db.create_all()
    admin_user = User.query.filter_by(username="1").first()
    if not admin_user:
        print("Creazione utente admin...")
        hashed_password = bcrypt.generate_password_hash("1").decode('utf-8')
        admin = User(username="1", password=hashed_password, is_admin=True)
        db.session.add(admin)
        db.session.commit()
        print("Utente admin creato con successo!")
    else:
        print("Utente admin già esistente.")

# Gestione utenti e sportelli (Admin)
@app.route('/gestisci_utenti', methods=['GET', 'POST'])
@login_required
def gestisci_utenti():
    if not current_user.is_admin:
        return jsonify({"message": "Accesso negato. Solo gli amministratori possono gestire gli utenti."}), 403
    
    if request.method == 'POST':
        data = request.get_json()
        action = data.get("action")
        username = data.get("username")
        password = data.get("password")
        sportello_nome = data.get("sportello_nome")
        sportello_numero = data.get("sportello_numero")
        
        if action == "add":
            if User.query.filter_by(username=username).first():
                return jsonify({"message": "Utente già esistente."}), 400
            hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')
            new_user = User(username=username, password=hashed_password, sportello_nome=sportello_nome, sportello_numero=sportello_numero)
            db.session.add(new_user)
            db.session.commit()
            return jsonify({"message": "Utente aggiunto con successo."})
        
        elif action == "update":
            user = User.query.filter_by(username=username).first()
            if user:
                user.sportello_nome = sportello_nome
                user.sportello_numero = sportello_numero
                db.session.commit()
                return jsonify({"message": "Sportello aggiornato con successo."})
            return jsonify({"message": "Utente non trovato."}), 404
        
        elif action == "delete":
            user = User.query.filter_by(username=username).first()
            if user:
                db.session.delete(user)
                db.session.commit()
                return jsonify({"message": "Utente eliminato con successo."})
            return jsonify({"message": "Utente non trovato."}), 404
    
    users = User.query.all()
    return jsonify([{ "id": user.id, "username": user.username, "is_admin": user.is_admin, "sportello_nome": user.sportello_nome, "sportello_numero": user.sportello_numero } for user in users])

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        if user and bcrypt.check_password_hash(user.password, password):
            login_user(user)
            if user.is_admin:
                return redirect(url_for('dashboard_admin'))
            else:
                return redirect(url_for('dashboard_user'))
        else:
            return jsonify({"message": "Credenziali errate."})
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/dashboard_admin')
@login_required
def dashboard_admin():
    if not current_user.is_admin:
        return redirect(url_for('dashboard_user'))
    return render_template('dashboard_admin.html')

@app.route('/dashboard_user')
@login_required
def dashboard_user():
    return render_template('dashboard_user.html')

@app.route('/visualizzazione')
@login_required
def visualizzazione():
    return render_template('visualizzazione.html')

@app.route('/prendi_numero')
@login_required
def prendi_numero():
    return render_template('prendi_numero.html')

@app.route('/gestione_code')
@login_required
def gestione_code():
    return render_template('gestione_code.html')

@app.route('/prendi_nuovo_numero', methods=['POST'])
def prendi_nuovo_numero():
    """Genera un nuovo numero per il cliente senza alterare la sequenza di chiamata."""
    global numero_cliente
    numero_cliente += 1  # Incrementa il numero del cliente in attesa
    return jsonify({"message": f"Il tuo numero è: {numero_cliente}"})

@app.route('/chiama_prossimo', methods=['POST'])
def chiama_prossimo():
    """Chiama il prossimo numero in ordine progressivo e aggiorna automaticamente la visualizzazione."""
    global numero_chiamato
    if numero_chiamato < numero_cliente:  # Evita di chiamare numeri non assegnati
        numero_chiamato += 1
        parla_numero(numero_chiamato)  # Pronuncia il numero chiamato
    return jsonify({"message": f"Numero attuale: {numero_chiamato}", "numero": numero_chiamato})

@app.route('/richiama_stesso', methods=['POST'])
def richiama_stesso():
    """Richiama lo stesso numero attuale senza modificarlo."""
    global numero_chiamato
    parla_numero(numero_chiamato)  # Pronuncia il numero chiamato
    return jsonify({"message": f"Numero attuale: {numero_chiamato}", "numero": numero_chiamato})

@app.route('/chiama_precedente', methods=['POST'])
def chiama_precedente():
    """Chiama il numero precedente se esiste."""
    global numero_chiamato
    if numero_chiamato > 1:
        numero_chiamato -= 1
        parla_numero(numero_chiamato)  # Pronuncia il numero chiamato
    return jsonify({"message": f"Numero attuale: {numero_chiamato}", "numero": numero_chiamato})

@app.route('/ottieni_numero_attuale', methods=['GET'])
def ottieni_numero_attuale():
    """Restituisce il numero attuale chiamato dall'operatore."""
    global numero_chiamato
    return jsonify({"message": f"Numero attuale: {numero_chiamato}", "numero": numero_chiamato})

@app.route('/resetta_coda', methods=['POST'])
def resetta_coda():
    """Resetta la numerazione sia per i clienti in attesa che per i numeri chiamati."""
    global numero_cliente, numero_chiamato
    numero_cliente = 0  # Reset della numerazione clienti
    numero_chiamato = 0  # Reset del numero chiamato
    return jsonify({"message": "La coda è stata resettata.", "numero": numero_chiamato})


# Avvio del server Flask
if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000, debug=True)
