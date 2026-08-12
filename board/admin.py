# -*- coding: utf-8 -*-
from django.contrib import admin
from unfold.admin import ModelAdmin

from .models import Board, BoardElement


@admin.register(Board)
class BoardAdmin(ModelAdmin):
    list_display = ('code', 'title', 'owner', 'lesson', 'updated_at')
    search_fields = ('code', 'title', 'owner__username')
    autocomplete_fields = ('owner', 'members', 'lesson')
    readonly_fields = ('code', 'created_at', 'updated_at')


@admin.register(BoardElement)
class BoardElementAdmin(ModelAdmin):
    list_display = ('element_id', 'board', 'type', 'author', 'z_index', 'updated_at')
    list_filter = ('type',)
    search_fields = ('element_id', 'board__code')
    autocomplete_fields = ('board', 'author')
    readonly_fields = ('created_at', 'updated_at')
