#importing libraries
from datetime import date, datetime, time as dtime, timedelta
import os

from flask import (
    Flask, request, render_template, redirect, url_for,
    flash, session, send_from_directory, abort
)
from flask_login import login_required
from werkzeug.security import generate_password_hash
from werkzeug.utils import secure_filename
from sqlalchemy.exc import IntegrityError
#for password hashing

#flask app setup
app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///hospital.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.secret_key = 'asdfghjkl'

#patient record upload
app.config['UPLOAD_FOLDER'] = os.path.join(app.root_path, 'static', 'uploads')
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16 MB
ALLOWED_EXT = {'pdf', 'png', 'jpg', 'jpeg', 'gif'}
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

#importing models from model.py
from models import (
    db, init_db, Patient, Doctor, Admin,
    Appointment, Treatment, DoctorAvailability, PatientRecord,
    doctor_is_available  # convenience function defined in models.py
)



# Helper functions

def doctor_has_conflict(doctor_id, appt_date, appt_time, exclude_appt_id=None):
    """
    Returns True if a doctor already has an appointment within ±5 minutes.
    """
    reference_dt = datetime.combine(appt_date, appt_time)
    lower_bound = reference_dt - timedelta(minutes=5)
    upper_bound = reference_dt + timedelta(minutes=5)

    query_check = Appointment.query.filter(
        Appointment.doctor_id == doctor_id,
        Appointment.date == appt_date,
        Appointment.time >= lower_bound.time(),
        Appointment.time <= upper_bound.time()
    )
    if exclude_appt_id:
        query_check = query_check.filter(Appointment.id != exclude_appt_id)

    match_count = query_check.count()
    return match_count > 0


def allowed_file(filename):
    has_dot = '.' in filename
    valid_ext = filename.rsplit('.', 1)[1].lower() in ALLOWED_EXT
    return has_dot and valid_ext


def get_available_slots(doctor, appt_date, slot_minutes=30):
    """
    Returns available time slots
    Uses DoctorAvailability entries and excludes already-booked appointment times.
    """
    from datetime import datetime, timedelta

    valid_slots = []
    weekday_idx = appt_date.weekday()

    # gather existing appointment times for the doctor on that date
    booked_times = {rec.time for rec in Appointment.query.filter_by(doctor_id=doctor.id, date=appt_date).all()}

    availabilities = doctor.availabilities.filter_by(day_of_week=weekday_idx).all()
    for av_record in availabilities:
        shift_start = datetime.combine(appt_date, av_record.start_time)
        shift_end = datetime.combine(appt_date, av_record.end_time)

        current_step = shift_start
        while current_step + timedelta(minutes=slot_minutes) <= shift_end:
            time_candidate = current_step.time()
            # skip if within ±5 minutes of an existing appointment
            is_clashing = False
            for booked_t in booked_times:
                booked_dt = datetime.combine(appt_date, booked_t)
                time_diff = abs((booked_dt - current_step).total_seconds())
                if time_diff < 300:
                    is_clashing = True
                    break

            if not is_clashing:
                valid_slots.append(time_candidate)

            current_step += timedelta(minutes=slot_minutes)
    return valid_slots



# Routes
@app.route('/')
def home():
    return render_template('login.html')
#home page

# Render login pages
@app.route('/auth/login', methods=['GET'])
def login():
    target_role = request.args.get('role', 'patient')
    if target_role == 'doctor':
        return render_template('doc_login.html')
    elif target_role == 'admin':
        return render_template('admin_login.html')
    else:
        return render_template('patient_login.html')
#login page

# Patient registration
@app.route('/auth/register', methods=['GET', 'POST'])
def register():
    if request.method == 'GET':
        return render_template('patient_register.html')

    # POST: registeration of patient
    form_data = request.form
    p_name = form_data.get('name', '').strip()
    p_age = form_data.get('age')
    p_gender = form_data.get('gender')
    p_contact = form_data.get('contact', '').strip()
    p_username = form_data.get('username', '').strip()
    p_pass = form_data.get('password', '')

    valid_req = p_name and p_username and p_pass

    if not valid_req:
        flash('Name, username and password are required.', 'danger')
        return render_template('patient_register.html'), 400

    try:
        new_patient = Patient(
            name=p_name,
            age=int(p_age) if p_age else None,
            gender=p_gender,
            contact=p_contact,
            username=p_username
        )
        new_patient.set_password(p_pass)
        db.session.add(new_patient)
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        flash('Username already taken — choose another username.', 'warning')
        return render_template('patient_register.html'), 409
    # unique username
    except Exception:
        db.session.rollback()
        flash('An unexpected error occurred. Try again.', 'danger')
        return render_template('patient_register.html'), 500

    flash('Registration successful. Please login.', 'success')
    return redirect(url_for('login', role='patient'))


