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



# --- HELPER FUNCTION: Get Teacher's IP ---
def get_client_ip(request):
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip


# --- AUTHENTICATION VIEWS ---

def login_view(request):
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
    logout(request)
    messages.success(request, "You have been logged out.")
    return redirect('login')


def signup_view(request):
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



@login_required
def teacher_dashboard_view(request):
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
    lectures = Lecture.objects.filter(teacher=request.user)
    
    # Get unique subjects from past sessions
    past_session_subjects = AttendanceSession.objects.filter(
        teacher=request.user
    ).values_list('subject', flat=True).distinct()
    
    # Combine lecture names with past session subjects for dropdown
    all_subjects = set(list(lectures.values_list('name', flat=True)) + list(past_session_subjects))

    context = {
        'teacher': request.user,
        'lectures': lectures,
        'all_subjects': sorted(all_subjects),
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
def end_class_view(request):
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
    if request.user.role != 'teacher':
        messages.error(request, "Access denied.")
        return redirect('login')

    if request.method == 'POST':
        # 1. Get the data submitted from the Modal form
        subject = request.POST.get('subject')
        report_type = request.POST.get('report_type')
        start_date = request.POST.get('start_date')
        end_date = request.POST.get('end_date')

        # 2. Fetch all COMPLETED sessions for this teacher, subject, and date range
        sessions = AttendanceSession.objects.filter(
            teacher=request.user,
            subject=subject,
            start_time__date__gte=start_date,
            start_time__date__lte=end_date,
            is_active=False
        )

        # 3. Setup PDF response
        response = HttpResponse(content_type='application/pdf')
        filename = f"BeQr_{report_type}_{subject}_{start_date}_to_{end_date}.pdf"
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
            f"<b>Subject:</b> {subject} | <b>Period:</b> {start_date} to {end_date} | <b>Teacher:</b> {request.user.first_name} {request.user.last_name}",
            normal_style
        )
        elements.append(metadata)
        elements.append(Spacer(1, 0.3*inch))

        # --- REPORT LOGIC A: Monthly Master List ---
        if report_type == 'master':
            elements.append(Paragraph("Monthly Master Attendance Report", heading_style))
            
            attendances = Attendance.objects.filter(session__in=sessions).order_by('session__start_time', 'student__roll_number')
            
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
                    ('FONTSIZE', (0, 1), (-1, -1), 9),
                    ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.lightgrey]),
                ]))
                elements.append(table)
            else:
                elements.append(Paragraph("No attendance records found for this period.", normal_style))

        # --- REPORT LOGIC B: 75% Defaulter List ---
        elif report_type == 'defaulter':
            elements.append(Paragraph("Defaulter List (Attendance < 75%)", heading_style))
            
            total_classes = sessions.count()
            if total_classes > 0:
                students = CustomUser.objects.filter(role='student').order_by('roll_number')
                defaulters = []
                
                for student in students:
                    attended = Attendance.objects.filter(student=student, session__in=sessions, status='present').count()
                    percentage = (attended / total_classes) * 100
                    if percentage < 75.0:
                        defaulters.append({
                            'roll': student.roll_number,
                            'name': f"{student.first_name} {student.last_name}",
                            'total': total_classes,
                            'attended': attended,
                            'percentage': percentage
                        })
                
                if defaulters:
                    data = [['Roll No', 'Student Name', 'Total Classes', 'Attended', 'Percentage', 'Status']]
                    for d in defaulters:
                        data.append([
                            str(d['roll']),
                            d['name'],
                            str(d['total']),
                            str(d['attended']),
                            f"{d['percentage']:.1f}%",
                            "⚠️ Alert"
                        ])
                    
                    table = Table(data, colWidths=[1*inch, 2*inch, 1.2*inch, 0.9*inch, 1*inch, 0.9*inch])
                    table.setStyle(TableStyle([
                        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#d32f2f')),
                        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                        ('FONTSIZE', (0, 0), (-1, 0), 10),
                        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                        ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#ffebee')),
                        ('GRID', (0, 0), (-1, -1), 1, colors.black),
                        ('FONTSIZE', (0, 1), (-1, -1), 9),
                        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#ffcdd2')]),
                    ]))
                    elements.append(table)
                else:
                    elements.append(Paragraph("✓ No defaulters found! All students have attendance ≥ 75%", normal_style))
            else:
                elements.append(Paragraph("No completed sessions found in this date range.", normal_style))

        # --- REPORT LOGIC C: Security & Telemetry Audit ---
        elif report_type == 'audit':
            elements.append(Paragraph("Security & Telemetry Audit Report", heading_style))
            
            attendances = Attendance.objects.filter(session__in=sessions).order_by('session__start_time', 'student__roll_number')
            
            if attendances.exists():
                data = [['Roll No', 'Name', 'Date', 'Time In', 'Time Out', 'Status', 'IP Address', 'GPS']]
                for att in attendances:
                    gps = 'N/A'
                    if att.scanned_latitude and att.scanned_longitude:
                        gps = f"{att.scanned_latitude:.4f}, {att.scanned_longitude:.4f}"
                    
                    data.append([
                        str(att.student.roll_number),
                        f"{att.student.first_name} {att.student.last_name}"[:20],
                        att.session.start_time.strftime('%d-%b-%Y'),
                        att.time_in.strftime('%I:%M %p') if att.time_in else '-',
                        att.time_out.strftime('%I:%M %p') if att.time_out else '-',
                        att.get_status_display(),
                        att.scanned_ip or 'N/A',
                        gps
                    ])
                
                table = Table(data, colWidths=[0.8*inch, 1.5*inch, 1*inch, 0.85*inch, 0.85*inch, 0.8*inch, 1*inch, 1.4*inch])
                table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1976d2')),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                    ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('FONTSIZE', (0, 0), (-1, 0), 9),
                    ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
                    ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#e3f2fd')),
                    ('GRID', (0, 0), (-1, -1), 1, colors.black),
                    ('FONTSIZE', (0, 1), (-1, -1), 8),
                    ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f5f5f5')]),
                ]))
                elements.append(table)
            else:
                elements.append(Paragraph("No audit records found for this period.", normal_style))

        # Add footer
        elements.append(Spacer(1, 0.3*inch))
        footer_style = ParagraphStyle(
            'Footer',
            parent=styles['Normal'],
            fontSize=8,
            textColor=colors.grey,
            alignment=TA_CENTER
        )
        footer = Paragraph(
            f"Generated on {timezone.now().strftime('%d-%b-%Y %I:%M %p')} | BeQr Attendance System",
            footer_style
        )
        elements.append(footer)

        # Build PDF
        doc.build(elements)
        buffer.seek(0)
        response.write(buffer.getvalue())
        return response

    return redirect('teacher_dashboard')




