import os
import sys
from datetime import date, time, timedelta

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app, db  # noqa: E402
from app.models import Doctor, Patient, DoctorAvailability, Appointment  # noqa: E402

TOMORROW = date.today() + timedelta(days=1)
PASSWORD = 'secret123'


@pytest.fixture
def app(tmp_path):
    app = create_app({
        'TESTING': True,
        'SQLALCHEMY_DATABASE_URI': f"sqlite:///{tmp_path / 'test.db'}",
        'WTF_CSRF_ENABLED': False,
        'SECRET_KEY': 'test-secret',
    })
    yield app
    with app.app_context():
        db.session.remove()
        db.drop_all()


@pytest.fixture
def make(app):
    """Helpers that create records directly in the database."""
    class Make:
        def doctor(self, username='drx', available_on=TOMORROW, start=time(9), end=time(12), **kw):
            with app.app_context():
                d = Doctor(username=username, email=f'{username}@example.com', password=PASSWORD,
                           full_name=username.title(), phone='9876543210',
                           license_number=f'LIC-{username}', department_id=kw.pop('department_id', 1), **kw)
                db.session.add(d)
                db.session.commit()
                if available_on:
                    db.session.add(DoctorAvailability(doctor_id=d.id, date=available_on, start_time=start, end_time=end))
                    db.session.commit()
                return d.id

        def patient(self, username='alice'):
            with app.app_context():
                p = Patient(username=username, email=f'{username}@example.com', password=PASSWORD,
                            full_name=username.title(), phone='9876543210')
                db.session.add(p)
                db.session.commit()
                return p.id

        def appointment(self, patient_id, doctor_id, day=TOMORROW, at=time(10), status='Booked'):
            with app.app_context():
                a = Appointment(patient_id=patient_id, doctor_id=doctor_id, appointment_date=day,
                                appointment_time=at, status=status)
                db.session.add(a)
                db.session.commit()
                return a.id
    return Make()


@pytest.fixture
def login(app):
    def _login(username, role, password=PASSWORD):
        client = app.test_client()
        res = client.post('/login', data={'username': username, 'password': password, 'user_type': role})
        assert res.status_code == 302, f'login failed for {username}'
        return client
    return _login


@pytest.fixture
def admin(login):
    return login('admin', 'admin', 'admin123')


def book(client, doctor_id, day=TOMORROW, at='10:00'):
    return client.post('/patient/book-appointment', data={
        'doctor_id': doctor_id, 'appointment_date': day.isoformat(), 'appointment_time': at
    }, follow_redirects=True)
