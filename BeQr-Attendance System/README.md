#  BeQr - QR Code-Based Smart Attendance Management System

<div align="center">

**A Highly Secure, Full-Stack Biometric and Network-Validated Attendance System Built with Django**

---

##  Academic Submission Details

**Project Type:**  Final Year Project  
**Student:** Sagar Maru   
**Development Date:** March 2026  

---

</div>

##  Executive Summary

Traditional digital attendance systems (static QR codes, time-based systems) are highly vulnerable to:
- **Proxy Attendance:** Someone else scans for the student
- **VPN/Mobile Data Spoofing:** Students pretend to be in classroom from home
- **WhatsApp Screenshot Sharing:** QR code image forwarded to friends
- **Buddy Punching:** Multiple students using same device

**BeQr eliminates all these loopholes** using a custom **Triple-Layer Verification Protocol** and a **Dual-Scan Workflow (Check-In/Check-Out)**. It ensures that a student is **physically present in the classroom, using their own device, connected to the university network, at the exact time of the lecture**.

---

##  The Unique Selling Proposition (USP)

### Three-Layer Security Architecture:

#### **Layer 1: Time-Bound Rolling QR Codes (PyJWT)**
- QR codes are encrypted using JSON Web Tokens (JWT)
- Each QR expires strictly after **20 seconds** during check-in phase
- QR codes rotate automatically every 20 seconds
- Students must scan a **fresh QR code** (prevents WhatsApp screenshot sharing)
- After **15 minutes**, check-in period closes automatically
- **Technology:** PyJWT library with HS256 encryption

#### **Layer 2: Geofencing & Network Validation (Geopy + CIDR)**
- **GPS Verification:** Students must be within **50 meters** of teacher's location
  - Uses Haversine formula to calculate precise distance
  - Prevents fake GPS apps (requires real GPS hardware)
  - Validates latitude/longitude coordinates
  
- **IP Subnet Matching:** Students must connect to university's Wi-Fi network
  - Teacher's IP address acts as anchor point
  - Validates student's IP is on same /24 CIDR subnet
  - Blocks VPNs and mobile data connections
  - **Technology:** Python `ipaddress` library

#### **Layer 3: Device Fingerprinting (Browser Cookies)**
- Unique `device_id` created from browser fingerprint on first scan
- Device ID locked to secure, httponly cookie (1-year validity)
- Prevents "Buddy Punching" (same device = same person)
- Cannot be spoofed by multiple students on same phone
- **Technology:** Django session + secure httponly cookies

### **Dual-Scan Workflow (Check-In/Check-Out):**

```
Timeline of a Class Session:
├─ 00:00  Teacher clicks "Start New Class"
│  ├─ Session created with GPS anchor + IP anchor
│  ├─ Check-in QR generated (15-minute validity)
│  └─ Students can scan QR codes
│
├─ 00:05  Student A scans check-in QR
│  ├─ Attendance status: "incomplete"
│  ├─ Security validated: GPS ✓, IP ✓, Device ✓
│  └─ time_in = current timestamp
│
├─ 10:00  Teacher clicks "Initiate Checkout"
│  ├─ Check-in phase closes (no more dynamic QR)
│  ├─ Static check-out QR generated
│  └─ Students can now scan check-out QR
│
├─ 10:15  Student A scans check-out QR
│  ├─ Attendance status: "present" (both scans completed)
│  ├─ Security validated again: GPS ✓, IP ✓, Device ✓
│  └─ time_out = current timestamp
│
└─ 10:30  Teacher clicks "End Class Now"
   ├─ Session marked as inactive
   ├─ Students without check-in → marked "absent"
   ├─ Students with check-in but no check-out → marked "absent"
   └─ Report generated automatically
```

---

##  Key Features

###  **For Students**

 **Mobile-First QR Scanner**
- Responsive web interface works on all devices
- Real-time camera access via browser HTML5 API
- No app installation required
- Clean, minimalist UI optimized for speed

 **Dual-Scan Integrity**
- Required to scan at **both** start and end of lecture
- Prevents mid-class bunking (cannot just check-in and leave)
- Clear visual feedback for each scan phase

 **Live Attendance History**
