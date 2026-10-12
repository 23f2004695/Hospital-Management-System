from app import db
from flask_login import UserMixin
from datetime import datetime, timedelta, timezone
from werkzeug.security import generate_password_hash, check_password_hash


def utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


class UserBase(UserMixin):
    """Shared login behaviour. The session ID includes the role because each role has its own table."""
    role = None

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def get_id(self):
        return f'{self.role}:{self.id}'

class Admin(UserBase, db.Model):
    role = 'admin'
    __tablename__ = 'admins'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    full_name = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(20), nullable=False)
    created_at = db.Column(db.DateTime, default=utcnow)
    is_active = db.Column(db.Boolean, default=True)

    def __init__(self, username, email, password, full_name, phone):
        self.username = username
        self.email = email
        self.password_hash = generate_password_hash(password)
        self.full_name = full_name
        self.phone = phone


class Department(db.Model):
    __tablename__ = 'departments'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    description = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=utcnow)

    doctors = db.relationship('Doctor', backref='department', lazy=True)

class Doctor(UserBase, db.Model):
    role = 'doctor'
    __tablename__ = 'doctors'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    full_name = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(20), nullable=False)
    license_number = db.Column(db.String(50), unique=True, nullable=False)
    department_id = db.Column(db.Integer, db.ForeignKey('departments.id'), nullable=False)
    experience_years = db.Column(db.Integer, default=0)
    qualification = db.Column(db.String(200))
    consultation_fee = db.Column(db.Float, default=500.0)
    is_available = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=utcnow)

    appointments = db.relationship('Appointment', backref='doctor', lazy=True)
    availability = db.relationship('DoctorAvailability', backref='doctor', lazy=True, cascade='all, delete-orphan')

    is_active = True

    SLOT_MINUTES = 30

    def slots_for(self, day):
        """Free 30-minute start times on a given day: inside availability, not booked, not in the past."""
        avail = DoctorAvailability.query.filter_by(doctor_id=self.id, date=day, is_available=True).first()
        if not avail:
            return []
        booked = {a.appointment_time for a in Appointment.query.filter_by(
            doctor_id=self.id, appointment_date=day, status='Booked')}
        now = datetime.now()
        slots = []
        current = datetime.combine(day, avail.start_time)
        end = datetime.combine(day, avail.end_time)
        while current + timedelta(minutes=self.SLOT_MINUTES) <= end:
            if current.time() not in booked and current > now:
                slots.append(current.time())
            current += timedelta(minutes=self.SLOT_MINUTES)
        return slots

    def __init__(self, username, email, password, full_name, phone, license_number, department_id, **kwargs):
        self.username = username
        self.email = email
        self.password_hash = generate_password_hash(password)
        self.full_name = full_name
        self.phone = phone
        self.license_number = license_number
        self.department_id = department_id
        for key, value in kwargs.items():
            setattr(self, key, value)


class Patient(UserBase, db.Model):
    role = 'patient'
    __tablename__ = 'patients'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    full_name = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(20), nullable=False)
    date_of_birth = db.Column(db.Date)
    gender = db.Column(db.String(10))
    address = db.Column(db.Text)
    blood_group = db.Column(db.String(5))
    emergency_contact = db.Column(db.String(20))
    medical_history = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=utcnow)
    is_active = db.Column(db.Boolean, default=True)

    appointments = db.relationship('Appointment', backref='patient', lazy=True)

    def __init__(self, username, email, password, full_name, phone, **kwargs):
        self.username = username
        self.email = email
        self.password_hash = generate_password_hash(password)
        self.full_name = full_name
        self.phone = phone
        for key, value in kwargs.items():
            setattr(self, key, value)


class DoctorAvailability(db.Model):
    __tablename__ = 'doctor_availability'

    id = db.Column(db.Integer, primary_key=True)
    doctor_id = db.Column(db.Integer, db.ForeignKey('doctors.id'), nullable=False)
    date = db.Column(db.Date, nullable=False)
    start_time = db.Column(db.Time, nullable=False)
    end_time = db.Column(db.Time, nullable=False)
    is_available = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=utcnow)

class Appointment(db.Model):
    __tablename__ = 'appointments'

    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patients.id'), nullable=False)
    doctor_id = db.Column(db.Integer, db.ForeignKey('doctors.id'), nullable=False)
    appointment_date = db.Column(db.Date, nullable=False)
    appointment_time = db.Column(db.Time, nullable=False)
    status = db.Column(db.String(20), default='Booked')
    reason = db.Column(db.Text)
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=utcnow)
    updated_at = db.Column(db.DateTime, default=utcnow, onupdate=utcnow)

    treatments = db.relationship('Treatment', backref='appointment', lazy=True)

    @property
    def treatment(self):
        return self.treatments[0] if self.treatments else None

class Treatment(db.Model):
    __tablename__ = 'treatments'

    id = db.Column(db.Integer, primary_key=True)
    appointment_id = db.Column(db.Integer, db.ForeignKey('appointments.id'), nullable=False)
    diagnosis = db.Column(db.Text, nullable=False)
    prescription = db.Column(db.Text)
    treatment_notes = db.Column(db.Text)
    follow_up_required = db.Column(db.Boolean, default=False)
    follow_up_date = db.Column(db.Date)
    created_at = db.Column(db.DateTime, default=utcnow)


USER_MODELS = {'admin': Admin, 'doctor': Doctor, 'patient': Patient}
