<div align="center">
<img src="static/images/beqr.png" alt="BeQr Banner" width="100%">

📱 BeQr - QR Code-Based Smart Attendance Management System

A highly secure, full-stack biometric and network-validated attendance system built with Django.

</div>

🎓 Academic Submission Details

This project is developed and submitted as a BCA Final Year Project.

Student: Sagar Maru

Enrolment: 230431163

Guided by: Prof. Bhavin Mehta

Submitted to: Faculty Of Computer Application, Noble University, Junagadh.

📖 About The Project

Traditional digital attendance systems (like static QR codes) are highly vulnerable to proxy attendance, VPN spoofing, and buddy punching via WhatsApp sharing.

BeQr eliminates these loopholes using a custom Triple-Layer Verification Protocol and a Dual-Scan Workflow (Check-In/Check-Out). It ensures that a student is physically present in the classroom, using their own device, connected to the university network, at the exact time of the lecture.

🛡️ The Unique Selling Proposition (USP)

BeQr secures the attendance process using a rigorous 3-layer architecture:

Layer 1: Time-Bound Rolling QR (PyJWT) QR codes are encrypted using JSON Web Tokens and expire strictly after a 15-minute window. This defeats the "WhatsApp Photo Forwarding" loophole.

Layer 2: Network & Geofencing (CIDR + Geopy) Students must connect to the University's Wi-Fi. The backend uses IP Subnet Matching to block VPNs/Mobile Data, and the Haversine formula calculates physical distance to defeat Fake GPS apps.

Layer 3: Device Fingerprinting (Cookies) A unique device_id is locked to the browser upon the first scan, preventing "Buddy Punching" (one student marking attendance for multiple friends on the same phone).

🚀 Key Features

🎓 For Students

Mobile-First Scanner: Clean, web-based QR scanner for instant check-ins.

Dual-Scan Integrity: Requires scanning at both the start and end of the lecture to prevent mid-class bunking.

Live History: Track attendance records, dates, and calculated percentages.

👨‍🏫 For Teachers

Command Center: Manage schedules, initiate live sessions, and view active participants.

Dynamic Generation: One-click generation of the cryptographic QR matrix.

Manual Override: When students facing hardware issues.

👨‍💻 For Administrators

Master List Validation: Strict sign-up firewall. Only students pre-approved in the University Master List can create accounts.

Role-Based Access Control (RBAC): Complete separation of privileges between Admins, Faculty, and Students.

🛠️ Tech Stack & Dependencies

Component

Technology / Library

Purpose

Backend Framework

Django 5.2.8

Core application logic and ORM.

Database

MySQL & mysqlclient

Fast, relational database with row-level locking.

QR Engine

qrcode & pillow

Generates and draws the visual QR matrix.

Cryptography

PyJWT

Encodes session data into time-expiring tokens.

Geolocation

geopy

Calculates distance between Teacher and Student.

Security

python-dotenv

Hides secret keys and DB credentials from source code.

Frontend UI

HTML5, Bootstrap 5

Responsive, mobile-ready user interface.

⚙️ Local Installation Guide

Follow these steps to set up the BeQr project locally on your machine (macOS/Windows/Linux).

1. Prerequisites

Python 3.10+

MySQL Server (e.g., MySQL Workbench)

Git

2. Clone the Repository

git clone [https://github.com/yourusername/BeQr-Attendance-System.git](https://github.com/yourusername/BeQr-Attendance-System.git)
cd BeQr-Attendance-System


3. Set Up Virtual Environment

# Create the environment
python3 -m venv venv

# Activate it
source venv/bin/activate  # On macOS/Linux
# venv\Scripts\activate   # On Windows


4. Install Dependencies

pip install -r requirements.txt


5. Configure the Database (.env)

Create a .env file in the root directory (next to manage.py) to keep your credentials secure:

SECRET_KEY=your_django_secret_key_here
DB_NAME=beqr_db
DB_USER=root
DB_PASSWORD=your_mysql_password


(Ensure you have created a database named beqr_db in your MySQL Server).

6. Run Migrations & Create Admin

python manage.py makemigrations
python manage.py migrate
python manage.py createsuperuser


7. Launch the Server

python manage.py runserver


Visit http://127.0.0.1:8000/ in your browser.

🚦 Usage Workflow

Initial Setup: Log in to the Django Admin panel (/admin). Add valid Enrollment Numbers to the Allowed Students table. Create Faculty users (Faculty IDs are auto-generated).

Student Onboarding: Students click "Sign Up" and enter their University Enrollment Number. If it matches the Admin's Master List, the account is created.

Running a Class: The Teacher logs in, clicks "Start Class", and displays the generated QR code on the projector.

Marking Attendance: Students log in, scan the QR code via their phone, pass the background validation (IP + Location + Device), and are marked present.

📂 Project Structure

BeQr-Attendance System/
├── beqr/               # Django Settings & Root URL Configurations
├── core/               # Main Application Logic
│   ├── templates/      # HTML UI (Separated by Teacher/Student roles)
│   ├── models.py       # Database Schema (CustomUser, Lecture, Session)
│   ├── views.py        # Core Business & Validation Logic
│   └── forms.py        # Security Validation & Master List Check
├── media/              # Storage for Generated QR codes
├── static/             # CSS, JavaScript, and Images
├── requirements.txt    # Python dependencies
└── manage.py           # Django execution script


👨‍💻 Author

Sagar Maru
Linkedin : https://www.linkedin.com/in/sagar-maru-b987b9294/


📝 License

This project was developed for educational purposes as part of a BCA academic submission.