- Real-time attendance dashboard
- Track attendance percentage per subject
- Visual indicators for missing classes
- Date-wise attendance breakdown
- Identifies subjects below 75% (defaulter alert)

 **Security Validation Display**
- Shows GPS coordinates during scan
- Displays IP address and subnet validation
- Shows device fingerprint confirmation
- Builds trust through transparency

###  **For Teachers**

 **Command Center Dashboard**
- Live session overview with real-time student check-ins
- Visual countdown timer (15-minute check-in window)
- Current QR code display with auto-refresh every 20 seconds
- List of students who have checked in

 **Session Management**
- One-click "Start New Class" (captures GPS + IP automatically)
- Toggle to "Initiate Checkout" phase
- "End Class Now" to finalize and auto-mark absent students
- Quick session navigation between multiple concurrent classes

 **Advanced Reporting System**
- **3 Report Types:**
  1. **Master Attendance Report** - Complete attendance for all students, dates, and statuses
  2. **Defaulters List** - Students with <75% attendance (at-risk alert)
  3. **Security Audit Report** - GPS coordinates, IP address, timestamp proof of anti-cheating measures

- **Features:**
  - PDF export with professional formatting
  - Date-range filtering (customizable period)
  - Subject-wise filtering
  - Attendance percentage calculations
  - Color-coded status (Present=Green, Absent=Red)

 **Lecture Management**
- Create and manage courses/subjects
- Link lectures to teacher account
- Historical subject tracking

---

##  Database Architecture

### **5 Core Tables:**

#### **1. CustomUser (Extended Django User)**
| Field | Type | Purpose |
|-------|------|---------|
| id | Integer (PK) | Auto-generated primary key |
| username | String | Unique login identifier |
| email | String | User email |
| password | String | Bcrypt hashed password |
| role | Choice | **'student'** or **'teacher'** |
| enrollment_number | String (unique) | **Students:** University ID (e.g., "BCA2024001") **Teachers:** Auto-generated Faculty ID (e.g., "JK5N2X") |
| roll_number | String | Class roll number (students only) |
| first_name | String | User's first name |
| last_name | String | User's last name |
| is_active | Boolean | Account enabled/disabled |

**Key Logic:**
- Teachers auto-generate 6-character Faculty IDs on registration
- Students must provide enrollment number matching AllowedStudent table
- Role determines access level and dashboard views

---

#### **2. AllowedStudent (Enrollment Whitelist)**
| Field | Type | Purpose |
|-------|------|---------|
| id | Integer (PK) | Auto-generated |
| enrollment_number | String (unique) | Master list of allowed enrollment IDs |
| email | String (optional) | Student email (for reference) |

**Purpose:** Acts as gatekeeper for student registration
- Admin/Teacher uploads CSV of allowed enrollment numbers
- During signup, system checks if enrollment_number exists here
- Prevents unauthorized student registration

---

#### **3. Lecture (Course/Subject Information)**
| Field | Type | Purpose |
|-------|------|---------|
| id | Integer (PK) | Auto-generated |
| name | String (255) | Subject name (e.g., "Django Models", "Web Development") |
| teacher | ForeignKey → CustomUser | Teacher teaching this lecture |
| created_at | DateTime | When lecture was created |

**Relationships:** One teacher → Many lectures (1:N relationship)

---

#### **4. AttendanceSession (Active/Past Class Sessions)**
| Field | Type | Purpose |
|-------|------|---------|
| id | Integer (PK) | Auto-generated |
| session_id | String (unique) | UUID identifier for session |
| teacher | ForeignKey → CustomUser | Teacher conducting session |
| course_name | String (100) | Course identifier (e.g., "BCA Sem 6") |
| division | String (10) | Class section (e.g., "A", "B") |
| subject | String (100) | Subject name |
| topic | String (255) | Lecture topic (e.g., "Django Models") |
| start_time | DateTime | Auto-set when teacher starts class |
| end_time | DateTime (nullable) | Set when teacher ends class |
| is_active | Boolean | True = class ongoing, False = class ended |
| is_checkout | Boolean | True = checkout phase, False = check-in phase |
| **latitude** | Float | **Teacher's GPS latitude (geofencing anchor)** |
| **longitude** | Float | **Teacher's GPS longitude (geofencing anchor)** |
| **anchor_ip** | GenericIPAddress | **Teacher's IP address (subnet validation anchor)** |
| qr_code | ImageField | Stored PNG image of QR code |

