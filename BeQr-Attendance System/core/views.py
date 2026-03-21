# ============================================================================
# BeQr ATTENDANCE SYSTEM - VIEWS MODULE
# ============================================================================
# This module contains all view functions for the BeQr Attendance System:
# - Authentication (Login, Signup, Password Reset)
# - Teacher Dashboard & Class Management
# - Dynamic QR Code Generation (20-second rotation with 15-minute boundary)
# - Attendance Scanning with Multi-Layer Security (GPS, IP, Device Fingerprint)
# - Report Generation (PDF exports with various report types)
# - Student Dashboard & History
# ============================================================================

from django.utils import timezone
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.contrib.auth.forms import SetPasswordForm
from django.contrib.auth.decorators import login_required
from .forms import StudentRegistrationForm, PasswordResetVerificationForm
from .models import Lecture, Attendance, CustomUser, AllowedStudent, AttendanceSession
import uuid
import base64
from io import BytesIO
from datetime import timedelta
from django.core.files import File
from django.conf import settings
from django.db.models import Count, Q
import ipaddress
import jwt
import qrcode, csv
from geopy.distance import geodesic
from jwt.exceptions import ExpiredSignatureError, InvalidTokenError
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT



# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def get_client_ip(request):
    """
    Extract the client's IP address from the request.
    
    Checks for X-Forwarded-For header first (for proxies), then falls back
    to REMOTE_ADDR for direct connections. Used for network subnet validation.
    
    Args:
        request: Django HTTP request object
        
    Returns:
        str: Client IP address
    """
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip


# ============================================================================
# AUTHENTICATION VIEWS
# ============================================================================
# Views for user login, signup, and password management
# Handles role-based redirects (teacher vs student dashboard)
# ============================================================================

def login_view(request):
    """
    User login view supporting both teachers and students.
    
    POST: Authenticates user credentials and redirects based on role
    GET: Displays login form
    
    Redirects:
    - Teacher → teacher_dashboard
    - Student → student_dashboard
    - Invalid credentials → login page with error message
    """
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')

        user = authenticate(request, username=username, password=password)

        if user is not None:
            login(request, user)
                        
            if user.role == 'teacher':
                return redirect('teacher_dashboard')
            else:
                return redirect('student_dashboard')
        else:
            messages.error(request, "Invalid username or password.")

    return render(request, 'core/login.html')


def logout_view(request):
    """
    User logout view.
    
    Clears session and redirects to login page with success message.
    """
    logout(request)
    messages.success(request, "You have been logged out.")
    return redirect('login')


def signup_view(request):
    """
    Student registration view.
    
    POST: Creates new student account (role automatically set to 'student')
    GET: Displays signup form
    
    Validation:
    - Form validation errors are displayed to user
    - Successful registration redirects to login page
    """
    if request.method == 'POST':
        form = StudentRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.role = 'student'  # Automatically set role to Student
            user.save()
            messages.success(request, "Account created successfully! Please login.")
            return redirect('login')
        else:
            messages.error(request, "Registration failed. Please correct the errors below.")
    else:
        form = StudentRegistrationForm()

    return render(request, 'core/signup.html', {'form': form})


def forgot_password_view(request):
    """
    Password reset initiation view.
    
    POST: Verifies user identity (enrollment number + email)
           Stores user ID in session for security
           Redirects to reset form
    GET: Displays password verification form
    
    Security: Uses session to maintain state between verification and reset
    """
    if request.method == 'POST':
        form = PasswordResetVerificationForm(request.POST)
        if form.is_valid():
            # Get the user found by the form
            user = form.user_cache
            
            # Store the user's ID in the session securely
            request.session['reset_user_id'] = user.id
            
            return redirect('reset_password_confirm')
    else:
        form = PasswordResetVerificationForm()

    return render(request, 'core/forgot_password.html', {'form': form})


def reset_password_confirm_view(request):
    """
    Password reset form view.
    
    Requires: Valid session with reset_user_id (from forgot_password_view)
    
    POST: Updates password using Django's SetPasswordForm (handles hashing)
    GET: Displays password reset form
    
    Security:
    - Checks for valid session before proceeding
    - Uses Django's security for password hashing
    - Clears session after successful reset
    """
    # Security Check: Do we have a verified user in the session?
    user_id = request.session.get('reset_user_id')
    
    if not user_id:
        messages.error(request, "Session expired or invalid. Please verify your details again.")
        return redirect('forgot_password')

    try:
        user = CustomUser.objects.get(id=user_id)
    except CustomUser.DoesNotExist:
        return redirect('forgot_password')

    if request.method == 'POST':
        # Use Django's built-in SetPasswordForm (handles encryption & validation)
        form = SetPasswordForm(user, request.POST)
        if form.is_valid():
            form.save()
            
            # Clear the session so they can't reset it again
            del request.session['reset_user_id']
            
            messages.success(request, "Password changed successfully! Please login.")
            return redirect('login')
    else:
        form = SetPasswordForm(user)

    return render(request, 'core/reset_password_form.html', {'form': form})



# ============================================================================
# TEACHER VIEWS - DASHBOARD & CLASS MANAGEMENT
# ============================================================================
# Views for teacher dashboard, class session management, and QR generation
# Includes dynamic QR rotation (20-second) with 15-minute check-in window
# ============================================================================

