# -*- coding: utf-8 -*-
"""
Management command: создаёт 8 ProblemGenerator-ов и Assignment-ов под урок
«Задание 12» курса ОГЭ. Тема — «Расчёты по формулам».

Код генераторов inline в этом файле — внешних файлов больше нет.

Usage:
    python manage.py seed_oge12
    python manage.py seed_oge12 --clear   # снести и пересоздать
"""

from django.core.management.base import BaseCommand
from django.db import transaction

from users.models import Course, Module, Lesson, ProblemGenerator, Assignment


# ──────────────────────────────────────────────────────────────────────────────
# Код генераторов
# ──────────────────────────────────────────────────────────────────────────────


GEN_T1_T2 = r'''
import random
from fractions import Fraction


def decimal_str(f):
    if f.denominator == 1: return str(f.numerator)
    sign = '-' if f.numerator < 0 else ''
    num = abs(f.numerator); den = f.denominator
    a = b = 0; t = den
    while t % 2 == 0: t //= 2; a += 1
    while t % 5 == 0: t //= 5; b += 1
    if t != 1: return sign + f"{num/den:.6f}".rstrip('0').rstrip('.').replace('.', ',')
    target = max(a, b)
    pad = num * (10**target) // den
    s = str(pad).rjust(target+1, '0')
    ip = s[:-target] or '0'
    dp = s[-target:].rstrip('0')
    return sign + (ip + ',' + dp if dp else ip)


def degree_word(n_str):
    """n_str — строка вида '15' или '-31' или '5,4'. Возвращает «градус/градуса/градусов»."""
    if ',' in n_str:
        return "градуса"  # для дробных — обычно «градуса»
    n = abs(int(n_str.replace('−', '-')))
    if n % 100 in (11, 12, 13, 14):
        return "градусов"
    last = n % 10
    if last == 1: return "градус"
    if last in (2, 3, 4): return "градуса"
    return "градусов"


def generate_task():
    """
    №12 ОГЭ, объединённый Тип 1+2: перевод температур F↔C.
    Раздвоение: F→C (целые tF, tC) или C→F (tC целое, tF — десятичный с 1 знаком).
    """
    direction = random.choice(['F_to_C', 'C_to_F'])

    if direction == 'F_to_C':
        # Идём от ответа: tC = 5k, tF = 32 + 9k → оба целые
        k = random.choice([n for n in range(-13, 18) if n != 0])
        tF = 32 + 9 * k
        tC = 5 * k
        tF_str = decimal_str(Fraction(tF))
        text = (
            rf"Перевести значение температуры по шкале Фаренгейта в шкалу Цельсия "
            rf"позволяет формула $t_C = \dfrac{{5}}{{9}}(t_F - 32)$, где $t_C$ — "
            rf"температура в градусах Цельсия, $t_F$ — температура в градусах Фаренгейта. "
            rf"Скольким градусам по шкале Цельсия соответствует {tF_str} {degree_word(tF_str)} "
            rf"по шкале Фаренгейта?"
        )
        answer = decimal_str(Fraction(tC))
    else:
        # tC любое целое (можно не кратно 5). Тогда tF = 1.8·tC + 32 — десятичная с 1 знаком.
        tC = random.choice([n for n in range(-50, 51) if n != 0])
        tF_frac = Fraction(18, 10) * tC + 32
        tC_str = decimal_str(Fraction(tC))
        text = (
            rf"Чтобы перевести значение температуры по шкале Цельсия в шкалу Фаренгейта, "
            rf"пользуются формулой $t_F = 1{{,}}8 \cdot t_C + 32$, где $t_C$ — "
            rf"температура в градусах Цельсия, $t_F$ — температура в градусах Фаренгейта. "
            rf"Скольким градусам по шкале Фаренгейта соответствует {tC_str} {degree_word(tC_str)} "
            rf"по шкале Цельсия?"
        )
        answer = decimal_str(tF_frac)

    return {"condition_text": text, "correct_answer": answer}


if __name__ == "__main__":
    random.seed(0)
    for i in range(6):
        t = generate_task()
        print(f"[{i+1}] {t['condition_text']}\n     ответ = {t['correct_answer']}\n")
'''


