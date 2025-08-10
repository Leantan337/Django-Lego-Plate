from django.shortcuts import render

def index(request):
    return render(request, 'polls/index.html', {'message': 'Hello from demo polls brick!'})
