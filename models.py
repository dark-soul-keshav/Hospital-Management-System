from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
#to verify and handle password

db = SQLAlchemy()

# creating different classes consisting tables
class Admin(db.Model):
    __tablename__ = 'admins'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    full_name = db.Column(db.String(150), nullable=True)
    contact = db.Column(db.String(50), nullable=True)
    # defines admin table

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
# helper function used in flow in app.py for admin class

class Department(db.Model):
    __tablename__ = 'departments'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), unique=True, nullable=False)
    description = db.Column(db.Text, nullable=True)

    doctors = db.relationship('Doctor', backref='department', lazy='dynamic')
    # link Doctor table, create back link to department table, and for efficiency lazy = dynamic

    def doctors_registered(self):
        return self.doctors.count()


class Doctor(db.Model):
    __tablename__ = 'doctors'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    specialization = db.Column(db.String(150), nullable=False)
    availability = db.Column(db.Text, nullable=True)
    contact = db.Column(db.String(50), nullable=True)

    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)

    department_id = db.Column(db.Integer, db.ForeignKey('departments.id'), nullable=True)

    appointments = db.relationship('Appointment', backref='doctor', lazy='dynamic')

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class Patient(db.Model):
    __tablename__ = 'patients'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    age = db.Column(db.Integer, nullable=True)
    gender = db.Column(db.String(20), nullable=True)
    contact = db.Column(db.String(50), nullable=True)
    email = db.Column(db.String(120), nullable=True)

    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    appointments = db.relationship('Appointment', backref='patient', lazy='dynamic')

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class Appointment(db.Model):
    __tablename__ = 'appointments'
    id = db.Column(db.Integer, primary_key=True)

    patient_id = db.Column(db.Integer, db.ForeignKey('patients.id'), nullable=False)
    doctor_id = db.Column(db.Integer, db.ForeignKey('doctors.id'), nullable=False)

    date = db.Column(db.Date, nullable=False)
    time = db.Column(db.Time, nullable=False)

    status = db.Column(db.String(30), nullable=False, default='Booked')

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    treatment = db.relationship('Treatment', backref='appointment', uselist=False)


class Treatment(db.Model):
    __tablename__ = 'treatments'
    id = db.Column(db.Integer, primary_key=True)
    appointment_id = db.Column(db.Integer, db.ForeignKey('appointments.id'), nullable=False, unique=True)
    diagnosis = db.Column(db.Text, nullable=True)
    prescription = db.Column(db.Text, nullable=True)
    notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class DoctorAvailability(db.Model):
    __tablename__ = 'doctor_availabilities'
    id = db.Column(db.Integer, primary_key=True)
    doctor_id = db.Column(db.Integer, db.ForeignKey('doctors.id', ondelete='CASCADE'), nullable=False)
    # 0 = Monday, 6 = Sunday (matches datetime.weekday())
    day_of_week = db.Column(db.Integer, nullable=False)
    start_time = db.Column(db.Time, nullable=False)
    end_time = db.Column(db.Time, nullable=False)

    doctor = db.relationship('Doctor', backref=db.backref('availabilities', cascade='all, delete-orphan', lazy='dynamic'))

    def __repr__(self):
        return f"<Avail doc={self.doctor_id} dow={self.day_of_week} {self.start_time}-{self.end_time}>"

# Add convenience method on Doctor (optional, put near Doctor class)
def doctor_is_available(doctor, appt_date, appt_time):
    dow = appt_date.weekday()  # Monday=0 .. Sunday=6
    # Query availabilities for the doctor on that weekday and check range
    for av in doctor.availabilities.filter_by(day_of_week=dow).all():
        if av.start_time <= appt_time < av.end_time:
            return True
    return False

class PatientRecord(db.Model):
    __tablename__ = 'patient_records'
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patients.id', ondelete='CASCADE'), nullable=False)
    filename = db.Column(db.String(255), nullable=False)           # server filename
    original_name = db.Column(db.String(255), nullable=True)       # original uploaded name
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)

    patient = db.relationship('Patient', backref=db.backref('records', cascade='all, delete-orphan', lazy='dynamic'))


def init_db(app, admin_username='admin', admin_password='admin123'):

#calls create_all() to create all tables if do not exists
    db.init_app(app)
    with app.app_context():
        db.create_all()

# admin exists is ensured
        if not Admin.query.filter_by(username=admin_username).first():
            admin = Admin(username=admin_username, full_name='Super Admin')
            admin.set_password(admin_password)
            db.session.add(admin)
            db.session.commit()
            print(f'Created default admin -> username: {admin_username}, password: {admin_password}')
