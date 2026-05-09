# -*- coding: utf-8 -*-
"""
Management command: наполнение «Задание 10» курса ОГЭ генераторами на вероятность.

Usage:
    python manage.py populate_oge10            # создать/обновить
    python manage.py populate_oge10 --clear    # удалить и пересоздать

Структура:
    Курс «ОГЭ» (slug=oge-maths)
      └ Модуль «Первая часть»
          └ Урок «Задание 10» (lesson_type='practice')
              ├ Тип 1: Билеты на экзамене
              ├ Тип 2: Фонарики
              ├ Тип 3: Ручка пишет хорошо
              ├ Тип 4: Ручки в магазине
              ├ Тип 5: Пазлы
              ├ Тип 6: Лыжники
              └ Тип 7: Такси
"""

from django.core.management.base import BaseCommand
from users.models import Course, Module, Lesson, Assignment, ProblemGenerator


# ──────────────────────────────────────────────────────────────────────────────
# Генераторы вероятностных задач
# ──────────────────────────────────────────────────────────────────────────────

GEN_EXAM = '''\
from fractions import Fraction

def generate_task():
    total = random.choice([10, 20, 25, 40, 50, 100])
    max_not = max(1, total // 3)
    not_learned = random.randint(1, max_not)
    learned = total - not_learned

    ask_learned = random.choice([True, False])
    if ask_learned:
        favorable = learned
        what = "выученный билет"
    else:
        favorable = not_learned
        what = "невыученный билет"

    frac = Fraction(favorable, total)
    decimal_str = f"{frac.numerator / frac.denominator:.6f}".rstrip('0').rstrip('.')

    names = ["Яша", "Саша", "Миша", "Коля", "Петя", "Дима", "Серёжа", "Антон"]
    name = random.choice(names)

    condition_text = (
        f"На экзамене {total} билетов, {name} не выучил "
        f"{not_learned} из них. Найдите вероятность того, что ему попадётся "
        f"{what}. Ответ дайте в виде десятичной дроби."
    )
    return {"condition_text": condition_text, "correct_answer": decimal_str}
'''

GEN_FLASHLIGHT = '''\
from fractions import Fraction

def generate_task():
    base_total = random.choice([10, 16, 20, 25, 32, 40, 50, 80, 100])
    base_broken = random.randint(1, min(10, base_total - 1))
    multiplier = random.choice([1, 2, 3, 4, 5, 6, 7, 8, 9, 10])
    total = base_total * multiplier
    broken = base_broken * multiplier
    working = total - broken

    ask_working = random.choice([True, False])
    if ask_working:
        favorable = working
        what = "окажется исправен"
    else:
        favorable = broken
        what = "окажется неисправен"

    frac = Fraction(favorable, total)
    decimal_value = frac.numerator / frac.denominator
    decimal_str = f"{decimal_value:.6f}".rstrip('0').rstrip('.')

    condition_text = (
        f"В среднем из {total} карманных фонариков, поступивших в продажу, "
        f"{broken} неисправных. Найдите вероятность того, что выбранный "
        f"наудачу в магазине фонарик {what}. "
        f"Ответ дайте в виде десятичной дроби."
    )
    return {"condition_text": condition_text, "correct_answer": decimal_str}
'''

GEN_PEN = '''\
def generate_task():
    bad = random.randint(1, 20)
    bad_str = f"0,{bad:02d}"
    good = 100 - bad
    good_value = good / 100
    good_str = f"{good_value:.6f}".rstrip('0').rstrip('.')

    condition_text = (
        f"Вероятность того, что новая шариковая ручка пишет плохо "
        f"(или не пишет), равна {bad_str}. Покупатель в магазине выбирает "
        f"одну шариковую ручку. Найдите вероятность того, что эта ручка "
        f"пишет хорошо. Ответ дайте в виде десятичной дроби."
    )
    return {"condition_text": condition_text, "correct_answer": good_str}
'''

GEN_PENS_SHOP = '''\
from fractions import Fraction

def generate_task():
    total = random.choice([40, 50, 80, 100, 200])
    color_pool = [
        ("красных",     "красной",      "красная"),
        ("синих",       "синей",        "синяя"),
        ("зелёных",     "зелёной",      "зелёная"),
        ("фиолетовых",  "фиолетовой",   "фиолетовая"),
        ("чёрных",      "чёрной",       "чёрная"),
        ("голубых",     "голубой",      "голубая"),
        ("оранжевых",   "оранжевой",    "оранжевая"),
    ]
    colors = random.sample(color_pool, 5)

    def pen_count(n, color):
        if n % 10 == 1 and n % 100 != 11:
            return f"{n} {color[2]}"
        else:
            return f"{n} {color[0]}"

    a = random.randint(1, total // 5)
    b = random.randint(1, total // 5)
    c = random.randint(1, total // 5)
    remainder = total - a - b - c
    if remainder % 2 != 0:
        if c < total // 5:
            c += 1
        else:
            c -= 1
        remainder = total - a - b - c
    if remainder <= 0:
        a, b, c = total // 6, total // 6, total // 6
        remainder = total - a - b - c
        if remainder % 2 != 0:
            c += 1
            remainder = total - a - b - c

    half = remainder // 2
    counts = [a, b, c, half, half]
    ask_indices = random.sample(range(5), 2)
    favorable = counts[ask_indices[0]] + counts[ask_indices[1]]

    frac = Fraction(favorable, total)
    decimal_str = f"{frac.numerator / frac.denominator:.6f}".rstrip('0').rstrip('.')

    listing = ", ".join(pen_count(counts[i], colors[i]) for i in range(3))
    listing += f", остальные {colors[3][0]} и {colors[4][0]}, их поровну"

    ask1 = colors[ask_indices[0]][1]
    ask2 = colors[ask_indices[1]][1]

    condition_text = (
        f"В магазине канцтоваров продаётся {total} ручек: {listing}. "
        f"Найдите вероятность того, что случайно выбранная ручка будет "
        f"{ask1} или {ask2}. "
        f"Ответ дайте в виде десятичной дроби."
    )
    return {"condition_text": condition_text, "correct_answer": decimal_str}
'''

