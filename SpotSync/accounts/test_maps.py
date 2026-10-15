"""Maps configuration review uses synthetic placeholders and mocked transport."""

from unittest.mock import Mock, patch

import requests
from django.template.loader import render_to_string
from django.test import TestCase, override_settings

from .context_processors import maps
from .models import Business
from .views import geocode_address


@override_settings(
    GOOGLE_MAPS_API_KEY='server-only-test-placeholder',
    GOOGLE_MAPS_BROWSER_API_KEY='browser-only-test-placeholder',
)
class MapsIsolationTests(TestCase):
    def test_browser_context_exposes_only_browser_binding(self):
        self.assertEqual(maps(None), {
            'GOOGLE_MAPS_BROWSER_API_KEY': 'browser-only-test-placeholder',
        })

    def test_all_maps_templates_render_only_browser_binding(self):
        business = Business.objects.create(name='Synthetic', address='Test', phone_number='000')
        for template in ('appointment', 'business_detail', 'reservation', 'waiting_list', 'edit_business_info'):
            with self.subTest(template=template):
                html = render_to_string(f'accounts/{template}.html', {'business': business, **maps(None)})
                self.assertIn('key=browser-only-test-placeholder', html)
                self.assertNotIn('server-only-test-placeholder', html)

    @patch('accounts.views.requests.get')
    def test_geocoding_sends_only_server_binding(self, get):
        get.return_value = Mock()
        get.return_value.json.return_value = {
            'status': 'OK', 'results': [{'geometry': {'location': {'lat': 0, 'lng': 12}}}],
        }
        self.assertEqual(geocode_address('A & B'), (0, 12))
        get.assert_called_once_with(
            'https://maps.googleapis.com/maps/api/geocode/json',
            params={'address': 'A & B', 'key': 'server-only-test-placeholder'}, timeout=5,
        )
        get.return_value.raise_for_status.assert_called_once_with()

    @patch('accounts.views.requests.get')
    def test_transport_and_http_errors_do_not_log_credentials(self, get):
        sensitive_url = 'https://maps.googleapis.com/?key=server-only-test-placeholder'
        for error in (requests.Timeout(sensitive_url), requests.HTTPError(sensitive_url)):
            with self.subTest(error=type(error).__name__):
                get.side_effect = error
                with self.assertLogs('accounts.views', level='WARNING') as logs:
                    self.assertEqual(geocode_address('Test'), (None, None))
                self.assertEqual(logs.output, [
                    'WARNING:accounts.views:Geocoding failed; preserving the existing coordinates.',
                ])

    @patch('accounts.views.requests.get')
    def test_denied_response_payload_is_not_logged_or_returned(self, get):
        get.return_value = Mock()
        get.return_value.json.return_value = {
            'status': 'REQUEST_DENIED', 'error_message': 'server-only-test-placeholder',
        }
        with self.assertNoLogs('accounts.views', level='WARNING'):
            self.assertEqual(geocode_address('Test'), (None, None))

    @patch('accounts.views.requests.get')
    def test_invalid_json_preserves_coordinates_without_logging_exception(self, get):
        get.return_value = Mock()
        get.return_value.json.side_effect = ValueError('server-only-test-placeholder')
        with self.assertLogs('accounts.views', level='WARNING') as logs:
            self.assertEqual(geocode_address('Test'), (None, None))
        self.assertNotIn('server-only-test-placeholder', '\n'.join(logs.output))
