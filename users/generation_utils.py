# users/generation_utils.py
import json
import random
from typing import Dict, Any

def generate_fraction_task():
    """
    Генератор задачи с дробями (ваш код, адаптированный для сайта)
    Возвращает данные в формате для сохранения в task_data
    """
    # 1. Выбор первого числа a
    # a должно быть целым, |a| > 3, |a| < 12, и a+1 тоже должно удовлетворять
    possible_a = [n for n in range(-11, 11) if abs(n) > 3 and abs(n) < 12 and abs(n+1) > 3 and abs(n+1) < 12]
    a = random.choice(possible_a)
    b = a + 1
    
    # 2. Выбор знаменателя
    d = random.randint(9, 19)
    
    # 3. Правильная дробь (между a и b)
    # a < x/d < b => a*d < x < b*d
    min_num = a * d
    max_num = b * d
    
    # Выбираем случайный целый числитель строго между min_num и max_num
    correct_numerator = random.randint(min_num + 1, max_num - 1)
    correct_fraction = (correct_numerator, d)
    
    # 4. Неправильные дроби
    fractions = [correct_fraction]
    
    # Случайно выбираем, сколько дробей будет меньше a, сколько больше b
    num_below = random.randint(0, 3)  # от 0 до 3 дробей меньше a
    num_above = 3 - num_below  # остальные больше b
    
    # Генерируем дроби меньше a: числители из (a-2)*d до a*d
    for _ in range(num_below):
        numerator = random.randint((a-2)*d, a*d - 1)
        fractions.append((numerator, d))
    
    # Генерируем дроби больше b: числители из b*d+1 до (b+2)*d
    for _ in range(num_above):
        numerator = random.randint(b*d + 1, (b+2)*d)
        fractions.append((numerator, d))
    
    # Перемешиваем и находим правильный ответ
    random.shuffle(fractions)
    correct_index = fractions.index(correct_fraction) + 1
    
    # Формируем текст условия
    condition_text = (
        f"Найдите дробь, которая находится между числами {a} и {b}.\n"
        f"Варианты дробей (все со знаменателем {d}):"
    )
    
    # Формируем данные для отображения с LaTeX
    fractions_latex = []
    for num, den in fractions:
        fractions_latex.append(f"\\frac{{{num}}}{{{den}}}")
    
    return {
        'type': 'fraction_between_numbers',
        'numbers': [a, b],
        'denominator': d,
        'fractions': fractions,  # список кортежей (числитель, знаменатель)
        'fractions_latex': fractions_latex,  # для отображения LaTeX
        'correct_answer': correct_index,
        'condition_text': condition_text,
        'answer_type': 'single_choice'  # выбор из 1-4
    }

def format_condition_for_display(task_data: Dict[str, Any]) -> str:
    """Форматирует условие задачи для отображения на сайте"""
    if task_data['type'] == 'fraction_between_numbers':
        a, b = task_data['numbers']
        d = task_data['denominator']
        
        condition = f"<p>Найдите дробь, которая находится между числами {a} и {b}.</p>"
        condition += f"<p>Дроби (все со знаменателем {d}):</p>"
        condition += "<ol>"
        
        for i, (num, den) in enumerate(task_data['fractions'], 1):
            condition += f"<li>$\\frac{{{num}}}{{{den}}}$</li>"
        
        condition += "</ol>"
        return condition
    
    return task_data.get('condition_text', 'Условие задачи')

def check_user_answer(task_data: Dict[str, Any], user_answer: str) -> bool:
    """Проверяет ответ пользователя"""
    if task_data['type'] == 'fraction_between_numbers':
        try:
            user_choice = int(user_answer.strip())
            correct_choice = task_data['correct_answer']
            return user_choice == correct_choice
        except ValueError:
            return False
    
    # Для других типов задач
    return str(user_answer).strip() == str(task_data.get('correct_answer', '')).strip()