GEN_PUZZLES = '''\
from fractions import Fraction

def generate_task():
    total = random.choice([10, 20, 25, 40, 50, 100])
    type_a_count = random.randint(1, total - 1)
    type_b_count = total - type_a_count

    themes = [
        ("с машинами",      "с видами городов"),
        ("с животными",     "с пейзажами"),
        ("с динозаврами",   "с замками"),
        ("со спортсменами", "с природой"),
        ("с самолётами",    "с морем"),
        ("с роботами",      "с цветами"),
    ]
    theme_a, theme_b = random.choice(themes)

    names = [
        ("Саша",   "Саше"),
        ("Миша",   "Мише"),
        ("Коля",   "Коле"),
        ("Петя",   "Пете"),
        ("Дима",   "Диме"),
        ("Серёжа", "Серёже"),
        ("Антон",  "Антону"),
        ("Маша",   "Маше"),
        ("Катя",   "Кате"),
        ("Аня",    "Ане"),
    ]
    name, name_dat = random.choice(names)

    ask_a = random.choice([True, False])
    if ask_a:
        favorable = type_a_count
        ask_theme = theme_a
    else:
        favorable = type_b_count
        ask_theme = theme_b

    frac = Fraction(favorable, total)
    decimal_str = f"{frac.numerator / frac.denominator:.6f}".rstrip('0').rstrip('.')

    condition_text = (
        f"Родительский комитет закупил {total} пазлов для подарков детям, "
        f"из них {type_a_count} {theme_a} и {type_b_count} {theme_b}. "
        f"Подарки распределяются случайным образом, среди получателей есть {name}. "
        f"Найдите вероятность того, что {name_dat} достанется пазл {ask_theme}. "
        f"Ответ дайте в виде десятичной дроби."
    )
    return {"condition_text": condition_text, "correct_answer": decimal_str}
'''

GEN_SKIERS = '''\
from fractions import Fraction

def generate_task():
    country_pool = [
        ("России",      "из России"),
        ("Норвегии",    "из Норвегии"),
        ("Швеции",      "из Швеции"),
        ("Финляндии",   "из Финляндии"),
        ("Дании",       "из Дании"),
        ("Германии",    "из Германии"),
        ("США",         "из США"),
        ("Великобритании", "из Великобритании"),
        ("Эстонии",     "из Эстонии"),
        ("Латвии",      "из Латвии"),
        ("Литвы",       "из Литвы"),
    ]
    chosen = random.sample(country_pool, 3)
    total = random.choice([8, 10, 16, 20, 25, 32, 40, 50])

    count_a = random.randint(1, total - 2)
    remaining = total - count_a
    count_b = random.randint(1, remaining - 1)
    count_c = remaining - count_b
    counts = [count_a, count_b, count_c]

    ask_indices = random.sample([0, 1, 2], 2)
    ask_indices.sort()
    third_index = [i for i in [0, 1, 2] if i not in ask_indices][0]
    favorable = counts[ask_indices[0]] + counts[ask_indices[1]]

    frac = Fraction(favorable, total)
    decimal_value = frac.numerator / frac.denominator
    decimal_str = f"{decimal_value:.6f}".rstrip('0').rstrip('.')

    def athlete_form(n):
        if n % 10 == 1 and n % 100 != 11:
            return f"{n} спортсмен"
        elif 2 <= n % 10 <= 4 and not (12 <= n % 100 <= 14):
            return f"{n} спортсмена"
        else:
            return f"{n} спортсменов"

    name_a = chosen[ask_indices[0]][0]
    name_b = chosen[ask_indices[1]][0]
    from_a = chosen[ask_indices[0]][1]
    from_b = chosen[ask_indices[1]][1]
    from_c = chosen[third_index][1]

    condition_text = (
        f"В лыжных гонках участвуют {athlete_form(counts[third_index])} {from_c}, "
        f"{athlete_form(counts[ask_indices[0]])} {from_a} "
        f"и {athlete_form(counts[ask_indices[1]])} {from_b}. "
        f"Порядок, в котором спортсмены стартуют, определяется жребием. "
        f"Найдите вероятность того, что первым будет стартовать спортсмен "
        f"{from_a} или {from_b}. "
        f"Ответ дайте в виде десятичной дроби."
    )
    return {"condition_text": condition_text, "correct_answer": decimal_str}
'''