# --- STUDENT VIEWS ---

@login_required
def student_dashboard_view(request):
    # 1. Security Check: Only Students allowed
    if request.user.role != 'student':
        messages.warning(request, "Access denied. You are not a student.")
        return redirect('teacher_dashboard')

    # 2. Fetch Real Data: Get the last 5 attendance records for this student
    recent_activity = Attendance.objects.filter(student=request.user).order_by('-time_in')[:5]

    context = {
        'student': request.user,
        'recent_attendance': recent_activity,
        'live_lecture': None, 
    }
    
    return render(request, 'core/student/dashboard.html', context)

import uuid # Make sure this is at the top of your file!

@login_required
def process_scan_view(request):
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


# --- API ENDPOINTS ---

def get_session_details(request, session_id):
    """API endpoint to fetch session details for the confirmation modal."""
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



# from django.http import HttpResponse
# from django.shortcuts import render, redirect
# from django.contrib.auth import authenticate, login, logout # For auth functions
# from django.contrib import messages # For flash messages
# from django.contrib.auth.forms import SetPasswordForm # Built-in form for password setting
# from django.contrib.auth.decorators import login_required # For protecting views
# from .forms import StudentRegistrationForm, PasswordResetVerificationForm # Import the new form
# from .models import Lecture, Attendance, CustomUser, AllowedStudent, AttendanceSession # Import models
# import uuid
# # Create your views here.
# # core/views.py

# # ... imports ...

# # CHANGE THE NAME HERE 👇
# def login_view(request):
#     if request.method == 'POST':
#         username = request.POST.get('username')
#         password = request.POST.get('password')

#         user = authenticate(request, username=username, password=password)

#         if user is not None:
#             # Now 'login' refers to the IMPORTED Django function, which is correct!
#             login(request, user) # Log the user in using the request and user objects.
                        
#             if user.role == 'teacher':
#                 return redirect('teacher_dashboard')
#             else:
#                 return redirect('student_dashboard')
#         else:
#             messages.error(request, "Invalid username or password.")

#     return render(request, 'core/login.html')

# def logout_view(request):
#     logout(request)
#     messages.success(request, "You have been logged out.")
#     return redirect('login')

