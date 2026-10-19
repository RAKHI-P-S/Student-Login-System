import os
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)
app.secret_key = 'super_secret_session_key_for_local_workspace'

# MySQL Configuration
app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+pymysql://root:@localhost/student_management_db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
os.makedirs(app.instance_path, exist_ok=True)
# ==========================================
# DATABASE MODELS
# ==========================================

class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(100), nullable=False)
    role = db.Column(db.String(20), nullable=False) # 'admin' or 'student'

class Student(db.Model):
    __tablename__ = 'students'
    id = db.Column(db.Integer, primary_key=True)
    roll_number = db.Column(db.String(50), unique=True, nullable=False)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    current_semester = db.Column(db.String(10), nullable=False)
    
    leaves = db.relationship('LeaveRequest', backref='student', lazy=True, cascade="all, delete-orphan")
    attendance_records = db.relationship('Attendance', backref='student', lazy=True, cascade="all, delete-orphan")
    marks = db.relationship('Mark', backref='student', lazy=True, cascade="all, delete-orphan")

class LeaveRequest(db.Model):
    __tablename__ = 'leave_requests'
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('students.id'), nullable=False)
    semester = db.Column(db.String(10), nullable=False)
    start_date = db.Column(db.String(20), nullable=False)
    end_date = db.Column(db.String(20), nullable=False)
    reason = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(20), default='Pending') # 'Pending', 'Approved', 'Rejected'

class Attendance(db.Model):
    __tablename__ = 'attendance'
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('students.id'), nullable=False)
    semester = db.Column(db.String(10), nullable=False)
    date = db.Column(db.String(20), nullable=False)
    status = db.Column(db.String(20), nullable=False) # 'Present' or 'Absent'

class Mark(db.Model):
    __tablename__ = 'marks'
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('students.id'), nullable=False)
    semester = db.Column(db.String(10), nullable=False)
    subject = db.Column(db.String(100), nullable=False)
    score = db.Column(db.Integer, nullable=False)

def init_db():
    with app.app_context():
        db.create_all()
        if not User.query.filter_by(email='admin@institution.com').first():
            db.session.add(User(email='admin@institution.com', password='admin123', role='admin'))
            db.session.commit()

# ==========================================
# AUTHENTICATION ROUTES
# ==========================================

@app.route('/', methods=['GET', 'POST'])
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email').strip()
        password = request.form.get('password').strip()
        selected_role = request.form.get('role')
        
        user = User.query.filter_by(email=email, password=password).first()
        
        if user and user.role == selected_role:
            session['user_id'] = user.id
            session['email'] = user.email
            session['role'] = user.role
            
            if user.role == 'admin':
                return redirect(url_for('admin_dashboard'))
            elif user.role == 'student':
                student_profile = Student.query.filter_by(email=user.email).first()
                if student_profile:
                    session['student_id'] = student_profile.id
                return redirect(url_for('student_dashboard'))
        
        flash('Invalid email, password, or role.', 'danger')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('Logged out successfully.', 'info')
    return redirect(url_for('login'))

# ==========================================
# ADMIN ROUTES
# ==========================================

@app.route('/admin/dashboard')
def admin_dashboard():
    if session.get('role') != 'admin': return redirect(url_for('login'))
    return render_template('admin/dashboard.html')

@app.route('/admin/students/add', methods=['GET', 'POST'])
def admin_add_student():
    if session.get('role') != 'admin': return redirect(url_for('login'))
    
    if request.method == 'POST':
        name = request.form.get('name').strip()
        email = request.form.get('email').strip()
        roll_num = request.form.get('roll_number').strip()
        semester = request.form.get('semester')
        password = request.form.get('password').strip()
        
        if User.query.filter_by(email=email).first() or Student.query.filter_by(roll_number=roll_num).first():
            flash('Error: Email or Roll Number already exists.', 'danger')
        else:
            try:
                db.session.add(User(email=email, password=password, role='student'))
                db.session.add(Student(roll_number=roll_num, name=name, email=email, current_semester=semester))
                db.session.commit()
                flash('Student added successfully.', 'success')
                return redirect(url_for('admin_roll_list'))
            except Exception:
                db.session.rollback()
                flash('An error occurred. Please try again.', 'danger')
                
    return render_template('admin/add_student.html')

