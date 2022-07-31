from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name="home_page"),
    path('display_manual_transactions/', views.display_manual_transactions, name="display_manual_transactions"),
]
