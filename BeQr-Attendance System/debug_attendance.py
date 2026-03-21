#!/usr/bin/env python
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'beqr.settings')
django.setup()

from core.models import Attendance
from django.utils import timezone
from django.conf import settings
from datetime import datetime

print("=" * 60)
print("TIMEZONE DEBUG INFORMATION")
print("=" * 60)
print(f"Django TIME_ZONE setting: {settings.TIME_ZONE}")
print(f"Django USE_TZ: {settings.USE_TZ}")
print()

now = timezone.now()
today = now.date()
today_str = str(today)

print(f"Current timezone.now(): {now}")
print(f"Current date (from timezone.now()): {today}")
print()

print("=" * 60)
print("ATTENDANCE RECORDS IN DATABASE")
print("=" * 60)

all_records = Attendance.objects.all()
print(f"Total records: {all_records.count()}\n")

print("Last 8 records:")
for i, record in enumerate(all_records.order_by('-time_in')[:8], 1):
    if record.time_in:
        record_date = record.time_in.date()
        match = "✓ TODAY" if record_date == today else f"  {record_date}"
        print(f"{i}. {record.student.username:15} | {record.time_in} | Status: {record.status:10} | {match}")
    else:
        print(f"{i}. {record.student.username:15} | No time_in | Status: {record.status:10}")

print()
print("=" * 60)
print("FILTER TESTING")
print("=" * 60)

# Test 1: Using __date filter
result1 = Attendance.objects.filter(time_in__date=today).count()
print(f"1. Using filter(time_in__date={today}): {result1} records")

# Test 2: Using __date with string
result2 = Attendance.objects.filter(time_in__date=today_str).count()
print(f"2. Using filter(time_in__date='{today_str}'): {result2} records")

# Test 3: Using date range with timezone-aware datetimes
start = timezone.make_aware(datetime(2026, 3, 13, 0, 0, 0))
end = timezone.make_aware(datetime(2026, 3, 14, 0, 0, 0))
result3 = Attendance.objects.filter(time_in__gte=start, time_in__lt=end).count()
print(f"3. Using filter(time_in__gte={start}, time_in__lt={end}): {result3} records")

# Test 4: Check student filter
from django.contrib.auth import get_user_model
User = get_user_model()
test_student = User.objects.filter(username='sagar').first()
if test_student:
    result4 = Attendance.objects.filter(student=test_student, time_in__date=today).count()
    print(f"4. For user 'sagar', using filter(time_in__date={today}): {result4} records")
