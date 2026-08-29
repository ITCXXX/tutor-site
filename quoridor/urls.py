# -*- coding: utf-8 -*-
from django.urls import path

from . import views

app_name = 'quoridor'

urlpatterns = [
    path('', views.play, name='play'),
]
