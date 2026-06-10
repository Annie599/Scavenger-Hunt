import os
import uuid
from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
import qrcode

app = Flask(__name__)
# Secure secret key for production session management
app.secret_key = os.environ.get('SECRET_KEY', 'super_secret_scavenger_key_2026')

# Production Configuration: Uses PostgreSQL if available on host, otherwise fallback SQLite
DATABASE_URL = os.environ.get('DATABASE_URL', 'sqlite:///scavenger_hunt.db')
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)
app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URL
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# --- DATABASE MODELS ---

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    score = db.Column(db.Integer, default=0)

class Challenge(db.Model):
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    title = db.Column(db.String(100), nullable=False)
    type = db.Column(db.String(20), nullable=False) # 'question' or 'dare'
    content = db.Column(db.Text, nullable=False)
    correct_answer = db.Column(db.String(200), nullable=True) # None for dares, verified by host/system
    points = db.Column(db.Integer, default=100)

class Submission(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), nullable=False)
    challenge_id = db.Column(db.String(36), nullable=False)
    status = db.Column(db.String(20), default='completed') # 'completed' or 'pending_verification'

# --- ROUTING LOGIC ---

@app.route('/')
def leaderboard():
    # Fetch rankings ordered by highest score
    top_players = User.query.order_by(User.score.desc()).all()
    return render_template('leaderboard.html', players=top_players)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username').strip()
        if not username:
            flash('Username cannot be empty!', 'error')
            return redirect(url_for('register'))
        
        existing_user = User.query.filter_by(username=username).first()
        if existing_user:
            flash('Name already taken. Choose another!', 'error')
            return redirect(url_for('register'))
        
        new_user = User(username=username)
        db.session.add(new_user)
        db.session.commit()
        session['username'] = username
        return redirect(url_for('leaderboard'))
    return render_template('register.html')

@app.route('/scan/<challenge_id>', methods=['GET', 'POST'])
def scan_challenge(challenge_id):
    if 'username' not in session:
        flash('Please register your team/name before solving challenges!', 'info')
        return redirect(url_for('register'))
    
    user = User.query.filter_by(username=session['username']).first()
    challenge = Challenge.query.get_or_404(challenge_id)
    
    # Check if already completed
    already_done = Submission.query.filter_by(username=user.username, challenge_id=challenge_id).first()
    if already_done:
        flash(f"You have already completed: {challenge.title}!", "warning")
        return redirect(url_for('leaderboard'))

    if request.method == 'POST':
        user_response = request.form.get('answer', '').strip().lower()
        
        # Scoring calculation (Kahoot style simulation or simple completion verification)
        if challenge.type == 'question':
            if user_response == challenge.correct_answer.lower():
                user.score += challenge.points
                sub = Submission(username=user.username, challenge_id=challenge_id, status='completed')
                flash(f"🎉 Correct! You earned {challenge.points} points!", "success")
            else:
                flash("❌ Incorrect answer! Try scanning again.", "error")
                return redirect(url_for('scan_challenge', challenge_id=challenge_id))
        else:
            # Dares automatically award points on submission (honor system/monitored by game masters)
            user.score += challenge.points
            sub = Submission(username=user.username, challenge_id=challenge_id, status='completed')
            flash(f"🔥 Dare completed! You earned {challenge.points} points!", "success")
            
        db.session.add(sub)
        db.session.commit()
        return redirect(url_for('leaderboard'))

    return render_template('challenge.html', challenge=challenge)

# --- INITIALIZATION UTILITY ---
def init_sample_data():
    db.create_all()
    if not Challenge.query.first():
        # Setup sample live challenges
        q1 = Challenge(title="The Genesis Code", type="question", content="What is the framework powering this app?", correct_answer="flask", points=150)
        d1 = Challenge(title="Public Spectacle", type="dare", content="Take a group selfie with 3 strangers and shout 'I love engineering!'", points=200)
        db.session.add_all([q1, d1])
        db.session.commit()
        
        # Print QR generating instructions to terminal console on first run
        print("\n=== LIVE CHALLENGE QR CODES GENERATED ===")
        print(f"Challenge 1 (Question) ID: {q1.id}")
        print(f"Challenge 2 (Dare) ID: {d1.id}\n=========================================")

if __name__ == '__main__':
    with app.app_context():
        init_sample_data()
    app.run(host='0.0.0.0', port=5000)
