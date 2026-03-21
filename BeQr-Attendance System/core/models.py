# ============================================================
# DATABASE MODELS - Core Data Schema
# ============================================================
#
# Defines all database models for the QR-based attendance system.
#
# Models:
# 1. CustomUser - Extended Django User for role-based authentication
# 2. AllowedStudent - Master list of students allowed to register
# 3. Lecture - Course/subject information
# 4. AttendanceSession - Active/past class sessions
# 5. Attendance - Individual student attendance records

import random
import string
import uuid
from django.utils import timezone
from django.db import models
from django.contrib.auth.models import AbstractUser

# ============================================================
# MODEL: CustomUser - Extended User with Roles
# ============================================================
#
# Extends Django's AbstractUser to add role-based access control.
#
# Fields:
# - role: 'student' or 'teacher' (default: student)
# - enrollment_number:
#   * For students: University enrollment number (unique)
#   * For teachers: Auto-generated 6-char Faculty ID (e.g., "JK5N2X")
# - roll_number: Class roll number (students only)
#
# Methods:
# - generate_unique_id(): Creates random unique ID for teachers
# - save(): Auto-assigns Faculty ID on first save if teacher
#
# Examples:
# - Student: username="john_doe", enrollment_number="BCA2024001", roll_number="15"
# - Teacher: username="prof_vora", enrollment_number="JK5N2X" (auto-generated)
class CustomUser(AbstractUser):
    ROLE_CHOICES = (
        ('student', 'Student'),
        ('teacher', 'Teacher'),
    )
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default='student')
    # This field acts as Enrollment No for Students AND Faculty ID for Teachers
    enrollment_number = models.CharField(max_length=50, unique=True, null=True, blank=True)
    roll_number = models.CharField(max_length=20, blank=True, null=True)
    
    def __str__(self):
        return self.username

    # --- Helper Function to Generate Random ID for Teachers ---
    def generate_unique_id(self):
        length = 6
        # Define valid characters: Uppercase letters and Numbers (e.g., A-Z, 0-9)
        characters = string.ascii_uppercase + string.digits
        
        while True:
            # Generate a random 6-char string (e.g., "TR45X9")
            new_id = ''.join(random.choices(characters, k=length))
            
            # Check if this ID already exists in the database
            if not CustomUser.objects.filter(enrollment_number=new_id).exists():
                return new_id

    # --- Override the Save Method ---
    def save(self, *args, **kwargs):
        # Logic: If this is a Teacher AND they don't have an ID yet...
        if self.role == 'teacher' and not self.enrollment_number:
            self.enrollment_number = self.generate_unique_id()
        
        # Finally, save the user to the database
        super().save(*args, **kwargs)

# ============================================================
# MODEL: AllowedStudent - Master Enrollment Whitelist
# ============================================================
#
# Acts as the master list of students allowed to register.
# Created by admin/teacher to control who can sign up.
#
# Fields:
# - enrollment_number: University enrollment number (unique)
# - email: Student email (optional)
#
# Usage:
# - During signup, student must provide enrollment_number that exists here
# - If enrollment_number not in AllowedStudent, signup is rejected
# - Prevents unauthorized student registration
#
# Example row:
# - enrollment_number: "BCA2024001"
# - email: "student@university.edu"
class AllowedStudent(models.Model):
    enrollment_number = models.CharField(max_length=50, unique=True)
    email = models.EmailField(blank=True, null=True)
    
    def __str__(self):
        return self.enrollment_number

# ============================================================
# MODEL: Lecture - Course/Subject Information
# ============================================================
#
# Stores lecture/subject information.
#
# Fields:
# - name: Lecture or subject name (e.g., "Python Programming", "Web Development")
# - teacher: Foreign key to CustomUser (teacher who teaches this lecture)
# - created_at: Timestamp when lecture was created
#
# Relationships:
# - Many lectures can be taught by one teacher
# - One lecture belongs to one teacher
#
# Example:
# - name: "Django Models"
# - teacher: prof_vora
# - created_at: 2026-03-13 10:30:00
class Lecture(models.Model):
    name = models.CharField(max_length=255)
    teacher = models.ForeignKey(CustomUser, on_delete=models.CASCADE, limit_choices_to={'role': 'teacher'})
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} by {self.teacher.username}"

