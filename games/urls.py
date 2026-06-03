from django.urls import path
from . import views

app_name = 'games'

urlpatterns = [
    path('', views.games_list, name='list'),
    path('new/', views.game_create, name='create'),
    path('nickname/', views.set_nickname, name='nickname'),
    path('<str:code>/', views.game_detail, name='detail'),
    path('<str:code>/join/', views.game_join, name='join'),
    path('<str:code>/state/', views.game_state, name='state'),
    path('<str:code>/move/', views.game_move, name='move'),
    path('<str:code>/rematch/', views.game_rematch, name='rematch'),
]
