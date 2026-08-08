import os
import re
import pymysql
import pymysql.cursors
from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'fallback-secret-key')

# Database configuration (plain pymysql, no Flask-MySQLdb extension needed)
DB_CONFIG = {
    'host': os.getenv('MYSQL_HOST', 'db'),          # 'db' for Docker, 'localhost' for local
    'user': os.getenv('MYSQL_USER', 'root'),
    'password': os.getenv('MYSQL_PASSWORD', 'admin'),
    'database': os.getenv('MYSQL_DB', 'loginapp'),
    'cursorclass': pymysql.cursors.DictCursor,
    'autocommit': False,
}


def get_db_connection():
    """Open a fresh pymysql connection for a single request."""
    return pymysql.connect(**DB_CONFIG)


# http://localhost:5000/pythonlogin/ - login page (GET + POST)
@app.route('/pythonlogin/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST' and 'username' in request.form and 'password' in request.form:
        username = request.form['username']
        password = request.form['password']

        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute('SELECT * FROM accounts WHERE username = %s', (username,))
                account = cursor.fetchone()
        finally:
            conn.close()

        # Verify the hashed password instead of comparing plaintext
        if account and check_password_hash(account['password'], password):
            session['loggedin'] = True
            session['id'] = account['id']
            session['username'] = account['username']
            return redirect(url_for('home'))
        else:
            flash("Incorrect username/password!", "danger")

    return render_template('auth/login.html', title="Login")


# http://localhost:5000/pythonlogin/register - registration page (GET + POST)
@app.route('/pythonlogin/register', methods=['GET', 'POST'])
def register():
    if (request.method == 'POST' and 'username' in request.form
            and 'password' in request.form and 'email' in request.form):
        username = request.form['username']
        password = request.form['password']
        email = request.form['email']

        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute('SELECT * FROM accounts WHERE username = %s', (username,))
                account = cursor.fetchone()

                if account:
                    flash("Account already exists!", "danger")
                elif not re.match(r'[^@]+@[^@]+\.[^@]+', email):
                    flash("Invalid email address!", "danger")
                elif not re.match(r'^[A-Za-z0-9]+$', username):
                    flash("Username must contain only characters and numbers!", "danger")
                elif not username or not password or not email:
                    flash("Incorrect username/password!", "danger")
                else:
                    # Hash the password before storing it - never store plaintext
                    hashed_password = generate_password_hash(password)
                    cursor.execute(
                        'INSERT INTO accounts (username, password, email) VALUES (%s, %s, %s)',
                        (username, hashed_password, email)
                    )
                    conn.commit()
                    flash("You have successfully registered!", "success")
                    return redirect(url_for('login'))
        finally:
            conn.close()

    elif request.method == 'POST':
        flash("Please fill out the form!", "danger")

    return render_template('auth/register.html', title="Register")


# http://localhost:5000/ - home page, only for logged-in users
@app.route('/')
def home():
    if 'loggedin' in session:
        return render_template('home/home.html', username=session['username'], title="Home")
    return redirect(url_for('login'))


@app.route('/profile')
def profile():
    if 'loggedin' in session:
        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute('SELECT * FROM accounts WHERE id = %s', (session['id'],))
                account = cursor.fetchone()
        finally:
            conn.close()
        return render_template('auth/profile.html', account=account, title="Profile")
    return redirect(url_for('login'))

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)