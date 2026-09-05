# -*- coding: utf-8 -*-
"""Формы раздела карточек."""

from django import forms

from .models import Card, Deck


class DeckForm(forms.ModelForm):
    """Создание и правка колоды."""

    class Meta:
        model = Deck
        fields = [
            'title', 'description', 'check_mode', 'reverse_enabled',
            'desired_retention', 'exam_date', 'new_per_day', 'reviews_per_day',
        ]
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'form-control', 'autofocus': True,
                'placeholder': 'Например: Формулы площадей',
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control', 'rows': 2,
                'placeholder': 'Необязательно: для кого и зачем',
            }),
            'check_mode': forms.Select(attrs={'class': 'form-select'}),
            'desired_retention': forms.NumberInput(attrs={
                'class': 'form-control', 'step': '0.01', 'min': '0.7', 'max': '0.97',
            }),
            'exam_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'new_per_day': forms.NumberInput(attrs={'class': 'form-control', 'min': '0'}),
            'reviews_per_day': forms.NumberInput(attrs={'class': 'form-control', 'min': '0'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['reverse_enabled'].widget.attrs['class'] = 'form-check-input'

    def clean_desired_retention(self):
        значение = self.cleaned_data['desired_retention']
        # Верхнюю границу держим на 0,97: выше планировщик начинает назначать
        # повторения чаще, чем человек успевает их делать, и колода превращается
        # в бесконечную очередь.
        if not 0.7 <= значение <= 0.97:
            raise forms.ValidationError('Разумные значения — от 0,70 до 0,97.')
        return значение


class ПростаяКолодаForm(forms.ModelForm):
    """Только название и описание — остальное берётся по умолчанию.

    Простой путь существует ровно для того, чтобы человек, у которого есть
    список слов, дошёл до карточек за один экран. Дюжина настроек планировщика
    на этом экране не помогает выбрать — она отпугивает; кому они нужны,
    открывает подробный путь или заходит в настройки готовой колоды.
    """

    class Meta:
        model = Deck
        fields = ['title', 'description']
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'form-control form-control-lg', 'autofocus': True,
                'placeholder': 'Название колоды',
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control', 'rows': 2,
                'placeholder': 'Описание (необязательно)',
            }),
        }


class CardForm(forms.ModelForm):
    """Правка одной карточки."""

    class Meta:
        model = Card
        fields = ['front', 'back', 'hint', 'accepted', 'distractors']
        widgets = {
            'front': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'back': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'hint': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'accepted': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'distractors': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }


class ImportForm(forms.Form):
    """Массовый ввод: один большой кусок текста."""

    текст = forms.CharField(
        label='Список карточек',
        widget=forms.Textarea(attrs={
            'class': 'form-control font-monospace', 'rows': 14,
            'placeholder': 'Формула площади круга | $S = \\pi R^2$\n'
                           'Сумма углов треугольника | $180^\\circ$',
        }),
    )
