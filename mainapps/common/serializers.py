from rest_framework import serializers

from .models import Unit


class DropdownOptionSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()


class UnitOptionSerializer(serializers.ModelSerializer):
    code = serializers.CharField(source="abbreviated_name", read_only=True)

    class Meta:
        model = Unit
        fields = [
            "id",
            "code",
            "name",
            "abbreviated_name",
            "dimension_type",
            "conversion_factor",
        ]