# def signup_view(request):
#     if request.method == 'POST':
#         form = StudentRegistrationForm(request.POST)
#         if form.is_valid():
#             user = form.save(commit=False)
#             user.role = 'student'  # Automatically set role to Student
#             user.save()
#             messages.success(request, "Account created successfully! Please login.")
#             return redirect('login')
#         else:
#             messages.error(request, "Registration failed. Please correct the errors below.")
#     else:
#         form = StudentRegistrationForm()

#     return render(request, 'core/signup.html', {'form': form})

# # 1. VERIFY USER DETAILS
# def forgot_password_view(request):
#     if request.method == 'POST':
#         form = PasswordResetVerificationForm(request.POST)
#         if form.is_valid():
#             # Get the user found by the form
#             user = form.user_cache
            
#             # Store the user's ID in the session securely
#             request.session['reset_user_id'] = user.id
            
#             return redirect('reset_password_confirm')
#     else:
#         form = PasswordResetVerificationForm()

#     return render(request, 'core/forgot_password.html', {'form': form})


# # 2. SET NEW PASSWORD
# def reset_password_confirm_view(request):
#     # Security Check: Do we have a verified user in the session?
#     user_id = request.session.get('reset_user_id')
    
#     if not user_id:
#         messages.error(request, "Session expired or invalid. Please verify your details again.")
#         return redirect('forgot_password')

#     try:
#         user = CustomUser.objects.get(id=user_id)
#     except CustomUser.DoesNotExist:
#         return redirect('forgot_password')

#     if request.method == 'POST':
#         # Use Django's built-in SetPasswordForm (handles encryption & validation)
#         form = SetPasswordForm(user, request.POST)
#         if form.is_valid():
#             form.save()
            
#             # Clear the session so they can't reset it again
#             del request.session['reset_user_id']
            
#             messages.success(request, "Password changed successfully! Please login.")
#             return redirect('login')
#     else:
#         form = SetPasswordForm(user)

#     return render(request, 'core/reset_password_form.html', {'form': form})


# @login_required
# def teacher_dashboard_view(request):
#     if request.user.role != 'teacher':
#         messages.warning(request, "Access denied. Restricted to faculty.")
#         return redirect('student_dashboard')

#     # 1. Fetch Teacher's Lectures
#     my_lectures = Lecture.objects.filter(teacher=request.user).order_by('-created_at')
    
#     # 2. Fetch Student Stats
#     # Count how many students have actually signed up
#     registered_count = CustomUser.objects.filter(role='student').count()
#     # Count how many are in the Master List
#     total_allowed = AllowedStudent.objects.count()
    
#     # 3. Fetch the actual list (for the popup)
#     allowed_students_list = AllowedStudent.objects.all().order_by('enrollment_number')

#     # 4. Check if there is already an ACTIVE session for this teacher
#     active_session = AttendanceSession.objects.filter(teacher=request.user, is_active=True).first()

#     context = {
#         'teacher': request.user,
#         'lectures': my_lectures,
#         'registered_count': registered_count-1,  # Exclude admin/test accounts if needed
#         'total_allowed': total_allowed,
#         'allowed_students': allowed_students_list, # Passing the list to template
#         'active_session': active_session, # Pass the session if it exists
#     }
    
#     return render(request, 'core/teacher/dashboard.html', context)



# @login_required
# def start_class_view(request):
#     if request.method == 'POST':
#         # Get data from the form (we will add this form to HTML next)
#         subject = request.POST.get('subject')
#         course = request.POST.get('course')
        
#         # Create the session
#         session = AttendanceSession.objects.create(
#             teacher=request.user,
#             subject=subject,
#             course_name=course,
#             session_id=str(uuid.uuid4()) # Unique ID for the QR code
#         )
#         return redirect('teacher_dashboard')
    
#     return redirect('teacher_dashboard')

# @login_required
# def end_class_view(request):
#     # Find the active session and close it
#     session = AttendanceSession.objects.filter(teacher=request.user, is_active=True).first()
#     if session:
#         session.is_active = False
#         session.end_time = timezone.now()
#         session.save()
#     return redirect('teacher_dashboard')



# @login_required
# def student_dashboard_view(request):
#     # 1. Security Check: Only Students allowed
#     if request.user.role != 'student':
#         messages.warning(request, "Access denied. You are not a student.")
#         return redirect('teacher_dashboard')

#     # 2. Fetch Real Data: Get the last 5 attendance records for this student
#     recent_activity = Attendance.objects.filter(student=request.user).order_by('-time_in')[:5]

#     context = {
#         'student': request.user,
#         'recent_attendance': recent_activity,
#         'live_lecture': None, # We will activate this later when building the 'Start Class' feature
#     }
    
#     return render(request, 'core/student/dashboard.html', context)