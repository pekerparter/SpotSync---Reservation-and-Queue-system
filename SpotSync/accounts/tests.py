"""Regression coverage for the existing routes and customer/staff workflows."""

import secrets
from datetime import datetime, timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase
from django.urls import resolve, reverse
from django.utils import timezone

from . import views
from .models import (
    Appointment,
    Business,
    BusinessRolePermission,
    Category,
    Queue,
    Reservation,
)


class AccountTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.password = secrets.token_urlsafe(24)
        cls.user = get_user_model().objects.create_user(
            username='customer', email='customer@example.invalid', password=cls.password,
        )

    def test_public_pages_and_protected_redirects(self):
        self.assertRedirects(self.client.get('/'), reverse('custom_login'))
        for name in ('custom_login', 'register', 'password_reset'):
            with self.subTest(name=name):
                self.assertEqual(self.client.get(reverse(name)).status_code, 200)
        for name in ('landing_page', 'profile', 'my_reservations', 'categories'):
            with self.subTest(name=name):
                response = self.client.get(reverse(name))
                self.assertEqual(response.status_code, 302)
                self.assertTrue(response.url.startswith(reverse('custom_login')))

    def test_email_login_and_logout(self):
        response = self.client.post(reverse('custom_login'), {
            'username': self.user.email, 'password': self.password,
        })
        self.assertRedirects(response, reverse('landing_page'))
        self.assertEqual(int(self.client.session['_auth_user_id']), self.user.pk)
        self.client.post(reverse('custom_logout'))
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_registration_hashes_password_and_rejects_duplicate_email(self):
        password = secrets.token_urlsafe(24)
        data = {
            'first_name': 'New', 'last_name': 'Customer',
            'email': 'new@example.invalid', 'phone_number': '000',
            'password1': password, 'password2': password,
        }
        self.assertRedirects(self.client.post(reverse('register'), data), reverse('custom_login'))
        user = get_user_model().objects.get(email=data['email'])
        self.assertTrue(user.check_password(password))
        self.assertEqual(user.staff_role, 'CUSTOMER')
        self.assertContains(self.client.post(reverse('register'), data), 'Email is already in use.')
        self.assertEqual(get_user_model().objects.filter(email=data['email']).count(), 1)

    def test_profile_update(self):
        self.client.force_login(self.user)
        response = self.client.post(reverse('profile'), {
            'first_name': 'Updated', 'last_name': 'Customer',
            'email': self.user.email, 'phone_number': '123',
        })
        self.assertRedirects(response, reverse('profile'))
        self.user.refresh_from_db()
        self.assertEqual(self.user.first_name, 'Updated')
        self.assertEqual(self.user.phone_number, '123')

    def test_password_reset_sends_email(self):
        response = self.client.post(reverse('password_reset'), {'email': self.user.email})
        self.assertRedirects(response, reverse('password_reset_done'))
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, [self.user.email])
        self.assertIn('/accounts/reset/', mail.outbox[0].body)


class BookingTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user(username='customer')
        cls.other_user = get_user_model().objects.create_user(username='other')
        cls.business = Business.objects.create(
            name='Test business', address='Test address', phone_number='000',
            reservation_options=['Court A'], appointment_reasons=['Consultation'],
            enable_time_estimation=True, time_per_customer=5,
        )
        cls.category = Category.objects.create(name='Reservations')
        cls.business.categories.add(cls.category)
        # Choose a future Monday; default business hours run Monday through Friday.
        today = timezone.localdate()
        cls.date = today + timedelta(days=(7 - today.weekday()) % 7 + 7)

    def setUp(self):
        self.client.force_login(self.user)

    def test_business_hours_created_once(self):
        self.assertEqual(self.business.business_hours.count(), 7)
        self.business.get_business_hours()
        self.assertEqual(self.business.business_hours.count(), 7)
        self.assertEqual(self.business.business_hours.filter(is_working_day=True).count(), 5)

    def test_category_and_business_navigation(self):
        self.assertContains(self.client.get(reverse('categories')), self.category.name)
        self.assertContains(self.client.get(reverse('view_all', args=['reservations'])), self.business.name)
        self.assertRedirects(
            self.client.get(reverse('business_detail', args=[self.business.pk])),
            reverse('reservation', args=[self.business.pk]),
        )
        Category.objects.create(name='Appointments').businesses.add(self.business)
        response = self.client.get(reverse('business_detail', args=[self.business.pk]))
        self.assertTemplateUsed(response, 'accounts/business_category_choice.html')

    def test_reservation_aliases_preserve_paths_and_callback(self):
        for path in (f'/accounts/reservation/{self.business.pk}/',
                     f'/accounts/business/{self.business.pk}/reservation/'):
            with self.subTest(path=path):
                self.assertIs(resolve(path).func, views.reservation)
                self.assertContains(self.client.get(path), self.business.name)
        self.assertEqual(reverse('reservation', args=[self.business.pk]),
                         f'/accounts/reservation/{self.business.pk}/')
        self.assertEqual(reverse('edit_staff', args=[self.business.pk]),
                         f'/accounts/accounts/business/{self.business.pk}/edit-staff/')

    def test_reservation_create_duplicate_and_cancel(self):
        data = {'date': self.date.isoformat(), 'time': '10:00', 'option': 'Court A'}
        url = reverse('make_reservation', args=[self.business.pk])
        self.assertTrue(self.client.post(url, data).json()['success'])
        self.assertFalse(self.client.post(url, data).json()['success'])
        booking = Reservation.objects.get(user=self.user)
        self.assertEqual(booking.option, 'Court A')
        self.assertContains(self.client.get(reverse('my_reservations')), self.business.name)
        self.assertContains(self.client.get(reverse('booking_details', args=['reservation', booking.pk])), 'Court A')
        self.assertTrue(self.client.post(reverse('cancel_booking', args=['reservation', booking.pk])).json()['success'])
        booking.refresh_from_db()
        self.assertEqual(booking.status, 'cancelled')

    def test_appointment_create_duplicate_and_cancel(self):
        data = {'date': self.date.isoformat(), 'time': '11:00', 'reason': 'Consultation'}
        url = reverse('book_appointment', args=[self.business.pk])
        self.assertTrue(self.client.post(url, data).json()['success'])
        self.assertFalse(self.client.post(url, data).json()['success'])
        booking = Appointment.objects.get(user=self.user)
        self.assertEqual(booking.reason, 'Consultation')
        self.assertTrue(self.client.post(reverse('cancel_booking', args=['appointment', booking.pk])).json()['success'])
        booking.refresh_from_db()
        self.assertEqual(booking.status, 'cancelled')

    def test_booking_details_and_cancellation_are_scoped_to_customer(self):
        booking = Reservation.objects.create(
            user=self.other_user, business=self.business,
            date=self.date, time='12:00', option='Court A',
        )
        self.assertEqual(self.client.get(reverse('booking_details', args=['reservation', booking.pk])).status_code, 404)
        self.assertEqual(self.client.post(reverse('cancel_booking', args=['reservation', booking.pk])).status_code, 404)
        booking.refresh_from_db()
        self.assertEqual(booking.status, 'booked')

    def test_slots_respect_hours_bookings_and_cancelled_appointments(self):
        Reservation.objects.create(user=self.user, business=self.business,
                                   date=self.date, time='10:00', option='Court A')
        appointment = Appointment.objects.create(user=self.user, business=self.business,
                                                date=self.date, time='10:00')
        for name, count in (('get_available_reservation_slots', 8),
                            ('get_available_appointment_slots', 16)):
            with self.subTest(name=name):
                response = self.client.get(reverse(name, args=[self.business.pk]),
                                           {'date': self.date.isoformat(), 'option': 'Court A'})
                slots = response.json()['slots']
                self.assertEqual(len(slots), count)
                self.assertEqual(slots[0], {'time': '09:00', 'available': True})
                self.assertFalse(next(slot for slot in slots if slot['time'] == '10:00')['available'])
                closed = self.client.get(reverse(name, args=[self.business.pk]),
                                         {'date': (self.date + timedelta(days=5)).isoformat()})
                self.assertEqual(closed.json(), {'slots': []})
        appointment.status = 'cancelled'
        appointment.save()
        slots = self.client.get(reverse('get_available_appointment_slots', args=[self.business.pk]),
                                {'date': self.date.isoformat()}).json()['slots']
        self.assertTrue(next(slot for slot in slots if slot['time'] == '10:00')['available'])

    def test_queue_join_duplicate_remove_and_renumber(self):
        now = timezone.make_aware(datetime.combine(self.date, datetime.min.time()).replace(hour=10))
        with patch('accounts.views.timezone.localtime', return_value=now):
            url = reverse('add_to_queue', args=[self.business.pk])
            response = self.client.post(url).json()
            self.assertEqual(response['status'], 'success')
            self.assertEqual(response['position'], 1)
            self.assertEqual(response['estimated_wait_time'], 5)
            self.assertEqual(self.client.post(url).json()['status'], 'error')
            other = Queue.objects.create(user=self.other_user, business=self.business)
            self.assertEqual(other.position, 2)
            self.assertEqual(other.people_ahead, 1)
            response = self.client.post(reverse('remove_from_queue', args=[self.business.pk]))
            self.assertEqual(response.json()['status'], 'success')
        other.refresh_from_db()
        self.business.refresh_from_db()
        self.assertEqual(other.position, 1)
        self.assertEqual(self.business.people_in_queue, 1)

    def test_queue_count_update_preserves_return_contract(self):
        Queue.objects.create(user=self.user, business=self.business)
        self.business.people_in_queue = 99
        # The effective method historically returns None; removing the shadowed
        # definition must not change that public behavior.
        self.assertIsNone(self.business.update_people_in_queue())
        self.business.refresh_from_db()
        self.assertEqual(self.business.people_in_queue, 1)

    def test_mutations_keep_post_only_guards(self):
        for name in ('add_to_queue', 'make_reservation', 'book_appointment'):
            with self.subTest(name=name):
                self.assertEqual(self.client.get(reverse(name, args=[self.business.pk])).status_code, 405)


class StaffTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.business = Business.objects.create(name='Staff business', address='Test', phone_number='000')
        cls.owner = get_user_model().objects.create_user(
            username='owner', business=cls.business, staff_role='OWNER',
        )
        BusinessRolePermission.objects.create(
            business=cls.business, role='OWNER', can_edit_info=True,
            can_edit_staff=True, can_edit_service=True, can_display_customers=True,
        )

    def test_authorized_staff_pages(self):
        self.client.force_login(self.owner)
        self.assertEqual(self.client.get(reverse('business_portal')).status_code, 200)
        for name in ('edit_staff', 'edit_business_info', 'edit_service', 'business_customer_list'):
            with self.subTest(name=name):
                self.assertContains(self.client.get(reverse(name, args=[self.business.pk])), self.business.name)

    def test_staff_pages_keep_existing_image_urls(self):
        self.business.image = 'business_images/test.webp'
        self.business.save(update_fields=['image'])
        self.client.force_login(self.owner)
        for name, args in (('business_portal', []), ('edit_business_info', [self.business.pk])):
            with self.subTest(name=name):
                self.assertContains(self.client.get(reverse(name, args=args)), '/media/business_images/test.webp')

    def test_staff_can_update_own_business_booking_status(self):
        self.client.force_login(self.owner)
        booking = Appointment.objects.create(
            business=self.business, user=self.owner, date=timezone.localdate(), time='10:00',
        )
        response = self.client.post(reverse('update_booking_status', args=['appointment', booking.pk]), {'status': 'done'})
        self.assertTrue(response.json()['success'])
        booking.refresh_from_db()
        self.assertEqual(booking.status, 'done')
