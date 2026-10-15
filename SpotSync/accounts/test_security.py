import json
import os
import secrets
import subprocess
import sys
from pathlib import Path
from unittest.mock import Mock, patch

import requests
from django.contrib.auth import authenticate, get_user_model
from django.contrib.auth.models import AnonymousUser
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from .auth_backends import EmailBackend
from .models import Appointment, Business, BusinessRolePermission
from .views import geocode_address

User = get_user_model()


class BusinessAuthorizationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.business = Business.objects.create(name='Local', address='Test', phone_number='000')
        cls.other = Business.objects.create(name='Other', address='Test', phone_number='000')
        cls.owner = User.objects.create_user(username='owner', email='owner@example.invalid', business=cls.business, staff_role='OWNER')
        cls.manager = User.objects.create_user(username='manager', business=cls.business, staff_role='MANAGER')
        cls.worker = User.objects.create_user(username='worker', business=cls.business, staff_role='WORKER')
        cls.customer = User.objects.create_user(username='customer', email='customer@example.invalid')
        cls.outsider = User.objects.create_user(username='outsider', business=cls.other, staff_role='OWNER')
        cls.foreign_worker = User.objects.create_user(username='foreign', email='foreign@example.invalid', business=cls.other, staff_role='WORKER')
        for business in (cls.business, cls.other):
            for role in ('OWNER', 'MANAGER', 'WORKER'):
                BusinessRolePermission.objects.create(
                    business=business, role=role, can_edit_info=True, can_edit_staff=True,
                    can_display_customers=True, can_edit_service=True,
                )

    def test_model_permissions_fail_closed_for_wrong_business_and_nonstaff(self):
        for user in (AnonymousUser(), self.customer, self.outsider):
            self.assertFalse(self.business.user_has_permission(user, 'can_edit_info'))
        self.assertFalse(self.business.user_has_permission(self.owner, 'role'))
        self.assertTrue(self.business.user_has_permission(self.owner, 'can_edit_info'))
        self.owner.is_active = False
        self.assertFalse(self.business.user_has_permission(self.owner, 'can_edit_info'))
        self.worker.staff_role = 'INVALID'
        self.assertFalse(self.worker.is_business_staff)

    def protected_endpoints(self):
        for name in ('edit_staff', 'edit_business_info', 'edit_service', 'business_customer_list', 'get_role_permissions'):
            yield 'get', reverse(name, args=[self.business.pk]), {}
        for name in ('edit_business_info', 'edit_service', 'add_staff_member', 'update_role_permissions'):
            yield 'post', reverse(name, args=[self.business.pk]), {}
        for name in ('delete_staff_member', 'update_staff_member'):
            yield 'post', reverse(name, args=[self.business.pk, self.worker.pk]), {}

    def test_all_staff_endpoints_require_login(self):
        for method, url, data in self.protected_endpoints():
            with self.subTest(method=method, url=url):
                self.assertEqual(getattr(self.client, method)(url, data).status_code, 302)
        self.assertEqual(BusinessRolePermission.objects.count(), 6)

    @patch('accounts.views.geocode_address')
    def test_customer_and_foreign_staff_cannot_read_or_mutate_business(self, geocode):
        for user in (self.customer, self.outsider):
            self.client.force_login(user)
            for method, url, data in self.protected_endpoints():
                with self.subTest(user=user.username, method=method, url=url):
                    self.assertEqual(getattr(self.client, method)(url, data).status_code, 403)
        self.business.refresh_from_db()
        self.assertEqual(self.business.name, 'Local')
        geocode.assert_not_called()

    def test_only_owner_can_change_permissions_even_without_own_edit_flag(self):
        url = reverse('update_role_permissions', args=[self.business.pk])
        for actor in (self.worker, self.manager):
            self.client.force_login(actor)
            self.assertEqual(self.client.post(url, {}).status_code, 403)
        self.client.force_login(self.owner)
        self.assertTrue(self.client.post(url, {}).json()['success'])
        self.assertFalse(self.business.role_permissions.get(role='WORKER').can_edit_info)
        self.assertTrue(self.client.post(url, {'worker-edit-info': 'on'}).json()['success'])
        self.assertTrue(self.business.role_permissions.get(role='WORKER').can_edit_info)

    def test_staff_targets_must_belong_to_requested_business(self):
        self.client.force_login(self.owner)
        for name in ('delete_staff_member', 'update_staff_member'):
            data = {'email': 'changed@example.invalid', 'role': 'WORKER'}
            response = self.client.post(reverse(name, args=[self.business.pk, self.foreign_worker.pk]),
                                        data=json.dumps(data), content_type='application/json')
            self.assertEqual(response.status_code, 404)
        self.foreign_worker.refresh_from_db()
        self.assertEqual(self.foreign_worker.email, 'foreign@example.invalid')

    def test_role_escalation_and_invalid_roles_rejected_on_add_and_update(self):
        for actor, role in ((self.manager, 'OWNER'), (self.worker, 'OWNER'), (self.owner, 'INVALID')):
            self.client.force_login(actor)
            self.assertEqual(self.client.post(reverse('add_staff_member', args=[self.business.pk]),
                                             {'email': self.customer.email, 'role': role}).status_code, 403)
            response = self.client.post(reverse('update_staff_member', args=[self.business.pk, self.worker.pk]),
                                        {'email': 'worker@example.invalid', 'role': role}, content_type='application/json')
            self.assertEqual(response.status_code, 403)
        self.customer.refresh_from_db()
        self.assertIsNone(self.customer.business_id)

    def test_owner_can_add_update_remove_worker(self):
        self.client.force_login(self.owner)
        self.assertTrue(self.client.post(reverse('add_staff_member', args=[self.business.pk]),
                                        {'email': self.customer.email, 'role': 'WORKER'}).json()['success'])
        response = self.client.post(reverse('update_staff_member', args=[self.business.pk, self.customer.pk]),
                                    {'email': 'updated@example.invalid', 'role': 'MANAGER'}, content_type='application/json')
        self.assertTrue(response.json()['success'])
        self.assertTrue(self.client.post(reverse('delete_staff_member', args=[self.business.pk, self.customer.pk])).json()['success'])
        self.customer.refresh_from_db()
        self.assertEqual(self.customer.staff_role, 'CUSTOMER')
        self.assertIsNone(self.customer.business_id)

    def test_staff_update_rejects_bad_json_email_duplicates_and_self_demotion(self):
        self.client.force_login(self.owner)
        url = reverse('update_staff_member', args=[self.business.pk, self.worker.pk])
        for data in ('{', '[]', '{"email": 4}', '{"email":"invalid","role":"WORKER"}',
                     json.dumps({'email': self.customer.email, 'role': 'WORKER'})):
            with self.subTest(data=data):
                self.assertEqual(self.client.post(url, data, content_type='application/json').status_code, 400)
        self.assertEqual(self.client.post(url, {'email': 'valid@example.invalid', 'role': []}, content_type='application/json').status_code, 403)
        response = self.client.post(reverse('update_staff_member', args=[self.business.pk, self.owner.pk]),
                                    {'email': self.owner.email, 'role': 'WORKER'}, content_type='application/json')
        self.assertEqual(response.status_code, 403)

    def test_csrf_protection_is_retained(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.owner)
        self.assertEqual(client.post(reverse('update_role_permissions', args=[self.business.pk]), {}).status_code, 403)

    def test_same_business_staff_still_need_each_granted_permission(self):
        self.business.role_permissions.filter(role='WORKER').update(
            can_edit_info=False, can_edit_staff=False, can_edit_service=False, can_display_customers=False,
        )
        self.client.force_login(self.worker)
        for name in ('edit_staff', 'edit_business_info', 'edit_service', 'business_customer_list', 'get_role_permissions'):
            self.assertEqual(self.client.get(reverse(name, args=[self.business.pk])).status_code, 403)

    def test_managers_cannot_edit_other_managers_or_remove_owners(self):
        self.client.force_login(self.manager)
        response = self.client.post(reverse('update_staff_member', args=[self.business.pk, self.manager.pk]),
                                    {'email': 'manager@example.invalid', 'role': 'MANAGER'}, content_type='application/json')
        self.assertEqual(response.status_code, 403)
        response = self.client.post(reverse('delete_staff_member', args=[self.business.pk, self.owner.pk]))
        self.assertFalse(response.json()['success'])
        self.owner.refresh_from_db()
        self.assertEqual(self.owner.business_id, self.business.pk)

    @patch('accounts.views.geocode_address', return_value=(0, 12))
    def test_zero_geocoded_coordinates_are_saved(self, geocode):
        self.client.force_login(self.owner)
        response = self.client.post(reverse('edit_business_info', args=[self.business.pk]),
                                    {'name': 'Local', 'address': 'Updated', 'phone_number': '000'})
        self.assertEqual(response.status_code, 302)
        self.business.refresh_from_db()
        self.assertEqual((self.business.latitude, self.business.longitude), (0, 12))

    def test_information_save_does_not_overwrite_queue_changes_during_geocoding(self):
        from .models import Queue
        def geocode(address):
            Queue.objects.create(business=self.business, user=self.customer)
            return None, None
        self.client.force_login(self.owner)
        with patch('accounts.views.geocode_address', side_effect=geocode):
            response = self.client.post(reverse('edit_business_info', args=[self.business.pk]),
                                        {'name': 'Local', 'address': 'Updated', 'phone_number': '000'})
        self.assertEqual(response.status_code, 302)
        self.business.refresh_from_db()
        self.assertEqual(self.business.people_in_queue, 1)

    def test_staff_booking_mutation_requires_customer_permission_and_valid_status(self):
        booking = Appointment.objects.create(business=self.business, user=self.customer, date='2030-01-07', time='10:00')
        url = reverse('update_booking_status', args=['appointment', booking.pk])
        self.business.role_permissions.filter(role='WORKER').update(can_display_customers=False)
        self.client.force_login(self.worker)
        self.assertEqual(self.client.post(url, {'status': 'done'}).status_code, 403)
        self.client.force_login(self.owner)
        self.assertFalse(self.client.post(url, {'status': 'in_queue'}).json()['success'])
        booking.refresh_from_db()
        self.assertEqual(booking.status, 'booked')


