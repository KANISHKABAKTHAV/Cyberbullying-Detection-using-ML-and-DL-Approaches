from flask import Flask, render_template, request, redirect, url_for, flash, session
import sqlite3
import os
from werkzeug.utils import secure_filename
from tensorflow.keras.preprocessing.image import load_img, img_to_array
from tensorflow.keras.applications.resnet50 import preprocess_input
import joblib
import numpy as np
from functions import custom_input_prediction
import re
import string
from datetime import datetime
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import PassiveAggressiveClassifier
from PIL import Image
from tensorflow.keras.preprocessing.text import Tokenizer
from tensorflow.keras.preprocessing.sequence import pad_sequences
import webbrowser



app = Flask(__name__)
app.secret_key = '7103'

app.config['UPLOAD_FOLDER'] = 'static/uploads'  
app.config['ALLOWED_EXTENSIONS'] = {'png', 'jpg', 'jpeg', 'gif'}



def get_db():
    conn = sqlite3.connect('database.db')
    conn.row_factory = sqlite3.Row  
    return conn

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']


def preprocess_image(image_path, target_size=(224, 224)):
    img = load_img(image_path, target_size=target_size)
    img = img_to_array(img)
    img = preprocess_input(img)  
    return img


def create_tables():
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            mail TEXT NOT NULL UNIQUE,
            password TEXT NOT NULL,
            status TEXT DEFAULT 'active'
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS warning (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT,
            email TEXT,
            content TEXT,
            image TEXT,
            detection TEXT,
            timestamp TEXT,
            warning_message TEXT
        )
    ''')


        
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS posts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT NOT NULL,
        content TEXT NOT NULL,
        image TEXT,
        detection TEXT,
        timestamp TEXT
    )
    ''')

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS admin_posts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT NOT NULL,
        content TEXT NOT NULL,
        image TEXT,
        detection TEXT,
        timestamp TEXT
    )
    ''')


    cursor.execute('''
    CREATE TABLE IF NOT EXISTS users_info (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        name TEXT NOT NULL,
        email TEXT NOT NULL,
        phone TEXT,
        profile_image TEXT
    );
    ''')

    conn.commit()
    conn.close()

create_tables()

@app.route('/', methods=['GET', 'POST'])
def home():
    return render_template('home.html')

@app.route('/index', methods=['GET', 'POST'])
def index():
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        mail = request.form['mail']
        password = request.form['password']

        conn = get_db()
        cursor = conn.cursor()

        cursor.execute('SELECT * FROM users WHERE mail = ?', (mail,))
        user = cursor.fetchone()

        if user:
            flash("Username already exists!", "danger")
            conn.close()
            return redirect(url_for('register'))

        cursor.execute('INSERT INTO users (username, mail, password) VALUES (?, ?, ?)', (username, mail, password))
        conn.commit()
        conn.close()

        flash("Registration successful!", "success")
        return redirect(url_for('login'))

    return render_template('register.html')



@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        mail = request.form['mail']
        password = request.form['password']

        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM users WHERE mail = ? AND password = ?', (mail, password))
        user = cursor.fetchone()

        if user:
            if user['status'] == 'blocked':
                conn.close()
                session['blocked_email'] = user['mail']
                session['blocked_username'] = user['username']
                return redirect(url_for('blocked_page'))

            else:
                session['user_id'] = user['id']
                session['username'] = user['username']
                session['email'] = user['mail']   
                flash("Login successful!", "success")
                conn.close()
                return redirect(url_for('dashboard'))
        else:
            flash("Invalid credentials!", "danger")
            conn.close()
            return redirect(url_for('login'))
    return render_template('login.html')


@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    username = session.get('username')

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM users_info WHERE username = ?', (username,))
    user_info = cursor.fetchone()

    cursor.execute('SELECT * FROM posts ORDER BY timestamp DESC')
    posts = cursor.fetchall()
    conn.close()

    return render_template('dashboard.html', user_info=user_info, posts=posts)


@app.route('/post/<int:post_id>', methods=['POST'])
def post(post_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    username = session['username']
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM posts WHERE id = ? AND username = ?", (post_id, username))
    post = cursor.fetchone()

    if post:
        cursor.execute("DELETE FROM posts WHERE id = ?", (post_id,))
        cursor.execute("DELETE FROM admin_posts WHERE id = ?", (post_id,))
        conn.commit()

    conn.close()
    flash("Post deleted successfully.", "success")
    return redirect(url_for('dashboard'))





@app.route('/view_post')
def view_post():

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM posts')
    posts = cursor.fetchall()

    return render_template('view_post.html', posts=posts)

@app.route('/update_profile', methods=['GET', 'POST'])
def update_profile():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        phone = request.form['phone']
        
        
        profile_image = None
        if 'profile_image' in request.files:
            file = request.files['profile_image']
            if file and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                profile_image = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(profile_image)
        
        username = session.get('username')

        conn = get_db()
        cursor = conn.cursor()

        cursor.execute('''
            INSERT INTO users_info (username, name, email, phone, profile_image)
            VALUES (?, ?, ?, ?, ?)
        ''', (username, name, email, phone, profile_image))
        conn.commit()

        session['name'] = name
        session['email'] = email
        session['phone'] = phone
        if profile_image:
            session['profile_image'] = profile_image

        flash("Profile updated successfully!", "success")
        return redirect(url_for('view_profile'))
    
    return render_template('profile.html')

@app.route('/view_profile', methods=['GET', 'POST'])
def view_profile():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    username = session.get('username')
    print(username)
    
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM users_info WHERE username = ?', (username,))
    user_info = cursor.fetchone()
    print(user_info)
    conn.close()

    if user_info:
        profile_image = user_info[5]  
        profile_image = profile_image.replace("\\", "/")  
        
        return render_template('profile1.html', user_info=user_info, profile_image=profile_image)

    else:
        flash("No profile data found!", "danger")
        return redirect(url_for('dashboard'))



@app.route('/predict', methods=['GET', 'POST'])
def predict():
    if request.method == 'POST':
        if 'user_id' not in session:
            flash('Please log in to submit a post.', 'warning')
            return redirect(url_for('login'))

        comment = request.form['comment']
        image = request.files['image']

        image_filename = secure_filename(image.filename)
        image_path = os.path.join(app.config['UPLOAD_FOLDER'], image_filename)
        image.save(image_path)

        result = custom_input_prediction(comment)
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        conn = get_db()
        cursor = conn.cursor()

        cursor.execute('''
            INSERT INTO posts (username, content, image, detection, timestamp)
            VALUES (?, ?, ?, ?, ?)
        ''', (session['username'], comment, image_filename, result, timestamp))

        bullying_categories = ['age', 'ethnicity', 'gender', 'other_cyberbullying', 'religion']
        if any(category in result.lower() for category in bullying_categories):
            cursor.execute('''
                INSERT INTO admin_posts (username, content, image, detection, timestamp)
                VALUES (?, ?, ?, ?, ?)
            ''', (session['username'], comment, image_filename, result, timestamp))

        conn.commit()
        conn.close()

        flash('Post submitted successfully!', 'success')
        return redirect(url_for('dashboard'))

    return render_template('index.html')

@app.route('/warning_message')
def warning_message():
    if 'username' not in session:
        return redirect(url_for('login'))

    user_email = session.get('email')  

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("SELECT username, email, content, image, detection, timestamp, warning_message FROM warning WHERE email = ?", (user_email,))
    warnings = cursor.fetchall()

    conn.close()

    return render_template('warning.html', warnings=warnings)

@app.route('/logout')
def logout():
    session.clear()
    flash("You have been logged out!", "info")
    return redirect(url_for('login'))

    
admin_use = 'admin'
admin_log = 'admin'
@app.route('/admin_login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        if admin_use == username and admin_log == password:
            flash("Login successful!", "success")
            conn = get_db()
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM posts')
            posts = cursor.fetchall()
            
            return render_template('admin_dash.html', posts=posts)

        flash("Invalid username or password!", "danger")
        return redirect(url_for('admin_login'))

    return render_template('admin_login.html')

@app.route('/admin_dash', methods=['GET', 'POST'])
def admin_dash():
    return render_template('admin_dash.html')



@app.route('/admin_dash1', methods=['GET', 'POST'])
def admin_dash1():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM posts')
    posts = cursor.fetchall()
    return render_template('admin_dash.html', posts=posts)

def get_prices():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT id, username, content, image, detection,timestamp FROM admin_posts") 
    data = cursor.fetchall()
    conn.close()
    return data

@app.route('/show_prices')
def show_prices():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT id, username, content, image, detection, timestamp FROM admin_posts ORDER BY timestamp DESC")
    prices = cursor.fetchall()
    conn.close()
    return render_template('show_prices.html', prices=prices)


@app.route('/get_username', methods=['POST'])
def get_username():
    username = request.form.get('username')
    content = request.form.get('content')
    image = request.form.get('image')
    detection = request.form.get('detection')
    timestamp = request.form.get('timestamp')

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("SELECT username, mail FROM users WHERE username = ?", (username,))
    data = cursor.fetchone()

    if data:
        fetched_username, fetched_email = data
        warning_message = "⚠️ Your post has violated the community policy."

        cursor.execute("""
            INSERT INTO warning (username, email, content, image, detection, timestamp, warning_message)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (fetched_username, fetched_email, content, image, detection, timestamp, warning_message))

        cursor.execute("SELECT COUNT(*) FROM warning WHERE email = ?", (fetched_email,))
        warning_count = cursor.fetchone()[0]

        if warning_count >= 3:
            cursor.execute("UPDATE users SET status = 'blocked' WHERE mail = ?", (fetched_email,))
            flash(f"🚫 User '{fetched_username}' has been BLOCKED after 3 warnings!", "danger")
        else:
            flash(f"⚠️ Warning sent to {fetched_username}! ({warning_count}/3)", "info")

        conn.commit()
        conn.close()

        prices = get_prices()
        return render_template('show_prices.html', prices=prices)
    else:
        conn.close()
        flash("Username not found!", "danger")
        prices = get_prices()
        return render_template('show_prices.html', prices=prices)



@app.route('/blocked_users')
def blocked_users():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT username, mail FROM users WHERE status = 'blocked'")
    blocked = cursor.fetchall()
    conn.close()
    return render_template('blocked_users.html', blocked=blocked)

@app.route('/blocked')
def blocked_page():
    return render_template('blocked.html')



@app.route('/view_post1')
def view_post1():
    
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM posts')
    posts = cursor.fetchall()

    return render_template('view_post_admin.html', posts=posts)



@app.route('/delete_post/<int:post_id>', methods=['POST'])
def delete_post(post_id):
    post_id = int(post_id)  
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM posts WHERE id = ?', (post_id,))
    cursor.execute('DELETE FROM admin_posts WHERE id = ?', (post_id,))
    conn.commit()
    conn.close()

    flash('Post deleted successfully.', 'success')
    return redirect(url_for('dashboard'))





@app.route('/edit_post/<int:post_id>', methods=['GET', 'POST'])
def edit_post(post_id):
    username = session.get('username')
    conn = get_db()
    cursor = conn.cursor()

    if request.method == 'POST':
        new_content = request.form['new_content']

        detection_result = custom_input_prediction(new_content)
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        cursor.execute('''
            UPDATE posts 
            SET content = ?, detection = ?, timestamp = ?
            WHERE id = ? AND username = ?
        ''', (new_content, detection_result, timestamp, post_id, username))

        bullying_categories = ['age', 'ethnicity', 'gender', 'other_cyberbullying', 'religion']
        if any(category in detection_result.lower() for category in bullying_categories):
            cursor.execute('SELECT id FROM admin_posts WHERE id = ? AND username = ?', (post_id, username))
            existing_admin_post = cursor.fetchone()

            if existing_admin_post:
                cursor.execute('''
                    UPDATE admin_posts
                    SET content = ?, detection = ?, timestamp = ?
                    WHERE id = ? AND username = ?
                ''', (new_content, detection_result, timestamp, post_id, username))
            else:
                cursor.execute('''
                    INSERT INTO admin_posts (id, username, content, image, detection, timestamp)
                    SELECT id, username, content, image, ?, ?
                    FROM posts WHERE id = ? AND username = ?
                ''', (detection_result, timestamp, post_id, username))
        else:
            cursor.execute('DELETE FROM admin_posts WHERE id = ? AND username = ?', (post_id, username))

        conn.commit()
        conn.close()

        flash('Post updated and rechecked successfully.', 'success')
        return redirect(url_for('dashboard'))

    cursor.execute('SELECT * FROM posts WHERE id = ? AND username = ?', (post_id, username))
    post = cursor.fetchone()
    conn.close()

    return render_template('edit_post.html', post=post)



if __name__ == '__main__':
    webbrowser.open('http://127.0.0.1:7103')
    app.run(debug=False,port=7103)