@login_required
def teacher_dashboard_view(request):
    """
    Main teacher dashboard displaying active class and lecture history.
    
    Security: Requires @login_required and role='teacher'
    
    Features:
    1. Active Session Display:
       - Shows live QR code and countdown timer
       - Displays real-time student check-ins
       - Allows teacher to switch between check-in and check-out phases
    
    2. Lecture History:
       - Past sessions with attendance statistics
       - Shows present/absent counts per lecture
       - Paginated view (10 sessions shown by default)
    
    3. Report Generation:
       - Links to PDF report generator
       - Supports multiple report types (master, defaulters, audit)
    
    4. Student Management:
       - Shows allowed students for current courses
       - Faculty stats (total classes, registered students)
    
    Context Variables:
    - active_session: Current DanceSession (if any)
    - live_students: Students who have checked in this session
    - past_sessions: Historical lecture data with stats
    - remaining_seconds: Time left in 15-minute check-in window
    - all_subjects: List of unique subjects for dropdown
    """
    if request.user.role != 'teacher':
        messages.warning(request, "Access denied. Restricted to faculty.")
        return redirect('student_dashboard')

    # Fetch Student Stats
    registered_count = CustomUser.objects.filter(role='student').count()
    total_allowed = AllowedStudent.objects.count()
    allowed_students_list = AllowedStudent.objects.all().order_by('enrollment_number')

    # Check for active session
    active_session = AttendanceSession.objects.filter(teacher=request.user, is_active=True).first()
    live_students = []
    remaining_seconds = 0
    if active_session:
        live_students = Attendance.objects.filter(session=active_session).order_by('-time_in')
        
        # Calculate remaining seconds for the QR code (15 minutes total)
        elapsed = (timezone.now() - active_session.start_time).total_seconds()
        remaining_seconds = max(0, 900 - int(elapsed))  # 900 seconds = 15 minutes

    # --- NEW: Fetch Past Sessions & Calculate Stats ---
    all_past_sessions = AttendanceSession.objects.filter(
        teacher=request.user, 
        is_active=False
    ).annotate(
        present_count=Count('attendance', filter=Q(attendance__status='present')),
        absent_count=Count('attendance', filter=Q(attendance__status='absent')),
        incomplete_count=Count('attendance', filter=Q(attendance__status='incomplete')),
        total_scanned=Count('attendance')  # Total students who scanned at least once
    ).order_by('-start_time')
    
    # Show only last 10 by default, but pass all sessions to template
    past_sessions = list(all_past_sessions)
    has_more = len(past_sessions) > 10
    
    # Fetch all lectures AND unique subjects from past sessions (for report generation dropdown)
    # ORDERED BY MOST RECENT FIRST
    lectures = Lecture.objects.filter(teacher=request.user).order_by('-created_at') if hasattr(Lecture.objects.model, 'created_at') else Lecture.objects.filter(teacher=request.user)
    
    # Get past sessions ordered by most recent
    past_session_subjects_queryset = AttendanceSession.objects.filter(
        teacher=request.user
    ).values('subject').order_by('-start_time').distinct()
    
    # Build subjects list with recent items first
    all_subjects = []
    seen_subjects = set()
    
    # Add lecture names first (most recent)
    for lecture in lectures:
        if lecture.name not in seen_subjects:
            all_subjects.append(lecture.name)
            seen_subjects.add(lecture.name)
    
    # Add past session subjects (ordered by most recent)
    for session_obj in past_session_subjects_queryset:
        subject = session_obj['subject']
        if subject not in seen_subjects:
            all_subjects.append(subject)
            seen_subjects.add(subject)

    context = {
        'teacher': request.user,
        'lectures': lectures,
        'all_subjects': all_subjects,  # Already ordered by most recent
        'past_sessions': past_sessions,
        'has_more_sessions': has_more,
        'total_sessions': len(past_sessions),
        'registered_count': max(0, registered_count - 1),
        'total_allowed': total_allowed,
        'allowed_students': allowed_students_list, 
        'active_session': active_session, 
        'live_students': live_students,
        'remaining_seconds': remaining_seconds,
    }
    
    return render(request, 'core/teacher/dashboard.html', context)


@login_required
def start_class_view(request):
    """
    Initialize a new classroom session and generate initial QR code.
    
    Called by: Modal/Inline form on teacher dashboard
    
    POST Parameters:
    - subject: Lecture subject name (e.g., "JavaScript", "PHP")
    - course: Course identifier (e.g., "BCA Sem 6")
    - division: Class division (e.g., "A", "B")
    - topic: Current topic/chapter being taught
    - latitude: GPS coordinate (center of classroom)
    - longitude: GPS coordinate (center of classroom)
    
    Process:
    1. Create AttendanceSession record with GPS anchor (geofencing)
    2. Capture teacher's IP for subnet validation (proxy detection)
    3. Create 'pending' attendance records for all allowed students
    4. Generate initial 15-minute JWT token
    5. Create QR code image from JWT token
    6. Save QR code to session.qr_code field (for phase 2 checkout)
    
    Security:
    - GPS: Sets 50-meter geofence around classroom (in process_scan_view)
    - IP: Validates students are on same Wi-Fi subnet as teacher
    - JWT: 15-minute expiry for check-in phase (initial QR validity)
    - Device FP: Prevents multiple students using same device
    
    Returns:
    - Redirect to teacher_dashboard (QR display happens via dashboard view)
    """
    if request.user.role != 'teacher':
        return redirect('login')

    if request.method == 'POST':
        # Get data from the modal/inline form
        subject = request.POST.get('subject')
        course = request.POST.get('course')
        division = request.POST.get('division')
        topic = request.POST.get('topic')
        lat = request.POST.get('latitude')
        lon = request.POST.get('longitude')
        
        # Capture Teacher's IP (The Subnet Anchor)
        teacher_ip = get_client_ip(request)

        # 1. Create the Active Session
        session = AttendanceSession.objects.create(
            teacher=request.user,
            subject=subject,
            course_name=course,
            division=division,
            topic=topic,
            latitude=lat if lat else None,
            longitude=lon if lon else None,
            anchor_ip=teacher_ip,
            session_id=str(uuid.uuid4())
        )

        # 1b. Create attendance records for all allowed students with 'pending' status
        # This way, students who don't scan will be counted as absent
        allowed_students = AllowedStudent.objects.all()
        for allowed in allowed_students:
            try:
                # Try to find the student account
                student = CustomUser.objects.get(enrollment_number=allowed.enrollment_number, role='student')
                # Create attendance record if it doesn't exist
                Attendance.objects.get_or_create(
                    student=student,
                    session=session,
                    defaults={'status': 'pending'}
                )
            except CustomUser.DoesNotExist:
                # Student hasn't registered yet, skip
                pass

        # 2. Layer 1 Security: Create the 15-Minute Expiry JWT Payload
        payload = {
            'session_id': session.session_id,
            'type': 'check_in',
            'exp': timezone.now() + timedelta(minutes=15) 
        }
        
        # Encrypt token using your Django SECRET_KEY
        token = jwt.encode(payload, settings.SECRET_KEY, algorithm='HS256')

        # 3. Generate the visual QR Code from the Token
        qr = qrcode.QRCode(version=1, box_size=10, border=5)
        qr.add_data(token)
        qr.make(fit=True)
        img = qr.make_image(fill='black', back_color='white')

        # Save the image file to the Session record
        buffer = BytesIO()
        img.save(buffer, format="PNG")
        file_name = f'qr_{session.session_id}.png'
        session.qr_code.save(file_name, File(buffer), save=True)

        return redirect('teacher_dashboard')
    
    return redirect('teacher_dashboard')

