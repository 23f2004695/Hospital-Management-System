from app import db
from app.models import Admin, Patient


def test_each_role_lands_on_its_dashboard(make, login, admin):
    make.doctor()
    make.patient()
    assert admin.get('/home').headers['Location'].endswith('/admin/dashboard')
    assert login('drx', 'doctor').get('/home').headers['Location'].endswith('/doctor/dashboard')
    assert login('alice', 'patient').get('/home').headers['Location'].endswith('/patient/dashboard')


def test_wrong_password_or_role_is_rejected(app, make):
    make.patient()
    client = app.test_client()
    res = client.post('/login', data={'username': 'alice', 'password': 'nope', 'user_type': 'patient'})
    assert b'Invalid username' in res.data
    res = client.post('/login', data={'username': 'alice', 'password': 'secret123', 'user_type': 'doctor'})
    assert b'Invalid username' in res.data


def test_patient_one_is_not_loaded_as_admin_one(app, make, login):
    """Admin, doctor and patient IDs all start at 1. The old user loader mixed them up."""
    patient_id = make.patient()
    assert patient_id == 1
    client = login('alice', 'patient')

    page = client.get('/patient/profile').get_data(as_text=True)
    assert 'value="Alice"' in page
    assert 'Hospital Administrator' not in page

    client.post('/patient/profile', data={'full_name': 'Alice Smith', 'email': 'alice@example.com', 'phone': '9876543210'})
    with app.app_context():
        assert db.session.get(Admin, 1).full_name == 'Hospital Administrator'
        assert db.session.get(Patient, 1).full_name == 'Alice Smith'


def test_doctor_one_dashboard_works(make, login):
    make.doctor()
    assert login('drx', 'doctor').get('/doctor/dashboard').status_code == 200


def test_roles_cannot_open_each_others_pages(make, login):
    make.doctor()
    make.patient()
    patient = login('alice', 'patient')
    doctor = login('drx', 'doctor')
    assert patient.get('/admin/dashboard').status_code == 302
    assert patient.get('/doctor/dashboard').status_code == 302
    assert doctor.get('/admin/manage-patients').status_code == 302
    assert doctor.get('/patient/profile').status_code == 302


def test_old_style_session_cannot_become_admin(app, make):
    """A cookie with a bare user id (like the old app issued) is ignored."""
    make.patient()
    client = app.test_client()
    with client.session_transaction() as sess:
        sess['_user_id'] = '1'
        sess['user_type'] = 'admin'
    assert client.get('/admin/dashboard').status_code == 302


def test_register_validates_without_crashing(app):
    client = app.test_client()
    res = client.post('/register', data={'username': 'new'})
    assert res.status_code == 200
    assert b'is required' in res.data

    base = {'username': 'bob', 'email': 'bob@example.com', 'password': 'secret123', 'full_name': 'Bob', 'phone': '9876543210'}
    assert b'valid email' in client.post('/register', data={**base, 'email': 'nope'}).data
    assert b'at least 6' in client.post('/register', data={**base, 'password': '123'}).data
    assert client.post('/register', data=base).status_code == 302
    assert b'already exists' in client.post('/register', data={**base, 'username': 'BOB', 'email': 'other@example.com'}).data


def test_blocked_patient_is_logged_out_and_cannot_log_back_in(app, make, login, admin):
    patient_id = make.patient()
    client = login('alice', 'patient')
    admin.post(f'/admin/patient/{patient_id}/toggle')

    assert client.get('/patient/dashboard').status_code == 302
    res = app.test_client().post('/login', data={'username': 'alice', 'password': 'secret123', 'user_type': 'patient'})
    assert b'deactivated' in res.data


def test_logout_needs_post(make, login):
    make.patient()
    client = login('alice', 'patient')
    assert client.get('/logout').status_code == 405
    assert client.post('/logout').status_code == 302
    assert client.get('/patient/dashboard').status_code == 302


def test_csrf_protection_is_on(tmp_path):
    from app import create_app
    app = create_app({'TESTING': True, 'SQLALCHEMY_DATABASE_URI': f"sqlite:///{tmp_path / 'csrf.db'}"})
    res = app.test_client().post('/login', data={'username': 'admin', 'password': 'admin123', 'user_type': 'admin'})
    assert res.status_code == 302
    assert '/admin' not in res.headers['Location']


def test_404_page(app):
    res = app.test_client().get('/does-not-exist')
    assert res.status_code == 404
    assert b'find that page' in res.data