# ============================================================
# MODEL: AttendanceSession - Active/Past Class Sessions
# ============================================================
#
# Represents a single class session (active or completed).
# Created when teacher starts a class.
# Contains all security anchor data for geofencing and validation.
#
# Fields - Basic Info:
# - session_id: Unique UUID for this session (primary identifier)
# - teacher: Teacher conducting this session
# - course_name: e.g., "BCA Sem 6"
# - division: Class section, e.g., "A", "B"
# - subject: e.g., "Software Development Engineering"
# - topic: Lecture topic, e.g., "Django Models"
#
# Fields - Time & Status:
# - start_time: When teacher started the class (auto-set)
# - end_time: When teacher ended the class (set when session closes)
# - is_active: True while class is ongoing, False after closed
# - is_checkout: True after "Initiate Checkout" clicked (for check-out QR)
#
# Fields - Security Anchors (Set when teacher starts class):
# - latitude: Teacher's GPS latitude (for 50m geofencing)
# - longitude: Teacher's GPS longitude (for 50m geofencing)
# - anchor_ip: Teacher's IP address (for subnet validation)
#
# Fields - QR Code:
# - qr_code: Image field storing generated check-in/check-out QR code PNG
#
# Workflow:
# 1. Teacher clicks "Start New Class" → Session created (is_active=True)
# 2. System captures teacher's GPS and IP address
# 3. Check-in QR code generated with JWT token
# 4. Students scan QR code within 15 minutes
# 5. Teacher clicks "Initiate Checkout" → is_checkout=True, check-out QR generated (10-min)
# 6. Students scan check-out QR code
# 7. Teacher clicks "End Class Now" → is_active=False, end_time set
# 8. All pending attendance records marked as absent
#
# Security:
# - GPS: Students must be within 50m of teacher's location
# - IP: Students must be on same subnet as teacher (/24 CIDR)
# - Prevents attendance from outside classroom
#
# Example:
# - session_id: "550e8400-e29b-41d4-a716-446655440000"
# - teacher: prof_vora
# - subject: "SDE"
# - topic: "DFD Design"
# - is_active: False (class ended)
# - is_checkout: False
# - latitude: 53.1234
# - longitude: -8.4567
# - anchor_ip: "192.168.1.100"
class AttendanceSession(models.Model):
    session_id = models.CharField(max_length=100, unique=True, default=uuid.uuid4)
    teacher = models.ForeignKey(CustomUser, on_delete=models.CASCADE, limit_choices_to={'role': 'teacher'})
    
    # Class Details
    course_name = models.CharField(max_length=100) # e.g., "BCA Sem 6"
    division = models.CharField(max_length=10, blank=True, null=True) # e.g., "A"
    subject = models.CharField(max_length=100)     # e.g., "Python"
    topic = models.CharField(max_length=255, blank=True, null=True)   # e.g., "Django Models"
    
    # Time and Status Flags
    start_time = models.DateTimeField(auto_now_add=True)
    end_time = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    is_checkout = models.BooleanField(default=False) # Tracks Dual-Scan Check-Out phase
    
    # --- ANCHOR FIELDS FOR TRIPLE-LAYER SECURITY ---
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)
    anchor_ip = models.GenericIPAddressField(null=True, blank=True)
    
    # Field to store the generated QR code image
    qr_code = models.ImageField(upload_to='qr_codes/', blank=True, null=True)

    def __str__(self):
        return f"{self.subject} ({self.course_name}) - {self.teacher.username}"