@login_required
def generate_dynamic_qr_view(request):
    """
    AJAX API endpoint for dynamic QR code generation during check-in phase.
    
    Called by: JavaScript on teacher dashboard every 18 seconds
    
    Implements: 20-second rotation with 15-minute boundary
    
    Check-in Timeline (Minutes 0-15):
    - QR rotates every 20 seconds automatically
    - Each QR has unique encrypted JWT token + nonce (UUID)
    - Frontend shows countdown: "Expires in 20s"
    - Students must scan fresh QR codes (prevents screenshot sharing)
    
    After 15 Minutes (Deadline):
    - API rejects dynamic QR generation
    - Returns: expired=True error message
    - Frontend stops rotation, grays out QR image
    - Students cannot check in anymore (period closed)
    - Switch to check-out phase with normal QR
    
    Security Measures:
    1. Role Check: Only teachers can access
    2. Session Check: Active session must exist
    3. Phase Check: Rejects during checkout phase
    4. Time Boundary: Rejects after 15-minute deadline
    5. JWT Token: 20-second expiry prevents late scans
    6. Nonce: Unique UUID in each token prevents caching
    7. Base64: Image encoding for safe JSON transmission
    
    Response Format (Success):
    {
        'success': True,
        'qr_image': 'data:image/png;base64,{base64_string}',
        'token': '{jwt_token}',
        'expires_in': 20,
        'generated_at': '2026-03-18T10:30:45.123456Z',
        'check_in_deadline': '2026-03-18T10:45:00.000000Z',
        'time_remaining_minutes': 14
    }
    
    Response Format (Expired):
    {
        'success': False,
        'error': 'Check-in period expired',
        'message': 'The 15-minute check-in window has ended. Please use check-out QR.',
        'expired': True,
        'check_in_deadline': '2026-03-18T10:45:00.000000Z'
    }
    """
    if request.user.role != 'teacher':
        return JsonResponse({'error': 'Access denied'}, status=403)
    
    # Check for active session
    active_session = AttendanceSession.objects.filter(teacher=request.user, is_active=True).first()
    
    if not active_session:
        return JsonResponse({'error': 'No active session'}, status=400)
    
    # CHECK-IN PHASE TIME BOUNDARY (15 minutes)
    check_in_deadline = active_session.start_time + timedelta(minutes=15)
    current_time = timezone.now()
    
    # If in checkout phase OR after 15-min check-in deadline: reject dynamic QR
    if active_session.is_checkout or current_time > check_in_deadline:
        return JsonResponse({
            'success': False,
            'error': 'Check-in period expired',
            'message': 'The 15-minute check-in window has ended. Please use check-out QR.',
            'expired': True,
            'check_in_deadline': check_in_deadline.isoformat()
        }, status=400)
    
    # Generate a fresh token with 20-second expiry (within 15-min window)
    payload = {
        'session_id': active_session.session_id,
        'type': 'check_in',
        'exp': timezone.now() + timedelta(seconds=20),  # 20 seconds expiry for rotation
        'nonce': str(uuid.uuid4())  # Unique identifier to prevent caching
    }
    
    token = jwt.encode(payload, settings.SECRET_KEY, algorithm='HS256')
    
    # Generate QR code from token
    qr = qrcode.QRCode(version=1, box_size=10, border=5)
    qr.add_data(token)
    qr.make(fit=True)
    img = qr.make_image(fill='black', back_color='white')
    
    # Convert to base64 for display in HTML
    buffer = BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)
    qr_base64 = base64.b64encode(buffer.getvalue()).decode()
    
    return JsonResponse({
        'success': True,
        'qr_image': f'data:image/png;base64,{qr_base64}',
        'token': token,
        'expires_in': 20,  # 20 seconds
        'generated_at': timezone.now().isoformat(),
        'check_in_deadline': check_in_deadline.isoformat(),
        'time_remaining_minutes': int((check_in_deadline - current_time).total_seconds() / 60)
    })


@login_required
def end_class_view(request):
    """
    Handle class session end events with 2-phase checkout process.
    
    TWO-PHASE CLASS CLOSURE:
    
    Phase 1: initiate_checkout
    - Switches session from check-in to check-out mode (is_checkout=True)
    - Stops dynamic QR rotation (20-second cycle ends)
    - Generates static check-out QR with 10-minute expiry
    - Students must scan check-out QR within 10 minutes
    - Marks attendance as 'incomplete' until check-out scanned
    
    Phase 2: close_session
    - Sets session.is_active=False (signals class ended)
    - Records end_time timestamp
    - Finalizes attendance:
      * Students with 'pending' status → marked 'absent'
      * Students with 'incomplete' status → marked 'absent'
      * Students with 'present' status → stays 'present'
    - Attendance records locked (no more scanning allowed)
    
    POST Actions:
    - 'initiate_checkout': Start phase 2
    - 'close_session': Finalize and end session
    
    Redirects:
    - Always returns to teacher_dashboard
    """
    session = AttendanceSession.objects.filter(teacher=request.user, is_active=True).first()
    if not session:
        return redirect('teacher_dashboard')

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'initiate_checkout':
            # Phase 2: Generate the Check-Out QR Code
            session.is_checkout = True
            session.save()
            
            payload = {
                'session_id': session.session_id,
                'type': 'check_out',
                'exp': timezone.now() + timedelta(minutes=10) # 10 minute check-out window
            }
            token = jwt.encode(payload, settings.SECRET_KEY, algorithm='HS256')
            
            qr = qrcode.QRCode(version=1, box_size=10, border=5)
            qr.add_data(token)
            qr.make(fit=True)
            img = qr.make_image(fill='black', back_color='white')

            buffer = BytesIO()
            img.save(buffer, format="PNG")
            file_name = f'checkout_qr_{session.session_id}.png'
            session.qr_code.save(file_name, File(buffer), save=True)

        # ...existing code...
        elif action == 'close_session':
            # Phase 3: Finalize everything
            session.is_active = False
            session.end_time = timezone.now()
            session.save()
            
            # Mark all students with 'pending' status as 'absent'
            # (students who never checked in)
            Attendance.objects.filter(
                session=session,
                status='pending'
            ).update(status='absent')
            
            # Mark incomplete students as absent (Optional logic based on your requirements)
            Attendance.objects.filter(session=session, status='incomplete').update(status='absent')
            
            messages.success(request, "Class session ended successfully.")

    return redirect('teacher_dashboard')

