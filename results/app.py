from flask import Flask, render_template, request, redirect, url_for, session,jsonify,flash
import sqlite3
from functions import custom_input_prediction

app = Flask(__name__)
app.secret_key = b'(\xee\x00\xd4\xce"\xcf\xe8@\r\xde\xfc\xbdJ\x08W'

app = Flask(__name__)
app.secret_key = "123"
database="test2.db"

con = sqlite3.connect(database)
con.execute("create table if not exists register(pid integer primary key AUTOINCREMENT,name text,mail text,password text)")
con.execute("create table if not exists response1(pid integer primary key AUTOINCREMENT,name TEXT,email text,response text)")
con.execute("CREATE TABLE IF NOT EXISTS comments (id INTEGER PRIMARY KEY AUTOINCREMENT, email TEXT, comment TEXT, category TEXT, admin_response TEXT)")


con.close()



# Page title
@app.route('/index')
def index():
    return render_template('index.html')

@app.route('/')
def home():
    return render_template('register1.html')

@app.route('/dashboard')
def dashboard():
    if 'user' not in session:
        return redirect(url_for('login'))

    con = sqlite3.connect(database)
    cur = con.cursor()
    
    # Count the number of messages for the logged-in user
    cur.execute("SELECT COUNT(*) FROM messages WHERE email = ?", (session['user_email'],))
    message_count = cur.fetchone()[0]
    
    con.close()
    
    return render_template('dashboard.html', message_count=message_count)


@app.route('/register', methods=['GET','POST'])
def register():
    if request.method=='POST':
            name=request.form['name']
            mail=request.form['mail']
            password=request.form["password"]
            con=sqlite3.connect(database)
            cur=con.cursor()
            cur.execute("insert into register(name,mail,password)values(?,?,?)",(name,mail,password))
            con.commit()
            return render_template('register1.html')
    return render_template('register1.html')



name1=[]
email1=[]
@app.route('/login', methods=["GET", "POST"])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        con = sqlite3.connect(database)
        cur = con.cursor()
        cur.execute("SELECT * FROM register WHERE mail=? AND password=?", (email, password))
        data = cur.fetchone()
        con.close()
        if data:
            session['name'] = data[1]  # Storing username in session
            session['email'] = data[2]
            return render_template("dashboard.html")
        else:
            flash('Invalid login credentials', 'danger')
    return render_template("register1.html")


ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "admin"

@app.route('/adminlogin', methods=["GET", "POST"])
def adminlogin():
    if request.method == 'POST':
        username = request.form['name']
        password = request.form['password']
        if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
            session['admin'] = True  # Store session for admin access
            return redirect(url_for('admin_dashboard'))
        else:
            flash('Invalid username or password', 'danger')
    return render_template('register1.html')



# Prediction route
@app.route('/predict', methods=['POST'])
def predict():
    if 'email' not in session:
        return redirect(url_for('login'))

    email = session['email']  # Use email instead of username
    tweet_input = request.form['tweet_input']

    if tweet_input:
        category = custom_input_prediction(tweet_input)

        # Store email instead of username
        con = sqlite3.connect(database)
        cur = con.cursor()
        cur.execute("INSERT INTO comments (email, comment, category) VALUES (?, ?, ?)", 
                    (email, tweet_input, category))
        con.commit()
        con.close()

        return render_template('prediction.html', prediction=category)
    else:
        return render_template('index.html', error_message="No Tweet Text Entered!")


@app.route('/admin_dashboard')
def admin_dashboard():
    if 'admin' not in session:
        return redirect(url_for('adminlogin'))

    con = sqlite3.connect(database)
    cur = con.cursor()

    # Fetch all comments and responses
    cur.execute("SELECT email, comment, category, admin_response FROM comments")
    comments = cur.fetchall()

    # Count the number of unread messages (i.e., messages without an admin response)
    cur.execute("SELECT COUNT(*) FROM comments WHERE admin_response IS NULL")
    unread_message_count = cur.fetchone()[0]

    con.close()

    return render_template("admin_dashboard.html", comments=comments, unread_message_count=unread_message_count)



@app.route('/send_response', methods=['POST'])
def send_response():
    if 'admin' not in session:
        return redirect(url_for('adminlogin'))

    email = request.form['email']  # Get user email
    comment_text = request.form['comment_text']  # Get original comment
    admin_response = request.form['admin_response']  # New response

    if not admin_response:
        return redirect(url_for('admin_dashboard'))

    con = sqlite3.connect(database)
    cur = con.cursor()

    # Fetch all previous comments & responses
    cur.execute("SELECT admin_response FROM comments WHERE email = ? AND comment = ?", (email, comment_text))
    existing_response = cur.fetchone()

    if existing_response and existing_response[0]:  
        # Append new response to previous responses
        updated_response = f"{existing_response[0]} | New: {admin_response}"
    else:
        updated_response = admin_response  # First-time response

    # Update the database with full response history
    cur.execute("UPDATE comments SET admin_response = ? WHERE email = ? AND comment = ?", 
                (updated_response, email, comment_text))
    
    con.commit()
    con.close()

    print(f"Updated Response for Email {email}, Comment: {comment_text}, Response: {updated_response}")

    return redirect(url_for('admin_dashboard'))








@app.route('/message')
def message():
    if 'email' not in session:
        return redirect(url_for('login'))

    email = session['email']
    
    con = sqlite3.connect(database)
    cur = con.cursor()
    
    # Fetch all comments and responses for the user
    cur.execute("""
        SELECT comment, category, COALESCE(admin_response, 'No Response Yet') 
        FROM comments 
        WHERE email=? 
        ORDER BY id DESC
    """, (email,))
    
    user_comments = cur.fetchall()

    # Count messages that have admin responses
    cur.execute("SELECT COUNT(*) FROM comments WHERE email = ? AND admin_response IS NOT NULL", (email,))
    user_message_count = cur.fetchone()[0]

    con.close()

    return render_template('message.html', user_comments=user_comments, user_message_count=user_message_count)




if __name__ == "__main__":
    app.run(port=100)