# Admin dashboard + login
@app.route('/admin/dashboard', methods=['GET', 'POST'])
def admin_dashboard():
    # POST: admin login
    if request.method == 'POST':
        u_name = request.form.get('username', '').strip()
        pwd = request.form.get('password', '')
        admin_user = Admin.query.filter_by(username=u_name).first()

        valid_login = admin_user and admin_user.check_password(pwd)
        if not valid_login:
            flash('Invalid admin credentials.', 'danger')
            return render_template('admin_login.html'), 401

        session['admin_id'] = admin_user.id
        flash(f'Welcome, {admin_user.username}!', 'success')
        return redirect(url_for('admin_dashboard'))

    # dashboard
    if 'admin_id' not in session:
        flash('Please login as admin to access the admin dashboard.', 'warning')
        return redirect(url_for('login', role='admin'))

    # statistics
    count_docs = Doctor.query.count()
    count_pats = Patient.query.count()
    count_appts = Appointment.query.count()
    count_upcoming = Appointment.query.filter(Appointment.date >= date.today()).count()

    search_str = request.args.get('q', '').strip()
    f_type = request.args.get('type', 'doctor')

    docs_list = Doctor.query.order_by(Doctor.id.desc()).all()
    pats_list = Patient.query.order_by(Patient.id.desc()).limit(20).all()

#search logic
    if search_str:
        if f_type == 'doctor':
            filtered_docs = Doctor.query.filter(
                (Doctor.name.ilike(f'%{search_str}%')) |
                (Doctor.specialization.ilike(f'%{search_str}%')) |
                (Doctor.username.ilike(f'%{search_str}%'))
            ).all()
            final_doctors = filtered_docs
            final_patients = pats_list
        else:
            filtered_pats = Patient.query.filter(
                (Patient.name.ilike(f'%{search_str}%')) |
                (Patient.username.ilike(f'%{search_str}%')) |
                (Patient.contact.ilike(f'%{search_str}%'))
            ).all()
            final_patients = filtered_pats
            final_doctors = docs_list
    else:
        final_doctors = docs_list
        final_patients = pats_list

    recent_appts = Appointment.query.order_by(Appointment.date.desc(), Appointment.time.desc()).limit(50).all()

    current_admin = Admin.query.get(session['admin_id'])

    return render_template(
        'admin_dashboard.html',
        total_doctors=count_docs,
        total_patients=count_pats,
        total_appointments=count_appts,
        upcoming_appointments=count_upcoming,
        doctors=final_doctors,
        patients=final_patients,
        appointments=recent_appts,
        query=search_str,
        filter_type=f_type,
        admin=current_admin
    )


# Doctor dashboard and login
@app.route('/doctor/dashboard', methods=['GET', 'POST'])
def doctor_dashboard():
    if request.method == 'POST':
        login_user = request.form.get('username', '').strip()
        login_pass = request.form.get('password', '')

        doc_obj = Doctor.query.filter_by(username=login_user).first()
        if not doc_obj or not doc_obj.check_password(login_pass):
            flash('Invalid doctor credentials.', 'danger')
            return render_template('doc_login.html'), 401

        session['doctor_id'] = doc_obj.id
        flash(f'Welcome Dr. {doc_obj.name}!', 'success')
        return redirect(url_for('doctor_dashboard'))

    if 'doctor_id' not in session:
        flash('Please login as doctor to access the doctor dashboard.', 'warning')
        return redirect(url_for('login', role='doctor'))

    current_doctor = Doctor.query.get_or_404(session['doctor_id'])
    my_appts = Appointment.query.filter_by(doctor_id=current_doctor.id).order_by(Appointment.date.asc(),
                                                                                 Appointment.time.asc()).all()
    return render_template('doctor_dashboard.html', doctor=current_doctor, appointments=my_appts)


