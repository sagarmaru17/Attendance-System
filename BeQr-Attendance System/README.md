BeQR is a secure, fast, and reliable QR code-based attendance system designed for universities and institutions. It ensures students are physically present in lectures by requiring them to scan two QR codes (start and end of each lecture).

---

# 📝 License
# This project is for educational purposes as part of the BCA Semester Project by - Sagar Maru.

---

# BeQr - Smart Attendance & Identity System

**BeQr** is a secure, full-stack web application designed to streamline attendance tracking using dynamic QR codes. It replaces traditional manual systems with a digital, role-based model featuring real-time validation, location geofencing, and automated reporting.

![BeQr Banner](static/images/beqr.png)




---

## Requirements

| Modual Name | Command | Description |
| :--- | :--- | :--- |
| **Django** | django | The main framework running your website and Admin Panel. |
| **MySQL Client** | mysqlclient | The "Driver" that allows Django to talk to your MySQL Database. |
| **QR Code** | qrcode | The library that actually generates the QR code pattern from your data. |
| **Pillow** | pillow | An image processing library. qrcode uses this to draw the image and save it as a PNG. |
| **Django REST Framework** | djangorestframework | Required for building the APIs (future mobile app connection). |
| **PyJWT** | pyjwt | Used to create "JSON Web Tokens" (Secure, encrypted tokens) for your QR codes so students cannot fake them. |


pip install django djangorestframework mysqlclient qrcode pillow pyjwt

---

## 🚀 Key Features

### 🎓 For Students
* **Mobile-First Dashboard:** Clean, app-like interface for easy access on phones.
* **One-Tap Scan:** Integrated QR scanner to mark attendance instantly.
* **Attendance History:** View past records, status (Present/Absent), and dates.
* **Secure Profile:** Roll number and enrollment verification integrated.

### 👨‍🏫 For Teachers
* **Command Center:** Manage schedules and active lectures.
* **Dynamic QR Generation:** Generate time-bound, encrypted QR codes for "Start" and "End" of class.
* **Live Monitoring:** See students joining in real-time.
* **Manual Override:** Adjust attendance for students with technical issues.
* **Reports:** Export attendance sheets to PDF/CSV.

### 🛡️ Security & Core
* **Role-Based Access Control (RBAC):** Strict separation between Students, Teachers, and Admins.
* **Master List Validation:** Only students with University-approved Enrollment Numbers can sign up.
* **Auto-Generated Faculty IDs:** Teachers get unique, random 6-digit IDs for security.
* **Geofencing & IP Validation:** (In Progress) Ensures students are physically present in the classroom.

---

## 🛠️ Tech Stack

| Component | Technology | Description |
| :--- | :--- | :--- |
| **Backend** | Python & Django | Core logic and security |
| **Database** | MySQL | Relational data storage |
| **Frontend** | HTML5, Bootstrap 5 | Responsive UI/UX |
| **API** | Django REST Framework | For future mobile app integration |
| **QR Engine** | Python `qrcode` + `Pillow` | Image generation |
| **Security** | `PyJWT` | Token-based verification |

---

## ⚙️ Installation Guide

Follow these steps to set up the project locally.

### 1. Prerequisites
* Python 3.10 or higher
* MySQL Server installed and running
* Git

### 2. Clone the Repository
```bash

Set Up Virtual Environment
Bash

# Create the environment
python3 -m venv venv

# Activate it
source venv/bin/activate  # On macOS/Linux
# venv\Scripts\activate   # On Windows

Install Dependencies
Bash

pip install -r requirements.txt

Configure Database
Make sure your MySQL server is running.

Create a database named beqr_db.

Update beqr_project/settings.py with your MySQL credentials:

Python

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': 'beqr_db',
        'USER': 'bqr',
        'PASSWORD': 'YOUR_PASSWORD',
        'HOST': '127.0.0.1',
        'PORT': '3306',
    }
}


Run Migrations
Bash

python manage.py makemigrations
python manage.py migrate

Create Superuser (Admin)
Bash

python manage.py createsuperuser

Run the Server
Bash

python manage.py runserver
Visit http://127.0.0.1:8000/ in your browser.

🚦 Usage & Workflow
Setting Up the System (First Time)
Log in as Admin at http://127.0.0.1:8000/admin/.

Add Allowed Students: Go to the "Allowed Students" table and add valid Enrollment Numbers. Students cannot sign up unless their number is here.

Create Teachers: Go to "Users", create a new user, and select the role "Teacher". The system will auto-generate their Faculty ID.

Student Sign Up
Go to the Login page and click "Create Account".

Enter your Username, Email, and Valid Enrollment Number.

Once registered, log in to access the Student Dashboard.

📂 Project Structure
Plaintext

BeQr-Attendance System/
├── beqr/               # Main Django settings
├── core/               # Main Application logic
│   ├── templates/      # HTML files (organized by role)
│   ├── models.py       # Database Schema (CustomUser, Lecture, Attendance)
│   ├── views.py        # Business Logic
│   └── forms.py        # Registration & Validation forms
├── media/              # Generated QR codes & User uploads
├── static/             # CSS, JavaScript, Images
└── manage.py           # Django command utility
🤝 Contributing
Fork the repository.

Create a new feature branch (git checkout -b feature/AmazingFeature).

Commit your changes (git commit -m 'Add some AmazingFeature').

Push to the branch (git push origin feature/AmazingFeature).

Open a Pull Request.

📝 License
This project is for educational purposes as part of the BCA Semester Project by - Sagar Maru.