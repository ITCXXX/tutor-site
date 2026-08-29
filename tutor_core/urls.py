from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    # Р Р°Р·РґРµР» РёРіСЂ: РµРґРёРЅС‹Р№ РІС…РѕРґ вЂ” С…Р°Р± РЅР° /games/. РљРѕРЅРєСЂРµС‚РЅС‹Р№ РїСѓС‚СЊ РґРѕ Р·Р°Р±РѕСЂРѕРІ
    # РѕР±СЏР·Р°РЅ РёРґС‚Рё Р РђРќР¬РЁР• include, РёРЅР°С‡Рµ '<str:code>/' РІРЅСѓС‚СЂРё games РїСЂРёРјРµС‚
    # 'zabory' Р·Р° РєРѕРґ РїР°СЂС‚РёРё.
    path('games/zabory/', include('quoridor.urls', namespace='quoridor')),
    path('games/', include('games.urls', namespace='games')),
    path('board/', include('board.urls', namespace='board')),
    path('', include('users.urls')),  # РџРѕРґРєР»СЋС‡Р°РµРј Р’РЎР• РјР°СЂС€СЂСѓС‚С‹ РёР· РїСЂРёР»РѕР¶РµРЅРёСЏ users
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