@login_required
def generate_report_view(request):
    """
    Generate PDF attendance reports with multiple formats.
    
    Security: Requires @login_required and role='teacher'
    
    POST Parameters:
    - subject: Lecture subject name (case-insensitive filter)
    - report_type: Type of report to generate (master, defaulters, audit)
    - start_date: Report period start (YYYY-MM-DD format)
    - end_date: Report period end (YYYY-MM-DD format)
    
    REPORT TYPES:
    
    1. Master Attendance Report (report_type='master'):
       - Complete attendance list for all allowed students
       - Shows if each student was present/absent in each lecture
       - Calculates total attendance percentage per student
       - Sorted by roll number
    
    2. Defaulters List (report_type='defaulters'):
       - Students with <75% attendance in subject
       - Shows present/absent counts
       - Highlights at-risk students for follow-up
    
    3. Security Audit Report (report_type='audit'):
       - GPS coordinates of each scan (geofencing validation)
       - IP addresses used (network subnet validation)
       - Device fingerprints (anti-proxy detection)
       - Timestamp precision (second-level accuracy)
       - Technical proof of anti-cheating measures
    
    Process:
    1. Validate teacher role
    2. Parse form data (dates, subject, report type)
    3. Query attendance records for date range + subject
    4. Group by student/session/report type
    5. Calculate statistics (percentages, counts)
    6. Generate ReportLab PDF document
    7. Stream to browser for download
    
    PDF Generation:
    - Uses ReportLab for table formatting
    - Includes header with metadata
    - Color-coded status badges (present=green, absent=red)
    - Professional styling (HexColor #1f4788 for headers)
    - Page breaks for large reports
    
    Returns:
    - PDF file as attachment (browser download)
    - Filename: BeQr_{type}_{subject}_{dates}.pdf
    """
    if request.user.role != 'teacher':
        messages.error(request, "Access denied.")
        return redirect('login')

    if request.method == 'POST':
        # 1. Get the data submitted from the Modal form
        subject = request.POST.get('subject')
        report_type = request.POST.get('report_type')
        start_date_str = request.POST.get('start_date')
        end_date_str = request.POST.get('end_date')

        # Convert string dates to date objects for proper filtering
        from datetime import datetime
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
        end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()

        # Normalize the subject - strip whitespace and handle case
        subject = subject.strip() if subject else ''

        # DEBUG: Check what sessions exist
        all_sessions_in_range = AttendanceSession.objects.filter(
            teacher=request.user,
            start_time__date__gte=start_date,
            start_time__date__lte=end_date
        )
        
        # Debug: Log the subject value and available subjects
        print(f"DEBUG: Searching for subject: '{subject}' (length: {len(subject)})")
        available_subjects = [s['subject'] for s in all_sessions_in_range.values('subject').distinct()]
        print(f"DEBUG: Available subjects for this teacher: {available_subjects}")
        print(f"DEBUG: Total sessions in date range (all subjects): {all_sessions_in_range.count()}")

        # 2. Fetch attendance records for this teacher's sessions in the date range
        # Query attendance records directly, filtered by teacher and date range
        attendances = Attendance.objects.filter(
            session__teacher=request.user,
            session__start_time__date__gte=start_date,
            session__start_time__date__lte=end_date,
            session__subject__iexact=subject
        ).order_by('session__start_time', 'student__roll_number')
        
        # Get the sessions from these attendances
        sessions = AttendanceSession.objects.filter(
            pk__in=attendances.values('session__pk').distinct()
        ).order_by('-start_time')
        
        print(f"DEBUG: Attendances found: {attendances.count()}")
        print(f"DEBUG: Sessions from attendances: {sessions.count()}")

        # 3. Setup PDF response
        response = HttpResponse(content_type='application/pdf')
        filename = f"BeQr_{report_type}_{subject}_{start_date_str}_to_{end_date_str}.pdf"
        response['Content-Disposition'] = f'attachment; filename="{filename}"'

        # Create PDF document
        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=letter, topMargin=0.5*inch, bottomMargin=0.5*inch)
        elements = []
        
        # Define styles
        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=18,
            textColor=colors.HexColor('#1f4788'),
            spaceAfter=12,
            alignment=TA_CENTER,
            fontName='Helvetica-Bold'
        )
        heading_style = ParagraphStyle(
            'CustomHeading',
            parent=styles['Heading2'],
            fontSize=12,
            textColor=colors.HexColor('#1f4788'),
            spaceAfter=10,
            fontName='Helvetica-Bold'
        )
        subheading_style = ParagraphStyle(
            'CustomSubHeading',
            parent=styles['Heading3'],
            fontSize=10,
            textColor=colors.HexColor('#1f4788'),
            spaceAfter=8,
            fontName='Helvetica-Bold'
        )
        normal_style = ParagraphStyle(
            'CustomNormal',
            parent=styles['Normal'],
            fontSize=9,
            spaceAfter=4
        )

        # Add title
        title = Paragraph("📊 BeQr Attendance System - Report", title_style)
        elements.append(title)
        
        # Add metadata
        metadata = Paragraph(
            f"<b>Subject:</b> {subject} | <b>Period:</b> {start_date_str} to {end_date_str} | <b>Teacher:</b> {request.user.first_name} {request.user.last_name}",
            normal_style
        )
        elements.append(metadata)
        elements.append(Spacer(1, 0.2*inch))
        
        # Add generation timestamp
        from datetime import datetime
        gen_time = Paragraph(
            f"<i>Generated on {datetime.now().strftime('%d-%b-%Y %I:%M %p')} | BeQr Attendance System</i>",
            ParagraphStyle('Meta', parent=styles['Normal'], fontSize=7, textColor=colors.grey, alignment=TA_CENTER)
        )
        elements.append(gen_time)
        elements.append(Spacer(1, 0.3*inch))

        # --- REPORT LOGIC A: Monthly Master List ---
        if report_type == 'master':
            elements.append(Paragraph("📋 Monthly Master Attendance Report", heading_style))
            elements.append(Spacer(1, 0.15*inch))
            
            # Summary Stats
            total_records = attendances.count()
            present_records = attendances.filter(status='present').count()
            absent_records = attendances.filter(status='absent').count()
            incomplete_records = attendances.filter(status='incomplete').count()
            sessions_count = sessions.count()
            
            summary_text = f"<b>Summary:</b> {sessions_count} sessions conducted | {total_records} total records | {present_records} Present | {absent_records} Absent | {incomplete_records} Incomplete"
            elements.append(Paragraph(summary_text, normal_style))
            elements.append(Spacer(1, 0.15*inch))
            
            if attendances.exists():
                data = [['Roll No', 'Student Name', 'Date', 'Topic', 'Status']]
                for att in attendances:
                    data.append([
                        str(att.student.roll_number),
                        f"{att.student.first_name} {att.student.last_name}",
                        att.session.start_time.strftime('%d-%b-%Y'),
                        att.session.topic or '-',
                        att.get_status_display()
                    ])
                
                table = Table(data, colWidths=[1*inch, 2*inch, 1.2*inch, 1.5*inch, 1*inch])
                table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1f4788')),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                    ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('FONTSIZE', (0, 0), (-1, 0), 10),
                    ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                    ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                    ('GRID', (0, 0), (-1, -1), 1, colors.black),
                    ('FONTSIZE', (0, 1), (-1, -1), 8),
                    ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.lightgrey]),
                ]))
                elements.append(table)
            else:
                msg = f"<b>⚠️ No attendance records found</b> for {subject} between {start_date_str} and {end_date_str}. Please check if sessions have been conducted."
                elements.append(Paragraph(msg, normal_style))

        # --- REPORT LOGIC B: 75% Defaulter List ---
        elif report_type == 'defaulters':
            elements.append(Paragraph("📌 Defaulter List (Attendance < 75%)", heading_style))
            elements.append(Spacer(1, 0.15*inch))
            
            total_classes = sessions.count()
            
            if total_classes > 0:
                elements.append(Paragraph(f"<b>Total Classes Conducted:</b> {total_classes}", subheading_style))
                elements.append(Spacer(1, 0.1*inch))
                
                # Get all students with enrollment
                students = CustomUser.objects.filter(role='student').order_by('roll_number')
                defaulters = []
                
                for student in students:
                    attended = Attendance.objects.filter(student=student, session__in=sessions, status='present').count()
                    percentage = (attended / total_classes) * 100 if total_classes > 0 else 0
                    if percentage < 75.0:
                        defaulters.append({
                            'roll': student.roll_number,
                            'name': f"{student.first_name} {student.last_name}",
                            'total': total_classes,
                            'attended': attended,
                            'absent': total_classes - attended,
                            'percentage': percentage
                        })
                
                if defaulters:
                    elements.append(Paragraph(f"<b>Total Defaulters Found:</b> {len(defaulters)} students", subheading_style))
                    elements.append(Spacer(1, 0.1*inch))
                    
                    data = [['Roll No', 'Student Name', 'Attended', 'Total', 'Percentage', 'Status']]
                    for d in defaulters:
                        status = "🔴 Critical" if d['percentage'] < 50 else "🟡 Warning"
                        data.append([
                            str(d['roll']),
                            d['name'],
                            str(d['attended']),
                            str(d['total']),
                            f"{d['percentage']:.1f}%",
                            status
                        ])
                    
                    table = Table(data, colWidths=[0.9*inch, 2*inch, 0.8*inch, 0.8*inch, 1*inch, 1.2*inch])
                    table.setStyle(TableStyle([
                        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#d32f2f')),
                        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                        ('FONTSIZE', (0, 0), (-1, 0), 10),
                        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                        ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#ffebee')),
                        ('GRID', (0, 0), (-1, -1), 1, colors.black),
                        ('FONTSIZE', (0, 1), (-1, -1), 8),
                        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#ffcdd2')]),
                    ]))
                    elements.append(table)
                else:
                    elements.append(Paragraph("✅ <b>No defaulters found!</b> All students have attendance ≥ 75%", normal_style))
            else:
                msg = f"<b>⚠️ No sessions found</b> for {subject} between {start_date_str} and {end_date_str}."
                elements.append(Paragraph(msg, normal_style))

        # --- REPORT LOGIC C: Security & Telemetry Audit ---
        elif report_type == 'audit':
            elements.append(Paragraph("🔒 Security & Telemetry Audit Report", heading_style))
            elements.append(Spacer(1, 0.15*inch))
            
            # Use the attendances we already filtered
            audit_attendances = attendances.order_by('-session__start_time', 'student__roll_number')
            
            if audit_attendances.exists():
                data = [['Roll No', 'Student', 'Date', 'Scanned IP', 'GPS Location', 'Device FP']]
                for att in audit_attendances:
                    scanned_ip = att.scanned_ip or 'N/A'
                    device_fp = att.device_fingerprint[:12] + '...' if att.device_fingerprint else 'N/A'
                    gps_loc = f"({att.latitude:.4f}, {att.longitude:.4f})" if att.latitude and att.longitude else 'N/A'
                    
                    data.append([
                        str(att.student.roll_number),
                        f"{att.student.first_name}",
                        att.time_in.strftime('%d-%b %I:%M %p') if att.time_in else 'N/A',
                        scanned_ip,
                        gps_loc,
                        device_fp
                    ])
                
                table = Table(data, colWidths=[0.8*inch, 1.2*inch, 1.2*inch, 1.3*inch, 1.5*inch, 1*inch])
                table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1565c0')),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                    ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('FONTSIZE', (0, 0), (-1, 0), 9),
                    ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                    ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#e3f2fd')),
                    ('GRID', (0, 0), (-1, -1), 1, colors.black),
                    ('FONTSIZE', (0, 1), (-1, -1), 7),
                    ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#bbdefb')]),
                ]))
                elements.append(table)
            else:
                msg = f"<b>⚠️ No telemetry records found</b> for {subject} between {start_date_str} and {end_date_str}."
                elements.append(Paragraph(msg, normal_style))

        # Build PDF
        doc.build(elements)
        buffer.seek(0)
        response.write(buffer.getvalue())
        buffer.close()
        return response
    
    return redirect('teacher_dashboard')



