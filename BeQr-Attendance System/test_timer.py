#!/usr/bin/env python
"""Test the timer calculation fix"""
import os
import django
from datetime import timedelta

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'beqr.settings')
django.setup()

from core.models import CustomUser, AttendanceSession
from django.utils import timezone

print("=" * 60)
print("TESTING TIMER CALCULATION")
print("=" * 60)

# Get a teacher
teacher = CustomUser.objects.filter(role='teacher').first()
if not teacher:
    print("⚠️ No teachers found")
    exit(1)

# Get active session
active_session = AttendanceSession.objects.filter(teacher=teacher, is_active=True).first()

if active_session:
    print(f"\n✅ Active session found: {active_session.subject}")
    
    # Calculate remaining seconds (same as in the view)
    elapsed = (timezone.now() - active_session.start_time).total_seconds()
    remaining_seconds = max(0, 900 - int(elapsed))
    
    minutes = remaining_seconds // 60
    seconds = remaining_seconds % 60
    
    print(f"✅ Session started: {active_session.start_time}")
    print(f"✅ Elapsed: {int(elapsed)} seconds")
    print(f"✅ Remaining: {remaining_seconds} seconds")
    print(f"✅ Timer display: {minutes}:{seconds:02d}")
    
    if remaining_seconds > 0:
        print(f"\n✅ SUCCESS! Timer will show: Expires in {minutes}:{seconds:02d}")
    else:
        print(f"\n⚠️ Token has expired (remaining: {remaining_seconds}s)")
else:
    print("\n⚠️ No active session found. Start a class to test timer.")

print("\n" + "=" * 60)
