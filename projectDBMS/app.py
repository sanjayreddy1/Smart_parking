# app.py  – Smart Car Parking (Updated 14‑Jul‑2025)

from flask import (
    Flask, render_template, request, redirect,
    url_for, session, flash
)
from flask_mysqldb import MySQL
import MySQLdb.cursors
from datetime import datetime
import qrcode, io, base64
import config                         # <-- your DB creds here

app = Flask(__name__)
app.secret_key = 'replace_with_a_real_secret_key'

# ── MySQL connection ─────────────────────────────────────────
app.config['MYSQL_HOST']      = config.MYSQL_HOST
app.config['MYSQL_USER']      = config.MYSQL_USER
app.config['MYSQL_PASSWORD']  = config.MYSQL_PASSWORD
app.config['MYSQL_DB']        = config.MYSQL_DB
mysql = MySQL(app)

# ── LOGIN / LOGOUT ───────────────────────────────────────────
@app.route('/')
def root():               # simply send user to the login page
    return redirect('/login')

@app.route('/login', methods=['GET', 'POST'])
def login():
    error = ''
    if request.method == 'POST':
        user  = request.form['username']
        pw    = request.form['password']
        cur   = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cur.execute('SELECT * FROM users WHERE username=%s AND password=%s',
                    (user, pw))
        account = cur.fetchone()
        if account:
            # session
            session['loggedin'] = True
            session['username'] = account['username']
            session['role']     = account['role']
            # log login
            cur.execute('INSERT INTO login_logs (username, role) VALUES (%s,%s)',
                        (user, account['role']))
            mysql.connection.commit()
            return redirect('/dashboard')
        error = 'Incorrect username or password'
    return render_template('login.html', error=error)

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/login')

# ── DASHBOARD (single URL) ───────────────────────────────────
@app.route('/dashboard')
def dashboard():
    if 'loggedin' not in session:
        return redirect('/login')

    cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

    #  stats
    cur.execute('SELECT COUNT(*) AS total FROM slots')
    total = cur.fetchone()['total']
    cur.execute("SELECT COUNT(*) AS c FROM slots WHERE status='available'")
    available = cur.fetchone()['c']
    cur.execute("SELECT COUNT(*) AS c FROM slots WHERE status='occupied'")
    occupied = cur.fetchone()['c']
    cur.execute('SELECT SUM(amount) AS money FROM billing WHERE date=CURDATE()')
    income_today = cur.fetchone()['money'] or 0

    # slots, billing, logs
    cur.execute('SELECT * FROM slots ORDER BY slot_id')
    slots = cur.fetchall()
    cur.execute('SELECT * FROM billing ORDER BY date DESC, in_time DESC')
    billing = cur.fetchall()
    login_logs = []
    if session['role'] == 'admin':
        cur.execute('SELECT * FROM login_logs ORDER BY login_time DESC')
        login_logs = cur.fetchall()

    return render_template(
        'dashboard.html',
        username=session['username'],
        role=session['role'],
        total_slots=total,
        available_slots=available,
        occupied_slots=occupied,
        income_today=income_today,
        slots=slots,
        billing=billing,
        login_logs=login_logs
    )

# ── ADD SLOT (admin) ─────────────────────────────────────────
@app.route('/add_slot', methods=['POST'])
def add_slot():
    if session.get('role') != 'admin':
        return redirect('/dashboard')

    slot_id = request.form['slot_id'].strip()
    status  = request.form['status']
    vehicle = request.form.get('vehicle_number', '').strip() or None

    # server‑side validation
    if status == 'occupied' and not vehicle:
        flash('Vehicle number is required for an occupied slot!', 'danger')
        return redirect('/dashboard')

    cur = mysql.connection.cursor()
    cur.execute('SELECT id FROM slots WHERE slot_id=%s', (slot_id,))
    if cur.fetchone():
        flash('Slot already exists!', 'warning')
    else:
        cur.execute(
            'INSERT INTO slots (slot_id, status, vehicle_number) VALUES (%s,%s,%s)',
            (slot_id, status, vehicle)
        )
        mysql.connection.commit()
        flash('Slot added successfully.', 'success')
    return redirect('/dashboard')

