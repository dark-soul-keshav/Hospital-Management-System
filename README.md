# Hospital Management System (HMS)

A full‑stack **role‑based Hospital Management System web application** built using **Flask**, **SQLAlchemy**, and **SQLite**, enabling seamless interaction between **Admins, Doctors, and Patients**.

---

## 👤 Student Details
- **Name:** Keshav Singh
- **Roll Number:** 24f3002937
- **Email:** 24f3002937@ds.study.iitm.ac.in
- **Course:** IIT Madras BS in Data Science & NIT Delhi B.Tech in VLSI
- **About:** This is my first web application development project. It introduced me to real‑world backend development using Flask and strengthened my interest in full‑stack development.

---

## 📌 Project Overview
**Project Title:** Hospital Management System (HMS)

The system provides a digital platform to manage hospital operations such as:
- Patient registration and appointment booking
- Doctor scheduling and treatment management
- Admin‑level control over users and appointments

The application follows a **role‑based access control system** with three user types:
- **Admin**
- **Doctor**
- **Patient**

---

## 🧠 AI/LLM Usage Declaration
- Tool Used: ChatGPT (GPT‑5)
- Purpose: Logic optimization, JavaScript integration (MAD‑2), documentation, and limited debugging support
- Extent of Usage: ~20%
- All final application logic and implementation were done manually

---

## 🛠 Technologies & Frameworks
| Technology | Purpose |
|------------|---------|
| Flask | Backend web framework |
| SQLAlchemy | ORM for database operations |
| SQLite | Lightweight local database |
| Jinja2 | Template engine |
| Bootstrap 5 | Frontend UI styling |
| Werkzeug | Password hashing & security |
| HTML/CSS | Frontend structure & styling |

---

## 🗄️ Database Schema
**Main Tables:**
- Admin
- Doctor
- Patient
- Appointment
- Treatment
- DoctorAvailability
- PatientRecord

Relationships are maintained using SQLAlchemy ORM with proper foreign key constraints.

![alt text](hospital_er.png)
ER relationship diagram of tables used in database.
---

## 🔗 API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| / | GET | Home login page |
| /auth/login | GET | Role‑based login select |
| /auth/register | GET/POST | Patient registration |
| /admin/dashboard | GET/POST | Admin dashboard & login |
| /doctor/dashboard | GET/POST | Doctor dashboard & login |
| /patient/dashboard | GET/POST | Patient dashboard & login |
| /patient/appointment/book | POST | Book appointment |
| /patient/appointment/reschedule/<id> | POST | Reschedule appointment |
| /patient/appointment/cancel/<id> | POST | Cancel appointment |
| /admin/doctor/add | POST | Add new doctor |
| /admin/doctor/edit/<id> | POST | Edit doctor |
| /admin/doctor/delete/<id> | POST | Delete doctor |
| /admin/appointment/create | POST | Create appointment |
| /admin/appointment/edit/<id> | POST | Edit appointment |
| /admin/appointment/delete/<id> | POST | Delete appointment |
| /admin/appointment/status/<id> | POST | Update appointment status |
| /admin/doctor/<id>/appointments | GET | View doctor appointments |
| /admin/patient/<id>/appointments | GET | View patient appointments |
| /doctor/appointment/complete/<id> | POST | Complete appointment |
| /doctor/patient/<id>/history | GET | View patient history |
| /doctor/patient/<id>/records | GET | View patient records |
| /patient/profile/update | POST | Update patient profile |
| /admin/patient/edit/<id> | POST | Edit patient details |
| /logout | GET | Logout user |

---

## 🏗 Architecture
```
project/
│
├── app.py                # Main Flask application
├── models.py             # Database models
├── hospital.db           # SQLite database
├── templates/            # HTML (Jinja2) templates
├── static/
│   └── uploads/          # Patient medical records
└── README.md
```

---

## ✅ Implemented Features
- Role‑based authentication (Admin, Doctor, Patient)
- Secure password hashing
- Patient registration & profile management
- Doctor profile and availability management
- Appointment booking, rescheduling, and cancellation
- Conflict‑free appointment validation
- Real‑time doctor availability check
- Medical record file upload (PDF/Image)
- Doctor diagnosis and prescription entry
- Patient treatment history & medical record viewing
- Admin control over doctors, patients, and appointments
- Session‑based authentication

---

## 📂 File Upload Configuration
- Upload Directory: `static/uploads/`
- Allowed Formats: `pdf`, `png`, `jpg`, `jpeg`, `gif`
- Maximum File Size: **16 MB**

---

## 🚀 How to Run the Project

### 1. Install Dependencies
```bash
pip install flask flask_sqlalchemy flask_login werkzeug
```

### 2. Run the Application
```bash
python app.py
```

### 3. Open in Browser
```
http://127.0.0.1:5000/
```

The database and default admin will be initialized automatically using `init_db(app)`.

---

## 🔐 Security Features
- Secure password hashing using Werkzeug
- Session‑based authentication
- File type validation for uploads
- Access control for every role

---

## 📈 Learning Outcomes
- Flask backend routing and authentication
- SQLAlchemy ORM relationships
- Session handling & role‑based access control
- Secure file uploads
- Full‑stack web app structure

---

## 📜 License
This project is created for **academic and learning purposes only**.

---

✅ **Project Developed by:** Keshav Singh