GEN_T3 = r'''
import random


def generate_task():
    """№12 ОГЭ, Тип 3: P = I²R, найти R."""
    I = random.randint(3, 12)
    R = random.randint(2, 15)
    P = I * I * R
    text = (
        rf"Мощность постоянного тока (в ваттах) вычисляется по формуле $P = I^{{2}}R$, "
        rf"где $I$ — сила тока (в амперах), $R$ — сопротивление (в омах). Пользуясь "
        rf"этой формулой, найдите сопротивление $R$, если мощность составляет {P} Вт, "
        rf"а сила тока равна {I} А. Ответ дайте в омах."
    )
    return {"condition_text": text, "correct_answer": str(R)}


if __name__ == "__main__":
    random.seed(0)
    for i in range(4):
        t = generate_task()
        print(f"[{i+1}] {t['condition_text'][:200]}...\n     ответ = {t['correct_answer']}\n")
'''


GEN_T4 = r'''
import random


def generate_task():
    """№12 ОГЭ, Тип 4: a = ω²·R, найти R. ω и R целые."""
    omega = random.randint(2, 10)
    R = random.randint(2, 15)
    a = omega * omega * R
    text = (
        rf"Центростремительное ускорение при движении по окружности (в м/с²) "
        rf"вычисляется по формуле $a = \omega^{{2}}R$, где $\omega$ — угловая "
        rf"скорость (в с⁻¹), $R$ — радиус окружности (в метрах). Пользуясь этой "
        rf"формулой, найдите радиус $R$, если угловая скорость равна {omega} с⁻¹, "
        rf"а центростремительное ускорение равно {a} м/с². Ответ дайте в метрах."
    )
    return {"condition_text": text, "correct_answer": str(R)}


if __name__ == "__main__":
    random.seed(0)
    for i in range(4):
        t = generate_task()
        print(f"[{i+1}] {t['condition_text'][:200]}...\n     ответ = {t['correct_answer']}\n")
'''


GEN_T5 = r'''
import random
from fractions import Fraction


def decimal_str(f):
    if f.denominator == 1: return str(f.numerator)
    sign = '-' if f.numerator < 0 else ''
    num = abs(f.numerator); den = f.denominator
    a = b = 0; t = den
    while t % 2 == 0: t //= 2; a += 1
    while t % 5 == 0: t //= 5; b += 1
    if t != 1: return sign + f"{num/den:.6f}".rstrip('0').rstrip('.').replace('.', ',')
    target = max(a, b)
    pad = num * (10**target) // den
    s = str(pad).rjust(target+1, '0')
    ip = s[:-target] or '0'
    dp = s[-target:].rstrip('0')
    return sign + (ip + ',' + dp if dp else ip)


def generate_task():
    """№12 ОГЭ, Тип 5: S = d1·d2·sin(α)/2, найти d1.
       sin α — десятичная дробь с одной цифрой после запятой."""
    sin_int = random.randint(1, 9)         # sin α = 0,1 .. 0,9
    sin_a = Fraction(sin_int, 10)
    d1 = random.randint(3, 25)
    d2 = random.randint(4, 25)
    S = Fraction(d1 * d2) * sin_a / 2
    text = (
        rf"Площадь четырёхугольника можно вычислить по формуле "
        rf"$S = \dfrac{{d_1 \cdot d_2 \sin \alpha}}{{2}}$, где $d_1$ и $d_2$ — "
        rf"длины диагоналей четырёхугольника, $\alpha$ — угол между диагоналями. "
        rf"Пользуясь этой формулой, найдите длину диагонали $d_1$, если $d_2 = {d2}$, "
        rf"$\sin \alpha = {decimal_str(sin_a)}$, а $S = {decimal_str(S)}$."
    )
    return {"condition_text": text, "correct_answer": str(d1)}


if __name__ == "__main__":
    random.seed(0)
    for i in range(4):
        t = generate_task()
        print(f"[{i+1}] {t['condition_text'][:300]}...\n     ответ = {t['correct_answer']}\n")
'''


