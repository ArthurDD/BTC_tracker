from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name="home_page"),
    path('start_tracking/', views.start_tracking, name='start_tracking'),
]
