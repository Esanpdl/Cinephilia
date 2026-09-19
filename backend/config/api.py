"""Small, shared REST conventions; domain behavior stays in its own app."""
from rest_framework import serializers
from rest_framework.pagination import PageNumberPagination


class CatalogPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 60


class PageQuerySerializer(serializers.Serializer):
    page = serializers.IntegerField(min_value=1, default=1)
    page_size = serializers.IntegerField(min_value=1, max_value=60, default=20)


class ErrorSerializer(serializers.Serializer):
    detail = serializers.CharField()