# Patient dashboard and login
@app.route('/patient/dashboard', methods=['GET', 'POST'])
def patient_dashboard():
    # POST: patient login
    if request.method == 'POST':
        u_val = request.form.get('username', '').strip()
        p_val = request.form.get('password', '')

        pat_entry = Patient.query.filter_by(username=u_val).first()
        if not pat_entry or not pat_entry.check_password(p_val):
            flash('Invalid patient credentials.', 'danger')
            return render_template('patient_login.html'), 401

        session['patient_id'] = pat_entry.id
        flash(f'Welcome {pat_entry.name}!', 'success')
        return redirect(url_for('patient_dashboard'))

    if 'patient_id' not in session:
        flash('Please login to access the patient dashboard.', 'warning')
        return redirect(url_for('login', role='patient'))

    current_patient = Patient.query.get_or_404(session['patient_id'])

    # search logic
    spec_search = request.args.get('spec', '').strip()
    date_search_str = request.args.get('date', '').strip()
    parsed_date = None
    if date_search_str:
        try:
            parsed_date = datetime.strptime(date_search_str, '%Y-%m-%d').date()
        except Exception:
            parsed_date = None

# doctor specilization dropdpwn
    try:
        distinct_specs = Doctor.query.with_entities(Doctor.specialization).distinct().order_by(
            Doctor.specialization).all()
        spec_list = [item[0] for item in distinct_specs if item[0]]
    except Exception:
        spec_list = []

    # doctor search
    base_doc_query = Doctor.query.order_by(Doctor.id.desc())
    if spec_search:
        # filter by specialization selected from dropdown (case-insensitive)
        base_doc_query = base_doc_query.filter(Doctor.specialization.ilike(f'%{spec_search}%'))
    found_doctors = base_doc_query.all()

    # appointment history
    history = Appointment.query.filter_by(patient_id=current_patient.id).order_by(Appointment.date.desc(),
                                                                                  Appointment.time.desc()).all()

    # patient records
    uploaded_records = current_patient.records.order_by(PatientRecord.uploaded_at.desc()).all()

    #show available slots of chosen date
    slots_data = {}
    if parsed_date:
        for doc in found_doctors:
            found_slots = get_available_slots(doc, parsed_date)
            if found_slots:
                slots_data[doc.id] = found_slots

    return render_template(
        'patient_dashboard.html',
        patient=current_patient,
        doctors=found_doctors,
        query_spec=spec_search,
        query_date=date_search_str,
        available_map=slots_data,
        appointments=history,
        records=uploaded_records,
        specializations=spec_list
    )


# Book appointment by patient
@app.route('/patient/appointment/book', methods=['POST'])
def patient_book_appointment():
    if 'patient_id' not in session:
        flash('Please login to book appointments.', 'warning')
        return redirect(url_for('login', role='patient'))

    try:
        pid = session['patient_id']
        did = int(request.form.get('doctor_id'))
        d_str = request.form.get('date', '').strip()
        t_str = request.form.get('time', '').strip()

        chosen_date = datetime.strptime(d_str, '%Y-%m-%d').date()
        chosen_time = datetime.strptime(t_str, '%H:%M').time()

        doc_ref = Doctor.query.get(did)
        if not doc_ref:
            flash('Selected doctor not found.', 'danger')
            return redirect(url_for('patient_dashboard'))

        # conflict checks
        if not doctor_is_available(doc_ref, chosen_date, chosen_time):
            flash('Doctor not available at the selected slot.', 'warning')
            return redirect(url_for('patient_dashboard', spec=request.form.get('spec', ''), date=d_str))

        if doctor_has_conflict(did, chosen_date, chosen_time):
            flash('Doctor has another appointment near this time.', 'warning')
            return redirect(url_for('patient_dashboard', spec=request.form.get('spec', ''), date=d_str))

        # optional medical history file upload
        if 'record' in request.files:
            uploaded_file = request.files['record']
            if uploaded_file and uploaded_file.filename:
                if not allowed_file(uploaded_file.filename):
                    flash('File type not allowed. Use PDF or images.', 'warning')
                    return redirect(url_for('patient_dashboard', date=d_str))
                clean_name = secure_filename(uploaded_file.filename)
                stored_filename = f"{pid}_{int(datetime.utcnow().timestamp())}_{clean_name}"
                save_path = os.path.join(app.config['UPLOAD_FOLDER'], stored_filename)
                uploaded_file.save(save_path)

                new_rec = PatientRecord(patient_id=pid, filename=stored_filename, original_name=uploaded_file.filename)
                db.session.add(new_rec)

        appt_entry = Appointment(patient_id=pid, doctor_id=did, date=chosen_date, time=chosen_time, status='Booked')
        db.session.add(appt_entry)
        db.session.commit()
        flash('Appointment booked successfully.', 'success')
    except ValueError:
        db.session.rollback()
        flash('Invalid date/time format.', 'danger')
    except Exception:
        db.session.rollback()
        flash('Failed to book appointment. Try again.', 'danger')

    return redirect(url_for('patient_dashboard'))


