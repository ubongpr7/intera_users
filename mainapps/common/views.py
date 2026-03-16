from cities_light.models import City, Country, Region, SubRegion
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Unit
from .serializers import DropdownOptionSerializer, UnitOptionSerializer


class BaseGeoLookupView(APIView):
    permission_classes = [IsAuthenticated]
    model = None
    query_param = None
    filter_lookup = None

    def get_queryset(self):
        queryset = self.model.objects.all().order_by("name")
        if not self.query_param or not self.filter_lookup:
            return queryset

        parent_id = self.request.query_params.get(self.query_param)
        if not parent_id:
            return self.model.objects.none()

        return queryset.filter(**{self.filter_lookup: parent_id})

    def get(self, request):
        options = self.get_queryset().values("id", "name")
        serializer = DropdownOptionSerializer(options, many=True)
        return Response(serializer.data)


class CountryListView(BaseGeoLookupView):
    model = Country


class RegionListView(BaseGeoLookupView):
    model = Region
    query_param = "country_id"
    filter_lookup = "country_id"


class SubRegionListView(BaseGeoLookupView):
    model = SubRegion
    query_param = "region_id"
    filter_lookup = "region_id"


class CityListView(BaseGeoLookupView):
    model = City
    query_param = "subregion_id"
    filter_lookup = "subregion_id"


class UnitListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        queryset = Unit.objects.filter(is_active=True).order_by("dimension_type", "name")
        serializer = UnitOptionSerializer(queryset, many=True)
        return Response(serializer.data)
