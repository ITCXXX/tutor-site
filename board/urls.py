# -*- coding: utf-8 -*-
from django.urls import path

from . import views

app_name = 'board'

urlpatterns = [
    path('', views.boards_list, name='list'),
    path('new/', views.board_create, name='create'),
    path('join/', views.board_join, name='join'),
    # Файлы питона для окна кода. Без кода доски: они одни на весь сайт, и
    # адрес должен быть постоянным — браузер держит их в памяти год.
    path('py/<str:name>', views.pyodide_file, name='pyodide'),
    path('<str:code>/rename/', views.board_rename, name='rename'),
    path('<str:code>/password/', views.board_set_password, name='set_password'),
    path('<str:code>/delete/', views.board_delete, name='delete'),
    path('<str:code>/leave/', views.board_leave, name='leave'),
    path('<str:code>/duplicate/', views.board_duplicate, name='duplicate'),
    path('<str:code>/upload/', views.board_upload, name='upload'),
    path('<str:code>/ice/', views.board_ice, name='ice'),
    path('<str:code>/', views.board_room, name='room'),
]