# ============================================================================
# STUDENT VIEWS - DASHBOARD, HISTORY & QR SCANNING
# ============================================================================
# Views for student attendance dashboard, history, and QR code scanning
# Includes attendance statistics (daily, monthly, overall) and QR scanner
# ============================================================================

@login_required
def student_dashboard_view(request):
    """
    Main student dashboard displaying attendance statistics and recent activity.
    
    Security: Requires @login_required and role='student'
    
    Features:
    1. Real-Time Attendance Status:
       - Overall stats (total sessions, present, absent, incomplete)
       - Daily statistics (today's attendance counters)
       - Monthly statistics (this month's performance)
       - Attendance percentage (overall, daily, monthly)
    
    2. Recent Activity:
       - Last 5 attendance records with timestamps
       - Status badges (present, absent, incomplete, pending)
    
    3. QR Scanner Link:
       - Opens student QR scanner interface
       - Used to scan teacher's QR codes
    
    Statistics Calculated:
    - Overall: All sessions user participated in
    - Daily: Sessions today (midnight to now)
    - Monthly: Sessions this month (1st to now)
    
    Context Variables:
    - student: Current user (student object)
    - total_sessions: Total attendance records
    - present_count: Sessions marked present
    - absent_count: Sessions marked absent
    - incomplete_count: Sessions with pending checkout
    - daily/monthly: Same stats broken down by time period
    - attendance_percentage: Calculated for each period
    """
    # 1. Security Check: Only Students allowed
    if request.user.role != 'student':
        messages.warning(request, "Access denied. You are not a student.")
        return redirect('teacher_dashboard')

    from datetime import datetime, timedelta
    from django.utils import timezone

    # 2. Fetch Real Data: Get the last 5 attendance records for this student
    recent_activity = Attendance.objects.filter(student=request.user).order_by('-time_in')[:5]

    # 3. Calculate OVERALL/TOTAL attendance statistics
    total_sessions = Attendance.objects.filter(student=request.user).count()
    present_count = Attendance.objects.filter(student=request.user, status='present').count()
    absent_count = Attendance.objects.filter(student=request.user, status='absent').count()
    incomplete_count = Attendance.objects.filter(student=request.user, status='incomplete').count()
    
    # Calculate overall percentage
    attendance_percentage = (present_count / total_sessions * 100) if total_sessions > 0 else 0

    # 4. Calculate DAILY statistics (today)
    # Using date range instead of __date filter to work correctly with timezone-aware datetimes
    now = timezone.now()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    today_end = today_start + timedelta(days=1)
    
    daily_attendance = Attendance.objects.filter(
        student=request.user, 
        time_in__gte=today_start,
        time_in__lt=today_end
    )
    daily_total = daily_attendance.count()
    daily_present = daily_attendance.filter(status='present').count()
    daily_absent = daily_attendance.filter(status='absent').count()
    daily_incomplete = daily_attendance.filter(status='incomplete').count()
    daily_percentage = (daily_present / daily_total * 100) if daily_total > 0 else 0

    # 5. Calculate MONTHLY statistics (this month)
    now = timezone.now()
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    monthly_attendance = Attendance.objects.filter(student=request.user, time_in__gte=month_start)
    monthly_total = monthly_attendance.count()
    monthly_present = monthly_attendance.filter(status='present').count()
    monthly_absent = monthly_attendance.filter(status='absent').count()
    monthly_incomplete = monthly_attendance.filter(status='incomplete').count()
    monthly_percentage = (monthly_present / monthly_total * 100) if monthly_total > 0 else 0

    context = {
        'student': request.user,
        'recent_attendance': recent_activity,
        'live_lecture': None,
        # Overall stats (kept for backward compatibility)
        'total_sessions': total_sessions,
        'present_count': present_count,
        'absent_count': absent_count,
        'incomplete_count': incomplete_count,
        'attendance_percentage': round(attendance_percentage, 2),
        # Daily stats
        'daily_total': daily_total,
        'daily_present': daily_present,
        'daily_absent': daily_absent,
        'daily_incomplete': daily_incomplete,
        'daily_percentage': round(daily_percentage, 2),
        # Monthly stats
        'monthly_total': monthly_total,
        'monthly_present': monthly_present,
        'monthly_absent': monthly_absent,
        'monthly_incomplete': monthly_incomplete,
        'monthly_percentage': round(monthly_percentage, 2),
    }
    
    return render(request, 'core/student/dashboard.html', context)