**Lifecycle State Machine:**
```
[Created]
  ├─ is_active=TRUE, is_checkout=FALSE
  ├─ Dynamic check-in QR generated
  │
├─ [Check-in Phase - 0 to 15 minutes]
  │  Students scan rotating QR codes
  │
├─ [Checkout Initiated]
  │  └─ is_checkout=TRUE
  │  └─ Static check-out QR generated
  │
├─ [Check-out Phase]
  │  └─ Students scan one final QR
  │
└─ [Closed]
   ├─ is_active=FALSE
   ├─ end_time recorded
   └─ All pending status → changed to "absent"
```

---

#### **5. Attendance (Individual Student Records)**
| Field | Type | Purpose |
|-------|------|---------|
| id | Integer (PK) | Auto-generated |
| student | ForeignKey → CustomUser | Student (role='student') |
| lecture | ForeignKey → Lecture | Related course (optional) |
| session | ForeignKey → AttendanceSession | The class session |
| time_in | DateTime (nullable) | Check-in QR scan timestamp |
| time_out | DateTime (nullable) | Check-out QR scan timestamp |
| status | Choice | **'pending'**, **'incomplete'**, **'present'**, **'absent'** |
| **device_fingerprint** | String (255) | **Unique browser device ID (prevents buddy punching)** |
| **scanned_ip** | GenericIPAddress | **Student's IP when scanning (subnet validation)** |
| **scanned_latitude** | Float | **Student's GPS latitude when scanning (geofence validation)** |
| **scanned_longitude** | Float | **Student's GPS longitude when scanning (geofence validation)** |

**Unique Constraint:** `unique_together = ('student', 'session')`
- Ensures each student has exactly 1 attendance record per session

**Status Lifecycle:**
```
pending ──[student scans check-in]──> incomplete
  ↓                                      ↓
  └─ [teacher ends class] ──> absent    └─ [student scans checkout] ──> present
                                         ↓
                                    [teacher ends] ──> absent (if no checkout)
```

---

##  Technical Architecture

### **Technology Stack**

**Backend:**
- Django 5.2.8 (Python Web Framework)
- Python 3.13
- MySQL 8.0 (Database)
- ReportLab 4.0.9 (PDF generation)
- PyJWT 2.10.1 (JWT token encryption)
- Geopy 2.4.1 (GPS distance calculation)
- Pillow 12.0.0 (Image processing for QR codes)
- QRCode 8.2 (QR code generation)

**Frontend:**
- HTML5/CSS3
- Vanilla JavaScript (ES6+)
- Bootstrap 5 (Responsive UI)
- HTML5 Geolocation API (GPS access)
- HTML5 Canvas/Camera API (QR scanning)

**Security Libraries:**
- django.contrib.auth (Password hashing with PBKDF2)
- PyJWT with HS256 (Token encryption)
- httponly Cookies (XSS protection)
- CSRF Token Protection

**Infrastructure:**
- Django's built-in development server
- Ngrok (Public tunnel for testing)
- SQLite/MySQL database
- Media file storage for QR code images

---

##  Core Workflows

### **Workflow 1: Student Registration**

```
1. Student visits /signup/
   ├─ Enters: username, email, enrollment_number, roll_number, password
   │
2. Form validates:
   ├─ Check if enrollment_number exists in AllowedStudent table
   ├─ Check if enrollment_number not already used
   └─ Validate password strength
   │
3. If valid:
   ├─ Create CustomUser with role='student'
   ├─ Set enrollment_number to their university ID
   ├─ Hash password using Django's PBKDF2
   │
4. Redirect to login page → Student can now access dashboard
```

### **Workflow 2: Teacher Starting a Class**

