# -*- coding: utf-8 -*-
"""Маршруты раздела карточек."""

from django.urls import path

from . import views

app_name = 'cards'

urlpatterns = [
    path('', views.список, name='list'),
    path('new/', views.создать, name='create'),
    path('new/full/', views.создать_подробно, name='create_full'),
    path('prompt/', views.инструкция, name='prompt'),
    path('parse/', views.разобрать_список, name='parse'),

    path('<int:pk>/', views.колода, name='deck'),
    path('<int:pk>/edit/', views.править, name='edit'),
    path('<int:pk>/delete/', views.удалить, name='delete'),
    path('<int:pk>/import/', views.импорт, name='import'),
    path('<int:pk>/cards/', views.править_карточки, name='edit_cards'),
    path('<int:pk>/study/', views.учить, name='study'),
    path('<int:pk>/learn/', views.заучивание, name='learn'),
    path('<int:pk>/test/', views.тест, name='test'),
    path('<int:pk>/match/', views.подбор, name='match'),
    path('<int:pk>/stats/', views.статистика, name='stats'),
    path('<int:pk>/check/', views.проверить, name='check'),
    path('<int:pk>/check-many/', views.проверить_многие, name='check_many'),
    path('<int:pk>/answer/', views.ответ, name='answer'),

    path('card/<int:pk>/edit/', views.править_карточку, name='card_edit'),
    path('card/<int:pk>/delete/', views.удалить_карточку, name='card_delete'),
]
