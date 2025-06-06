from django.test import TestCase,override_settings
from django.test.client import Client
from http import HTTPStatus

class IPBlackListMiddlewareTest(TestCase):

    def setUp(self):
        self.client= Client()
        
    @override_settings(BANNED_IPS=None)
    def test_request_successful_without_blacklist_setting(self):
        response= self.client.get('/admin')
        self.assertEqual(response.status_code,HTTPStatus.OK)