# Reschedule appointment by patient
@app.route('/patient/appointment/reschedule/<int:appt_id>', methods=['POST'])
def patient_reschedule_appointment(appt_id):
    if 'patient_id' not in session:
        flash('Please login to reschedule appointments.', 'warning')
        return redirect(url_for('login', role='patient'))

    target_appt = Appointment.query.get_or_404(appt_id)
    if target_appt.patient_id != session['patient_id']:
        flash('You are not authorized to reschedule this appointment.', 'danger')
        return redirect(url_for('patient_dashboard'))

    try:
        new_d_str = request.form.get('date', '').strip()
        new_t_str = request.form.get('time', '').strip()
        updated_date = datetime.strptime(new_d_str, '%Y-%m-%d').date()
        updated_time = datetime.strptime(new_t_str, '%H:%M').time()

        if not doctor_is_available(target_appt.doctor, updated_date, updated_time):
            flash('Doctor not available at the chosen time.', 'warning')
            return redirect(url_for('patient_dashboard'))

        if doctor_has_conflict(target_appt.doctor_id, updated_date, updated_time, exclude_appt_id=target_appt.id):
            flash('Doctor has another appointment near this time.', 'warning')
            return redirect(url_for('patient_dashboard'))

        target_appt.date = updated_date
        target_appt.time = updated_time
        db.session.commit()
        flash('Appointment rescheduled.', 'success')
    except Exception:
        db.session.rollback()
        flash('Failed to reschedule. Use correct date/time format.', 'danger')

    return redirect(url_for('patient_dashboard'))


# Cancel appointment by patient
@app.route('/patient/appointment/cancel/<int:appt_id>', methods=['POST'])
def patient_cancel_appointment(appt_id):
    if 'patient_id' not in session:
        flash('Please login to cancel appointments.', 'warning')
        return redirect(url_for('login', role='patient'))

    appt_obj = Appointment.query.get_or_404(appt_id)
    if appt_obj.patient_id != session['patient_id']:
        flash('You are not authorized to cancel this appointment.', 'danger')
        return redirect(url_for('patient_dashboard'))

    try:
        appt_obj.status = 'Cancelled'
        db.session.commit()
        flash('Appointment cancelled.', 'success')
    except Exception:
        db.session.rollback()
        flash('Failed to cancel appointment.', 'danger')

    return redirect(url_for('patient_dashboard'))


