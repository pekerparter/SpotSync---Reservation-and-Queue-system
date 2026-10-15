from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from threading import Barrier
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.db import connections
from django.test import Client, TestCase, TransactionTestCase, skipUnlessDBFeature
from django.urls import reverse
from django.utils import timezone

from .models import Appointment, Business, BusinessRolePermission, Queue, Reservation

User = get_user_model()


def future_monday():
    today = timezone.localdate()
    return today + timedelta(days=(7 - today.weekday()) % 7 + 7)


class BookingRegressionTests(TestCase):
    def setUp(self):
        self.business = Business.objects.create(name='Booking', address='Test', phone_number='000',
                                                enable_time_estimation=True, time_per_customer=5)
        self.user = User.objects.create_user(username='customer')
        self.other = User.objects.create_user(username='other')
        self.client.force_login(self.user)
        self.day = future_monday()

    def test_same_day_mixed_booking_times_render_and_select_nearest(self):
        reservation = Reservation.objects.create(business=self.business, user=self.user, date=self.day, time='10:00')
        appointment = Appointment.objects.create(business=self.business, user=self.user, date=self.day, time='11:00')
        response = self.client.get(reverse('landing_page'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['upcoming_booking'], reservation)
        appointment.time = '09:00'
        appointment.save()
        self.assertEqual(self.client.get(reverse('landing_page')).context['upcoming_booking'].pk, appointment.pk)
        self.assertIsInstance(self.client.get(reverse('landing_page')).context['upcoming_booking'], Appointment)

    def test_invalid_dates_and_legacy_intervals_return_bounded_errors(self):
        for name, interval in (('get_available_reservation_slots', 'reservation_interval'),
                               ('get_available_appointment_slots', 'appointment_interval')):
            url = reverse(name, args=[self.business.pk])
            for data in ({}, {'date': 'invalid'}, {'date': '2030-02-31'}):
                with self.subTest(name=name, data=data):
                    self.assertEqual(self.client.get(url, data).status_code, 400)
            for value in (0, -1, None):
                Business.objects.filter(pk=self.business.pk).update(**{interval: value})
                self.assertEqual(self.client.get(url, {'date': self.day.isoformat()}).status_code, 400)

    def test_booking_creation_rejects_past_closed_off_grid_and_invalid_inputs(self):
        for name in ('make_reservation', 'book_appointment'):
            url = reverse(name, args=[self.business.pk])
            for data in ({}, {'date': self.day.isoformat(), 'time': 'invalid'}):
                self.assertEqual(self.client.post(url, data).status_code, 400)
            for day, time in ((self.day, '03:00'), (self.day, '09:07'),
                              (self.day + timedelta(days=5), '10:00'), (self.day - timedelta(days=21), '10:00')):
                response = self.client.post(url, {'date': day.isoformat(), 'time': time})
                self.assertFalse(response.json()['success'])
        self.assertEqual(Appointment.objects.count(), 0)
        self.assertEqual(Reservation.objects.count(), 0)

    def test_configured_options_and_reasons_cannot_be_bypassed(self):
        self.business.reservation_options = ['Court A']
        self.business.appointment_reasons = ['Consultation']
        self.business.save()
        for name, field in (('make_reservation', 'option'), ('book_appointment', 'reason')):
            response = self.client.post(reverse(name, args=[self.business.pk]),
                                        {'date': self.day.isoformat(), 'time': '10:00', field: 'arbitrary'})
            self.assertEqual(response.status_code, 400)

    def test_cancelled_reservation_constraint_is_honestly_reflected_without_losing_history(self):
        self.business.reservation_options = ['Court A']
        self.business.save()
        old = Reservation.objects.create(business=self.business, user=self.other, date=self.day,
                                          time='10:00', option='Court A', status='cancelled')
        response = self.client.get(reverse('get_available_reservation_slots', args=[self.business.pk]),
                                   {'date': self.day.isoformat(), 'option': 'Court A'})
        self.assertFalse(next(s for s in response.json()['slots'] if s['time'] == '10:00')['available'])
        self.assertFalse(self.client.post(reverse('make_reservation', args=[self.business.pk]),
                                         {'date': self.day.isoformat(), 'time': '10:00', 'option': 'Court A'}).json()['success'])
        old.refresh_from_db()
        self.assertEqual(old.user_id, self.other.pk)
        self.assertEqual(old.status, 'cancelled')

    def test_queue_removal_is_post_only_and_updates_estimates_and_positions(self):
        first = Queue.objects.create(business=self.business, user=self.user)
        second = Queue.objects.create(business=self.business, user=self.other)
        url = reverse('remove_from_queue', args=[self.business.pk])
        self.assertEqual(self.client.get(url).status_code, 405)
        first.refresh_from_db()
        self.assertEqual(first.status, 'in_queue')
        self.assertEqual(self.client.post(url).json()['status'], 'success')
        second.refresh_from_db()
        self.business.refresh_from_db()
        self.assertEqual((second.position, second.estimated_wait_time), (1, 5))
        self.assertEqual((self.business.people_in_queue, self.business.estimated_wait_time), (1, 5))

    def test_direct_queue_replacement_delete_and_reactivation_remain_consistent(self):
        first = Queue.objects.create(business=self.business, user=self.user)
        second = Queue.objects.create(business=self.business, user=self.other)
        replacement = Queue.objects.create(business=self.business, user=self.user)
        first.refresh_from_db()
        second.refresh_from_db()
        self.assertEqual(first.status, 'cancelled')
        self.assertEqual((second.position, replacement.position), (1, 2))
        second.delete()
        replacement.refresh_from_db()
        self.assertEqual((replacement.position, replacement.estimated_wait_time), (1, 5))
        first.status = 'in_queue'
        first.save(update_fields=['status'])
        replacement.refresh_from_db()
        self.business.refresh_from_db()
        self.assertEqual(replacement.status, 'cancelled')
        self.assertEqual((self.business.people_in_queue, self.business.estimated_wait_time), (1, 5))

    def test_queue_join_returns_saved_position_when_legacy_positions_have_gaps(self):
        queued = Queue.objects.create(business=self.business, user=self.other)
        Queue.objects.filter(pk=queued.pk).update(position=9)
        now = timezone.make_aware(datetime.combine(self.day, datetime.min.time()).replace(hour=10))
        with patch('accounts.views.timezone.localtime', return_value=now):
            response = self.client.post(reverse('add_to_queue', args=[self.business.pk])).json()
        saved = Queue.objects.get(user=self.user, status='in_queue')
        self.assertEqual(response['position'], saved.position)
        self.assertEqual(saved.position, 2)

    def test_invalid_service_configuration_rolls_back_before_any_changes(self):
        self.user.business, self.user.staff_role = self.business, 'OWNER'
        self.user.save()
        BusinessRolePermission.objects.create(business=self.business, role='OWNER', can_edit_service=True)
        for data in ({'reservation_interval': '0'}, {'appointment_interval': '-1'},
                     {'reservation_options': '{}'}, {'opening_time_0': 'invalid'},
                     {'time_per_customer': '-3'}):
            response = self.client.post(reverse('edit_service', args=[self.business.pk]), data)
            self.assertEqual(response.status_code, 400)
            self.business.refresh_from_db()
            self.assertEqual(self.business.reservation_interval, 60)
            self.assertEqual(self.business.business_hours.count(), 7)

    def test_staff_cannot_reactivate_appointment_over_an_active_booking(self):
        self.user.business, self.user.staff_role = self.business, 'OWNER'
        self.user.save()
        BusinessRolePermission.objects.create(business=self.business, role='OWNER', can_display_customers=True)
        old = Appointment.objects.create(business=self.business, user=self.user, date=self.day, time='10:00', status='cancelled')
        Appointment.objects.create(business=self.business, user=self.other, date=self.day, time='10:00')
        response = self.client.post(reverse('update_booking_status', args=['appointment', old.pk]), {'status': 'booked'})
        self.assertFalse(response.json()['success'])
        old.refresh_from_db()
        self.assertEqual(old.status, 'cancelled')

    def test_service_estimate_changes_refresh_existing_queue_entries(self):
        self.user.business, self.user.staff_role = self.business, 'OWNER'
        self.user.save()
        BusinessRolePermission.objects.create(business=self.business, role='OWNER', can_edit_service=True)
        queued = Queue.objects.create(business=self.business, user=self.other)
        response = self.client.post(reverse('edit_service', args=[self.business.pk]), {
            'reservation_interval': '60', 'appointment_interval': '30',
            'enable_time_estimation': 'on', 'time_per_customer': '7',
        }, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertTrue(response.json()['success'])
        queued.refresh_from_db()
        self.business.refresh_from_db()
        self.assertEqual(queued.estimated_wait_time, 7)
        self.assertEqual(self.business.estimated_wait_time, 7)


@skipUnlessDBFeature('has_select_for_update')
class ConcurrentBookingTests(TransactionTestCase):
    """Real independent connections exercise PostgreSQL locking, not mocked locks."""

    def setUp(self):
        self.business = Business.objects.create(name='Concurrent', address='Test', phone_number='000')
        self.users = [User.objects.create_user(username=f'customer-{i}') for i in range(2)]
        self.day = future_monday()

    def simultaneous_posts(self, name, data, same_user=False):
        barrier = Barrier(2, timeout=10)
        def submit(index):
            try:
                client = Client()
                client.force_login(User.objects.get(pk=self.users[0 if same_user else index].pk))
                barrier.wait()
                response = client.post(reverse(name, args=[self.business.pk]), data)
                self.assertEqual(response.status_code, 200)
                return response.json()
            finally:
                connections.close_all()
        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [executor.submit(submit, i) for i in range(2)]
            return [future.result(timeout=20) for future in futures]

    def test_concurrent_appointments_only_book_once(self):
        results = self.simultaneous_posts('book_appointment', {'date': self.day.isoformat(), 'time': '10:00'})
        self.assertEqual(sum(r['success'] for r in results), 1)
        self.assertEqual(Appointment.objects.count(), 1)

    def test_concurrent_null_option_reservations_only_book_once(self):
        results = self.simultaneous_posts('make_reservation', {'date': self.day.isoformat(), 'time': '10:00'})
        self.assertEqual(sum(r['success'] for r in results), 1)
        self.assertEqual(Reservation.objects.count(), 1)

    def test_concurrent_queue_entries_have_distinct_positions(self):
        now = timezone.make_aware(datetime.combine(self.day, datetime.min.time()).replace(hour=10))
        with patch('accounts.views.timezone.localtime', return_value=now):
            results = self.simultaneous_posts('add_to_queue', {})
        self.assertTrue(all(r['status'] == 'success' for r in results))
        self.assertEqual(list(Queue.objects.order_by('position').values_list('position', flat=True)), [1, 2])
        self.business.refresh_from_db()
        self.assertEqual(self.business.people_in_queue, 2)

    def test_concurrent_same_user_joins_only_create_one_entry(self):
        now = timezone.make_aware(datetime.combine(self.day, datetime.min.time()).replace(hour=10))
        with patch('accounts.views.timezone.localtime', return_value=now):
            results = self.simultaneous_posts('add_to_queue', {}, same_user=True)
        self.assertEqual(sum(r['status'] == 'success' for r in results), 1)
        self.assertEqual(Queue.objects.filter(status='in_queue').count(), 1)
