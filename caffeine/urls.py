from django.urls import path

from . import views

urlpatterns = [
    path('', views.index),
    path('result/', views.result),
    path('text/', views.text),
    path('summary/', views.summary),
    path('keytext/', views.keytext),
    path('model/', views.model),
    path('board/', views.board),
    path('savedb/', views.savedb),
    path('getxy/', views.getxy),
    path('code_to_text/', views.code_to_text),
    path('<str:id>/', views.history_result),
]
