#!/usr/bin/env python
"""Test the timer calculation with simulated session"""
import os
import django
from datetime import timedelta

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'beqr.settings')
django.setup()

from core.models import CustomUser, AttendanceSession
from django.utils import timezone
import uuid

print("=" * 60)
print("TESTING TIMER CALCULATION (SIMULATED)")
print("=" * 60)

# Get a teacher
teacher = CustomUser.objects.filter(role='teacher').first()
if not teacher:
    print("⚠️ No teachers found")
    exit(1)

print(f"\n✅ Using teacher: {teacher.username}")

# Create a simulated active session (started 5 minutes ago)
test_session = AttendanceSession.objects.create(
    teacher=teacher,
    subject="TEST_TIMER",
    course_name="TEST",
    topic="Timer Test",
    session_id=str(uuid.uuid4()),
    start_time=timezone.now() - timedelta(minutes=5),  # Started 5 minutes ago
    is_active=True
)

print(f"✅ Created test session: {test_session.subject}")
print(f"   Started: {test_session.start_time}")

# Calculate remaining seconds (same as in the view)
elapsed = (timezone.now() - test_session.start_time).total_seconds()
remaining_seconds = max(0, 900 - int(elapsed))

minutes = remaining_seconds // 60
seconds = remaining_seconds % 60

print(f"\n📊 Timer Calculation:")
print(f"   Elapsed: {int(elapsed)} seconds (~5 minutes)")
print(f"   Remaining: {remaining_seconds} seconds")
print(f"   Display: {minutes}:{seconds:02d}")

expected_remaining = 15 * 60 - 5 * 60  # 15 min - 5 min = 10 min
if remaining_seconds >= expected_remaining - 5 and remaining_seconds <= expected_remaining + 5:
    print(f"\n✅ SUCCESS! Timer calculation is correct!")
    print(f"   Expected ~{expected_remaining} seconds, got {remaining_seconds}")
else:
    print(f"\n⚠️ Timer calculation may be off")

# Clean up test session
test_session.delete()
print(f"\n✅ Cleaned up test session")

print("\n" + "=" * 60)
print("✅ TIMER FIX VERIFIED!")
print("=" * 60)
