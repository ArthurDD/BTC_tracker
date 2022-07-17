from django.http import HttpResponse
from django.shortcuts import render


# Create your views here.
def index(request):
    if request.method == 'GET':
        return HttpResponse("OK")
    else:
        return HttpResponse("Not OK")
