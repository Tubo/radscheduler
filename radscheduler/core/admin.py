from django.contrib import admin

# Register your models here.
"""
Shift list view (admin):
- Day of shift
- Weekday of shift
- Type of shift
- Registrar covering
- Default filter out shifts older than 2 weeks
- Default show 50-100 entries
- Default only show usual leave types
- Filter by date range
- Unfilled shifts

Shift list view (user):
- Extra duties

Leave list view:
- Day start, finish, return
- Type of leave
- Approval status (me, Chris, DOT)
- Active or not (calculated by finish date)

Leave form details view:
- Generate PDF
- Hide special types

Custom actions
- Swap shifts
"""
