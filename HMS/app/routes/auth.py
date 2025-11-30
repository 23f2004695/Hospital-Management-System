from flask import Blueprint, render_template, request, flash, redirect, url_for, session
from flask_login import login_user, logout_user, login_required, current_user
from app.models import Admin, Doctor, Patient
from app import db

auth = Blueprint('auth', __name__)

@auth.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user_type = request.form.get('user_type')

        user = None

        if user_type == 'admin':
            user = Admin.query.filter_by(username=username).first()
        elif user_type == 'doctor':
            user = Doctor.query.filter_by(username=username).first()
        elif user_type == 'patient':
            user = Patient.query.filter_by(username=username).first()

        if user and user.check_password(password):
            login_user(user)
            session['user_type'] = user_type

            if user_type == 'admin':
                return redirect(url_for('admin.dashboard'))
            elif user_type == 'doctor':
                return redirect(url_for('doctor.dashboard'))
            else:
                return redirect(url_for('patient.dashboard'))
        else:
            flash('Invalid username, password, or user type!', 'error')

    return render_template('login.html')

@auth.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        full_name = request.form.get('full_name')
        phone = request.form.get('phone')

        if Patient.query.filter_by(username=username).first():
            flash('Username already exists!', 'error')
            return render_template('register.html')

        if Patient.query.filter_by(email=email).first():
            flash('Email already exists!', 'error')
            return render_template('register.html')

        patient = Patient(
            username=username,
            email=email,
            password=password,
            full_name=full_name,
            phone=phone
        )

        db.session.add(patient)
        db.session.commit()

        flash('Registration successful! Please login.', 'success')
        return redirect(url_for('auth.login'))

    return render_template('register.html')

@auth.route('/logout')
@login_required
def logout():
    logout_user()
    session.pop('user_type', None)
    flash('You have been logged out.', 'info')
    return redirect(url_for('index'))
