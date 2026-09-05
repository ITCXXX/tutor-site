from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    # Раздел игр: единый вход — хаб на /games/. Конкретный путь до заборов
    # обязан идти РАНЬШЕ include, иначе '<str:code>/' внутри games примет
    # 'zabory' за код партии.
    path('games/zabory/', include('quoridor.urls', namespace='quoridor')),
    path('games/', include('games.urls', namespace='games')),
    path('board/', include('board.urls', namespace='board')),
    path('cards/', include('cards.urls', namespace='cards')),
    path('', include('users.urls')),  # Подключаем ВСЕ маршруты из приложения users
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
