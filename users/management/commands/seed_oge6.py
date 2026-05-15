# -*- coding: utf-8 -*-
"""
Management command: создаёт 4 ProblemGenerator-а и Assignment-а под урок
«Задание 6» курса ОГЭ. Код генераторов inline в этом файле — внешних
файлов больше нет.

Usage:
    python manage.py seed_oge6
    python manage.py seed_oge6 --clear   # снести и пересоздать
"""

from django.core.management.base import BaseCommand
from django.db import transaction

from users.models import Course, Module, Lesson, ProblemGenerator, Assignment


# ──────────────────────────────────────────────────────────────────────────────
# Генераторы
# ──────────────────────────────────────────────────────────────────────────────

# Общая утилита: Fraction → строка с запятой, без хвостовых нулей.
DECIMAL_STR = '''
def decimal_str(f):
    if f.denominator == 1:
        return str(f.numerator)
    sign = '-' if f.numerator < 0 else ''
    num = abs(f.numerator); den = f.denominator
    a = b = 0; t = den
    while t % 2 == 0: t //= 2; a += 1
    while t % 5 == 0: t //= 5; b += 1
    if t != 1:
        return sign + f"{num/den:.6f}".rstrip('0').rstrip('.').replace('.', ',')
    target = max(a, b)
    pad_num = num * (10 ** target) // den
    s = str(pad_num).rjust(target + 1, '0')
    int_part = s[:-target] or '0'
    dec_part = s[-target:].rstrip('0')
    return sign + (int_part + ',' + dec_part if dec_part else int_part)
'''


GEN_T1_T2 = DECIMAL_STR + r'''

def generate_task():
    """
    №6 ОГЭ, Тип 1+2: a/b ± c/d.
    Берём две положительные обыкновенные дроби с «удобными» знаменателями
    (только множители 2 и 5), считаем результат — он автоматически
    конечная десятичная дробь.
    """
    NICE_DENOMS = [2, 4, 5, 10, 20, 25, 50]
    op = random.choice(['+', '-'])

    for _ in range(50):
        b = random.choice(NICE_DENOMS)
        d = random.choice(NICE_DENOMS)
        a = random.randint(1, 4 * b)
        c = random.randint(1, 4 * d)
        f1 = Fraction(a, b)
        f2 = Fraction(c, d)
        if f1.denominator == 1 or f2.denominator == 1:
            continue
        R = f1 + f2 if op == '+' else f1 - f2
        if R == 0:
            continue
        if abs(R.numerator) > 200:
            continue
        break
    else:
        f1 = Fraction(1, 2); f2 = Fraction(3, 10); R = f1 + f2; op = '+'

    def flatex(f):
        return rf"\dfrac{{{f.numerator}}}{{{f.denominator}}}"

    expression = f"{flatex(f1)} {op} {flatex(f2)}"
    return {
        "condition_text": rf"Найдите значение выражения ${expression}$.",
        "correct_answer": decimal_str(R),
    }
'''


GEN_T3_T4 = DECIMAL_STR + r'''

def generate_task():
    """
    №6 ОГЭ, Тип 3+4: a/b · c/d или a/b : c/d.
    Идём от ответа: фиксируем R с конечным десятичным представлением,
    подбираем первую дробь f1, считаем f2 = R/f1 (умножение)
    или f2 = f1/R (деление).
    """
    op = random.choice(['*', '/'])

    for _ in range(80):
        R_den = random.choice([1, 2, 4, 5, 10, 20, 50])
        R_num = random.randint(1, 80)
        R = Fraction(R_num, R_den)

        b = random.randint(2, 20)
        a = random.randint(1, 30)
        f1 = Fraction(a, b)

        if op == '*':
            f2 = R / f1
        else:
            f2 = f1 / R

        if f2 == 0: continue
        if abs(f2.numerator) > 80 or f2.denominator > 80: continue
        if f1.denominator == 1: continue
        if f2.denominator == 1: continue
        break
    else:
        f1 = Fraction(3, 5); f2 = Fraction(7, 4); op = '*'; R = f1 * f2

    def flatex(f):
        return rf"\dfrac{{{f.numerator}}}{{{f.denominator}}}" if f.denominator > 1 else str(f.numerator)

    op_latex = r"\cdot" if op == '*' else ":"
    expression = f"{flatex(f1)} {op_latex} {flatex(f2)}"
    return {
        "condition_text": rf"Найдите значение выражения ${expression}$.",
        "correct_answer": decimal_str(R),
    }
'''


GEN_T5_T6 = DECIMAL_STR + r'''

def generate_task():
    """
    №6 ОГЭ, Тип 5+6: десятичная ± десятичная.
    Берём a, b ∈ [1.1, 9.9] с одним знаком после запятой (исключая целые),
    считаем R = a ± b.
    """
    op = random.choice(['+', '-'])
    for _ in range(50):
        a_int = random.randint(11, 99)
        b_int = random.randint(11, 99)
        if a_int % 10 == 0 or b_int % 10 == 0:
            continue
        a = Fraction(a_int, 10)
        b = Fraction(b_int, 10)
        R = a + b if op == '+' else a - b
        if R == 0:
            continue
        break
    else:
        a = Fraction(56, 10); b = Fraction(38, 10); R = a + b; op = '+'

    expression = f"{decimal_str(a)} {op} {decimal_str(b)}"
    return {
        "condition_text": rf"Найдите значение выражения ${expression}$.",
        "correct_answer": decimal_str(R),
    }
'''