@login_required
def student_history_view(request):
    """
    Display complete attendance history for the student
    Grouped by month and day for better organization
    """
    if request.user.role != 'student':
        messages.warning(request, "Access denied. You are not a student.")
        return redirect('teacher_dashboard')

    # Fetch all attendance records sorted by date (newest first)
    all_attendance = Attendance.objects.filter(student=request.user).order_by('-time_in')

    # Group attendance by month and day
    from collections import OrderedDict
    from datetime import datetime
    
    grouped_attendance = {}  # month_year -> (sort_key, {day_date -> records})
    
    for record in all_attendance:
        if record.time_in:
            # Get month and year (e.g., "Mar 2026")
            month_year = record.time_in.strftime('%b %Y')
            month_sort_key = record.time_in.strftime('%Y-%m')  # For sorting: YYYY-MM
            
            # Get day (e.g., "18 Mar 2026")
            day_date = record.time_in.strftime('%d %b %Y')
            day_sort_key = record.time_in.strftime('%Y-%m-%d')  # For sorting: YYYY-MM-DD
            
            # Initialize month if not exists
            if month_year not in grouped_attendance:
                grouped_attendance[month_year] = {
                    'sort_key': month_sort_key,
                    'days': OrderedDict()
                }
            
            # Initialize day if not exists
            if day_date not in grouped_attendance[month_year]['days']:
                grouped_attendance[month_year]['days'][day_date] = {
                    'sort_key': day_sort_key,
                    'records': []
                }
            
            # Add record
            grouped_attendance[month_year]['days'][day_date]['records'].append(record)
    
    # Sort months (newest first) and sort days within each month (newest first)
    sorted_months = []
    for month_year in sorted(grouped_attendance.keys(), 
                             key=lambda x: grouped_attendance[x]['sort_key'], 
                             reverse=True):
        month_data = grouped_attendance[month_year]
        
        # Sort days within month (newest first)
        sorted_days = []
        for day_date in sorted(month_data['days'].keys(),
                              key=lambda x: month_data['days'][x]['sort_key'],
                              reverse=True):
            day_data = month_data['days'][day_date]
            sorted_days.append((day_date, day_data['records']))
        
        sorted_months.append((month_year, sorted_days))

    context = {
        'student': request.user,
        'all_attendance': all_attendance,
        'grouped_attendance': sorted_months,  # Month -> Day -> Records (sorted)
    }
    
    return render(request, 'core/student/history.html', context)


