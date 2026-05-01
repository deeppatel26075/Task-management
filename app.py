import os
from flask import Flask, render_template, redirect, url_for, flash, request, jsonify
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timezone, timedelta
from models import db, User, Task, TaskInstance, Score

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-prod')
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///project_pa.db')
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
        if User.query.filter_by(email=email).first():
            flash('Email already registered', 'error')
            return redirect(url_for('register'))
        new_user = User(name=name, email=email, password_hash=generate_password_hash(password, method='scrypt'))
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
    tasks = Task.query.filter(Task.user_id == user_id).all()
    for task in tasks:
        task_date = task.date_created.date()
        if task_date > target_date:
            continue
        is_applicable = False
        if task.recurrence_type == 'daily':
            is_applicable = True
        elif task.recurrence_type == 'one-time' and task_date == target_date:
            is_applicable = True
        if is_applicable:
            instance = TaskInstance.query.filter_by(task_id=task.id, date=target_date).first()
            if not instance:
                db.session.add(TaskInstance(task_id=task.id, date=target_date))
    db.session.commit()

def calculate_score_and_streak(user_id, target_date):
    instances = TaskInstance.query.join(Task).filter(
        Task.user_id == user_id,
        TaskInstance.date == target_date
    ).all()

    priority_points = {'High': 20, 'Medium': 10, 'Low': 5}
    status_multiplier = {'Full': 1.0, 'Half': 0.5, 'Missed': -1.0, 'Pending': 0.0}

    daily_total = 0.0
    all_high_done = True
    has_high_tasks = False
    has_any_tasks = len(instances) > 0

    for instance in instances:
        task = instance.task
        points = priority_points.get(task.priority, 0)
        multiplier = status_multiplier.get(instance.status, 0.0)
        daily_total += points * multiplier
        if task.priority == 'High':
            has_high_tasks = True
            if instance.status != 'Full':
                all_high_done = False

    # Update Score record
    score_record = Score.query.filter_by(user_id=user_id, date=target_date).first()
    if not score_record:
        score_record = Score(user_id=user_id, date=target_date, daily_score=daily_total)
        db.session.add(score_record)
    else:
        score_record.daily_score = daily_total

    # Streak logic — only applied when target_date is today
    today = datetime.now(timezone.utc).date()
    if target_date == today:
        user = db.session.get(User, user_id)
        if has_any_tasks:
            if has_high_tasks and all_high_done:
                # Increment streak (or start at 1 if it was 0)
                user.streak_count = user.streak_count + 1
            elif has_high_tasks and not all_high_done:
                user.streak_count = 0
            # If no high tasks exist, streak is neutral (neither increment nor reset)

    db.session.commit()

@app.route('/dashboard')
@login_required
def dashboard():
    date_str = request.args.get('date')
    if date_str:
        try:
            target_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError:
            target_date = datetime.now(timezone.utc).date()
    else:
        target_date = datetime.now(timezone.utc).date()

    generate_instances_for_date(current_user.id, target_date)
    calculate_score_and_streak(current_user.id, target_date)

    score_record = Score.query.filter_by(user_id=current_user.id, date=target_date).first()
    daily_score = score_record.daily_score if score_record else 0.0

    instances = TaskInstance.query.join(Task).filter(
        Task.user_id == current_user.id,
        TaskInstance.date == target_date
    ).order_by(Task.priority).all()

    # Compute task stats for the stat cards
    total = len(instances)
    done = sum(1 for i in instances if i.status == 'Full')
    completion_pct = round((done / total * 100) if total > 0 else 0)

    # Max possible score for normalization (ring visualization)
    max_possible = sum(
        {'High': 20, 'Medium': 10, 'Low': 5}.get(i.task.priority, 0)
        for i in instances
    )
    score_pct = min(100, max(0, round((daily_score / max_possible * 100) if max_possible > 0 else 0)))

    prev_date = (target_date - timedelta(days=1)).strftime('%Y-%m-%d')
    next_date = (target_date + timedelta(days=1)).strftime('%Y-%m-%d')

    return render_template('dashboard.html',
                           daily_score=daily_score,
                           score_pct=score_pct,
                           streak=current_user.streak_count,
                           instances=instances,
                           current_date=target_date.strftime('%Y-%m-%d'),
                           prev_date=prev_date,
                           next_date=next_date,
                           total_tasks=total,
                           done_tasks=done,
                           completion_pct=completion_pct,
                           discipline_tier=current_user.discipline_tier,
                           tier_next=current_user.tier_next_milestone)

@app.route('/progress_data')
@login_required
def progress_data():
    days = int(request.args.get('days', 7))
    end_date = datetime.now(timezone.utc).date()
    start_date = end_date - timedelta(days=days - 1)

    scores = Score.query.filter(
        Score.user_id == current_user.id,
        Score.date >= start_date,
        Score.date <= end_date
    ).order_by(Score.date).all()

    score_map = {s.date: s.daily_score for s in scores}
    labels, data = [], []
    current_dt = start_date
    while current_dt <= end_date:
        labels.append(current_dt.strftime('%m/%d'))
        data.append(score_map.get(current_dt, 0.0))
        current_dt += timedelta(days=1)

    return jsonify({'labels': labels, 'data': data})