#add doctor to database
@app.route('/admin/doctor/add', methods=['POST'])
def admin_add_doctor():
    if 'admin_id' not in session:
        flash('Unauthorized', 'danger')
        return redirect(url_for('login', role='admin'))

    d_name = request.form.get('name', '').strip()
    d_spec = request.form.get('specialization', '').strip()
    d_avail = request.form.get('availability', '').strip()
    d_contact = request.form.get('contact', '').strip()
    d_user = request.form.get('username', '').strip()
    d_pass = request.form.get('password', '').strip()

    if not (d_name and d_spec and d_user and d_pass):
        flash('Name, specialization, username and password are required.', 'danger')
        return redirect(url_for('admin_dashboard'))

    try:
        new_doc_obj = Doctor(
            name=d_name,
            specialization=d_spec,
            availability=d_avail,
            contact=d_contact,
            username=d_user
        )
        new_doc_obj.set_password(d_pass)
        db.session.add(new_doc_obj)
        db.session.flush()  # to get new_doc.id

        # doctor availability logic input
        for day_idx in range(7):
            is_enabled = request.form.get(f'day_{day_idx}_enabled')
            str_start = request.form.get(f'day_{day_idx}_start', '').strip()
            str_end = request.form.get(f'day_{day_idx}_end', '').strip()

            if is_enabled:
                try:
                    time_start = datetime.strptime(str_start, '%H:%M').time()
                    time_end = datetime.strptime(str_end, '%H:%M').time()
                except Exception:
                    db.session.rollback()
                    flash(f'Invalid time for day {day_idx}. Use HH:MM.', 'danger')
                    return redirect(url_for('admin_dashboard'))

                if not (time_start < time_end):
                    db.session.rollback()
                    flash(f'Start time must be before end time for day {day_idx}.', 'danger')
                    return redirect(url_for('admin_dashboard'))

                av_entry = DoctorAvailability(
                    doctor_id=new_doc_obj.id,
                    day_of_week=day_idx,
                    start_time=time_start,
                    end_time=time_end
                )
                db.session.add(av_entry)

        db.session.commit()
        flash('Doctor added successfully with availability.', 'success')
    except IntegrityError:
        db.session.rollback()
        flash('Username already taken for doctor. Choose another username.', 'warning')
    except Exception:
        db.session.rollback()
        flash('Failed to add doctor. Try again.', 'danger')

    return redirect(url_for('admin_dashboard'))


# edit doctor
@app.route('/admin/doctor/edit/<int:doc_id>', methods=['POST'])
def admin_edit_doctor(doc_id):
    if 'admin_id' not in session:
        flash('Unauthorized', 'danger')
        return redirect(url_for('login', role='admin'))

    target_doc = Doctor.query.get_or_404(doc_id)

    # Doctor registeration form
    d_name = request.form.get('name', '').strip()
    d_spec = request.form.get('specialization', '').strip()
    d_notes = request.form.get('availability', '').strip()
    d_contact = request.form.get('contact', '').strip()
    d_user = request.form.get('username', '').strip()
    d_pass = request.form.get('password', '').strip()

    if not (d_name and d_spec and d_user):
        flash('Name, specialization and username are required.', 'danger')
        return redirect(url_for('admin_dashboard'))

    target_doc.name = d_name
    target_doc.specialization = d_spec
    target_doc.availability = d_notes
    target_doc.contact = d_contact
    target_doc.username = d_user
    if d_pass:
        target_doc.set_password(d_pass)

    try:
        DoctorAvailability.query.filter_by(doctor_id=target_doc.id).delete()
        for day_idx in range(7):
            day_enabled = request.form.get(f'day_{day_idx}_enabled')
            s_time_str = request.form.get(f'day_{day_idx}_start', '').strip()
            e_time_str = request.form.get(f'day_{day_idx}_end', '').strip()

            if day_enabled:
                try:
                    start_t = datetime.strptime(s_time_str, '%H:%M').time()
                    end_t = datetime.strptime(e_time_str, '%H:%M').time()
                except Exception:
                    db.session.rollback()
                    flash(f'Invalid time for day {day_idx}. Use HH:MM.', 'danger')
                    return redirect(url_for('admin_dashboard'))

                if not (start_t < end_t):
                    db.session.rollback()
                    flash(f'Start time must be before end time for day {day_idx}.', 'danger')
                    return redirect(url_for('admin_dashboard'))

                new_av = DoctorAvailability(
                    doctor_id=target_doc.id,
                    day_of_week=day_idx,
                    start_time=start_t,
                    end_time=end_t
                )
                db.session.add(new_av)

        db.session.commit()
        flash('Doctor updated successfully.', 'success')
    except IntegrityError:
        db.session.rollback()
        flash('Username already taken. Choose another username.', 'warning')
    except Exception:
        db.session.rollback()
        flash('Failed to update doctor.', 'danger')

    return redirect(url_for('admin_dashboard'))


# Admin: delete doctor
@app.route('/admin/doctor/delete/<int:doc_id>', methods=['POST'])
def admin_delete_doctor(doc_id):
    if 'admin_id' not in session:
        flash('Unauthorized', 'danger')
        return redirect(url_for('login', role='admin'))

    doc_to_del = Doctor.query.get_or_404(doc_id)
    try:
        db.session.delete(doc_to_del)
        db.session.commit()
        flash('Doctor removed successfully.', 'success')
    except Exception:
        db.session.rollback()
        flash('Failed to remove doctor.', 'danger')

    return redirect(url_for('admin_dashboard'))