# ── UPDATE / CLOSE SLOT ─────────────────────────────────────
@app.route('/update_slot/<int:slot_pk>', methods=['POST'])
def update_slot(slot_pk):
    if 'loggedin' not in session:
        return redirect('/login')

    new_status = request.form['status']
    vehicle    = request.form.get('vehicle_number', '').strip() or None

    cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cur.execute('SELECT * FROM slots WHERE id=%s', (slot_pk,))
    slot = cur.fetchone()
    if not slot:
        flash('Slot not found.', 'danger')
        return redirect('/dashboard')

    now = datetime.now()

    #  Going AVAILABLE ➞ OCCUPIED  (start billing)
    if slot['status'] == 'available' and new_status == 'occupied':
        if not vehicle:
            flash('Vehicle number required!', 'danger')
            return redirect('/dashboard')
        cur.execute('UPDATE slots SET status=%s, vehicle_number=%s WHERE id=%s',
                    (new_status, vehicle, slot_pk))
        cur.execute(
            'INSERT INTO billing (slot_id, vehicle_number, in_time, date) '
            'VALUES (%s,%s,%s,%s)',
            (slot['slot_id'], vehicle, now, now.date())
        )

    #  Going OCCUPIED ➞ AVAILABLE  (stop billing)
    elif slot['status'] == 'occupied' and new_status == 'available':
        cur.execute('UPDATE slots SET status=%s, vehicle_number=NULL WHERE id=%s',
                    (new_status, slot_pk))
        cur.execute(
            'SELECT * FROM billing WHERE slot_id=%s AND out_time IS NULL '
            'ORDER BY in_time DESC LIMIT 1',
            (slot['slot_id'],)
        )
        bill = cur.fetchone()
        if bill:
            duration = round((now - bill['in_time']).total_seconds() / 3600, 2)
            amount   = round(duration * 160, 2)
            cur.execute(
                'UPDATE billing SET out_time=%s, duration_hours=%s, amount=%s '
                'WHERE id=%s',
                (now, duration, amount, bill['id'])
            )

    mysql.connection.commit()
    return redirect('/dashboard')

# ── DELETE SLOT (admin) ─────────────────────────────────────
@app.route('/delete_slot/<int:slot_pk>')
def delete_slot(slot_pk):
    if session.get('role') != 'admin':
        return redirect('/dashboard')
    cur = mysql.connection.cursor()
    cur.execute('DELETE FROM slots WHERE id=%s', (slot_pk,))
    mysql.connection.commit()
    flash('Slot deleted.', 'info')
    return redirect('/dashboard')

# ── CREATE USER (admin) ─────────────────────────────────────
@app.route('/create_user', methods=['POST'])
def create_user():
    if session.get('role') != 'admin':
        return redirect('/dashboard')
    uname = request.form['username'].strip()
    pw    = request.form['password'].strip()
    role  = request.form['role']
    cur   = mysql.connection.cursor()
    cur.execute('SELECT id FROM users WHERE username=%s', (uname,))
    if cur.fetchone():
        flash('Username already taken.', 'warning')
    else:
        cur.execute('INSERT INTO users (username,password,role) VALUES (%s,%s,%s)',
                    (uname, pw, role))
        mysql.connection.commit()
        flash('User created.', 'success')
    return redirect('/dashboard')

# ── PRINT BILL (QR) ─────────────────────────────────────────
@app.route('/print_bill/<int:bill_id>')
def print_bill(bill_id):
    if 'loggedin' not in session:
        return redirect('/login')

    cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cur.execute('SELECT * FROM billing WHERE id=%s', (bill_id,))
    bill = cur.fetchone()
    if not bill:
        return 'Bill not found', 404

    qr_data = f"Slot: {bill['slot_id']}\nVehicle: {bill['vehicle_number']}\nAmount: ₹{bill['amount']}"
    img = qrcode.make(qr_data)
    buf = io.BytesIO()
    img.save(buf)
    qr_base64 = base64.b64encode(buf.getvalue()).decode()

    return render_template('print_bill.html', bill=bill, qr_code=qr_base64)

# ── FLASK MAIN ──────────────────────────────────────────────
if __name__ == '__main__':
    app.run(debug=True)