@app.route('/admin/roll-list')
def admin_roll_list():
    if session.get('role') != 'admin': return redirect(url_for('login'))
    students = Student.query.order_by(Student.roll_number.asc()).all()
    return render_template('admin/roll_list.html', students=students)

@app.route('/admin/attendance', methods=['GET', 'POST'])
def admin_manage_attendance():
    if session.get('role') != 'admin': return redirect(url_for('login'))
    
    target_date = request.form.get('date') or datetime.today().strftime('%Y-%m-%d')
    target_sem = request.form.get('semester') or 'S1'
    
    if request.method == 'POST' and 'save_attendance' in request.form:
        students_to_mark = Student.query.filter_by(current_semester=target_sem).all()
        for s in students_to_mark:
            status = request.form.get(f"status_{s.id}", 'Absent')
            existing = Attendance.query.filter_by(student_id=s.id, date=target_date).first()
            if existing:
                existing.status = status
            else:
                db.session.add(Attendance(student_id=s.id, semester=target_sem, date=target_date, status=status))
        db.session.commit()
        flash('Attendance saved successfully.', 'success')
        
    students = Student.query.filter_by(current_semester=target_sem).order_by(Student.name.asc()).all()
    return render_template('admin/attendance.html', students=students, target_date=target_date, target_sem=target_sem)

@app.route('/admin/marks/add', methods=['GET', 'POST'])
def admin_add_marks():
    if session.get('role') != 'admin': return redirect(url_for('login'))
    
    if request.method == 'POST':
        student_id = request.form.get('student_id')
        semester = request.form.get('semester')
        subject = request.form.get('subject').strip()
        score = request.form.get('score')
        
        db.session.add(Mark(student_id=student_id, semester=semester, subject=subject, score=score))
        db.session.commit()
        flash('Marks added successfully.', 'success')
        return redirect(url_for('admin_dashboard'))
        
    students = Student.query.order_by(Student.name.asc()).all()
    return render_template('admin/add_mark.html', students=students)

@app.route('/admin/leaves', methods=['GET', 'POST'])
def admin_manage_leaves():
    if session.get('role') != 'admin': return redirect(url_for('login'))
    
    if request.method == 'POST':
        request_id = request.form.get('request_id')
        action = request.form.get('action')
        leave = LeaveRequest.query.get(request_id)
        if leave:
            leave.status = action
            db.session.commit()
            flash(f'Leave status updated to {action}.', 'success')
            
    leaves = LeaveRequest.query.join(Student).order_by(LeaveRequest.id.desc()).all()
    return render_template('admin/leave_manage.html', leaves=leaves)

# ==========================================
# STUDENT ROUTES
# ==========================================

@app.route('/student/dashboard')
def student_dashboard():
    if session.get('role') != 'student': return redirect(url_for('login'))
    return render_template('student/dashboard.html')

@app.route('/student/profile')
def student_profile():
    if session.get('role') != 'student': return redirect(url_for('login'))
    profile = Student.query.get(session.get('student_id'))
    return render_template('student/profile.html', profile=profile)

@app.route('/student/leave/apply', methods=['GET', 'POST'])
def student_apply_leave():
    if session.get('role') != 'student': return redirect(url_for('login'))
    
    student_id = session.get('student_id')
    profile = Student.query.get(student_id)
    
    if request.method == 'POST':
        new_leave = LeaveRequest(
            student_id=student_id,
            semester=profile.current_semester,
            start_date=request.form.get('start_date'),
            end_date=request.form.get('end_date'),
            reason=request.form.get('reason').strip()
        )
        db.session.add(new_leave)
        db.session.commit()
        flash('Leave application submitted.', 'success')
        return redirect(url_for('student_dashboard'))
        
    leaves = LeaveRequest.query.filter_by(student_id=student_id).order_by(LeaveRequest.id.desc()).all()
    return render_template('student/leave_apply.html', leaves=leaves, current_sem=profile.current_semester)

@app.route('/student/grade-card')
def student_grade_card():
    if session.get('role') != 'student': return redirect(url_for('login'))
    student_id = session.get('student_id')
    selected_sem = request.args.get('semester', 'S1')
    marks = Mark.query.filter_by(student_id=student_id, semester=selected_sem).all()
    return render_template('student/grade_card.html', marks=marks, selected_sem=selected_sem)

if __name__ == '__main__':
    init_db()
    app.run(debug=True, port=5000)

