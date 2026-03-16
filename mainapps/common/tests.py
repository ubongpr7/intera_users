from django.test import TestCase,override_settings
from django.test.client import Client
from http import HTTPStatus
from rest_framework.test import APIClient
from cities_light.models import City, Country, Region, SubRegion

from mainapps.accounts.models import User
from mainapps.common.models import Unit

class IPBlackListMiddlewareTest(TestCase):

    def setUp(self):
        self.client= Client()
        
    @override_settings(BANNED_IPS=None)
    def test_request_successful_without_blacklist_setting(self):
        response= self.client.get('/admin/')
        self.assertEqual(response.status_code,HTTPStatus.FOUND)


class CommonReferenceApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(email="common@example.com", password="password123")
        self.client.force_authenticate(user=self.user)

        self.country = Country.objects.create(name="Nigeria", code2="NG", code3="NGA")
        self.region = Region.objects.create(name="Lagos", country=self.country)
        self.subregion = SubRegion.objects.create(name="Ikeja", country=self.country, region=self.region)
        self.city = City.objects.create(name="Alausa", country=self.country, region=self.region, subregion=self.subregion)
        self.unit = Unit.objects.create(
            name="Kilogram",
            abbreviated_name="kg",
            dimension_type=Unit.DimensionType.MASS,
        )

    def test_country_region_subregion_and_city_endpoints_return_filtered_results(self):
        self.assertEqual(self.client.get("/common/countries/").status_code, HTTPStatus.OK)

        regions_response = self.client.get(f"/common/regions/?country_id={self.country.id}")
        self.assertEqual(regions_response.status_code, HTTPStatus.OK)
        self.assertEqual(regions_response.json(), [{"id": self.region.id, "name": "Lagos"}])

        subregions_response = self.client.get(f"/common/subregions/?region_id={self.region.id}")
        self.assertEqual(subregions_response.status_code, HTTPStatus.OK)
        self.assertEqual(subregions_response.json(), [{"id": self.subregion.id, "name": "Ikeja"}])

        cities_response = self.client.get(f"/common/cities/?subregion_id={self.subregion.id}")
        self.assertEqual(cities_response.status_code, HTTPStatus.OK)
        self.assertEqual(cities_response.json(), [{"id": self.city.id, "name": "Alausa"}])

    def test_units_endpoint_returns_active_units(self):
        response = self.client.get("/common/units/")
        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertEqual(
            response.json(),
            [
                {
                    "id": self.unit.id,
                    "code": "kg",
                    "name": "Kilogram",
                    "abbreviated_name": "kg",
                    "dimension_type": "MASS",
                    "conversion_factor": 1.0,
                }
            ],
        )