# Admin: appointment create/edit/delete/status
@app.route('/admin/appointment/create', methods=['POST'])
def admin_create_appointment():
    if 'admin_id' not in session:
        flash('Unauthorized', 'danger')
        return redirect(url_for('login', role='admin'))

    try:
        pat_id = int(request.form.get('patient_id'))
        doc_id = int(request.form.get('doctor_id'))

        raw_date = request.form.get('date', '').strip()
        raw_time = request.form.get('time', '').strip()

        a_date = datetime.strptime(raw_date, '%Y-%m-%d').date()
        a_time = datetime.strptime(raw_time, '%H:%M').time()

        doc_obj = Doctor.query.get(doc_id)
        if not doc_obj:
            flash('Selected doctor not found.', 'danger')
            return redirect(url_for('admin_dashboard'))

        day_num = a_date.weekday()
        is_slot_open = False

        # Check doctor availability records
        for slot in doc_obj.availabilities.filter_by(day_of_week=day_num).all():
            if slot.start_time <= a_time < slot.end_time:
                is_slot_open = True
                break

        if not is_slot_open:
            flash('Doctor not available at chosen date/time. Please pick another slot.', 'warning')
            return redirect(url_for('admin_dashboard'))

        if doctor_has_conflict(doc_id, a_date, a_time):
            flash('This doctor already has an appointment within 5 minutes of the selected time.', 'warning')
            return redirect(url_for('admin_dashboard'))

        admin_appt = Appointment(patient_id=pat_id, doctor_id=doc_id, date=a_date, time=a_time, status='Booked')
        db.session.add(admin_appt)
        db.session.commit()
        flash('Appointment created successfully.', 'success')
    except ValueError:
        db.session.rollback()
        flash('Invalid date/time format. Use YYYY-MM-DD and HH:MM.', 'danger')
    except Exception:
        db.session.rollback()
        flash('Failed to create appointment. Try again.', 'danger')

    return redirect(url_for('admin_dashboard'))


@app.route('/admin/appointment/edit/<int:appt_id>', methods=['POST'])
def admin_edit_appointment(appt_id):
    if 'admin_id' not in session:
        flash('Unauthorized', 'danger')
        return redirect(url_for('login', role='admin'))

    appt_record = Appointment.query.get_or_404(appt_id)
    try:
        pid_input = request.form.get('patient_id')
        did_input = request.form.get('doctor_id')
        date_input = request.form.get('date', '').strip()
        time_input = request.form.get('time', '').strip()
        stat_input = request.form.get('status', '').strip()

        final_pid = int(pid_input) if pid_input else appt_record.patient_id
        final_did = int(did_input) if did_input else appt_record.doctor_id
        final_date = appt_record.date
        final_time = appt_record.time

        if date_input:
            final_date = datetime.strptime(date_input, '%Y-%m-%d').date()
        if time_input:
            final_time = datetime.strptime(time_input, '%H:%M').time()

        doc_check = Doctor.query.get(final_did)
        if not doc_check:
            flash('Selected doctor not found.', 'danger')
            return redirect(url_for('admin_dashboard'))

        weekday_val = final_date.weekday()
        can_book = False
        for av_slot in doc_check.availabilities.filter_by(day_of_week=weekday_val).all():
            if av_slot.start_time <= final_time < av_slot.end_time:
                can_book = True
                break
        if not can_book:
            flash('Doctor not available at chosen date/time. Please pick another slot.', 'warning')
            return redirect(url_for('admin_dashboard'))

        if doctor_has_conflict(final_did, final_date, final_time, exclude_appt_id=appt_record.id):
            flash('Cannot reschedule—doctor has another appointment within 5 minutes.', 'warning')
            return redirect(url_for('admin_dashboard'))

        appt_record.patient_id = final_pid
        appt_record.doctor_id = final_did
        appt_record.date = final_date
        appt_record.time = final_time
        if stat_input and stat_input in ('Booked', 'Completed', 'Cancelled'):
            appt_record.status = stat_input

        db.session.commit()
        flash('Appointment updated successfully.', 'success')
    except ValueError:
        db.session.rollback()
        flash('Invalid date/time format. Use YYYY-MM-DD and HH:MM.', 'danger')
    except Exception:
        db.session.rollback()
        flash('Failed to update appointment.', 'danger')

    return redirect(url_for('admin_dashboard'))


