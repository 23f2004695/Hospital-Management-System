from flask import Blueprint, render_template, request, flash, redirect, url_for, session
from flask_login import login_user, logout_user, login_required, current_user
from sqlalchemy import func

from app import db
from app.models import Patient, USER_MODELS
from app.utils import FormError, field, email_field, phone_field, password_field

auth = Blueprint('auth', __name__)


@auth.route('/home')
@login_required
def home():
    """Send each user to their own dashboard."""
    return redirect(url_for(f'{current_user.role}.dashboard'))


@auth.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('auth.home'))

    if request.method == 'POST':
        username = (request.form.get('username') or '').strip()
        password = request.form.get('password') or ''
        model = USER_MODELS.get(request.form.get('user_type'))

        user = model.query.filter(func.lower(model.username) == username.lower()).first() if model else None

        if not user or not user.check_password(password):
            flash('Invalid username, password, or user type!', 'error')
        elif not user.is_active:
            flash('Your account has been deactivated. Please contact the hospital.', 'error')
        else:
            session.clear()
            login_user(user)
            return redirect(url_for('auth.home'))

    return render_template('login.html')


@auth.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('auth.home'))

    if request.method == 'POST':
        try:
            username = field(request.form, 'username', max_len=80)
            email = email_field(request.form)
            password = password_field(request.form)
            full_name = field(request.form, 'full_name', 'Full name', max_len=100)
            phone = phone_field(request.form)

            if Patient.query.filter(func.lower(Patient.username) == username.lower()).first():
                raise FormError('Username already exists!')
            if Patient.query.filter(func.lower(Patient.email) == email).first():
                raise FormError('Email already exists!')
        except FormError as e:
            flash(str(e), 'error')
            return render_template('register.html', form=request.form)

        db.session.add(Patient(username=username, email=email, password=password, full_name=full_name, phone=phone))
        db.session.commit()

        flash('Registration successful! Please login.', 'success')
        return redirect(url_for('auth.login'))

    return render_template('register.html', form={})


@auth.route('/logout', methods=['POST'])
@login_required
def logout():
    logout_user()
    session.clear()
    flash('You have been logged out.', 'info')
    return redirect(url_for('index'))
