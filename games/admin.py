# -*- coding: utf-8 -*-
from django.contrib import admin
from unfold.admin import ModelAdmin

from .models import Game, SiteSetting


@admin.register(SiteSetting)
class SiteSettingAdmin(ModelAdmin):
    list_display = ('id', 'games_enabled', 'updated_at')
    list_editable = ('games_enabled',)
    fieldsets = (
        (None, {'fields': ('games_enabled',)}),
        ('Служебное', {'fields': ('updated_at',), 'classes': ('collapse',)}),
    )
    readonly_fields = ('updated_at',)

    def has_add_permission(self, request):
        # Запрещаем создавать второй объект настроек.
        return not SiteSetting.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Game)
class GameAdmin(ModelAdmin):
    list_display = ('code', 'status', 'x_player', 'o_player',
                    'current', 'winner', 'updated_at')
    list_filter = ('status', 'winner')
    search_fields = ('code', 'x_player__username', 'o_player__username')
    readonly_fields = ('code', 'created_at', 'updated_at', 'last_move',
                       'board', 'big_board')
    autocomplete_fields = ('x_player', 'o_player')
    fieldsets = (
        ('Основное', {
            'fields': ('code', 'status', 'winner', 'current', 'next_local')
        }),
        ('Игроки', {'fields': ('x_player', 'o_player')}),
        ('Состояние', {
            'fields': ('board', 'big_board', 'last_move'),
            'classes': ('collapse',),
        }),
        ('Даты', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )
