from django.urls import path

from .views import CityListView, CountryListView, RegionListView, SubRegionListView, UnitListView


urlpatterns = [
    path("countries/", CountryListView.as_view(), name="common-countries"),
    path("regions/", RegionListView.as_view(), name="common-regions"),
    path("subregions/", SubRegionListView.as_view(), name="common-subregions"),
    path("cities/", CityListView.as_view(), name="common-cities"),
    path("units/", UnitListView.as_view(), name="common-units"),
]