# ============================================================
# MODEL: Attendance - Individual Student Attendance Records
# ============================================================
#
# Tracks attendance for each student in each session.
# Created automatically when teacher starts a session (status: pending).
# Updated when student scans QR codes or teacher manually overrides.
#
# STATUS WORKFLOW:
# - pending: Initial state (created when session starts)
# - incomplete: Student scanned check-in, waiting for check-out
# - present: Student completed both check-in and check-out
# - absent: Student never scanned OR teacher marked absent
#
# Fields - Basic Reference:
# - student: Foreign key to student (CustomUser with role='student')
# - lecture: Related Lecture (optional, filled from session.subject)
# - session: Foreign key to AttendanceSession this attendance is for
#
# Fields - Time Tracking:
# - time_in: Timestamp when student scanned check-in QR
# - time_out: Timestamp when student scanned check-out QR
# - status: Current attendance status (pending/present/absent/incomplete)
#
# Fields - Security & Audit:
# - device_fingerprint: Unique device ID from browser cookie
#   * Used to prevent buddy punching (same device, multiple students)
#   * Stored in secure httponly cookie for 1 year
#
# - scanned_ip: Student's IP address when scanning
#   * Validated to be on same subnet as teacher (/24 CIDR)
#
# - scanned_latitude: GPS latitude when student scanned
#   * Validated to be within 50m of teacher's location
#
# - scanned_longitude: GPS longitude when student scanned
#   * Validated to be within 50m of teacher's location
#
# Constraints:
# - unique_together: (student, session)
#   * Ensures each student can only have 1 attendance record per session
#   * Prevents duplicate attendance for same student same session
#
# Lifecycle Example:
#
# 1. Teacher starts session (SDE class)
#    \u2192 Attendance created with status='pending' for all allowed students
#
# 2. Student A scans check-in QR (09:30 AM)
#    \u2192 time_in = 09:30 AM
#    \u2192 status = 'incomplete'
#    \u2192 device_fingerprint, scanned_ip, scanned_latitude, scanned_longitude recorded
#
# 3. Student A scans check-out QR (10:15 AM)
#    \u2192 time_out = 10:15 AM
#    \u2192 status = 'present'
#
# 4. Teacher ends session at 10:30 AM
#    \u2192 All records still with status='pending' \u2192 marked as 'absent'
#    \u2192 Student B, C, D marked absent (never scanned)
#
# Example Record:
# - student: john_doe (roll=15)
# - session: SDE (Div B) - started 2026-03-13 09:00 AM
# - status: present
# - time_in: 2026-03-13 09:05 AM
# - time_out: 2026-03-13 10:15 AM
# - device_fingerprint: \"a1b2c3d4-e5f6-...\"
# - scanned_ip: \"192.168.1.105\"
# - scanned_latitude: 53.1234
# - scanned_longitude: -8.4567
class Attendance(models.Model):
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('present', 'Present'),
        ('absent', 'Absent'),
        ('incomplete', 'Incomplete'),
    )
    student = models.ForeignKey(CustomUser, on_delete=models.CASCADE, limit_choices_to={'role': 'student'})
    lecture = models.ForeignKey(Lecture, on_delete=models.CASCADE, null=True, blank=True)
    session = models.ForeignKey(AttendanceSession, on_delete=models.CASCADE, null=True, blank=True)
    
    time_in = models.DateTimeField(null=True, blank=True)
    time_out = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default='pending')

    # --- SECURITY & AUDIT FIELDS ---
    device_fingerprint = models.CharField(max_length=255, blank=True, null=True, help_text="Used to block buddy punching")
    scanned_ip = models.GenericIPAddressField(null=True, blank=True)
    scanned_latitude = models.FloatField(null=True, blank=True)
    scanned_longitude = models.FloatField(null=True, blank=True)

    class Meta:
        # Enforce that a student can only have one attendance record per live session
        unique_together = ('student', 'session')

    def __str__(self):
        return f"{self.student.username} - {self.session.subject if self.session else 'No Session'} - {self.status}"
    

# class Attendance(models.Model):
#     STATUS_CHOICES = (
#         ('pending', 'Pending'),
#         ('present', 'Present'),
#         ('absent', 'Absent'),
#         ('incomplete', 'Incomplete'),
#     )
#     student = models.ForeignKey(CustomUser, on_delete=models.CASCADE, limit_choices_to={'role': 'student'})
#     lecture = models.ForeignKey(Lecture, on_delete=models.CASCADE, null=True, blank=True)
#     session = models.ForeignKey(AttendanceSession, on_delete=models.CASCADE, null=True, blank=True) # Link to active session
    
#     time_in = models.DateTimeField(null=True, blank=True)
#     time_out = models.DateTimeField(null=True, blank=True)
#     status = models.CharField(max_length=15, choices=STATUS_CHOICES, default='pending')

#     def __str__(self):
#         return f"{self.student.username} - {self.lecture.name if self.lecture else 'No Lecture'} - {self.status}"
    

