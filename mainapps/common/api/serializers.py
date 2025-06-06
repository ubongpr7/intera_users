# types/serializers.py
from rest_framework import serializers
from mainapps.common.models import Currency, TypeOf, Unit
from rest_framework import serializers
from cities_light.models import Country, Region, SubRegion, City


class TypeOfSerializer(serializers.ModelSerializer):
    class Meta:
        model = TypeOf
        fields = '__all__'
        depth = 1  # To show nested parent/children relationships
class CurrencySerializer(serializers.ModelSerializer):
    class Meta:
        model = Currency
        fields = '__all__'



class CountrySerializer(serializers.ModelSerializer):
    class Meta:
        model = Country
        fields = ['id', 'name']
class UnitSerializer(serializers.ModelSerializer):
    class Meta:
        model = Unit
        fields = ['id', 'name']

class RegionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Region
        fields = ['id', 'name', 'country']

class SubRegionSerializer(serializers.ModelSerializer):
    class Meta:
        model = SubRegion
        fields = ['id', 'name', 'region']

class CitySerializer(serializers.ModelSerializer):
    class Meta:
        model = City
        fields = ['id', 'name', 'subregion']