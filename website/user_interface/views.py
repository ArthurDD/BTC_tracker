import ast

from django.http import HttpResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
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


@csrf_exempt
def display_manual_transactions(request):
    if request.method == "GET":

        transactions = [{'index': 1, "txid": 'abcde', 'amount': 14, 'rto': 0.5},
                        {'index': 2, "txid": 'fghij', 'amount': 4, 'rto': 1.5},
                        {'index': 3, "txid": 'klmno', 'amount': 1, 'rto': 0.2},
                        {'index': 4, "txid": 'pqrst', 'amount': 50, 'rto': 0.02},
                        {'index': 5, "txid": 'uvwxy', 'amount': 66, 'rto': 5}]
        layer = 2
        return render(request, 'user_interface/modal.html', context={'transactions': transactions, 'layer': layer})
    elif request.method == 'POST':
        data = request.POST['data']
        data = ast.literal_eval(data)
        return render(request, 'user_interface/modal.html', context={'transactions': data['transactions'],
                                                                     'layer': data['layer']})
