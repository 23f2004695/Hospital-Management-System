import os
import secrets

from flask import Flask, render_template, flash, redirect, request
from flask_login import LoginManager
from flask_sqlalchemy import SQLAlchemy
from flask_wtf.csrf import CSRFProtect, CSRFError

db = SQLAlchemy()
login_manager = LoginManager()
csrf = CSRFProtect()

DEFAULT_DEPARTMENTS = [
    ('Cardiology', 'Heart and cardiovascular system care'),
    ('Neurology', 'Brain and nervous system disorders'),
    ('Oncology', 'Cancer treatment and care'),
    ('Pediatrics', 'Medical care for children'),
    ('Orthopedics', 'Bone and muscle disorders'),
    ('Dermatology', 'Skin and related conditions'),
    ('General Medicine', 'General health and wellness'),
    ('Emergency', 'Emergency medical services'),
]


def create_app(config=None):
    app = Flask(__name__, instance_relative_config=True)
    os.makedirs(app.instance_path, exist_ok=True)

    app.config.update(
        SECRET_KEY=os.environ.get('SECRET_KEY') or _instance_secret(app.instance_path),
        SQLALCHEMY_DATABASE_URI=os.environ.get('DATABASE_URL', 'sqlite:///hospital.db'),
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        ADMIN_USERNAME=os.environ.get('ADMIN_USERNAME', 'admin'),
        ADMIN_PASSWORD=os.environ.get('ADMIN_PASSWORD', 'admin123'),
        ADMIN_EMAIL=os.environ.get('ADMIN_EMAIL', 'admin@hospital.com'),
    )
    if config:
        app.config.update(config)

    db.init_app(app)
    csrf.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Please log in to access this page.'
    login_manager.login_message_category = 'info'

    @login_manager.user_loader
    def load_user(user_id):
        # IDs look like "patient:3". Admins, doctors and patients live in separate tables,
        # so a bare number would match the wrong person (patient 1 would load as admin 1).
        from app.models import USER_MODELS
        role, _, raw_id = str(user_id).partition(':')
        model = USER_MODELS.get(role)
        if not model or not raw_id.isdigit():
            return None
        user = db.session.get(model, int(raw_id))
        if user is None or not user.is_active:
            return None
        return user

    from app.routes.auth import auth
    from app.routes.admin import admin
    from app.routes.doctor import doctor
    from app.routes.patient import patient

    app.register_blueprint(auth)
    app.register_blueprint(admin, url_prefix='/admin')
    app.register_blueprint(doctor, url_prefix='/doctor')
    app.register_blueprint(patient, url_prefix='/patient')

    @app.route('/')
    def index():
        return render_template('index.html')

    # A global (not a context processor) so imported macros can use it too
    badges = {'Booked': 'bg-primary', 'Completed': 'bg-success', 'Cancelled': 'bg-secondary'}
    app.jinja_env.globals['status_badge'] = lambda status: badges.get(status, 'bg-light text-dark')

    @app.errorhandler(CSRFError)
    def csrf_error(e):
        flash('Your form expired. Please try again.', 'error')
        return redirect(request.referrer or '/')

    @app.errorhandler(403)
    def forbidden(e):
        return render_template('error.html', code=403, message="You don't have access to that page."), 403

    @app.errorhandler(404)
    def not_found(e):
        return render_template('error.html', code=404, message="We couldn't find that page."), 404

    @app.errorhandler(500)
    def server_error(e):
        db.session.rollback()
        return render_template('error.html', code=500, message='Something went wrong on our side. Please try again.'), 500

    with app.app_context():
        db.create_all()
        _seed_defaults(app)

    return app


def _instance_secret(instance_path):
    """Use a random secret key kept in the instance folder, so it's never in the code."""
    path = os.path.join(instance_path, 'secret_key')
    if not os.path.exists(path):
        with open(path, 'w') as f:
            f.write(secrets.token_hex(32))
    with open(path) as f:
        return f.read().strip()


def _seed_defaults(app):
    from app.models import Admin, Department

    if not Admin.query.first():
        db.session.add(Admin(
            username=app.config['ADMIN_USERNAME'],
            email=app.config['ADMIN_EMAIL'],
            password=app.config['ADMIN_PASSWORD'],
            full_name='Hospital Administrator',
            phone='1234567890',
        ))

    if not Department.query.first():
        for name, description in DEFAULT_DEPARTMENTS:
            db.session.add(Department(name=name, description=description))

    db.session.commit()
