import os
from flask import Flask, render_template, redirect, url_for, flash, request, jsonify
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timezone, timedelta
from models import db, User, Task, TaskInstance, Score

app = Flask(__name__)
app.config['SECRET_KEY'] = 'dev-secret-key-change-in-prod'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///project_pa.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)
login_manager = LoginManager()
login_manager.login_view = 'login'
login_manager.init_app(app)

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))

@app.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        user = User.query.filter_by(email=email).first()
        
        if user and check_password_hash(user.password_hash, password):
            login_user(user)
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid email or password', 'error')
            
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
        
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        password = request.form.get('password')
        
        user_exists = User.query.filter_by(email=email).first()
        if user_exists:
            flash('Email already registered', 'error')
            return redirect(url_for('register'))
            
        new_user = User(
            name=name,
            email=email,
            password_hash=generate_password_hash(password, method='scrypt')
        )
        db.session.add(new_user)
        db.session.commit()
        
        login_user(new_user)
        return redirect(url_for('dashboard'))
        
    return render_template('register.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

def generate_instances_for_date(user_id, target_date):
    """Ensure TaskInstances exist for all applicable tasks on target_date."""
    # Find all tasks that apply to this date
    # 1. Daily tasks created on or before this date
    # 2. One-time tasks created exactly on this date
    tasks = Task.query.filter(Task.user_id == user_id).all()
    
    for task in tasks:
        task_date = task.date_created.date()
        if task_date > target_date:
            continue # Task wasn't created yet on target_date
            
        is_applicable = False
        if task.recurrence_type == 'daily':
            is_applicable = True
        elif task.recurrence_type == 'one-time' and task_date == target_date:
            is_applicable = True
            
        if is_applicable:
            # Check if instance already exists
            instance = TaskInstance.query.filter_by(task_id=task.id, date=target_date).first()
            if not instance:
                instance = TaskInstance(task_id=task.id, date=target_date)
                db.session.add(instance)
                
    db.session.commit()

@app.route('/dashboard')
@login_required
def dashboard():
    # Parse date from query param, default to today
    date_str = request.args.get('date')
    if date_str:
        try:
            target_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError:
            target_date = datetime.now(timezone.utc).date()
    else:
        target_date = datetime.now(timezone.utc).date()
        
    # Generate missing instances for the requested date
    generate_instances_for_date(current_user.id, target_date)
    
    # Calculate score for that specific date
    calculate_score_and_streak(current_user.id, target_date)
    
    # Get the score record for the date
    score_record = Score.query.filter_by(user_id=current_user.id, date=target_date).first()
    daily_score = score_record.daily_score if score_record else 0.0
    
    # Get instances for the date to display
    instances = TaskInstance.query.join(Task).filter(
        Task.user_id == current_user.id,
        TaskInstance.date == target_date
    ).order_by(Task.priority).all() # Simplistic ordering
    
    # Calculate previous and next dates for UI navigation
    prev_date = (target_date - timedelta(days=1)).strftime('%Y-%m-%d')
    next_date = (target_date + timedelta(days=1)).strftime('%Y-%m-%d')
    
    return render_template('dashboard.html', 
                           daily_score=daily_score, 
                           streak=current_user.streak_count,
                           instances=instances,
                           current_date=target_date.strftime('%Y-%m-%d'),
                           prev_date=prev_date,
                           next_date=next_date)

@app.route('/progress_data')
@login_required
def progress_data():
    days = int(request.args.get('days', 7))
    end_date = datetime.now(timezone.utc).date()
    start_date = end_date - timedelta(days=days-1)
    
    scores = Score.query.filter(
        Score.user_id == current_user.id,
        Score.date >= start_date,
        Score.date <= end_date
    ).order_by(Score.date).all()
    
    # Create a map to ensure all days have a value (even if 0)
    score_map = {score.date: score.daily_score for score in scores}
    
    labels = []
    data = []
    
    current_dt = start_date
    while current_dt <= end_date:
        labels.append(current_dt.strftime('%m/%d'))
        data.append(score_map.get(current_dt, 0.0))
        current_dt += timedelta(days=1)
        
    return jsonify({'labels': labels, 'data': data})

def calculate_score_and_streak(user_id, target_date):
    # Calculate for the specific target date
    instances = TaskInstance.query.join(Task).filter(
        Task.user_id == user_id,
        TaskInstance.date == target_date
    ).all()
    
    priority_points = {'High': 20, 'Medium': 10, 'Low': 5}
    status_multiplier = {'Full': 1.0, 'Half': 0.5, 'Missed': -1.0, 'Pending': 0.0}
    
    daily_total = 0
    all_high_done = True
    has_high_tasks = False
    
    for instance in instances:
        task = instance.task
        points = priority_points.get(task.priority, 0)
        multiplier = status_multiplier.get(instance.status, 0.0)
        daily_total += points * multiplier
        
        if task.priority == 'High':
            has_high_tasks = True
            if instance.status != 'Full':
                all_high_done = False
                
    # Update Score
    score_record = Score.query.filter_by(user_id=user_id, date=target_date).first()
    if not score_record:
        score_record = Score(user_id=user_id, date=target_date, daily_score=daily_total)
        db.session.add(score_record)
    else:
        score_record.daily_score = daily_total
        
    # Simplified Streak Logic (only applied if target_date is today)
    today = datetime.now(timezone.utc).date()
    if target_date == today:
        user = db.session.get(User, user_id)
        if not all_high_done and has_high_tasks:
            user.streak_count = 0

    db.session.commit()

@app.route('/add_task', methods=['POST'])
@login_required
def add_task():
    title = request.form.get('title')
    priority = request.form.get('priority')
    recurrence = request.form.get('recurrence', 'one-time')
    current_date = request.form.get('current_date')
    
    if title and priority in ['High', 'Medium', 'Low']:
        new_task = Task(title=title, priority=priority, recurrence_type=recurrence, user_id=current_user.id)
        # If user is adding it while viewing a past date, create it for that date
        try:
            target_date = datetime.strptime(current_date, '%Y-%m-%d')
            new_task.date_created = target_date
        except:
            pass
            
        db.session.add(new_task)
        db.session.commit()
        
    if current_date:
        return redirect(url_for('dashboard', date=current_date))
    return redirect(url_for('dashboard'))

@app.route('/update_task_instance/<int:instance_id>/<status>')
@login_required
def update_task_instance(instance_id, status):
    if status not in ['Full', 'Half', 'Missed', 'Pending']:
        return redirect(url_for('dashboard'))
        
    instance = db.session.get(TaskInstance, instance_id)
    if not instance or instance.task.user_id != current_user.id:
        return redirect(url_for('dashboard'))
        
    instance.status = status
    db.session.commit()
    
    calculate_score_and_streak(current_user.id, instance.date)
    return redirect(url_for('dashboard', date=instance.date.strftime('%Y-%m-%d')))

@app.route('/delete_task/<int:task_id>')
@login_required
def delete_task(task_id):
    current_date = request.args.get('current_date')
    task = db.session.get(Task, task_id)
    if task and task.user_id == current_user.id:
        db.session.delete(task)
        db.session.commit()
        
    if current_date:
        # Recalculate score without this task
        target_date = datetime.strptime(current_date, '%Y-%m-%d').date()
        calculate_score_and_streak(current_user.id, target_date)
        return redirect(url_for('dashboard', date=current_date))
    return redirect(url_for('manage'))

@app.route('/manage')
@login_required
def manage():
    tasks = Task.query.filter_by(user_id=current_user.id).order_by(Task.date_created.desc()).all()
    return render_template('manage.html', tasks=tasks)

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True, port=5000)