@app.route('/add_task', methods=['POST'])
@login_required
def add_task():
    title = request.form.get('title')
    priority = request.form.get('priority')
    recurrence = request.form.get('recurrence', 'one-time')
    current_date = request.form.get('current_date')

    if title and priority in ['High', 'Medium', 'Low']:
        new_task = Task(title=title, priority=priority, recurrence_type=recurrence, user_id=current_user.id)
        try:
            target_date = datetime.strptime(current_date, '%Y-%m-%d')
            new_task.date_created = target_date
        except Exception:
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
        try:
            target_date = datetime.strptime(current_date, '%Y-%m-%d').date()
            calculate_score_and_streak(current_user.id, target_date)
        except Exception:
            pass
        return redirect(url_for('dashboard', date=current_date))
    return redirect(url_for('manage'))

@app.route('/manage')
@login_required
def manage():
    tasks = Task.query.filter_by(user_id=current_user.id).order_by(Task.date_created.desc()).all()
    return render_template('manage.html', tasks=tasks)

@app.route('/analytics')
@login_required
def analytics():
    today = datetime.now(timezone.utc).date()
    start_30 = today - timedelta(days=29)

    scores_30 = Score.query.filter(
        Score.user_id == current_user.id,
        Score.date >= start_30,
        Score.date <= today
    ).order_by(Score.date).all()

    score_map = {s.date: s.daily_score for s in scores_30}

    # Build heatmap data (last 30 days)
    heatmap = []
    cur = start_30
    while cur <= today:
        val = score_map.get(cur, 0.0)
        level = 0
        if val > 0: level = 1
        if val > 10: level = 2
        if val > 20: level = 3
        if val > 35: level = 4
        if val > 50: level = 5
        heatmap.append({'date': cur.strftime('%Y-%m-%d'), 'score': val, 'level': level})
        cur += timedelta(days=1)

    # Insights
    scores_vals = [s.daily_score for s in scores_30]
    avg_score = round(sum(scores_vals) / len(scores_vals), 1) if scores_vals else 0
    best_score = max(scores_vals) if scores_vals else 0
    best_day = next((s.date.strftime('%b %d') for s in scores_30 if s.daily_score == best_score), 'N/A') if scores_vals else 'N/A'
    active_days = sum(1 for v in scores_vals if v > 0)

    # Priority breakdown
    all_instances = TaskInstance.query.join(Task).filter(
        Task.user_id == current_user.id,
        TaskInstance.date >= start_30
    ).all()
    total_inst = len(all_instances)
    high_done = sum(1 for i in all_instances if i.task.priority == 'High' and i.status == 'Full')
    high_total = sum(1 for i in all_instances if i.task.priority == 'High')
    med_done = sum(1 for i in all_instances if i.task.priority == 'Medium' and i.status == 'Full')
    med_total = sum(1 for i in all_instances if i.task.priority == 'Medium')
    low_done = sum(1 for i in all_instances if i.task.priority == 'Low' and i.status == 'Full')
    low_total = sum(1 for i in all_instances if i.task.priority == 'Low')

    def pct(done, total):
        return round(done / total * 100) if total > 0 else 0

    return render_template('analytics.html',
                           heatmap=heatmap,
                           avg_score=avg_score,
                           best_score=round(best_score, 1),
                           best_day=best_day,
                           active_days=active_days,
                           streak=current_user.streak_count,
                           discipline_tier=current_user.discipline_tier,
                           tier_next=current_user.tier_next_milestone,
                           high_pct=pct(high_done, high_total), high_done=high_done, high_total=high_total,
                           med_pct=pct(med_done, med_total), med_done=med_done, med_total=med_total,
                           low_pct=pct(low_done, low_total), low_done=low_done, low_total=low_total,
                           total_tasks_tracked=total_inst)

@app.route('/analytics_data')
@login_required
def analytics_data():
    days = int(request.args.get('days', 30))
    end_date = datetime.now(timezone.utc).date()
    start_date = end_date - timedelta(days=days - 1)
    scores = Score.query.filter(
        Score.user_id == current_user.id,
        Score.date >= start_date,
        Score.date <= end_date
    ).order_by(Score.date).all()
    score_map = {s.date: s.daily_score for s in scores}
    labels, data = [], []
    cur = start_date
    while cur <= end_date:
        labels.append(cur.strftime('%m/%d'))
        data.append(score_map.get(cur, 0.0))
        cur += timedelta(days=1)
    avg = round(sum(data) / len(data), 1) if data else 0
    return jsonify({'labels': labels, 'data': data, 'avg': avg})

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True, port=5000)
