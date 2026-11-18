from django.urls import path
from app1.views import home,user_login,register

urlpatterns = [
    path('',home,name='home'),
    path('login/',user_login,name='login'),
    path('register/',register,name='register')
]