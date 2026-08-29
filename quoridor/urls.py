# -*- coding: utf-8 -*-
from django.urls import path

from . import views

app_name = 'quoridor'

urlpatterns = [
    # Конкретные пути обязаны идти ДО '<str:code>/', иначе он перехватит
    # слова «local» и «new» как коды партий.
    path('', views.lobby, name='play'),
    path('local/', views.play_local, name='local'),
    path('new/', views.game_create, name='create'),
    path('<str:code>/', views.game_detail, name='game'),
    path('<str:code>/join/', views.game_join, name='join'),
    path('<str:code>/state/', views.game_state, name='state'),
    path('<str:code>/move/', views.game_move, name='move'),
    path('<str:code>/resign/', views.game_resign, name='resign'),
]
