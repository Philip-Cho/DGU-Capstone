from django.urls import include,path

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
    path('recommandsave/', views.recommandsave),
    path('code_to_text/', views.code_to_text),
    path('searchlec/', views.searchlec),
    path("""board/<id>/""", views.history_result, name="history_result"),
    path("""<lecture_name>/""", views.index_result, name="index_result"),
]

