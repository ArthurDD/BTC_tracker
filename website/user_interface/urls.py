from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name="home_page"),
    path('start_tracking/', views.start_tracking, name='start_tracking'),
    path('display_graph/', views.display_graph, name="display_graph"),
]