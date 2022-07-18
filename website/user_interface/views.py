from django.http import HttpResponse
from django.shortcuts import render


# Create your views here.
from chain_parser import ChainParser
from graph_visualisation import GraphVisualisation
from pathlib import Path


def index(request):
    if request.method == 'GET':
        print(f"Path: {Path(__file__).resolve().parent.parent.parent}")
        return render(request, 'user_interface/home.html', {'max_layer_number': range(1, 100)})
    else:
        return HttpResponse("Not OK")


def start_tracking(request):
    if request.method == 'POST':
        print(f"The form has been received. {dict(request.POST)}")
        address = request.POST.get("address_input")
        layer = request.POST.get("layer_input")

        # chain_parser = ChainParser(address, layer)
        # chain_parser.start_analysis()
        #
        # tree = GraphVisualisation(chain_parser.transaction_lists)
        # file_name = tree.build_tree()

        # return HttpResponse("Form received!")
        return render(request, 'user_interface/tree.html', {'file_name': "transaction-graph-15.gv.svg"})
    else:
        return HttpResponse("Not what we wanted, sorry")
