from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
import os

db = SQLAlchemy()
login_manager = LoginManager()

def create_app():
    app = Flask(__name__)

    # Configuration
    app.config['SECRET_KEY'] = 'hospital-management-secret-key-2025'
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///hospital.db'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    # Initialize extensions
    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Please log in to access this page.'
    login_manager.login_message_category = 'info'

    # User loader for Flask-Login
    @login_manager.user_loader
    def load_user(user_id):
        from app.models import Admin, Doctor, Patient
        # Check if user is admin
        user = Admin.query.get(int(user_id))
        if user:
            return user
        # Check if user is doctor
        user = Doctor.query.get(int(user_id))
        if user:
            return user
        # Check if user is patient
        user = Patient.query.get(int(user_id))
        if user:
            return user
        return None

    # Register Blueprints
    from app.routes.auth import auth
    from app.routes.admin import admin
    from app.routes.doctor import doctor
    from app.routes.patient import patient

    app.register_blueprint(auth)
    app.register_blueprint(admin, url_prefix='/admin')
    app.register_blueprint(doctor, url_prefix='/doctor')
    app.register_blueprint(patient, url_prefix='/patient')

    # Main routes
    @app.route('/')
    def index():
        from flask import render_template
        return render_template('index.html')

    return app