```
1. Teacher logs in → sees teacher dashboard
   │
2. Clicks "Start New Class"
   ├─ Fills form: subject, course_name, division, topic
   │
3. System captures:
   ├─ GPS (latitude, longitude) from teacher's device
   ├─ IP address from request (get_client_ip)
   └─ Current timestamp
   │
4. System creates:
   ├─ AttendanceSession record with GPS/IP anchors
   ├─ Pending Attendance records for all allowed students
   │
5. System generates Check-In QR:
   ├─ Create JWT payload: {session_id, type='check_in', exp=now+15min}
   ├─ Encrypt with Django SECRET_KEY (HS256)
   ├─ Generate QR image from token
   ├─ Save QR image to session.qr_code
   │
6. Every 20 seconds (via AJAX):
   ├─ JavaScript calls /api/generate-dynamic-qr/
   ├─ Backend validates: session still in 15-min window
   ├─ Creates new JWT token with unique nonce
   ├─ Generates new QR image
   └─ Returns Base64 encoded PNG via JSON
   │
7. Frontend updates QR display:
   ├─ Shows countdown timer (20 seconds)
   ├─ Refreshes QR image automatically
   └─ Prevents screenshot sharing (different QR each 20s)
```

### **Workflow 3: Student Scanning QR (Check-In)**

```
1. Student opens attendance page
   ├─ Browser requests GPS permission
   ├─ Gets location: (latitude, longitude)
   │
2. Student scans Check-In QR code (using webcam)
   ├─ JavaScript QR decoder extracts JWT token
   │
3. System validates JWT:
   ├─ Verify signature using Django SECRET_KEY
   ├─ Check: not expired (20-second window)
   ├─ Extract session_id from payload
   │
4. System validates location:
   ├─ Calculate distance: student GPS vs teacher GPS (Haversine formula)
   ├─ Check: distance ≤ 50 meters
   ├─ Reject if too far (red error message)
   │
5. System validates network:
   ├─ Extract student's IP from request
   ├─ Get teacher's anchor_ip from AttendanceSession
   ├─ Compare both using CIDR /24 subnet mask
   ├─ Reject if different subnet (VPN/mobile data detected)
   │
6. System validates device:
   ├─ Check browser cookie for existing device_fingerprint
   ├─ If first scan: generate new device_id, store in cookie
   ├─ If exists: verify same device (prevent buddy punching)
   │
7. If all validations pass:
   ├─ Create device_fingerprint (or verify existing)
   ├─ Update Attendance record:
   │  ├─ time_in = current timestamp
   │  ├─ status = 'incomplete'
   │  ├─ device_fingerprint = device_id
   │  ├─ scanned_ip = student's IP
   │  ├─ scanned_latitude = student's GPS latitude
   │  └─ scanned_longitude = student's GPS longitude
   │
8. Return success response:
   ├─ Show green checkmark
   ├─ Display: "Checked in successfully!"
   ├─ Show time_in timestamp
   └─ Update teacher's dashboard (live list of checked-in students)
```

### **Workflow 4: Teacher Initiating Checkout**

```
1. Teacher clicks "Initiate Checkout" on dashboard
   │
2. System transitions session state:
   ├─ Set is_checkout = TRUE
   ├─ Keep is_active = TRUE (session still open)
   │
3. System generates static check-out QR:
   ├─ Create JWT: {session_id, type='check_out', exp=now+10min}
   ├─ Generate QR image
   ├─ Save to session.qr_code (overwrites check-in QR)
   │
4. Frontend updates display:
   ├─ Hide countdown timer (check-out QR is static)
   ├─ Display check-out QR code
   ├─ Message: "Class checkout initiated"
   │
5. Teacher can view:
   ├─ Students who checked in (time_in recorded)
   ├─ Students with status = 'incomplete' (waiting for check-out)
   ├─ Real-time list of students checking out
```

### **Workflow 5: Student Scanning QR (Check-Out)**

```
1. Student scans Check-Out QR code
   ├─ Same validation as check-in (GPS, IP, Device, JWT)
   │
2. If all validations pass:
   ├─ Update Attendance record:
   │  ├─ time_out = current timestamp
   │  └─ status = 'present' (both scans completed ✓)
   │
3. Return success response:
   ├─ Show green checkmark: "Checked out successfully!"
   └─ Display time_out timestamp
```

### **Workflow 6: Teacher Ending Class**