GEN_T7_T8 = DECIMAL_STR + r'''

def generate_task():
    """
    №6 ОГЭ, Тип 7+8: десятичная · десятичная или десятичная : десятичная.

    Умножение: a, b — оба с одной цифрой после запятой, R = a·b.
    Деление: ответ R и делитель b — десятичные ≤2 знаков (берём целое из
    [1, 999] и делим на 100). Делимое a = R·b — может иметь до 4 цифр после
    запятой. Ответ — произвольная десятичная дробь (возможны и целые случаи).
    """
    op = random.choice(['*', '/'])

    if op == '*':
        for _ in range(40):
            a_int = random.randint(11, 99)
            b_int = random.randint(11, 99)
            if a_int % 10 == 0 or b_int % 10 == 0:
                continue
            a = Fraction(a_int, 10)
            b = Fraction(b_int, 10)
            R = a * b
            break
        op_latex = r"\cdot"
    else:
        for _ in range(80):
            R_int = random.randint(11, 999)
            b_int = random.randint(11, 999)
            # Пропускаем R = 1 и b = 1 (тривиально).
            if R_int == 100 or b_int == 100:
                continue
            R = Fraction(R_int, 100)
            b = Fraction(b_int, 100)
            a = R * b
            # Масштаб делимого: 0,1 ≤ a ≤ 50.
            if a < Fraction(1, 10) or a > Fraction(50):
                continue
            break
        else:
            R = Fraction(36, 10); b = Fraction(25, 10); a = R * b
        op_latex = ":"

    expression = f"{decimal_str(a)} {op_latex} {decimal_str(b)}"
    return {
        "condition_text": rf"Найдите значение выражения ${expression}$.",
        "correct_answer": decimal_str(R),
    }
'''


PROTOTYPES = [
    # (order, code, gen_name, assignment_title)
    (1, GEN_T1_T2, 'OGE6: Тип 1+2 — обыкн. дроби ±',   'Сложение и вычитание обыкновенных дробей'),
    (2, GEN_T3_T4, 'OGE6: Тип 3+4 — обыкн. дроби ·/:', 'Умножение и деление обыкновенных дробей'),
    (3, GEN_T5_T6, 'OGE6: Тип 5+6 — десятичные ±',     'Сложение и вычитание десятичных дробей'),
    (4, GEN_T7_T8, 'OGE6: Тип 7+8 — десятичные ·/:',   'Умножение и деление десятичных дробей'),
]


# ──────────────────────────────────────────────────────────────────────────────
# Команда
# ──────────────────────────────────────────────────────────────────────────────


class Command(BaseCommand):
    help = 'Создаёт 4 ProblemGenerator-а и Assignment-а под урок «Задание 6» курса ОГЭ.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--clear', action='store_true',
            help='Удалить существующее «Задание 6» и пересоздать.',
        )

    @transaction.atomic
    def handle(self, *args, **opts):
        course = Course.objects.filter(slug='oge-maths').first()
        if not course:
            self.stdout.write(self.style.ERROR(
                'Курс ОГЭ (slug=oge-maths) не найден.'
            ))
            return

        # Ищем модуль 'Первая часть' по имени, не first() по order — иначе с
        # появлением модуля 'Задания 1-5' (order=0) создавался дубль урока.
        module, _ = Module.objects.get_or_create(
            course=course, title='Первая часть',
            defaults={'order': 1, 'description': ''},
        )

        if opts['clear']:
            old = Lesson.objects.filter(module=module, title='Задание 6').first()
            if old:
                ProblemGenerator.objects.filter(assignments__lesson=old).delete()
                old.delete()
                self.stdout.write(self.style.WARNING('Старое «Задание 6» удалено.'))

        lesson, created = Lesson.objects.get_or_create(
            module=module, title='Задание 6',
            defaults={'order': 6, 'lesson_type': 'practice'},
        )
        if not created and lesson.order != 6:
            lesson.order = 6
            lesson.save(update_fields=['order'])
        if created:
            self.stdout.write(self.style.SUCCESS(f'Урок создан: {lesson.title}'))

        # Поиск Assignment по (lesson, order) — title мог быть переименован
        # вручную, поэтому по нему искать нельзя (иначе плодим дубли).
        existing_by_order = {a.order: a for a in lesson.assignments.all()}

        for order, code, gen_name, asg_title in PROTOTYPES:
            generator, _ = ProblemGenerator.objects.update_or_create(
                name=gen_name,
                defaults={
                    'generator_type': 'python_function',
                    'python_code': code,
                    'config': {},
                },
            )

            assign = existing_by_order.get(order)
            if assign:
                # title не перезаписываем — мог быть переименован.
                assign.problem_generator = generator
                assign.assignment_type = 'test'
                assign.answer_type = 'decimal_input'
                assign.required_correct = 3
                assign.save()
                shown_title = assign.title
            else:
                Assignment.objects.create(
                    lesson=lesson,
                    order=order,
                    title=asg_title,
                    description='',
                    assignment_type='test',
                    answer_type='decimal_input',
                    required_correct=3,
                    problem_generator=generator,
                )
                shown_title = asg_title

            self.stdout.write(self.style.SUCCESS(f'  [{order}] {shown_title} → {gen_name}'))

        self.stdout.write(self.style.SUCCESS(
            f'\nГотово: «Задание 6» курса ОГЭ — {len(PROTOTYPES)} прототипов.'
        ))