@login_required
def student_profile_view(request):
    """Display student profile and enrollment details"""
    if request.user.role != 'student':
        messages.warning(request, "Access denied. You are not a student.")
        return redirect('teacher_dashboard')

    context = {
        'student': request.user,
    }
    
    return render(request, 'core/student/profile.html', context)

import uuid # Make sure this is at the top of your file!

@login_required
def process_scan_view(request):
    """
    Process QR code scan with multi-layer security validation.
    
    SECURITY ARCHITECTURE - 4 VALIDATION LAYERS:
    
    Layer 1: Cryptographic & Time Validation
    - Verifies JWT signature using Django SECRET_KEY
    - Checks token expiry timestamp
    - If expired: Shows friendly error with teacher name
    - Prevents tampered/invalid tokens
    - Extracts session_id and scan_type from payload
    
    Layer 1B: Check-in Period Time Boundary (15-minute deadline)
    - Rejects check-in scans after 15 minutes since session start
    - Check-out scans allowed anytime (10-minute window)
    - Prevents late check-ins after deadline
    
    Layer 2: Geofencing Validation (GPS)
    - Compares student GPS coordinates to classroom anchor
    - Uses Haversine formula (geopy.geodesic)
    - 50-meter geofence threshold (prevents proxy scanning)
    - Fails if distance > 50m → "Geofence Failed" error
    
    Layer 3: Network Subnet Validation (IP)
    - Extracts student's IP address (handles proxies)
    - Compares to teacher's classroom Wi-Fi subnet (/24)
    - Prevents students from scanning from home
    - Allows localhost (127.0.0.1) for testing
    
    Layer 4: Device Fingerprinting (Anti-Buddy Punching)
    - Tracks device ID via secure cookie (beqr_device_id)
    - One device = one student per lecture
    - Detects if multiple students use same phone
    - Prevents "buddy punching" (friend marks you as present)
    
    POST Parameters:
    - qr_token: JWT token from QR code
    - latitude: Student's current GPS latitude
    - longitude: Student's current GPS longitude
    
    Process:
    1. Validate JWT token (Layer 1)
    2. Check time boundaries (Layer 1B)
    3. Verify GPS geofence (Layer 2)
    4. Validate IP subnet (Layer 3)
    5. Check device fingerprint (Layer 4)
    6. Record attendance (check-in or check-out)
    7. Set device ID cookie for future scans
    
    Returns:
    - Redirect to student_dashboard with success/error message
    
    Attendance States:
    - 'pending': Never scanned (created during session start)
    - 'incomplete': Checked in, awaiting checkout
    - 'present': Checked in AND checked out
    - 'absent': Never checked in (marked by teacher)
    """
    if request.user.role != 'student':
        return redirect('teacher_dashboard')

    if request.method == 'POST':
        qr_token = request.POST.get('qr_token')
        student_lat = request.POST.get('latitude')
        student_lon = request.POST.get('longitude')
        
        # --- LAYER 1: TIME & CRYPTOGRAPHY VALIDATION ---
        try:
            payload = jwt.decode(qr_token, settings.SECRET_KEY, algorithms=['HS256'])
            session_id = payload.get('session_id')
            scan_type = payload.get('type')
        except ExpiredSignatureError:
            # Decode without verification to get session_id and show faculty name
            try:
                unverified_payload = jwt.decode(qr_token, options={"verify_signature": False})
                session_id = unverified_payload.get('session_id')
                session = AttendanceSession.objects.filter(session_id=session_id).first()
                if session:
                    faculty_name = f"{session.teacher.first_name} {session.teacher.last_name}"
                    messages.error(request, f"QR Code has expired! Please contact Prof. {faculty_name}.")
                else:
                    messages.error(request, "QR Code has expired! Please ask the teacher to generate a new one.")
            except:
                messages.error(request, "QR Code has expired! Please ask the teacher to generate a new one.")
            return redirect('student_dashboard')
        except InvalidTokenError:
            messages.error(request, "Invalid or Tampered QR Code detected.")
            return redirect('student_dashboard')

        session = AttendanceSession.objects.filter(session_id=session_id, is_active=True).first()
        if not session:
            messages.error(request, "This class session has already been closed.")
            return redirect('student_dashboard')

        # --- LAYER 1B: CHECK-IN PERIOD TIME BOUNDARY (15 MINUTES) ---
        # Check-in only allowed within first 15 minutes of class start
        if scan_type == 'check_in':
            check_in_deadline = session.start_time + timedelta(minutes=15)
            if timezone.now() > check_in_deadline:
                faculty_name = f"{session.teacher.first_name} {session.teacher.last_name}"
                messages.error(request, f"Check-In Period Expired! The 15-minute check-in window ended. Please contact Prof. {faculty_name}.")
                return redirect('student_dashboard')

        # --- LAYER 2: LOCATION & GEOFENCING VALIDATION ---
        if not student_lat or not student_lon:
            messages.error(request, "GPS coordinates missing. Please allow location permissions.")
            return redirect('student_dashboard')

        if session.latitude and session.longitude:
            teacher_coords = (session.latitude, session.longitude)
            student_coords = (float(student_lat), float(student_lon))
            distance_meters = geodesic(teacher_coords, student_coords).meters
            
            if distance_meters > 50.0:
                messages.error(request, f"Geofence Failed: You are {int(distance_meters)} meters away from the classroom.")
                return redirect('student_dashboard')

        # --- LAYER 3: NETWORK SUBNET VALIDATION ---
        student_ip = get_client_ip(request)
        if session.anchor_ip and student_ip:
            try:
                teacher_network = ipaddress.IPv4Network(f"{session.anchor_ip}/24", strict=False)
                student_address = ipaddress.IPv4Address(student_ip)
                if student_address not in teacher_network and student_ip != '127.0.0.1':
                    messages.error(request, "Network Mismatch: Please connect to the College Wi-Fi to mark attendance.")
                    return redirect('student_dashboard')
            except ValueError:
                pass 

        # --- LAYER 4: DEVICE FINGERPRINTING (Anti-Buddy Punching) ---
        # Look for our secret cookie on the student's phone
        device_id = request.COOKIES.get('beqr_device_id')
        if not device_id:
            # If it's their first time, generate a unique ID for this phone
            device_id = str(uuid.uuid4())

        # Check if THIS specific phone has already been used by someone else in THIS specific lecture
        existing_scan = Attendance.objects.filter(
            session=session, 
            device_fingerprint=device_id
        ).exclude(student=request.user).first()
        
        if existing_scan:
            messages.error(request, "Security Alert: This device has already been used to mark attendance for another student in this class!")
            return redirect('student_dashboard')


        # --- FINAL PHASE: RECORD ATTENDANCE ---
        attendance_record, created = Attendance.objects.get_or_create(
            student=request.user,
            session=session,
            defaults={'lecture': Lecture.objects.filter(name=session.subject, teacher=session.teacher).first()}
        )

        if scan_type == 'check_in':
            if attendance_record.status != 'pending' and not created:
                messages.info(request, "You have already checked in to this class.")
            else:
                attendance_record.time_in = timezone.now()
                attendance_record.status = 'incomplete'
                attendance_record.scanned_ip = student_ip
                attendance_record.scanned_latitude = float(student_lat)
                attendance_record.scanned_longitude = float(student_lon)
                attendance_record.device_fingerprint = device_id # Save the fingerprint!
                attendance_record.save()
                messages.success(request, "Check-In Successful! Do not forget to scan the Check-Out QR at the end of class.")

        elif scan_type == 'check_out':
            if attendance_record.status == 'incomplete':
                attendance_record.time_out = timezone.now()
                attendance_record.status = 'present'
                attendance_record.save()
                messages.success(request, "Check-Out Successful! Your attendance is now marked as Present.")
            elif attendance_record.status == 'present':
                messages.info(request, "You have already completed the check-out process.")
            else:
                messages.error(request, "You cannot check out because you missed the initial Check-In scan.")

        # --- SET THE SECURE COOKIE ON THE PHONE ---
        response = redirect('student_dashboard')
        response.set_cookie(
            'beqr_device_id', 
            device_id, 
            max_age=31536000, # Cookie lasts for 1 year
            httponly=True,    # JavaScript cannot steal this cookie
            samesite='Lax'
        )
        return response

    return redirect('student_dashboard')



