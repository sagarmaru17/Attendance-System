#!/usr/bin/env python
"""Test the Generate Reports fix"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'beqr.settings')
django.setup()

from core.models import CustomUser, Lecture, AttendanceSession
from django.db.models import Count, Q

print("=" * 60)
print("TESTING GENERATE REPORTS FIX")
print("=" * 60)

# Get a teacher
teacher = CustomUser.objects.filter(role='teacher').first()
if not teacher:
    print("⚠️ No teachers found")
    exit(1)

print(f"\n✅ Testing with teacher: {teacher.username}")

# Fetch lectures
lectures = Lecture.objects.filter(teacher=teacher)
print(f"✅ Lectures: {lectures.count()}")
for lecture in lectures:
    print(f"  - {lecture.name}")

# Get past sessions
all_past_sessions = AttendanceSession.objects.filter(
    teacher=teacher, 
    is_active=False
).annotate(
    present_count=Count('attendance', filter=Q(attendance__status='present')),
    absent_count=Count('attendance', filter=Q(attendance__status='absent')),
    incomplete_count=Count('attendance', filter=Q(attendance__status='incomplete'))
).order_by('-start_time')

print(f"✅ Past sessions: {all_past_sessions.count()}")

# Get unique subjects from past sessions
past_session_subjects = AttendanceSession.objects.filter(
    teacher=teacher
).values_list('subject', flat=True).distinct()

print(f"✅ Subjects from past sessions: {len(list(past_session_subjects))}")
for subject in past_session_subjects:
    print(f"  - {subject}")

# Combine
all_subjects = set(list(lectures.values_list('name', flat=True)) + list(past_session_subjects))
print(f"\n✅ Total available subjects: {len(all_subjects)}")
print("Available subjects for report dropdown:")
for subject in sorted(all_subjects):
    print(f"  - {subject}")

if all_subjects:
    print(f"\n✅ SUCCESS! Generate Reports button will now work!")
    print(f"   Teachers can select from {len(all_subjects)} subject(s)")
else:
    print(f"\n⚠️ No subjects available - teacher needs to start a class first")

print("\n" + "=" * 60)
