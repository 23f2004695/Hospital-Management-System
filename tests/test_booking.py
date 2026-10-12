from datetime import date, time, timedelta

from app import db
from app.models import Appointment, Doctor
from conftest import TOMORROW, book


def count(app, **filters):
    with app.app_context():
        return Appointment.query.filter_by(**filters).count()


def test_slots_are_30_minutes_and_fit_inside_working_hours(app, make):
    doctor_id = make.doctor(start=time(9), end=time(11))
    with app.app_context():
        slots = db.session.get(Doctor, doctor_id).slots_for(TOMORROW)
    assert [s.strftime('%H:%M') for s in slots] == ['09:00', '09:30', '10:00', '10:30']


def test_booked_slots_disappear(app, make):
    doctor_id = make.doctor()
    make.appointment(make.patient(), doctor_id, at=time(10))
    with app.app_context():
        assert time(10) not in db.session.get(Doctor, doctor_id).slots_for(TOMORROW)


def test_past_slots_today_are_not_offered(app, make):
    doctor_id = make.doctor(available_on=date.today(), start=time(0), end=time(0, 30))
    with app.app_context():
        assert db.session.get(Doctor, doctor_id).slots_for(date.today()) == []


def test_patient_can_book_a_free_slot(app, make, login):
    doctor_id = make.doctor()
    make.patient()
    res = book(login('alice', 'patient'), doctor_id)
    assert b'Appointment booked' in res.data
    assert count(app, status='Booked') == 1


def test_booking_at_closing_time_is_rejected(app, make, login):
    """The old check allowed a 12:00 appointment when the doctor stops at 12:00."""
    doctor_id = make.doctor(end=time(12))
    make.patient()
    res = book(login('alice', 'patient'), doctor_id, at='12:00')
    assert b'no longer available' in res.data
    assert count(app) == 0


def test_same_slot_cannot_be_booked_twice(app, make, login):
    doctor_id = make.doctor()
    make.patient('alice')
    make.patient('bob')
    book(login('alice', 'patient'), doctor_id)
    res = book(login('bob', 'patient'), doctor_id)
    assert b'no longer available' in res.data
    assert count(app) == 1


def test_patient_cannot_be_in_two_places_at_once(app, make, login):
    dr1 = make.doctor('drone')
    dr2 = make.doctor('drtwo')
    make.patient()
    client = login('alice', 'patient')
    book(client, dr1)
    res = book(client, dr2)
    assert b'already have an appointment' in res.data
    assert count(app) == 1


def test_cannot_book_unavailable_or_missing_doctor(app, make, login):
    doctor_id = make.doctor(is_available=False)
    make.patient()
    client = login('alice', 'patient')
    assert b'not taking appointments' in book(client, doctor_id).data
    assert b'not taking appointments' in book(client, 999).data
    assert count(app) == 0


def test_garbage_input_does_not_crash(make, login):
    make.doctor()
    make.patient()
    client = login('alice', 'patient')
    assert client.post('/patient/book-appointment', data={'doctor_id': 'abc'}).status_code == 302
    assert client.get('/patient/book-appointment?department=abc&doctor=xyz&date=nope').status_code == 200


def test_cancelled_slot_can_be_booked_again(app, make, login):
    doctor_id = make.doctor()
    make.patient('alice')
    make.patient('bob')
    alice = login('alice', 'patient')
    book(alice, doctor_id)
    with app.app_context():
        appt_id = Appointment.query.first().id
    alice.post(f'/patient/cancel-appointment/{appt_id}')
    assert b'Appointment booked' in book(login('bob', 'patient'), doctor_id).data


def test_patient_cannot_cancel_someone_elses_appointment(app, make, login):
    doctor_id = make.doctor()
    alice_id = make.patient('alice')
    make.patient('bob')
    appt_id = make.appointment(alice_id, doctor_id)
    assert login('bob', 'patient').post(f'/patient/cancel-appointment/{appt_id}').status_code == 404
    assert count(app, status='Booked') == 1


def test_cancel_needs_post(make, login):
    doctor_id = make.doctor()
    appt_id = make.appointment(make.patient(), doctor_id)
    assert login('alice', 'patient').get(f'/patient/cancel-appointment/{appt_id}').status_code == 405


def test_booking_page_walks_through_the_steps(make, login):
    make.doctor()
    make.patient()
    client = login('alice', 'patient')
    page = client.get('/patient/book-appointment?department=1&doctor=1').get_data(as_text=True)
    assert TOMORROW.strftime('%a %d %b') in page
    assert '09:30' in page
    assert '12:00' not in page


def test_profile_rejects_bad_input(app, make, login):
    make.patient('alice')
    make.patient('bob')
    client = login('alice', 'patient')
    base = {'full_name': 'Alice', 'email': 'alice@example.com', 'phone': '9876543210'}
    future = (date.today() + timedelta(days=5)).isoformat()

    assert b'already uses that email' in client.post('/patient/profile', data={**base, 'email': 'bob@example.com'}, follow_redirects=True).data
    assert b'cannot be in the future' in client.post('/patient/profile', data={**base, 'date_of_birth': future}, follow_redirects=True).data
    assert b'is required' in client.post('/patient/profile', data={**base, 'full_name': ''}, follow_redirects=True).data
    assert b'current password is incorrect' in client.post('/patient/profile', data={**base, 'new_password': 'newpass1'}, follow_redirects=True).data


def test_profile_password_change(make, login):
    make.patient()
    client = login('alice', 'patient')
    client.post('/patient/profile', data={'full_name': 'Alice', 'email': 'alice@example.com', 'phone': '9876543210',
                                          'current_password': 'secret123', 'new_password': 'newpass1'})
    login('alice', 'patient', 'newpass1')