GEN_T6 = r'''
import random
from fractions import Fraction


def decimal_str(f):
    if f.denominator == 1: return str(f.numerator)
    sign = '-' if f.numerator < 0 else ''
    num = abs(f.numerator); den = f.denominator
    a = b = 0; t = den
    while t % 2 == 0: t //= 2; a += 1
    while t % 5 == 0: t //= 5; b += 1
    if t != 1: return sign + f"{num/den:.6f}".rstrip('0').rstrip('.').replace('.', ',')
    target = max(a, b)
    pad = num * (10**target) // den
    s = str(pad).rjust(target+1, '0')
    ip = s[:-target] or '0'
    dp = s[-target:].rstrip('0')
    return sign + (ip + ',' + dp if dp else ip)


def generate_task():
    """№12 ОГЭ, Тип 6: P = mgh, найти m. g = 9,8."""
    m = random.randint(2, 50)
    h = random.randint(2, 30)
    g = Fraction(98, 10)
    P = Fraction(m) * g * h
    text = (
        rf"Если тело массой $m$ кг подвешено на высоте $h$ м над горизонтальной "
        rf"поверхностью земли, то его потенциальная энергия (в джоулях) вычисляется "
        rf"по формуле $P = mgh$, где $g = 9{{,}}8$ м/с² — ускорение свободного "
        rf"падения. Найдите массу тела, подвешенного на высоте {h} м над поверхностью "
        rf"земли, если его потенциальная энергия равна {decimal_str(P)} джоулям. "
        rf"Ответ дайте в килограммах."
    )
    return {"condition_text": text, "correct_answer": str(m)}


if __name__ == "__main__":
    random.seed(0)
    for i in range(4):
        t = generate_task()
        print(f"[{i+1}] {t['condition_text'][:300]}...\n     ответ = {t['correct_answer']}\n")
'''


GEN_T7 = r'''
import random
from fractions import Fraction


def decimal_str(f):
    if f.denominator == 1: return str(f.numerator)
    sign = '-' if f.numerator < 0 else ''
    num = abs(f.numerator); den = f.denominator
    a = b = 0; t = den
    while t % 2 == 0: t //= 2; a += 1
    while t % 5 == 0: t //= 5; b += 1
    if t != 1: return sign + f"{num/den:.6f}".rstrip('0').rstrip('.').replace('.', ',')
    target = max(a, b)
    pad = num * (10**target) // den
    s = str(pad).rjust(target+1, '0')
    ip = s[:-target] or '0'
    dp = s[-target:].rstrip('0')
    return sign + (ip + ',' + dp if dp else ip)


def generate_task():
    """№12 ОГЭ, Тип 7: E = mv²/2, найти v. m, v целые. E может быть нецелым."""
    v = random.randint(5, 30)
    m = random.choice([500, 1000, 1200, 1500, 2000, 2400, 3000, 3500])
    E = Fraction(m * v * v, 2)
    text = (
        rf"Кинетическая энергия тела массой $m$ кг, двигающегося со скоростью $v$ м/с, "
        rf"вычисляется по формуле $E = \dfrac{{mv^{{2}}}}{{2}}$ и измеряется в джоулях "
        rf"(Дж). Известно, что автомобиль массой {m} кг обладает кинетической энергией "
        rf"{decimal_str(E)} джоулей. Найдите скорость этого автомобиля в метрах в секунду."
    )
    return {"condition_text": text, "correct_answer": str(v)}


if __name__ == "__main__":
    random.seed(0)
    for i in range(4):
        t = generate_task()
        print(f"[{i+1}] {t['condition_text'][:300]}...\n     ответ = {t['correct_answer']}\n")
'''


GEN_T8 = r'''
import random
from fractions import Fraction


def decimal_str(f):
    if f.denominator == 1: return str(f.numerator)
    sign = '-' if f.numerator < 0 else ''
    num = abs(f.numerator); den = f.denominator
    a = b = 0; t = den
    while t % 2 == 0: t //= 2; a += 1
    while t % 5 == 0: t //= 5; b += 1
    if t != 1: return sign + f"{num/den:.6f}".rstrip('0').rstrip('.').replace('.', ',')
    target = max(a, b)
    pad = num * (10**target) // den
    s = str(pad).rjust(target+1, '0')
    ip = s[:-target] or '0'
    dp = s[-target:].rstrip('0')
    return sign + (ip + ',' + dp if dp else ip)


def generate_task():
    """№12 ОГЭ, Тип 8: F = ρgV. ρ=1000, g=9,8. V — десятичная ≤ 5 с до 2 знаков."""
    V_int = random.randint(1, 500)         # V = V_int/100, ∈ [0.01, 5.00]
    V = Fraction(V_int, 100)
    F = V * 9800
    text = (
        rf"Сила Архимеда, выталкивающая на поверхность погружённое в воду тело, "
        rf"вычисляется по формуле $F = \rho g V$, где $\rho = 1000$ кг/м³ — плотность "
        rf"воды, $g = 9{{,}}8$ м/с² — ускорение свободного падения, а $V$ — объём "
        rf"тела в кубических метрах. Сила $F$ измеряется в ньютонах. Найдите силу "
        rf"Архимеда, действующую на погружённое в воду тело объёмом "
        rf"{decimal_str(V)} куб. м. Ответ дайте в ньютонах."
    )
    return {"condition_text": text, "correct_answer": decimal_str(F)}


if __name__ == "__main__":
    random.seed(0)
    for i in range(4):
        t = generate_task()
        print(f"[{i+1}] {t['condition_text'][:300]}...\n     ответ = {t['correct_answer']}\n")
'''