```
1. Teacher clicks "End Class Now"
   │
2. System finalizes session:
   ├─ Set is_active = FALSE
   ├─ Record end_time = current timestamp
   │
3. Auto-mark absent records:
   ├─ Find all Attendance with status='pending' (never scanned)
   │  └─ Update status = 'absent'
   │
   ├─ Find all Attendance with status='incomplete' (only checked-in)
   │  └─ Update status = 'absent'
   │
4. Session officially closed:
   ├─ No more scanning allowed
   ├─ Attendance reports can now be generated
   └─ Data locked for audit trail
```

### **Workflow 7: Teacher Generating Reports**

```
1. Teacher navigates to "Generate Reports"
   │
2. Fills report form:
   ├─ Select subject (dropdown auto-populated from past sessions)
   ├─ Select report type: 'master' | 'defaulters' | 'audit'
   ├─ Date range: start_date → end_date
   │
3. System queries database:
   ├─ Find AttendanceSession matching:
   │  ├─ teacher = current teacher
   │  ├─ subject = selected subject (case-insensitive)
   │  ├─ start_time between date range
   │  └─ is_active = FALSE (closed sessions only)
   │
   ├─ Fetch Attendance records for these sessions
   │
4. Generate report based on type:
   │
   A) Master Report:
   ├─ List all students (roll number, name)
   ├─ For each session in date range:
   │  ├─ Show attendance status (Present/Absent/Incomplete)
   │  ├─ Show date of class
   │  └─ Show topic taught
   │
   B) Defaulters Report:
   ├─ Calculate: total_classes = count of sessions in range
   ├─ For each student:
   │  ├─ Count present = Attendance records with status='present'
   │  ├─ Calculate percentage = (present / total_classes) × 100
   │  ├─ If percentage < 75%: include in report
   │  └─ Mark as "Alert: Low Attendance"
   │
   C) Audit Report:
   ├─ For each Attendance record:
   │  ├─ Student name, roll number
   │  ├─ Date of attendance
   │  ├─ Time in / Time out (timestamps)
   │  ├─ Final status
   │  ├─ Scanned IP (network validation proof)
   │  ├─ GPS coordinates (geofencing proof)
   │  └─ Device fingerprint (antifraud proof)
   │
5. PDF Generation:
   ├─ Use ReportLab to create professional document
   ├─ Add header with metadata
   ├─ Format data into tables
   ├─ Apply color-coding (present=green, absent=red)
   ├─ Add page breaks for large reports
   │
6. Return PDF:
   ├─ Set Content-Type: 'application/pdf'
   ├─ Set Content-Disposition: 'attachment'
   ├─ Filename: BeQr_{type}_{subject}_{dates}.pdf
   └─ Browser downloads file automatically
```

---

##  Installation & Setup

### **Prerequisites**
- Python 3.13+
- MySQL 8.0+
- Git
- pip (Python package manager)

### **Step 1: Clone the Repository**
```bash
git clone https://github.com/sagarmaru17/Attendance-System.git
cd "Attendance-System/BeQr-Attendance System"
```

### **Step 2: Create Virtual Environment**
```bash
python3 -m venv dja
source dja/bin/activate       # On macOS/Linux
# or
dja\Scripts\activate           # On Windows
```

### **Step 3: Install Dependencies**
```bash
pip install -r requirements.txt
```

### **Step 4: Configure Database**
Edit `beqr/settings.py`:
```python
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': 'beqr_attendance',
        'USER': 'your_mysql_user',
        'PASSWORD': 'your_mysql_password',
        'HOST': 'localhost',
        'PORT': '3306',
    }
}
```

### **Step 5: Run Migrations**
```bash
python manage.py migrate
```

### **Step 6: Create Superuser (Admin)**
```bash
python manage.py createsuperuser
# Username: admin
# Email: admin@example.com
# Password: (choose secure password)
```

### **Step 7: Add Allowed Students**
1. Go to admin panel: `http://localhost:8000/admin/`
2. Login with superuser credentials
3. Click "Allowed Students" → "Add Allowed Student"
4. Enter enrollment numbers (e.g., BCA2024001, BCA2024002)
5. Save

### **Step 8: Create Teacher Accounts**
1. In admin panel, create user with role='teacher'
2. System auto-generates 6-character Faculty ID
3. Teacher can now login and create classes

### **Step 9: Run Development Server**
```bash
python manage.py runserver 8000
```

Access at: `http://localhost:8000/`

