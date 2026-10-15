"""Shared slot validation without changing the historical booking schema."""

from datetime import date, datetime, time

from django.utils import timezone

from .models import Appointment, Reservation


def parse_date(value):
    if not isinstance(value, str) or len(value) != 10:
        raise ValueError('Invalid date format')
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise ValueError('Invalid date format') from None


def available_slots(business, day, kind, option=None):
    interval = getattr(business, f'{kind}_interval')
    if not isinstance(interval, int) or isinstance(interval, bool) or interval <= 0:
        raise ValueError('Invalid booking interval')
    hours = business.business_hours.filter(day=day.weekday(), is_working_day=True).first()
    if hours is None:
        return []
    model = Reservation if kind == 'reservation' else Appointment
    bookings = model.objects.filter(business=business, date=day)
    if kind == 'reservation' and option:
        # The legacy unique constraint includes cancelled non-null options.
        # Until a reviewed migration changes it, do not advertise those rows
        # as bookable or destroy their history to bypass the constraint.
        bookings = bookings.filter(option=option)
    else:
        bookings = bookings.exclude(status='cancelled')
    occupied = {value if isinstance(value, str) else value.strftime('%H:%M')
                for value in bookings.values_list('time', flat=True)}
    start = hours.opening_time.hour * 60 + hours.opening_time.minute
    end = hours.closing_time.hour * 60 + hours.closing_time.minute
    now = timezone.localtime()
    slots = []
    for minute in range(start, end, interval):
        slot = time(minute // 60, minute % 60)
        timestamp = timezone.make_aware(datetime.combine(day, slot))
        label = slot.strftime('%H:%M')
        slots.append({'time': label, 'available': timestamp > now and label not in occupied})
    return slots


def validate_booking(business, date_value, time_value, kind, option=None):
    day = parse_date(date_value)
    if not isinstance(time_value, str) or len(time_value) != 5:
        raise ValueError('Invalid time format')
    try:
        parsed_time = time.fromisoformat(time_value)
    except ValueError:
        raise ValueError('Invalid time format') from None
    if parsed_time.strftime('%H:%M') != time_value:
        raise ValueError('Invalid time format')
    return day, any(slot['time'] == time_value and slot['available']
                    for slot in available_slots(business, day, kind, option))
