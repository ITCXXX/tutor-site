# -*- coding: utf-8 -*-
"""
Management command: наполнение «Задание 9» курса ОГЭ генераторами уравнений.

Usage:
    python manage.py populate_oge9            # создать/обновить
    python manage.py populate_oge9 --clear    # очистить и заново

Структура:
    Курс «ОГЭ» (slug=oge-maths)
      └ Модуль «Первая часть»
          └ Урок «Задание 9» (lesson_type='practice')
              ├ Тип 1: Линейное уравнение
              ├ Тип 2: Уравнение со скобкой
              ├ Тип 3: Уравнение со скобкой и kx
              ├ Тип 4: Квадратное уравнение
              ├ Тип 5: Квадратное без свободного члена
              └ Тип 6: Разность квадратов
"""

from django.core.management.base import BaseCommand
from users.models import Course, Module, Lesson, Assignment, ProblemGenerator


# ──────────────────────────────────────────────────────────────────────────────
# Python-код генераторов
# ──────────────────────────────────────────────────────────────────────────────

GEN_LINEAR = '''\
from fractions import Fraction

def generate_task():
    x_frac = Fraction(random.randint(-70, 70), 10)
    x = float(x_frac)

    coeffs = [i for i in range(-5, 6) if i != 0]
    a = random.choice(coeffs)
    c = random.choice([i for i in coeffs if i != a])

    if random.random() < 0.3:
        d = 0
    else:
        d = random.randint(-20, 20)

    b_frac = (c - a) * x_frac + d
    if b_frac.denominator != 1:
        diff = (c - a) * x_frac
        found = False
        candidates = list(range(-20, 21))
        random.shuffle(candidates)
        for d_try in candidates:
            b_check = (c - a) * x_frac + d_try
            if b_check.denominator == 1:
                d = d_try
                b_frac = b_check
                found = True
                break
        if not found:
            x_frac = Fraction(random.randint(-7, 7))
            x = float(x_frac)
            d = random.randint(-20, 20)
            b_frac = (c - a) * x_frac + d

    b = int(b_frac)

    if x_frac.denominator == 1:
        answer_str = str(int(x_frac))
    else:
        answer_str = f"{x:.1f}".replace('.', ',')

    def format_side(coeff, free, swap):
        if coeff == 1:
            x_term = "x"
        elif coeff == -1:
            x_term = "-x"
        else:
            x_term = f"{coeff}x"
        if free == 0:
            return x_term
        if swap:
            if coeff == 1:
                return f"{free} + x"
            elif coeff == -1:
                return f"{free} - x"
            else:
                if coeff > 0:
                    return f"{free} + {coeff}x"
                else:
                    return f"{free} - {abs(coeff)}x"
        else:
            if free > 0:
                return f"{x_term} + {free}"
            else:
                return f"{x_term} - {abs(free)}"

    swap_left = random.choice([True, False])
    swap_right = random.choice([True, False])
    left = format_side(a, b, swap_left)
    right = format_side(c, d, swap_right)
    condition_text = f"Решите уравнение \\\\({left} = {right}\\\\)."
    return {"condition_text": condition_text, "correct_answer": answer_str}
'''

GEN_LINEAR_BRACKET = '''\
from fractions import Fraction

def generate_task():
    while True:
        x_frac = Fraction(random.randint(-70, 70), 10)
        a = random.choice([i for i in range(-5, 6) if i != 0])
        b = random.randint(-20, 20)
        c_frac = a * (x_frac - b)

        if abs(c_frac) > 20:
            continue

        if x_frac.denominator == 1:
            answer_str = str(int(x_frac))
        else:
            answer_str = f"{float(x_frac):.1f}".replace('.', ',')

        if c_frac.denominator == 1:
            c_str = str(int(c_frac))
        else:
            c_str = f"{float(c_frac):.1f}".replace('.', ',')

        if b > 0:
            x_minus_b = f"x - {b}"
        elif b < 0:
            x_minus_b = f"x + {abs(b)}"
        else:
            x_minus_b = "x"

        if a == 1:
            left = x_minus_b
        elif a == -1:
            if b == 0:
                left = "-x"
            else:
                left = f"-({x_minus_b})"
        else:
            if b == 0:
                left = f"{a}x"
            else:
                left = f"{a}({x_minus_b})"

        c_tex = c_str.replace(',', '{,}')
        condition_text = f"Решите уравнение \\\\({left} = {c_tex}\\\\)."
        return {"condition_text": condition_text, "correct_answer": answer_str}
'''

