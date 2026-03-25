# users/forms.py
from django import forms

class LoginForm(forms.Form):
    """
    Форма для входа учеников и родителей
    """
    username = forms.CharField(
        label='Логин',
        max_length=50,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Введите логин',
            'autofocus': True
        })
    )
    
    password = forms.CharField(
        label='Пароль', 
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Введите пароль'
        })
    )