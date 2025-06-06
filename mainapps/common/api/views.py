from rest_framework import generics
from mainapps.common.models import Currency, TypeOf, Unit
from mainapps.common.settings import currency_code_mappings
from .serializers import CurrencySerializer, TypeOfSerializer, UnitSerializer
from django.http import JsonResponse
# views.py
from rest_framework import generics
from cities_light.models import Country, Region, SubRegion, City
from .serializers import CountrySerializer, RegionSerializer, SubRegionSerializer, CitySerializer

def get_currencies(request):
    currencies = currency_code_mappings()
    currency_list = [{"code": code, "name": name} for code, name in currencies]
    return JsonResponse({"currencies": currency_list})

class CurrencyListView(generics.ListAPIView):
    serializer_class = CurrencySerializer

    def get_queryset(self):
        return Currency.objects.all()
        

class TypeOfListView(generics.ListAPIView):
    serializer_class = TypeOfSerializer
    
    def get_queryset(self):
        queryset = TypeOf.objects.all()
        model_filter = self.request.query_params.get('for_which_model')
        
        if model_filter:
            queryset = queryset.filter(which_model=model_filter)
            
        return queryset
    


class CountryListView(generics.ListAPIView):
    queryset = Country.objects.all()
    serializer_class = CountrySerializer

class UnitListView(generics.ListAPIView):
    queryset = Unit.objects.all()
    serializer_class = UnitSerializer

class RegionListView(generics.ListAPIView):
    serializer_class = RegionSerializer

    def get_queryset(self):
        country_id = self.request.query_params.get('country_id')
        return Region.objects.filter(country_id=country_id)

class SubRegionListView(generics.ListAPIView):
    serializer_class = SubRegionSerializer

    def get_queryset(self):
        region_id = self.request.query_params.get('region_id')
        return SubRegion.objects.filter(region_id=region_id)

class CityListView(generics.ListAPIView):
    serializer_class = CitySerializer

    def get_queryset(self):
        subregion_id = self.request.query_params.get('subregion_id')
        return City.objects.filter(subregion_id=subregion_id)