GEN_LINEAR_BRACKET_KX = '''\
from fractions import Fraction

def generate_task():
    while True:
        x_frac = Fraction(random.randint(-70, 70), 10)
        a = random.choice([i for i in range(-5, 6) if i != 0])
        b = random.randint(-20, 20)
        k = random.choice([i for i in range(-5, 6) if i != 0])
        k_left = random.choice([True, False])

        if k_left:
            net_coeff = a + k
        else:
            net_coeff = a - k

        if net_coeff == 0:
            continue

        if k_left:
            c_frac = a * (x_frac - b) + k * x_frac
        else:
            c_frac = a * (x_frac - b) - k * x_frac

        if abs(c_frac) > 20:
            continue
        if c_frac.denominator != 1:
            continue

        c = int(c_frac)

        if x_frac.denominator == 1:
            answer_str = str(int(x_frac))
        else:
            answer_str = f"{float(x_frac):.1f}".replace('.', ',')

        if b > 0:
            x_minus_b = f"x - {b}"
        elif b < 0:
            x_minus_b = f"x + {abs(b)}"
        else:
            x_minus_b = "x"

        if a == 1:
            bracket_part = x_minus_b
        elif a == -1:
            bracket_part = f"-({x_minus_b})" if b != 0 else "-x"
        else:
            bracket_part = f"{a}({x_minus_b})" if b != 0 else f"{a}x"

        if k == 1:
            kx_str = "+ x"
        elif k == -1:
            kx_str = "- x"
        elif k > 0:
            kx_str = f"+ {k}x"
        else:
            kx_str = f"- {abs(k)}x"

        if k_left:
            left = f"{bracket_part} {kx_str}"
            right = str(c)
        else:
            left = bracket_part
            right = f"{c} {kx_str}"

        condition_text = f"Решите уравнение \\\\({left} = {right}\\\\)."
        return {"condition_text": condition_text, "correct_answer": answer_str}
'''

GEN_QUADRATIC = '''\
def generate_task():
    r1 = random.randint(-20, 20)
    r2 = random.randint(-20, 20)
    b = -(r1 + r2)
    c = r1 * r2

    multiplier = 1
    if random.random() < 0.3:
        multiplier = random.choice([-5, -4, -3, -2, -1, 2, 3, 4, 5])

    a = 1 * multiplier
    b = b * multiplier
    c = c * multiplier

    ask_larger = random.choice([True, False])
    if ask_larger:
        answer = max(r1, r2)
        ask_text = "больший"
    else:
        answer = min(r1, r2)
        ask_text = "меньший"

    def format_equation(a, b, c):
        if a == 1:
            x2_part = "x^{2}"
        elif a == -1:
            x2_part = "-x^{2}"
        else:
            x2_part = f"{a}x^{{2}}"
        parts = [x2_part]
        if b > 0:
            parts.append(f"+ {b}x")
        elif b < 0:
            parts.append(f"- {abs(b)}x")
        if c > 0:
            parts.append(f"+ {c}")
        elif c < 0:
            parts.append(f"- {abs(c)}")
        return " ".join(parts) + " = 0"

    equation = format_equation(a, b, c)
    condition_text = (
        f"Найдите корни уравнения \\\\({equation}\\\\). "
        f"Если уравнение имеет более одного корня, "
        f"укажите {ask_text} из них."
    )
    return {"condition_text": condition_text, "correct_answer": str(answer)}
'''

GEN_QUADRATIC_NO_FREE = '''\
def generate_task():
    r = random.choice([i for i in range(-10, 11) if i != 0])
    a = random.randint(3, 15)
    b = a * r
    r1, r2 = 0, r

    ask_larger = random.choice([True, False])
    if ask_larger:
        answer = max(r1, r2)
        ask_text = "больший"
    else:
        answer = min(r1, r2)
        ask_text = "меньший"

    equation = f"{a}x^{{2}} = {b}x"
    condition_text = (
        f"Решите уравнение \\\\({equation}\\\\). "
        f"Если уравнение имеет более одного корня, "
        f"в ответ запишите {ask_text} из корней."
    )
    return {"condition_text": condition_text, "correct_answer": str(answer)}
'''

GEN_LINEAR_TWO_BRACKETS = '''\
from fractions import Fraction

def generate_task():
    while True:
        x_frac = Fraction(random.randint(-70, 70), 10)
        a = random.choice([i for i in range(-5, 6) if i != 0])
        b = random.randint(-20, 20)
        n = random.choice([i for i in range(-5, 6) if i != 0])
        m = random.randint(-20, 20)
        second_left = random.choice([True, False])

        if second_left:
            net_coeff = a + n
        else:
            net_coeff = a - n

        if net_coeff == 0:
            continue

        if second_left:
            c_frac = a * (x_frac - b) + n * (x_frac - m)
        else:
            c_frac = a * (x_frac - b) - n * (x_frac - m)

        if abs(c_frac) > 20:
            continue
        if c_frac.denominator != 1:
            continue

        c = int(c_frac)

        if x_frac.denominator == 1:
            answer_str = str(int(x_frac))
        else:
            answer_str = f"{float(x_frac):.1f}".replace('.', ',')

        def format_bracket(coeff, free):
            abs_coeff = abs(coeff)
            if free > 0:
                inner = f"x - {free}"
            elif free < 0:
                inner = f"x + {abs(free)}"
            else:
                inner = "x"
            if abs_coeff == 1:
                return f"({inner})" if free != 0 else "x"
            else:
                return f"{abs_coeff}({inner})" if free != 0 else f"{abs_coeff}x"

        def format_signed(coeff, free, is_first=False):
            bracket = format_bracket(coeff, free)
            if is_first:
                return f"-{bracket}" if coeff < 0 else bracket
            else:
                return f"- {bracket}" if coeff < 0 else f"+ {bracket}"

        first = format_signed(a, b, is_first=True)
        second = format_signed(n, m, is_first=False)

        if second_left:
            left = f"{first} {second}"
            right = str(c)
        else:
            left = first
            right = f"{c} {second}"

        condition_text = f"Решите уравнение \\\\({left} = {right}\\\\)."
        return {"condition_text": condition_text, "correct_answer": answer_str}
'''


