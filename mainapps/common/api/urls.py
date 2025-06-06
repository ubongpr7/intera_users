# types/urls.py
from django.urls import path
from . import  views

urlpatterns = [
    path('types/', views.TypeOfListView.as_view(), name='type-of-list'),
    path('units/', views.UnitListView.as_view(), name='unit-of-list'),
    path('currencies/', views.get_currencies, name='get-currencies'),
    path('currency/', views.CurrencyListView.as_view(), name='get-currency'),
    path('countries/', views.CountryListView.as_view(), name='country-list'),
    path('regions/', views.RegionListView.as_view(), name='region-list'),
    path('subregions/', views.SubRegionListView.as_view(), name='subregion-list'),
    path('cities/', views.CityListView.as_view(), name='city-list'),
]