@app.route('/admin/appointment/delete/<int:appt_id>', methods=['POST'])
def admin_delete_appointment(appt_id):
    if 'admin_id' not in session:
        flash('Unauthorized', 'danger')
        return redirect(url_for('login', role='admin'))

    target = Appointment.query.get_or_404(appt_id)
    try:
        db.session.delete(target)
        db.session.commit()
        flash('Appointment deleted.', 'success')
    except Exception:
        db.session.rollback()
        flash('Failed to delete appointment.', 'danger')

    return redirect(url_for('admin_dashboard'))


@app.route('/admin/appointment/status/<int:appt_id>', methods=['POST'])
def admin_change_appointment_status(appt_id):
    if 'admin_id' not in session:
        flash('Unauthorized', 'danger')
        return redirect(url_for('login', role='admin'))

    appt_item = Appointment.query.get_or_404(appt_id)
    status_val = request.form.get('status', '').strip()

    valid_statuses = ('Booked', 'Completed', 'Cancelled')
    if status_val not in valid_statuses:
        flash('Invalid status value.', 'warning')
        return redirect(url_for('admin_dashboard'))

    appt_item.status = status_val
    try:
        db.session.commit()
        flash('Appointment status updated.', 'success')
    except Exception:
        db.session.rollback()
        flash('Failed to update appointment status.', 'danger')

    return redirect(url_for('admin_dashboard'))


# Admin views for appointments by doctor/patient
@app.route('/admin/doctor/<int:doc_id>/appointments', methods=['GET'])
def admin_view_doctor_appointments(doc_id):
    if 'admin_id' not in session:
        flash('Please login as admin to access this page.', 'warning')
        return redirect(url_for('login', role='admin'))

    doc_entity = Doctor.query.get_or_404(doc_id)
    doc_appts = Appointment.query.filter_by(doctor_id=doc_id).order_by(Appointment.date.desc(),
                                                                       Appointment.time.desc()).all()
    return render_template('appointments_by_entity.html', entity_type='doctor', entity=doc_entity,
                           appointments=doc_appts)


@app.route('/admin/patient/<int:patient_id>/appointments', methods=['GET'])
def admin_view_patient_appointments(patient_id):
    if 'admin_id' not in session:
        flash('Please login as admin to access this page.', 'warning')
        return redirect(url_for('login', role='admin'))

    pat_entity = Patient.query.get_or_404(patient_id)
    pat_appts = Appointment.query.filter_by(patient_id=patient_id).order_by(Appointment.date.desc(),
                                                                            Appointment.time.desc()).all()
    return render_template('appointments_by_entity.html', entity_type='patient', entity=pat_entity,
                           appointments=pat_appts)


# Doctor completes appointment and saves treatment
@app.route('/doctor/appointment/complete/<int:appt_id>', methods=['POST'])
def doctor_complete_appointment(appt_id):
    if 'doctor_id' not in session:
        flash('Unauthorized', 'danger')
        return redirect(url_for('login', role='doctor'))

    active_appt = Appointment.query.get_or_404(appt_id)
    if active_appt.doctor_id != session['doctor_id']:
        flash('You are not allowed to modify this appointment.', 'danger')
        return redirect(url_for('doctor_dashboard'))

    diag_text = request.form.get('diagnosis', '').strip()
    rx_text = request.form.get('prescription', '').strip()
    note_text = request.form.get('notes', '').strip()

    try:
        if active_appt.treatment:
            existing_t = active_appt.treatment
            existing_t.diagnosis = diag_text or existing_t.diagnosis
            existing_t.prescription = rx_text or existing_t.prescription
            existing_t.notes = note_text or existing_t.notes
        else:
            new_t = Treatment(appointment_id=active_appt.id, diagnosis=diag_text, prescription=rx_text, notes=note_text)
            db.session.add(new_t)

        active_appt.status = 'Completed'
        db.session.commit()
        flash('Appointment marked completed and treatment saved.', 'success')
    except Exception:
        db.session.rollback()
        flash('Failed to save treatment. Try again.', 'danger')

    return redirect(url_for('doctor_dashboard'))