GEN_TAXI = '''\
from fractions import Fraction

def generate_task():
    total = random.choice([8, 10, 16, 20, 25, 32, 40, 50])
    featured = random.randint(1, total - 2)
    remaining = total - featured
    split = random.randint(1, remaining - 1)
    second = split
    third = remaining - split

    colors = random.sample([
        "чёрный", "жёлтый", "зелёный", "белый", "синий", "красный"
    ], 3)

    ask_index = random.randint(0, 2)
    counts = [featured, second, third]
    ask_color = colors[ask_index]

    plural_map = {
        "чёрный":  ("чёрная", "чёрных",  "чёрных"),
        "жёлтый":  ("жёлтая", "жёлтых",  "жёлтых"),
        "зелёный": ("зелёная","зелёных", "зелёных"),
        "белый":   ("белая",  "белых",   "белых"),
        "синий":   ("синяя",  "синих",   "синих"),
        "красный": ("красная","красных", "красных"),
    }

    def color_form(color, n):
        one, few, many = plural_map[color]
        if n % 10 == 1 and n % 100 != 11:
            return f"{n} {one}"
        else:
            return f"{n} {many}"

    neuter_map = {
        "чёрный":  "чёрное",
        "жёлтый":  "жёлтое",
        "зелёный": "зелёное",
        "белый":   "белое",
        "синий":   "синее",
        "красный": "красное",
    }

    frac = Fraction(counts[ask_index], total)
    decimal_value = frac.numerator / frac.denominator
    decimal_str = f"{decimal_value:.6f}".rstrip('0').rstrip('.')

    condition_text = (
        f"В фирме такси в данный момент свободно {total} машин: "
        f"{color_form(colors[0], counts[0])}, "
        f"{color_form(colors[1], counts[1])} и "
        f"{color_form(colors[2], counts[2])}. "
        f"По вызову выехала одна из машин, случайно оказавшаяся ближе всего к заказчику. "
        f"Найдите вероятность того, что к нему приедет {neuter_map[ask_color]} такси. "
        f"Ответ дайте в виде десятичной дроби."
    )
    return {"condition_text": condition_text, "correct_answer": decimal_str}
'''


PROTOTYPES = [
    ('probability_exam',       'Билеты на экзамене',      GEN_EXAM),
    ('probability_flashlight', 'Фонарики',                GEN_FLASHLIGHT),
    ('probability_pen',        'Ручка пишет хорошо',      GEN_PEN),
    ('probability_pens_shop',  'Ручки в магазине',        GEN_PENS_SHOP),
    ('probability_puzzles',    'Пазлы детям',             GEN_PUZZLES),
    ('probability_skiers',     'Лыжники из разных стран', GEN_SKIERS),
    ('probability_taxi',       'Такси',                   GEN_TAXI),
]


class Command(BaseCommand):
    help = 'Создаёт «Задание 10» курса ОГЭ с 7 генераторами задач на вероятность.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--clear', action='store_true',
            help='Удалить существующее «Задание 10» и пересоздать.',
        )

    def handle(self, *args, **opts):
        course = Course.objects.filter(slug='oge-maths').first()
        if not course:
            self.stdout.write(self.style.ERROR(
                'Курс ОГЭ (slug=oge-maths) не найден.'
            ))
            return

        module = course.modules.order_by('order').first()
        if not module:
            module = Module.objects.create(course=course, order=1, title='Первая часть')

        if opts['clear']:
            old = Lesson.objects.filter(module=module, title='Задание 10').first()
            if old:
                ProblemGenerator.objects.filter(assignments__lesson=old).delete()
                old.delete()
                self.stdout.write(self.style.WARNING('Старое «Задание 10» удалено.'))

        lesson, created = Lesson.objects.get_or_create(
            module=module, title='Задание 10',
            defaults={'order': 10, 'lesson_type': 'practice'},
        )
        if not created and lesson.order != 10:
            lesson.order = 10
            lesson.save(update_fields=['order'])

        existing_orders = {a.order: a for a in lesson.assignments.all()}

        for i, (key, title, code) in enumerate(PROTOTYPES, start=1):
            gen_name = f'OGE10: {title}'
            gen, _ = ProblemGenerator.objects.update_or_create(
                name=gen_name,
                defaults={
                    'generator_type': 'python_function',
                    'python_code': code,
                },
            )

            assign = existing_orders.get(i)
            if assign:
                assign.title = title
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

        # Удаляем «лишние» прототипы (включая старый order=0 «10 чашки»)
        for order, a in existing_orders.items():
            if order < 1 or order > len(PROTOTYPES):
                a.delete()

        self.stdout.write(self.style.SUCCESS(
            f'Готово: «Задание 10» курса ОГЭ — {len(PROTOTYPES)} прототипов.'
        ))
