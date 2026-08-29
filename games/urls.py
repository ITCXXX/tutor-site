from django.urls import path
from . import views

app_name = 'games'

urlpatterns = [
    # Хаб — единый вход в раздел. Партии УТТТ переехали на /games/uttt/,
    # имя маршрута 'list' сохранено, поэтому все ссылки на него продолжают
    # работать. Оба конкретных пути обязаны идти ДО '<str:code>/', иначе
    # он перехватит их как код партии.
    path('', views.games_hub, name='hub'),
    path('uttt/', views.games_list, name='list'),
    path('new/', views.game_create, name='create'),
    path('nickname/', views.set_nickname, name='nickname'),
    path('<str:code>/', views.game_detail, name='detail'),
    path('<str:code>/join/', views.game_join, name='join'),
    path('<str:code>/state/', views.game_state, name='state'),
    path('<str:code>/move/', views.game_move, name='move'),
    path('<str:code>/rematch/', views.game_rematch, name='rematch'),
]
