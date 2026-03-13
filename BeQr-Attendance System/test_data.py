#!/usr/bin/env python
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'beqr.settings')
django.setup()

from core.models import CustomUser, AttendanceSession, Lecture, Attendance
from django.utils import timezone

# Check database
sessions = AttendanceSession.objects.all().count()
attendances = Attendance.objects.all().count()
teachers = CustomUser.objects.filter(role='teacher').count()
students = CustomUser.objects.filter(role='student').count()
lectures = Lecture.objects.all().count()

print(f"✅ Teachers: {teachers}")
print(f"✅ Students: {students}")
print(f"✅ Lectures: {lectures}")
print(f"✅ Sessions: {sessions}")
print(f"✅ Attendance Records: {attendances}")

if sessions > 0:
    print("\n📊 Session Details:")
    for session in AttendanceSession.objects.all()[:3]:
        print(f"  - {session.subject} ({session.teacher.username})")
        att_count = Attendance.objects.filter(session=session).count()
        print(f"    Attendances: {att_count}")
else:
    print("\n⚠️ No sessions found. Create a session first via teacher dashboard.")

if lectures > 0:
    print("\n📚 Lectures Available:")
    for lecture in Lecture.objects.all()[:5]:
        print(f"  - {lecture.name} by {lecture.teacher.username}")
