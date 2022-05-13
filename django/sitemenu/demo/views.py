from django.shortcuts import render

# Create your views here.
from django.shortcuts import render

# Create your views here.
def index(request):
    return render(request, 'index.html', {'title':'data'})

def home(request):
    return render(request, 'home.html', {'title':'home'})

def board(request):
    return render(request, 'board.html', {'title':'board'})