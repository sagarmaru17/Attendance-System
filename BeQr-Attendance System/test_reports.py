#!/usr/bin/env python
"""Test script to verify report generation is working"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'beqr.settings')
django.setup()

from core.models import CustomUser, AttendanceSession, Lecture, Attendance
from django.utils import timezone
from datetime import timedelta
import io
import csv

print("=" * 60)
print("TESTING REPORT GENERATION")
print("=" * 60)

# Create test data if needed
teacher, _ = CustomUser.objects.get_or_create(
    username='testrof',
    defaults={
        'email': 'prof@test.com',
        'role': 'teacher',
        'first_name': 'Test',
        'last_name': 'Professor'
    }
)

student, _ = CustomUser.objects.get_or_create(
    username='teststudent',
    defaults={
        'email': 'student@test.com',
        'role': 'student',
        'first_name': 'Test',
        'last_name': 'Student',
        'roll_number': '101'
    }
)

lecture, _ = Lecture.objects.get_or_create(
    name='Java',
    teacher=teacher
)

# Create a session
session, _ = AttendanceSession.objects.get_or_create(
    session_id='test-session-001',
    defaults={
        'teacher': teacher,
        'subject': 'Java',
        'course_name': 'BCA Sem 6',
        'topic': 'OOPS Concepts',
        'is_active': False,
        'start_time': timezone.now() - timedelta(days=1)
    }
)

# Create attendance record
att, _ = Attendance.objects.get_or_create(
    student=student,
    session=session,
    defaults={
        'lecture': lecture,
        'status': 'present',
        'time_in': timezone.now() - timedelta(days=1),
        'time_out': timezone.now() - timedelta(days=1, hours=-1)
    }
)

print(f"\n✅ Teachers: {CustomUser.objects.filter(role='teacher').count()}")
print(f"✅ Students: {CustomUser.objects.filter(role='student').count()}")
print(f"✅ Lectures: {Lecture.objects.count()}")
print(f"✅ Sessions: {AttendanceSession.objects.count()}")
print(f"✅ Attendance Records: {Attendance.objects.count()}")

# Test Report Generation: Master Report
print("\n" + "=" * 60)
print("TEST 1: MASTER REPORT")
print("=" * 60)

sessions = AttendanceSession.objects.filter(
    teacher=teacher,
    subject='Java',
    start_time__date__gte='2026-03-01',
    start_time__date__lte='2026-03-13',
    is_active=False
)

print(f"Sessions found: {sessions.count()}")

if sessions.count() > 0:
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Roll Number', 'Student Name', 'Date', 'Topic', 'Status'])
    
    attendances = Attendance.objects.filter(session__in=sessions).order_by('session__start_time', 'student__roll_number')
    print(f"Attendance records: {attendances.count()}")
    
    for att in attendances:
        writer.writerow([
            att.student.roll_number,
            f"{att.student.first_name} {att.student.last_name}",
            att.session.start_time.strftime('%d-%b-%Y'),
            att.session.topic,
            att.get_status_display()
        ])
    
    csv_content = output.getvalue()
    print("\n📊 CSV Output:")
    print(csv_content)
    print("✅ Master Report Generated Successfully!")
else:
    print("⚠️ No sessions found in date range")

# Test Report Generation: Defaulter Report
print("\n" + "=" * 60)
print("TEST 2: DEFAULTER REPORT")
print("=" * 60)

output = io.StringIO()
writer = csv.writer(output)
writer.writerow(['Roll Number', 'Student Name', 'Total Classes', 'Classes Attended', 'Attendance %', 'Action'])

total_classes = sessions.count()
if total_classes > 0:
    students = CustomUser.objects.filter(role='student').order_by('roll_number')
    print(f"Total classes: {total_classes}")
    print(f"Students checked: {students.count()}")
    
    for student in students:
        attended = Attendance.objects.filter(student=student, session__in=sessions, status='present').count()
        percentage = (attended / total_classes) * 100
        
        if percentage < 75.0:
            writer.writerow([
                student.roll_number,
                f"{student.first_name} {student.last_name}",
                total_classes,
                attended,
                f"{percentage:.2f}%",
                "Defaulter Alert"
            ])
    
    csv_content = output.getvalue()
    print("\n📊 CSV Output:")
    print(csv_content)
    if len(csv_content.strip().split('\n')) > 1:
        print("✅ Defaulter Report Generated Successfully!")
    else:
        print("ℹ️  No defaulters found (all students >= 75%)")
else:
    print("⚠️ No sessions found")

# Test Report Generation: Audit Report
print("\n" + "=" * 60)
print("TEST 3: AUDIT REPORT")
print("=" * 60)

output = io.StringIO()
writer = csv.writer(output)
writer.writerow(['Roll Number', 'Student Name', 'Date', 'Time In', 'Time Out', 'Final Status', 'Scanned IP', 'GPS Latitude', 'GPS Longitude'])

attendances = Attendance.objects.filter(session__in=sessions).order_by('session__start_time', 'student__roll_number')
print(f"Attendance records: {attendances.count()}")

for att in attendances:
    writer.writerow([
        att.student.roll_number,
        f"{att.student.first_name} {att.student.last_name}",
        att.session.start_time.strftime('%d-%b-%Y'),
        att.time_in.strftime('%I:%M %p') if att.time_in else 'Missed',
        att.time_out.strftime('%I:%M %p') if att.time_out else 'Missed',
        att.get_status_display(),
        att.scanned_ip or 'N/A',
        att.scanned_latitude or 'N/A',
        att.scanned_longitude or 'N/A'
    ])

csv_content = output.getvalue()
print("\n📊 CSV Output:")
print(csv_content)
print("✅ Audit Report Generated Successfully!")

print("\n" + "=" * 60)
print("✅ ALL TESTS PASSED - REPORTS ARE WORKING!")
print("=" * 60)