### **Step 10: (Optional) Expose to Public**
```bash
ngrok http 8000
```
Copy ngrok URL and update `CSRF_TRUSTED_ORIGINS` in settings.py

---

##  Database Schema Visualization

```
CustomUser (Users)
  ├─ id (PK)
  ├─ username (unique)
  ├─ email
  ├─ password (hashed)
  ├─ role ('student' | 'teacher')
  ├─ enrollment_number (unique)
  └─ roll_number
       │
       ├─ [1 teacher:N lectures] ──→ Lecture
       │   ├─ id (PK)
       │   ├─ name
       │   ├─ teacher_id (FK)
       │   └─ created_at
       │
       ├─ [1 teacher:N sessions] ──→ AttendanceSession
       │   ├─ id (PK)
       │   ├─ session_id (unique UUID)
       │   ├─ teacher_id (FK)
       │   ├─ subject, course_name, topic
       │   ├─ start_time, end_time
       │   ├─ is_active, is_checkout
       │   ├─ latitude, longitude (GPS anchor)
       │   ├─ anchor_ip (subnet anchor)
       │   └─ qr_code (image)
       │
       └─ [1 student:N attendance] ──→ Attendance
           ├─ id (PK)
           ├─ student_id (FK) [unique with session]
           ├─ session_id (FK) [unique with student]
           ├─ lecture_id (FK)
           ├─ time_in, time_out
           ├─ status ('pending'|'present'|'absent'|'incomplete')
           ├─ device_fingerprint (security)
           ├─ scanned_ip (security)
           ├─ scanned_latitude (security)
           └─ scanned_longitude (security)

AllowedStudent (Whitelist)
  ├─ id (PK)
  ├─ enrollment_number (unique, indexed)
  └─ email
```

---

##  Security Implementation Details

### **1. Authentication**
- Django's PBKDF2 password hashing (industry standard)
- Session-based authentication
- @login_required decorators on protected views
- Role-based access control (student vs teacher)

### **2. Authorization**
```python
# Example: Only teachers can access this view
if request.user.role != 'teacher':
    return redirect('error')
```

### **3. CSRF Protection**
- Django middleware enabled on all POST requests
- CSRF tokens in all forms
- ngrok origins whitelisted in settings

### **4. Time-Bound QR Codes (JWT)**
```python
# Token expires in 20 seconds (check-in phase)
payload = {
    'session_id': session_id,
    'type': 'check_in',
    'exp': timezone.now() + timedelta(seconds=20),
    'nonce': str(uuid.uuid4())  # Unique per QR, prevents caching
}
token = jwt.encode(payload, settings.SECRET_KEY, algorithm='HS256')
```

### **5. Geofencing (GPS Distance)**
```python
# Haversine formula: precise distance calculation
from geopy.distance import geodesic
teacher_location = (teacher_lat, teacher_lon)
student_location = (student_lat, student_lon)
distance = geodesic(teacher_location, student_location).meters

if distance > 50:  # 50-meter radius
    raise ValidationError("Outside classroom geofence")
```

### **6. Network Validation (IP Subnet)**
```python
import ipaddress
# /24 CIDR block ensures same local network
teacher_ip_network = ipaddress.ip_network(f'{teacher_ip}/24', strict=False)
student_ip = ipaddress.ip_address(scanned_ip)

if student_ip not in teacher_ip_network:
    raise ValidationError("Not on university network (VPN/Mobile data detected)")
```

### **7. Device Fingerprinting**
```python
# Browser fingerprint: unique per device
# Stored in secure httponly cookie (cannot be accessed via JavaScript)
response.set_cookie(
    'device_fp',
    device_fingerprint,
    max_age=31536000,  # 1 year
    secure=True,       # HTTPS only
    httponly=True,     # Cannot be stolen via XSS
    samesite='Strict'  # CSRF protection
)
```

---

##  Performance & Scalability

### **Optimizations Implemented**

1. **Default Database Indexing:**
   - PK on all tables
   - Unique constraint on enrollment_number
   - Foreign key indices on teacher, student, session

2. **Query Optimization:**
   - Prefetch related attendance records
   - Use select_related for foreign keys
   - Date range filtering instead of fetching all