class AuthenticationTests(TestCase):
    def test_backend_rejects_inactive_and_ambiguous_accounts(self):
        password = secrets.token_urlsafe(24)
        user = User.objects.create_user(username='inactive', email='same@example.invalid', password=password, is_active=False)
        backend = EmailBackend()
        self.assertIsNone(backend.authenticate(None, username=user.email, password=password))
        user.is_active = True
        user.save()
        User.objects.create_user(username='duplicate', email=user.email, password=password)
        self.assertIsNone(backend.authenticate(None, username=user.email, password=password))
        self.assertIsNone(authenticate(username=user.email, password=password))
        self.assertIsNone(backend.authenticate(None))
        self.assertIsNone(backend.authenticate(None, username='unknown', password=password))

    def test_set_password_requires_login_and_redirects_to_existing_login_route(self):
        url = reverse('set_new_password')
        self.assertEqual(self.client.get(url).status_code, 302)
        user = User.objects.create_user(username='password-user')
        self.client.force_login(user)
        password = secrets.token_urlsafe(24)
        response = self.client.post(url, {'new_password1': password, 'new_password2': password})
        self.assertRedirects(response, reverse('custom_login'))
        user.refresh_from_db()
        self.assertTrue(user.check_password(password))


class ConfigurationTests(TestCase):
    def test_production_requires_private_signing_key(self):
        env = dict(os.environ, SPOTSYNC_DEBUG='false', SPOTSYNC_SECRET_KEY='', PYTHONDONTWRITEBYTECODE='1')
        code = "from django.core.exceptions import ImproperlyConfigured\ntry:\n import SpotSync.settings\nexcept ImproperlyConfigured:\n pass\nelse:\n raise AssertionError('Missing signing key was accepted')"
        subprocess.run([sys.executable, '-c', code], env=env, check=True, capture_output=True,
                       cwd=Path(__file__).resolve().parents[1])

    def test_private_environment_configuration_is_used_without_embedding_values(self):
        env = dict(os.environ, SPOTSYNC_DEBUG='false', SPOTSYNC_SECRET_KEY=secrets.token_urlsafe(48),
                   PGPASSWORD=secrets.token_urlsafe(24), GOOGLE_MAPS_API_KEY=secrets.token_urlsafe(24),
                   GOOGLE_MAPS_BROWSER_API_KEY='', PYTHONDONTWRITEBYTECODE='1')
        code = "import os\nfrom SpotSync import settings\nassert not settings.DEBUG\nassert settings.SECRET_KEY == os.environ['SPOTSYNC_SECRET_KEY']\nassert settings.DATABASES['default']['PASSWORD'] == os.environ['PGPASSWORD']\nassert settings.GOOGLE_MAPS_BROWSER_API_KEY == ''"
        subprocess.run([sys.executable, '-c', code], env=env, check=True, capture_output=True,
                       cwd=Path(__file__).resolve().parents[1])

    @override_settings(GOOGLE_MAPS_API_KEY='server-only-test-placeholder', GOOGLE_MAPS_BROWSER_API_KEY='')
    def test_maps_without_browser_key_does_not_leak_server_credential(self):
        from django.template.loader import render_to_string
        business = Business.objects.create(name='Test', address='Test', phone_number='000')
        for template in ('appointment', 'business_detail', 'reservation', 'waiting_list', 'edit_business_info'):
            with self.subTest(template=template):
                html = render_to_string(f'accounts/{template}.html', {
                    'business': business, 'GOOGLE_MAPS_BROWSER_API_KEY': '',
                }, request=None)
                self.assertNotIn('maps.googleapis.com/maps/api/js', html)
                self.assertNotIn('server-only-test-placeholder', html)

    @override_settings(GOOGLE_MAPS_API_KEY='')
    @patch('accounts.views.requests.get')
    def test_no_geocoding_request_without_key(self, get):
        self.assertEqual(geocode_address('Test'), (None, None))
        get.assert_not_called()

    @override_settings(GOOGLE_MAPS_API_KEY='server-only-test-placeholder')
    @patch('accounts.views.requests.get')
    def test_geocoding_uses_encoded_parameters_timeout_and_handles_failure(self, get):
        get.side_effect = requests.Timeout('not logged')
        self.assertEqual(geocode_address('A & B'), (None, None))
        self.assertEqual(get.call_args.kwargs['params']['address'], 'A & B')
        self.assertEqual(get.call_args.kwargs['timeout'], 5)
        get.side_effect = None
        get.return_value = Mock()
        get.return_value.json.return_value = {'status': 'OK', 'results': [{'geometry': {'location': {'lat': 0, 'lng': 12}}}]}
        self.assertEqual(geocode_address('Test'), (0, 12))
        get.return_value.json.return_value = {'status': 'OK', 'results': []}
        self.assertEqual(geocode_address('Test'), (None, None))

    def test_current_configuration_and_templates_have_no_legacy_key_literals(self):
        root = Path(__file__).resolve().parents[1]
        files = [root / 'SpotSync/settings.py', *(root / 'accounts/templates/accounts').glob('*.html')]
        import re
        for path in files:
            self.assertIsNone(re.search(r'AIza[\w-]{35}', path.read_text()), path.name)
        self.assertNotIn('django-insecure-', (root / 'SpotSync/settings.py').read_text())
