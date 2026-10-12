import re
from datetime import datetime
from functools import wraps

from flask import flash, redirect, url_for
from flask_login import current_user

EMAIL_RE = re.compile(r'^[^@\s]+@[^@\s]+\.[^@\s]+$')
PHONE_RE = re.compile(r'^\+?[0-9 -]{7,20}$')
MIN_PASSWORD_LENGTH = 6
BLOOD_GROUPS = ('A+', 'A-', 'B+', 'B-', 'AB+', 'AB-', 'O+', 'O-')
GENDERS = ('Male', 'Female', 'Other')


class FormError(ValueError):
    """Raised for bad form input; the message is shown to the user."""


def role_required(role):
    """Only let logged-in users with this role through (admin, doctor or patient)."""
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            if not current_user.is_authenticated:
                flash('Please log in to access this page.', 'info')
                return redirect(url_for('auth.login'))
            if current_user.role != role:
                flash(f'That page is only for {role}s.', 'error')
                return redirect(url_for('auth.home'))
            return f(*args, **kwargs)
        return wrapper
    return decorator


def field(form, name, label=None, required=True, max_len=200):
    value = (form.get(name) or '').strip()
    label = label or name.replace('_', ' ').capitalize()
    if required and not value:
        raise FormError(f'{label} is required.')
    if len(value) > max_len:
        raise FormError(f'{label} is too long (max {max_len} characters).')
    return value


def email_field(form, name='email'):
    value = field(form, name, 'Email', max_len=120).lower()
    if not EMAIL_RE.match(value):
        raise FormError('Please enter a valid email address.')
    return value


def phone_field(form, name='phone', label='Phone', required=True):
    value = field(form, name, label, required=required, max_len=20)
    if value and not PHONE_RE.match(value):
        raise FormError(f'{label} should only contain digits (7 to 20 of them).')
    return value


def password_field(form, name='password'):
    value = form.get(name) or ''
    if len(value) < MIN_PASSWORD_LENGTH:
        raise FormError(f'Password must be at least {MIN_PASSWORD_LENGTH} characters.')
    return value


def number_field(form, name, label, cast=int, default=0, minimum=0):
    raw = (form.get(name) or '').strip()
    if not raw:
        return default
    try:
        value = cast(raw)
    except ValueError:
        raise FormError(f'{label} must be a number.')
    if value < minimum:
        raise FormError(f'{label} cannot be negative.')
    return value


def date_field(value, label='Date', required=True):
    if not value:
        if required:
            raise FormError(f'{label} is required.')
        return None
    try:
        return datetime.strptime(value, '%Y-%m-%d').date()
    except ValueError:
        raise FormError(f'{label} is not a valid date.')


def time_field(value, label='Time'):
    if not value:
        raise FormError(f'{label} is required.')
    try:
        return datetime.strptime(value, '%H:%M').time()
    except ValueError:
        raise FormError(f'{label} is not a valid time.')


def int_arg(value):
    """Parse an id from a query string; returns None for anything that isn't a number."""
    return int(value) if value and str(value).isdigit() else None