GEN_QUADRATIC_DIFF_SQ = '''\
def generate_task():
    a = random.randint(1, 20)
    r1 = a
    r2 = -a

    ask_larger = random.choice([True, False])
    if ask_larger:
        answer = max(r1, r2)
        ask_text = "больший"
    else:
        answer = min(r1, r2)
        ask_text = "меньший"

    equation = f"x^{{2}} - {a**2} = 0"
    condition_text = (
        f"Найдите корни уравнения \\\\({equation}\\\\). "
        f"Если уравнение имеет более одного корня, "
        f"укажите {ask_text} из них."
    )
    return {"condition_text": condition_text, "correct_answer": str(answer)}
'''


PROTOTYPES = [
    ('linear_equation',              'Линейное уравнение',                        GEN_LINEAR),
    ('linear_bracket_equation',      'Уравнение со скобкой',                      GEN_LINEAR_BRACKET),
    ('linear_bracket_kx_equation',   'Уравнение со скобкой и kx',                 GEN_LINEAR_BRACKET_KX),
    ('linear_two_brackets_equation', 'Уравнение с двумя скобками',                GEN_LINEAR_TWO_BRACKETS),
    ('quadratic_equation',           'Квадратное уравнение',                      GEN_QUADRATIC),
    ('quadratic_no_free_term',       'Квадратное уравнение без свободного члена', GEN_QUADRATIC_NO_FREE),
    ('quadratic_difference_squares', 'Разность квадратов',                        GEN_QUADRATIC_DIFF_SQ),
]


class Command(BaseCommand):
    help = 'Создаёт «Задание 9» курса ОГЭ с 6 генераторами уравнений.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--clear', action='store_true',
            help='Удалить существующее «Задание 9» и пересоздать.',
        )

    def handle(self, *args, **opts):
        course = Course.objects.filter(slug='oge-maths').first()
        if not course:
            self.stdout.write(self.style.ERROR(
                'Курс ОГЭ (slug=oge-maths) не найден. Создайте его сначала.'
            ))
            return

        # Ищем модуль 'Первая часть' по имени, не first() по order — иначе с
        # появлением модуля 'Задания 1-5' (order=0) создавался дубль урока.
        module, _ = Module.objects.get_or_create(
            course=course, title='Первая часть',
            defaults={'order': 1, 'description': ''},
        )

        if opts['clear']:
            old = Lesson.objects.filter(module=module, title='Задание 9').first()
            if old:
                # Удаляем сначала генераторы, привязанные к assignments этого урока
                ProblemGenerator.objects.filter(
                    assignments__lesson=old
                ).delete()
                old.delete()
                self.stdout.write(self.style.WARNING('Старое «Задание 9» удалено.'))

        lesson, _ = Lesson.objects.get_or_create(
            module=module, title='Задание 9',
            defaults={'order': 9, 'lesson_type': 'practice'},
        )

        # Удаляем существующие assignments внутри этого урока, чтобы пересоздать
        existing_orders = {a.order: a for a in lesson.assignments.all()}

        for i, (key, title, code) in enumerate(PROTOTYPES, start=1):
            gen_name = f'OGE9: {title}'
            gen, _ = ProblemGenerator.objects.update_or_create(
                name=gen_name,
                defaults={
                    'generator_type': 'python_function',
                    'python_code': code,
                },
            )

            assign = existing_orders.get(i)
            if assign:
                # title не перезаписываем — мог быть переименован вручную.
                assign.description = f'Генератор: {key}'
                assign.problem_generator = gen
                assign.answer_type = 'decimal_input'
                assign.required_correct = 3
                assign.save()
            else:
                Assignment.objects.create(
                    lesson=lesson,
                    order=i,
                    title=title,
                    description=f'Генератор: {key}',
                    problem_generator=gen,
                    answer_type='decimal_input',
                    required_correct=3,
                )

        # Удаляем «лишние» прототипы (если их было больше 6)
        for order, a in existing_orders.items():
            if order > len(PROTOTYPES):
                a.delete()

        self.stdout.write(self.style.SUCCESS(
            f'Готово: «Задание 9» курса ОГЭ — {len(PROTOTYPES)} прототипов.'
        ))
