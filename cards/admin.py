# -*- coding: utf-8 -*-
"""Админка раздела карточек — на случай ручной правки и разбора жалоб."""

from django.contrib import admin
from unfold.admin import ModelAdmin, TabularInline

from .models import Card, CardReview, CardState, Deck


class CardInline(TabularInline):
    model = Card
    extra = 0
    fields = ('order', 'front', 'back', 'hint')


@admin.register(Deck)
class DeckAdmin(ModelAdmin):
    list_display = ('title', 'owner', 'kind', 'visibility', 'карточек', 'updated_at')
    list_filter = ('kind', 'visibility')
    search_fields = ('title', 'description')
    inlines = [CardInline]

    @admin.display(description='Карточек')
    def карточек(self, объект):
        return объект.cards.count()


@admin.register(CardState)
class CardStateAdmin(ModelAdmin):
    list_display = ('card', 'user', 'direction', 'state', 'due', 'reps', 'lapses')
    list_filter = ('state', 'direction', 'suspended')
    search_fields = ('card__front', 'user__username')
    raw_id_fields = ('card', 'user')


@admin.register(CardReview)
class CardReviewAdmin(ModelAdmin):
    list_display = ('card', 'user', 'rating', 'reviewed_at', 'duration_ms')
    list_filter = ('rating',)
    search_fields = ('card__front', 'user__username')
    raw_id_fields = ('card', 'user')
