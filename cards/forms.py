# -*- coding: utf-8 -*-
"""Формы раздела карточек."""

from django import forms

from users.models import Lesson

from .models import Card, Deck


class DeckForm(forms.ModelForm):
    """Создание и правка колоды."""

    class Meta:
        model = Deck
        fields = [
            'title', 'description', 'kind', 'visibility', 'lesson',
            'ask_mode', 'check_mode', 'reverse_enabled',
            'front_lang', 'back_lang',
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
            'kind': forms.Select(attrs={'class': 'form-select'}),
            'ask_mode': forms.Select(attrs={'class': 'form-select'}),
            'check_mode': forms.Select(attrs={'class': 'form-select'}),
            'front_lang': forms.Select(attrs={'class': 'form-select'}),
            'back_lang': forms.Select(attrs={'class': 'form-select'}),
            'visibility': forms.Select(attrs={'class': 'form-select'}),
            'lesson': forms.Select(attrs={'class': 'form-select'}),
            'desired_retention': forms.NumberInput(attrs={
                'class': 'form-control', 'step': '0.01', 'min': '0.7', 'max': '0.97',
            }),
            'exam_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'new_per_day': forms.NumberInput(attrs={'class': 'form-control', 'min': '0'}),
            'reviews_per_day': forms.NumberInput(attrs={'class': 'form-control', 'min': '0'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Уроков в проекте много, а привязка колоды к уроку — редкий случай,
        # поэтому список остаётся необязательным и с понятной пустой строкой.
        self.fields['lesson'].queryset = (
            Lesson.objects.select_related('module', 'module__course')
            .order_by('module__course__title', 'module__order', 'order')
        )
        self.fields['lesson'].required = False
        self.fields['lesson'].empty_label = '— колода сама по себе —'
        # Без названия курса список бесполезен: «Задание 6» встречается в
        # каждом курсе, и выбрать из трёх одинаковых строк нельзя.
        self.fields['lesson'].label_from_instance = (
            lambda урок: '%s — %s' % (урок.module.course.title, урок.title)
        )
        self.fields['reverse_enabled'].widget.attrs['class'] = 'form-check-input'

    def clean_desired_retention(self):
        значение = self.cleaned_data['desired_retention']
        # Верхнюю границу держим на 0,97: выше планировщик начинает назначать
        # повторения чаще, чем человек успевает их делать, и колода превращается
        # в бесконечную очередь.
        if not 0.7 <= значение <= 0.97:
            raise forms.ValidationError('Разумные значения — от 0,70 до 0,97.')
        return значение


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