3. **Media Storage:**
   - QR codes stored as PNG images
   - Media files saved to /media/qr_codes/ directory
   - Django's FileSystemStorage for file management

4. **Frontend Optimization:**
   - AJAX for dynamic QR refresh (no page reload)
   - Lazy loading for attendance history
   - Debounced GPS requests (not every millisecond)

---

##  Troubleshooting

### **Q: "No active session" error**
**A:** Teacher must click "Start New Class" first. Session doesn't exist until created.

### **Q: GPS showing "access denied"**
**A:** 
- Must use HTTPS (or localhost with development server)
- Allow browser location permissions
- Device must have GPS hardware

### **Q: IP validation failing**
**A:** 
- Check teacher and student are on same Wi-Fi network
- Disable VPN
- Mobile data won't work (intentional blocking)

### **Q: "Access Denied: Enrollment Number not registered"**
**A:** Student's enrollment number must be added to AllowedStudent table first (via admin panel)

### **Q: Reports showing no data**
**A:** 
- Sessions must be closed (is_active=False) before reports work
- Date range must include session dates
- Subject name must match exactly

---

##  Project Metrics

| Metric | Value |
|--------|-------|
| **Total Tables** | 5 |
| **Total Views** | 20+ |
| **Database Records** | ~1000+ (depends on usage) |
| **QR Code Rotation** | Every 20 seconds |
| **Check-In Window** | 15 minutes |
| **Geofence Radius** | 50 meters |
| **Device Fingerprint** | 1 year validity |
| **IP Subnet Validation** | /24 CIDR block |
| **PDF Report Types** | 3 (Master, Defaulters, Audit) |
| **Lines of Code** | ~2000+ |
| **Development Time** | ~200+ hours |

---

##  Academic Significance

This project demonstrates:

 **Full-Stack Web Development**
- Backend: Django ORM, views, forms, authentication
- Frontend: HTML5, CSS3, JavaScript (ES6+)
- Database: Relational schema design

 **Advanced Security Concepts**
- JWT encryption & time-bound tokens
- Geofencing with GPS (Haversine formula)
- Network security (IP subnet validation)
- Device fingerprinting (anti-fraud)

 **Software Engineering Best Practices**
- MVC architecture (Models, Views, Controllers)
- DRY principle (Don't Repeat Yourself)
- Code documentation & comments
- Version control (Git)

 **Database Design**
- Relational schema with foreign keys
- Unique constraints & integrity
- Efficient indexing strategy
- Complex queries & aggregations

 **Real-World Problem Solving**
- Identified actual security loopholes
- Designed innovative solutions
- Implemented & tested thoroughly
- Documented for scalability

---

##  References & Technologies

- Django Documentation: https://docs.djangoproject.com/
- PyJWT: https://pyjwt.readthedocs.io/
- Geopy: https://geopy.readthedocs.io/
- ReportLab: https://www.reportlab.com/docs/reportlab-userguide.pdf
- RFC 7519 (JWT Standard): https://tools.ietf.org/html/rfc7519

---

##  License

This project is submitted as academic work and is provided "as-is" for educational purposes.

---

##  Contact & Support

**Student:** Sagar Maru  
**Repository:** https://github.com/sagarmaru17/Attendance-System  

For questions or feature requests, please open an issue on GitHub.

---

**Last Updated:** March 22, 2026  
**Status:**  Complete (Academic Submission)

Dynamic Generation: One-click generation of the cryptographic QR matrix.

Manual Override: When students facing hardware issues.

 For Administrators

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

 Local Installation Guide

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

 Usage Workflow

Initial Setup: Log in to the Django Admin panel (/admin). Add valid Enrollment Numbers to the Allowed Students table. Create Faculty users (Faculty IDs are auto-generated).

Student Onboarding: Students click "Sign Up" and enter their University Enrollment Number. If it matches the Admin's Master List, the account is created.

Running a Class: The Teacher logs in, clicks "Start Class", and displays the generated QR code on the projector.

Marking Attendance: Students log in, scan the QR code via their phone, pass the background validation (IP + Location + Device), and are marked present.

 Project Structure

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


 Author

Sagar Maru
Linkedin : https://www.linkedin.com/in/sagar-maru-b987b9294/


 License

This project was developed for educational purposes as part of a  academic submission.