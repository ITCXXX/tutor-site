# -*- coding: utf-8 -*-
"""Шаблонные фильтры раздела карточек.

Django-фильтр pluralize умеет только две формы («штука/штуки») и на трёх
молча возвращает пустую строку — получается «Добавить 4 карточ». Русскому
счёту нужны три формы, поэтому здесь свой фильтр.
"""

from django import template
from django.db.models import Count

register = template.Library()


@register.filter
def слово(число, формы):
    """Форма существительного при числе: 1 карточка, 2 карточки, 5 карточек.

    Использование: {{ n }} {{ n|слово:"карточка,карточки,карточек" }}
    """
    части = [ф.strip() for ф in str(формы).split(',')]
    if len(части) != 3:
        return части[-1] if части else ''
    одна, две, пять = части

    try:
        n = abs(int(число))
    except (TypeError, ValueError):
        return пять

    # 11–14 — исключение: «одиннадцать карточек», а не «карточка».
    if 11 <= n % 100 <= 14:
        return пять
    остаток = n % 10
    if остаток == 1:
        return одна
    if 2 <= остаток <= 4:
        return две
    return пять


@register.inclusion_tag('cards/_lesson_decks.html', takes_context=True)
def колоды_урока(context, урок):
    """Колоды, привязанные к этому уроку и видимые текущему пользователю.

    Сделано тегом, а не полем в контексте урока: страница урока принадлежит
    приложению users, и тащить в его вьюху знание про карточки значило бы
    связать два раздела там, где достаточно одной строки в шаблоне.
    """
    from cards.models import Deck

    пользователь = context.get('user')
    колоды = list(
        Deck.objects.filter(lesson=урок)
        .annotate(карточек=Count('cards'))
        .order_by('title')
    )
    return {'колоды': [к for к in колоды if к.виден(пользователь)]}
