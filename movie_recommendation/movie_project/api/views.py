from django.shortcuts import render
from rest_framework import viewsets
from api.models import Movie
from api.serializers import MovieSerializer

# Create your views here.
class MovieViewSet(viewsets.ModelViewSet):
    queryset=Movie.objects.all()
    serializer_class=MovieSerializer