# ============================================================================
# API ENDPOINTS - AJAX & REST CALLS
# ============================================================================
# RESTful endpoints for JavaScript/frontend AJAX requests
# Returns JSON responses for dynamic UI updates (modal confirmation, etc)
# ============================================================================

def get_session_details(request, session_id):
    """
    AJAX API endpoint to fetch session details for QR confirmation modal.
    
    Called by: Student QR scanner confirmation dialog (client-side AJAX)
    
    Purpose:
    - Displays session metadata before student confirms scan
    - Shows teacher name, subject, topic, course, date/time
    - Confirms 'check-in' vs 'check-out' phase
    - Provides user-friendly confirmation before processing
    
    Query Parameters:
    - type: 'check_in' or 'check_out' (defaults to 'check_in')
    
    Returns:
    {
        'session_id': '{uuid}',
        'subject': 'JavaScript',
        'teacher_name': 'Prof. John Doe',
        'topic': 'Async/Await',
        'course_name': 'BCA Sem 6',
        'date_time': '18 Mar 2026, 10:30 AM',
        'scan_type': 'check_in',
        'scan_type_display': 'Starting Lecture'
    }
    
    Error Responses:
    - 404: Session not found
    - 500: Database or internal error
    """
    try:
        session = AttendanceSession.objects.get(session_id=session_id)
        # Format the date and time
        session_datetime = session.start_time.strftime('%d %b %Y, %I:%M %p')
        
        # Determine scan type from request param or default to check_in
        scan_type = request.GET.get('type', 'check_in')
        scan_type_display = 'Ending Lecture' if scan_type == 'check_out' else 'Starting Lecture'
        
        return JsonResponse({
            'session_id': session.session_id,
            'subject': session.subject or '-',
            'teacher_name': f"{session.teacher.first_name} {session.teacher.last_name}",
            'topic': session.topic or '-',
            'course_name': session.course_name or '-',
            'date_time': session_datetime,
            'scan_type': scan_type,
            'scan_type_display': scan_type_display,
        })
    except AttendanceSession.DoesNotExist:
        return JsonResponse({'error': 'Session not found'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
def update_attendance_status_view(request):
    """
    ============================================================
    ENDPOINT: Update Student Attendance Status (Manual Override)
    ============================================================
    
    URL: POST /api/update-attendance/
    Authentication: @login_required (teacher only)
    
    Purpose:
    - Allows teachers to manually override/update student attendance status
    - Supports changing status from any state to: present, absent, pending, incomplete
    - Used by the "Action" button on teacher dashboard
    - Logs manual changes for audit trails
    
    Request Body (JSON):
    {
        'attendance_id': {integer},      # Attendance record ID
        'status': 'present',             # New status: present|absent|pending|incomplete
        'notes': 'Optional reason'       # Optional notes for the change
    }
    
    Security:
    - Requires @login_required (user must be logged in)
    - Checks that requesting user is a teacher
    - Checks that attendance record exists
    - Only allows updating status values to valid choices
    
    Returns:
    Success (200):
    {
        'success': True,
        'message': 'Attendance updated successfully',
        'attendance_id': 123,
        'old_status': 'pending',
        'new_status': 'present',
        'updated_by': 'prof_vora'
    }
    
    Error (400):
    {
        'success': False,
        'error': 'Invalid status value|Attendance record not found|Only teachers can update attendance'
    }
    """
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Method not allowed'}, status=405)
    
    # Security: Check if user is a teacher
    if request.user.role != 'teacher':
        return JsonResponse({'success': False, 'error': 'Only teachers can update attendance'}, status=403)
    
    try:
        import json
        data = json.loads(request.body)
        attendance_id = data.get('attendance_id')
        new_status = data.get('status')
        notes = data.get('notes', '')
        
        # Validate status value
        valid_statuses = ['pending', 'present', 'absent', 'incomplete']
        if new_status not in valid_statuses:
            return JsonResponse({
                'success': False,
                'error': f'Invalid status. Must be one of: {", ".join(valid_statuses)}'
            }, status=400)
        
        # Get the attendance record
        try:
            attendance = Attendance.objects.get(id=attendance_id)
        except Attendance.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Attendance record not found'}, status=404)
        
        # Store old status for response
        old_status = attendance.status
        
        # Update the status
        attendance.status = new_status
        attendance.save()
        
        return JsonResponse({
            'success': True,
            'message': 'Attendance updated successfully',
            'attendance_id': attendance_id,
            'old_status': old_status,
            'new_status': new_status,
            'updated_by': request.user.username
        })
    
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Invalid JSON in request body'}, status=400)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