#  view patient history (treatments)
@app.route('/doctor/patient/<int:patient_id>/history', methods=['GET'])
def doctor_view_patient_history(patient_id):
    if 'doctor_id' not in session:
        flash('Please login as doctor to view patient history.', 'warning')
        return redirect(url_for('login', role='doctor'))

    target_pat = Patient.query.get_or_404(patient_id)
    history_list = (Treatment.query
                    .join(Appointment, Treatment.appointment_id == Appointment.id)
                    .filter(Appointment.patient_id == patient_id)
                    .order_by(Appointment.date.desc())
                    .all())
    return render_template('patient_history.html', patient=target_pat, treatments=history_list)


# view patient records medical uploaded files
@app.route('/doctor/patient/<int:patient_id>/records', methods=['GET'])
def doctor_view_patient_records(patient_id):
    if 'doctor_id' not in session:
        flash('Please login as doctor to view patient records.', 'warning')
        return redirect(url_for('login', role='doctor'))

    p_record = Patient.query.get_or_404(patient_id)
    file_list = p_record.records.order_by(PatientRecord.uploaded_at.desc()).all()
    return render_template('patient_records.html', patient=p_record, records=file_list)


# Patient update profile area
@app.route('/patient/profile/update', methods=['POST'])
def patient_update_profile():
    if 'patient_id' not in session:
        flash('Please login to update profile.', 'warning')
        return redirect(url_for('login', role='patient'))

    my_profile = Patient.query.get_or_404(session['patient_id'])
    try:
        my_profile.name = request.form.get('name', my_profile.name).strip()
        val_age = request.form.get('age')
        my_profile.age = int(val_age) if val_age else None
        my_profile.contact = request.form.get('contact', my_profile.contact).strip()
        db.session.commit()
        flash('Profile updated.', 'success')
    except Exception:
        db.session.rollback()
        flash('Failed to update profile.', 'danger')
    return redirect(url_for('patient_dashboard'))


# Admin can edit patient details
@app.route('/admin/patient/edit/<int:patient_id>', methods=['POST'])
def admin_edit_patient(patient_id):
    if 'admin_id' not in session:
        flash('Unauthorized', 'danger')
        return redirect(url_for('login', role='admin'))

    pat_obj = Patient.query.get_or_404(patient_id)
    try:
        # Required fields in patient edit
        new_name = request.form.get('name', pat_obj.name).strip()
        raw_age = request.form.get('age', '')
        new_gen = request.form.get('gender', pat_obj.gender)
        new_cont = request.form.get('contact', pat_obj.contact).strip()
        new_mail = request.form.get('email', pat_obj.email or '').strip()
        new_user = request.form.get('username', pat_obj.username).strip()
        new_pass = request.form.get('password', '').strip()

        if not new_name or not new_user:
            flash('Name and username are required for patients.', 'danger')
            return redirect(url_for('admin_dashboard'))

        # apply updates
        pat_obj.name = new_name
        pat_obj.age = int(raw_age) if raw_age != '' else None
        pat_obj.gender = new_gen
        pat_obj.contact = new_cont
        pat_obj.email = new_mail
        pat_obj.username = new_user
        if new_pass:

            try:
                pat_obj.set_password(new_pass)
            except Exception:
                #in case password column is empty
                pat_obj.password_hash = generate_password_hash(new_pass)

        db.session.commit()
        flash('Patient updated successfully.', 'success')
    except IntegrityError:
        db.session.rollback()
        flash('Username already taken. Choose another username.', 'warning')
    except ValueError:
        db.session.rollback()
        flash('Invalid age value.', 'danger')
    except Exception:
        db.session.rollback()
        flash('Failed to update patient. Try again.', 'danger')

    return redirect(url_for('admin_dashboard'))


# Logout
@app.route('/logout')
def logout():
    session.pop('admin_id', None)
    session.pop('doctor_id', None)
    session.pop('patient_id', None)
    flash('You have been logged out successfully.', 'info')
    return redirect(url_for('home'))


# Run app
if __name__ == "__main__":
    # Ensure tables are created and default admin exists
    init_db(app)
    app.run(debug=True)