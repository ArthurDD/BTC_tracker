from django.http import HttpResponse
from django.shortcuts import render

from pathlib import Path


def index(request):
    if request.method == 'GET':
        print(f"Path: {Path(__file__).resolve().parent.parent.parent}")
        return render(request, 'user_interface/home.html', {'max_layer_number': range(1, 100)})
    else:
        return HttpResponse("Not OK")


def display_graph(request):
    if request.method == 'GET':
        file_name = request.GET.get('file_name')
        return render(request, 'user_interface/tree.html', {'file_name': file_name})
    else:
        return HttpResponse("Not what we wanted, sorry")


def display_charts(request):
    if request.method == "GET":
        return render(request, 'user_interface/charts.html', {'test_data': "We can pass data that way too."})