GEN_T9_T10 = r'''
import random


def generate_task():
    """№12 ОГЭ, объединённый Тип 9+10: C = a + b·n. Линейная стоимость колодца."""
    FIRMS = [
        ("Чистая вода", 6500, 4000),
        ("Родник",      6000, 4100),
        ("Источник",    7000, 3800),
        ("Колодезь",    5500, 4200),
        ("Артезианка",  8000, 3900),
    ]
    firm, base, per = random.choice(FIRMS)
    n = random.randint(3, 25)
    C = base + per * n
    text = (
        rf"В фирме «{firm}» стоимость (в рублях) колодца из железобетонных колец "
        rf"рассчитывается по формуле $C = {base} + {per}n$, где $n$ — число колец, "
        rf"установленных в колодце. Пользуясь этой формулой, рассчитайте стоимость "
        rf"колодца из {n} колец. Ответ дайте в рублях."
    )
    return {"condition_text": text, "correct_answer": str(C)}


if __name__ == "__main__":
    random.seed(0)
    for i in range(4):
        t = generate_task()
        print(f"[{i+1}] {t['condition_text']}\n     ответ = {t['correct_answer']}\n")
'''


# ──────────────────────────────────────────────────────────────────────────────
# Прототипы
# ──────────────────────────────────────────────────────────────────────────────

PROTOTYPES = [
    # (order, gen_name, asg_title, code)
    (1, 'OGE12: Тип 1+2 — F ↔ C', 'Перевод температур (F↔C)', GEN_T1_T2),
    (2, 'OGE12: Тип 3 — мощность', 'Мощность тока (P = I²R)', GEN_T3),
    (3, 'OGE12: Тип 4 — ускорение', 'Центростремительное ускорение (a = ω²R)', GEN_T4),
    (4, 'OGE12: Тип 5 — площадь', 'Площадь четырёхугольника', GEN_T5),
    (5, 'OGE12: Тип 6 — потенц. энергия', 'Потенциальная энергия (P = mgh)', GEN_T6),
    (6, 'OGE12: Тип 7 — кинет. энергия', 'Кинетическая энергия (E = mv²/2)', GEN_T7),
    (7, 'OGE12: Тип 8 — Архимед', 'Сила Архимеда (F = ρgV)', GEN_T8),
    (8, 'OGE12: Тип 9+10 — колодец', 'Стоимость колодца (C = a + b·n)', GEN_T9_T10),
]


class Command(BaseCommand):
    help = 'Создаёт «Задание 12» курса ОГЭ с 8 генераторами на расчёты по формулам.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--clear', action='store_true',
            help='Удалить существующее «Задание 12» и пересоздать.',
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
            old = Lesson.objects.filter(module=module, title='Задание 12').first()
            if old:
                ProblemGenerator.objects.filter(assignments__lesson=old).delete()
                old.delete()
                self.stdout.write(self.style.WARNING('Старое «Задание 12» удалено.'))

        lesson, created = Lesson.objects.get_or_create(
            module=module, title='Задание 12',
            defaults={'order': 12, 'lesson_type': 'practice'},
        )
        if not created and lesson.order != 12:
            lesson.order = 12
            lesson.save(update_fields=['order'])
        if created:
            self.stdout.write(self.style.SUCCESS(f'Урок создан: {lesson.title}'))

        # Поиск Assignment по (lesson, order) — title мог быть переименован
        # вручную (например, в «Тип N»), поэтому по нему искать нельзя.
        existing_by_order = {a.order: a for a in lesson.assignments.all()}

        for order, gen_name, asg_title, code in PROTOTYPES:
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
                # Не перезаписываем title — мог быть переименован.
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

            self.stdout.write(self.style.SUCCESS(f'  + [{order}] {shown_title}'))

        self.stdout.write(self.style.SUCCESS(
            f'\nГотово: «Задание 12» курса ОГЭ — {len(PROTOTYPES)} прототипов.'
        ))
