from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name="home_page"),
    path('display_graph/', views.display_graph, name="display_graph"),
    path('display_charts/', views.display_charts, name="display_charts"),
    path('display_manual_transactions/', views.display_manual_transactions, name="display_manual_transactions"),
]
