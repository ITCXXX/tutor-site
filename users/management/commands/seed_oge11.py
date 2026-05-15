# -*- coding: utf-8 -*-
"""
Management command: создаёт 4 ProblemGenerator-а и Assignment-а под урок
«Задание 11» курса ОГЭ. Тема — «Графики функций» (соответствие).

Архитектура (по образцу Школково):
    G1. LINEAR_SIGNS    — знаки k, b у прямой y=kx+b (Типы 1+2 объединены)
    G2. LINEAR_MATCH    — формула прямой ↔ график; k или b может быть 0 (Типы 3-5)
    G3. PARABOLA_SIGNS  — знаки a, c у параболы y=ax²+bx+c (Типы 6+7)
    G4. MIXED_MATCH     — смешанные (прямая + парабола + гипербола, варианты 2+1) (Типы 8+9)

Каждый генератор рандомизирует:
    - direction:  кто слева (А,Б,В), а кто справа (1,2,3) — знаки/формулы vs графики
    - grid:       мелкая сетка 1×1 с подписями осей включается или нет

Usage:
    python manage.py seed_oge11
    python manage.py seed_oge11 --clear
"""

from django.core.management.base import BaseCommand
from django.db import transaction

from users.models import Course, Module, Lesson, ProblemGenerator, Assignment


# ──────────────────────────────────────────────────────────────────────────────
# PLOTTER — общие SVG-хелперы и форматтеры формул
# ──────────────────────────────────────────────────────────────────────────────

PLOTTER = r'''
import random


# ─── Форматирование формул ───────────────────────────────────────────────────

def _minus(n):
    """Заменяет ASCII '-' на математический минус '−'."""
    return str(n).replace("-", "−")


def fmt_linear(k, b):
    """y = kx + b. Поддерживает k=0 (y=const) и b=0 (y=kx)."""
    if k == 0:
        return f"y = {_minus(b)}"
    if k == 1:
        kx = "x"
    elif k == -1:
        kx = "−x"
    else:
        kx = _minus(k) + "x"
    if b == 0:
        return f"y = {kx}"
    if b > 0:
        return f"y = {kx} + {b}"
    return f"y = {kx} − {-b}"


def fmt_parabola(a, b, c):
    """y = ax² + bx + c."""
    parts = []
    if a == 1:
        parts.append("x²")
    elif a == -1:
        parts.append("−x²")
    elif a != 0:
        parts.append(_minus(a) + "x²")
    if b == 1:
        parts.append(" + x")
    elif b == -1:
        parts.append(" − x")
    elif b > 0:
        parts.append(f" + {b}x")
    elif b < 0:
        parts.append(f" − {-b}x")
    if c > 0:
        parts.append(f" + {c}")
    elif c < 0:
        parts.append(f" − {-c}")
    return "y = " + ("".join(parts) if parts else "0")


def fmt_hyperbola(k):
    """y = k/x."""
    if k > 0:
        return f"y = {k}/x"
    return f"y = −{-k}/x"


def fmt_signs_linear(sk, sb):
    """e.g. 'k > 0, b > 0'."""
    op_k = ">" if sk > 0 else "<"
    op_b = ">" if sb > 0 else "<"
    return f"k {op_k} 0, b {op_b} 0"


def fmt_signs_parabola(sa, sc):
    """e.g. 'a > 0, c < 0'."""
    op_a = ">" if sa > 0 else "<"
    op_c = ">" if sc > 0 else "<"
    return f"a {op_a} 0, c {op_c} 0"


# ─── SVG: координатные оси + опциональная сетка ──────────────────────────────

def _svg_axes(L=6, grid=False):
    """Возвращает (head, body). Математические координаты переводятся в SVG
    через инверсию Y (без parent flip — текст не зеркалится)."""
    e = []
    if grid:
        for i in range(-L, L + 1):
            if i == 0:
                continue
            e.append('<line x1="' + str(i) + '" y1="' + str(-L) + '" x2="' + str(i) + '" y2="' + str(L) + '" stroke="#ddd" stroke-width="0.04"/>')
            e.append('<line x1="' + str(-L) + '" y1="' + str(-i) + '" x2="' + str(L) + '" y2="' + str(-i) + '" stroke="#ddd" stroke-width="0.04"/>')
    e.append('<line x1="' + str(-L) + '" y1="0" x2="' + str(L) + '" y2="0" stroke="#000" stroke-width="0.06"/>')
    e.append('<line x1="0" y1="' + str(-L) + '" x2="0" y2="' + str(L) + '" stroke="#000" stroke-width="0.06"/>')
    e.append('<polygon points="' + str(L) + ',0 ' + str(L - 0.3) + ',0.2 ' + str(L - 0.3) + ',-0.2" fill="#000"/>')
    e.append('<polygon points="0,' + str(-L) + ' 0.2,' + str(-L + 0.3) + ' -0.2,' + str(-L + 0.3) + '" fill="#000"/>')
    e.append('<text x="' + str(L + 0.4) + '" y="0.45" font-size="0.6" fill="#000">x</text>')
    e.append('<text x="0.3" y="' + str(-L + 0.1) + '" font-size="0.6" fill="#000">y</text>')
    if grid:
        for i in range(-L + 1, L):
            if i == 0:
                continue
            label = str(i) if i > 0 else "−" + str(-i)
            e.append('<text x="' + str(i) + '" y="0.65" font-size="0.45" fill="#666" text-anchor="middle">' + label + '</text>')
            e.append('<text x="-0.2" y="' + str(-i + 0.16) + '" font-size="0.45" fill="#666" text-anchor="end">' + label + '</text>')
    head = (
        '<svg xmlns="http://www.w3.org/2000/svg" '
        'viewBox="' + str(-L - 1) + ' ' + str(-L - 1) + ' ' + str(2 * L + 2) + ' ' + str(2 * L + 2) + '" '
        'width="180" height="180" '
        'style="display:inline-block;margin:4px;border:1px solid #ddd;background:#fff;border-radius:6px">'
    )
    return head, "".join(e)


def plot_linear(k, b, grid=False, L=6):
    head, body = _svg_axes(L, grid)
    pts = []
    for i in range(-L * 20, L * 20 + 1):
        x = i / 20.0
        y = k * x + b
        if -L <= y <= L:
            pts.append(f"{x:.3f},{-y:.3f}")
    if len(pts) >= 2:
        body += '<polyline points="' + " ".join(pts) + '" fill="none" stroke="#c0392b" stroke-width="0.13"/>'
    return head + body + "</svg>"


def plot_parabola(a, b, c, grid=False, L=6):
    head, body = _svg_axes(L, grid)
    segments = []
    cur = []
    for i in range(-L * 30, L * 30 + 1):
        x = i / 30.0
        y = a * x * x + b * x + c
        if -L <= y <= L:
            cur.append(f"{x:.3f},{-y:.3f}")
        else:
            if cur:
                segments.append(cur)
            cur = []
    if cur:
        segments.append(cur)
    for seg in segments:
        if len(seg) >= 2:
            body += '<polyline points="' + " ".join(seg) + '" fill="none" stroke="#c0392b" stroke-width="0.13"/>'
    return head + body + "</svg>"


def plot_hyperbola(k, grid=False, L=6):
    head, body = _svg_axes(L, grid)
    right = []
    for i in range(1, L * 40 + 1):
        x = i / 40.0
        if abs(x) < 0.15:
            continue
        y = k / x
        if -L <= y <= L:
            right.append(f"{x:.3f},{-y:.3f}")
    left = []
    for i in range(1, L * 40 + 1):
        x = -i / 40.0
        if abs(x) < 0.15:
            continue
        y = k / x
        if -L <= y <= L:
            left.append(f"{x:.3f},{-y:.3f}")
    if len(right) >= 2:
        body += '<polyline points="' + " ".join(right) + '" fill="none" stroke="#c0392b" stroke-width="0.13"/>'
    if len(left) >= 2:
        body += '<polyline points="' + " ".join(left) + '" fill="none" stroke="#c0392b" stroke-width="0.13"/>'
    return head + body + "</svg>"


# ─── Сборка задачи ───────────────────────────────────────────────────────────

def shuffle_for_answer(items_left, items_right_unshuffled):
    """Перемешивает правую сторону. Ответ: для каждого левого i — позиция в перемешанной правой + 1."""
    idx = list(range(len(items_right_unshuffled)))
    random.shuffle(idx)
    shuffled = [items_right_unshuffled[i] for i in idx]
    answer = "".join(str(idx.index(i) + 1) for i in range(len(items_left)))
    return shuffled, answer


def _render_column(items, labels, is_graph_col):
    out = '<div style="text-align:center;margin:0.5em 0">'
    for lab, item in zip(labels, items):
        if is_graph_col:
            out += (
                '<div style="display:inline-block;text-align:center;margin:6px;vertical-align:top">'
                '<div style="font-weight:bold;font-size:1.1em">' + lab + '</div>'
                + item +
                '</div>'
            )
        else:
            out += (
                '<div style="display:inline-block;margin:10px 18px;vertical-align:middle">'
                '<span style="font-weight:bold">' + lab + ')</span> ' + item +
                '</div>'
            )
    out += '</div>'
    return out


def _answer_table():
    return (
        '<table style="border-collapse:collapse;margin:0.5em auto">'
        '<thead><tr>'
        '<th style="border:1px solid #999;padding:0.4em 1em;background:#eef">А</th>'
        '<th style="border:1px solid #999;padding:0.4em 1em;background:#eef">Б</th>'
        '<th style="border:1px solid #999;padding:0.4em 1em;background:#eef">В</th>'
        '</tr></thead>'
        '<tbody><tr>'
        '<td style="border:1px solid #999;padding:0.6em;min-width:3em">&nbsp;</td>'
        '<td style="border:1px solid #999;padding:0.6em;min-width:3em">&nbsp;</td>'
        '<td style="border:1px solid #999;padding:0.6em;min-width:3em">&nbsp;</td>'
        '</tr></tbody></table>'
    )


def render_task(items_left, items_right, left_is_graph, intro, left_caption, right_caption,
                answer=None):
    """answer передаётся, чтобы пример в скобках не совпадал с реальным ответом."""
    PERMS = ["123", "132", "213", "231", "312", "321"]
    candidates = [p for p in PERMS if p != answer]
    example = random.choice(candidates) if candidates else "132"
    return (
        '<p>' + intro + '</p>'
        '<p><b>' + left_caption + ':</b></p>'
        + _render_column(items_left, ["А", "Б", "В"], left_is_graph) +
        '<p><b>' + right_caption + ':</b></p>'
        + _render_column(items_right, ["1", "2", "3"], not left_is_graph) +
        '<p>В таблице под каждой буквой укажите соответствующий номер.</p>'
        + _answer_table() +
        '<p style="color:#666;font-size:0.92em">'
        'В ответ запишите три цифры без пробелов и запятых '
        '(например, <code>' + example + '</code>).</p>'
    )
'''


# ──────────────────────────────────────────────────────────────────────────────
# G1: LINEAR_SIGNS — знаки коэффициентов k, b прямой
# ──────────────────────────────────────────────────────────────────────────────

GEN_T1 = PLOTTER + r'''

def generate_task():
    """Установите соответствие графика прямой y=kx+b и знаков коэффициентов."""
    abs_k = random.choice([2, 3])
    abs_b = random.choice([3, 4])
    grid = random.random() < 0.5

    sign_pairs = [(1, 1), (1, -1), (-1, 1), (-1, -1)]
    chosen = random.sample(sign_pairs, 3)

    descs = [fmt_signs_linear(sk, sb) for (sk, sb) in chosen]
    graphs = [plot_linear(sk * abs_k, sb * abs_b, grid) for (sk, sb) in chosen]

    if random.random() < 0.5:
        right, answer = shuffle_for_answer(graphs, descs)
        cond = render_task(
            graphs, right, True,
            "На рисунках изображены графики функций вида y = kx + b. "
            "Установите соответствие между графиками и знаками коэффициентов k и b.",
            "Графики", "Знаки коэффициентов",
        answer=answer,
    )
    else:
        right, answer = shuffle_for_answer(descs, graphs)
        cond = render_task(
            descs, right, False,
            "На рисунках изображены графики функций вида y = kx + b. "
            "Установите соответствие между знаками коэффициентов k и b и графиками функций.",
            "Знаки коэффициентов", "Графики",
        answer=answer,
    )

    return {"condition_text": cond, "correct_answer": answer}


if __name__ == "__main__":
    random.seed(1)
    for i in range(3):
        t = generate_task()
        print(f"[G1 #{i+1}] answer = {t['correct_answer']}")
'''


# ──────────────────────────────────────────────────────────────────────────────
# G2: LINEAR_MATCH — формула прямой ↔ график; k или b могут быть 0
# ──────────────────────────────────────────────────────────────────────────────

GEN_T2 = PLOTTER + r'''

def generate_task():
    """Формула прямой ↔ график. k или b могут зануляться. Знаки путаются."""
    abs_k = random.choice([2, 3])
    abs_b = random.choice([2, 3, 4])
    grid = random.random() < 0.5

    sign_pairs = random.sample([(1, 1), (1, -1), (-1, 1), (-1, -1)], 3)

    # Зануление: 0..2 функций могут получить k=0 (y=const) или b=0 (y=kx)
    n_zero = random.choices([0, 1, 2], weights=[3, 4, 2])[0]
    zero_indices = random.sample([0, 1, 2], n_zero) if n_zero > 0 else []
    zero_what = {i: random.choice(["k", "b"]) for i in zero_indices}

    funcs = []
    for i, (sk, sb) in enumerate(sign_pairs):
        k = sk * abs_k
        b = sb * abs_b
        if i in zero_what:
            if zero_what[i] == "k":
                k = 0
            else:
                b = 0
        if k == 0 and b == 0:
            b = sb * abs_b
        funcs.append((k, b))

    # Защита от дубликатов после зануления
    seen = set()
    for i in range(3):
        if funcs[i] in seen:
            k, b = funcs[i]
            for new_k in [-k if k != 0 else abs_k, -abs_k, abs_k, 0]:
                changed = False
                for new_b in [-b if b != 0 else abs_b, -abs_b, abs_b, 0]:
                    if (new_k, new_b) not in seen and not (new_k == 0 and new_b == 0):
                        funcs[i] = (new_k, new_b)
                        changed = True
                        break
                if changed:
                    break
        seen.add(funcs[i])

    formulas = [fmt_linear(k, b) for (k, b) in funcs]
    graphs = [plot_linear(k, b, grid) for (k, b) in funcs]

    if random.random() < 0.5:
        right, answer = shuffle_for_answer(graphs, formulas)
        cond = render_task(
            graphs, right, True,
            "Установите соответствие между графиками функций и формулами, которые их задают.",
            "Графики", "Формулы",
        answer=answer,
    )
    else:
        right, answer = shuffle_for_answer(formulas, graphs)
        cond = render_task(
            formulas, right, False,
            "Установите соответствие между формулами и графиками функций.",
            "Формулы", "Графики",
        answer=answer,
    )

    return {"condition_text": cond, "correct_answer": answer}


if __name__ == "__main__":
    random.seed(2)
    for i in range(3):
        t = generate_task()
        print(f"[G2 #{i+1}] answer = {t['correct_answer']}")
'''


# ──────────────────────────────────────────────────────────────────────────────
# G3: PARABOLA_SIGNS — знаки коэффициентов a, c параболы
# ──────────────────────────────────────────────────────────────────────────────

GEN_T3 = PLOTTER + r'''

def _make_parabola_with_vertex_constraint(sa, sc, abs_a, abs_c):
    """Возвращает (a, b, c) такие, что |xv| = |b/(2a)| ≤ 3."""
    a = sa * abs_a
    c = sc * abs_c
    candidates = [b for b in range(-3, 4) if abs(-b / (2.0 * a)) <= 3.0]
    b = random.choice(candidates)
    return a, b, c


def generate_task():
    """Установите соответствие графика параболы y=ax²+bx+c и знаков a, c."""
    abs_a = random.choice([1, 2])
    abs_c = random.choice([2, 3, 4])
    grid = random.random() < 0.5

    sign_pairs = random.sample([(1, 1), (1, -1), (-1, 1), (-1, -1)], 3)
    triples = [_make_parabola_with_vertex_constraint(sa, sc, abs_a, abs_c) for (sa, sc) in sign_pairs]

    descs = [fmt_signs_parabola(sa, sc) for (sa, sc) in sign_pairs]
    graphs = [plot_parabola(a, b, c, grid) for (a, b, c) in triples]

    if random.random() < 0.5:
        right, answer = shuffle_for_answer(graphs, descs)
        cond = render_task(
            graphs, right, True,
            "На рисунках изображены графики функций вида y = ax² + bx + c. "
            "Установите соответствие между графиками и знаками коэффициентов a и c.",
            "Графики", "Знаки коэффициентов",
        answer=answer,
    )
    else:
        right, answer = shuffle_for_answer(descs, graphs)
        cond = render_task(
            descs, right, False,
            "На рисунках изображены графики функций вида y = ax² + bx + c. "
            "Установите соответствие между знаками коэффициентов a и c и графиками функций.",
            "Знаки коэффициентов", "Графики",
        answer=answer,
    )

    return {"condition_text": cond, "correct_answer": answer}


if __name__ == "__main__":
    random.seed(3)
    for i in range(3):
        t = generate_task()
        print(f"[G3 #{i+1}] answer = {t['correct_answer']}")
'''


# ──────────────────────────────────────────────────────────────────────────────
# G4: MIXED_MATCH — формула ↔ график для смешанных функций
# ──────────────────────────────────────────────────────────────────────────────

GEN_T4 = PLOTTER + r'''

def _make_lines_same_mag(n, abs_k, abs_b):
    """n прямых с одним |k| и |b|, разными знаками."""
    pairs = random.sample([(1, 1), (1, -1), (-1, 1), (-1, -1)], n)
    return [(sk * abs_k, sb * abs_b) for (sk, sb) in pairs]


def _make_parabolas_same_mag(n, abs_a, abs_c):
    """n парабол с одним |a| и |c|, разными знаками. b=0 для чистоты."""
    pairs = random.sample([(1, 1), (1, -1), (-1, 1), (-1, -1)], n)
    return [(sa * abs_a, 0, sc * abs_c) for (sa, sc) in pairs]


def _make_hyperbolas_same_mag(n, abs_k):
    """n гипербол с одним |k|, разными знаками k."""
    if n == 2:
        return [(abs_k,), (-abs_k,)]
    return [(random.choice([abs_k, -abs_k]),) for _ in range(n)]


def generate_task():
    """Формула ↔ график для смешанных функций (прямые, параболы, гиперболы)."""
    from collections import Counter
    grid = random.random() < 0.5

    mix_kinds = random.choice([
        ("line", "parabola", "hyperbola"),
        ("line", "line", "parabola"),
        ("line", "line", "hyperbola"),
        ("parabola", "parabola", "line"),
        ("parabola", "parabola", "hyperbola"),
        ("hyperbola", "hyperbola", "line"),
        ("hyperbola", "hyperbola", "parabola"),
    ])
    cnt = Counter(mix_kinds)

    abs_k_lin = random.choice([1, 2, 3])
    abs_b_lin = random.choice([2, 3, 4])
    abs_a_par = random.choice([1, 2])
    abs_c_par = random.choice([2, 3, 4])
    abs_k_hyp = random.choice([2, 3, 4, 6])

    lines = _make_lines_same_mag(cnt["line"], abs_k_lin, abs_b_lin) if cnt["line"] else []
    parabolas = _make_parabolas_same_mag(cnt["parabola"], abs_a_par, abs_c_par) if cnt["parabola"] else []
    hyperbolas = _make_hyperbolas_same_mag(cnt["hyperbola"], abs_k_hyp) if cnt["hyperbola"] else []

    formulas = []
    graphs = []
    li = pi = hi = 0
    for kind in mix_kinds:
        if kind == "line":
            k, b = lines[li]; li += 1
            formulas.append(fmt_linear(k, b))
            graphs.append(plot_linear(k, b, grid))
        elif kind == "parabola":
            a, b, c = parabolas[pi]; pi += 1
            formulas.append(fmt_parabola(a, b, c))
            graphs.append(plot_parabola(a, b, c, grid))
        elif kind == "hyperbola":
            (k,) = hyperbolas[hi]; hi += 1
            formulas.append(fmt_hyperbola(k))
            graphs.append(plot_hyperbola(k, grid))

    if random.random() < 0.5:
        right, answer = shuffle_for_answer(graphs, formulas)
        cond = render_task(
            graphs, right, True,
            "Установите соответствие между графиками функций и формулами, которые их задают.",
            "Графики", "Формулы",
        answer=answer,
    )
    else:
        right, answer = shuffle_for_answer(formulas, graphs)
        cond = render_task(
            formulas, right, False,
            "Установите соответствие между формулами и графиками функций.",
            "Формулы", "Графики",
        answer=answer,
    )

    return {"condition_text": cond, "correct_answer": answer}


if __name__ == "__main__":
    random.seed(4)
    for i in range(3):
        t = generate_task()
        print(f"[G4 #{i+1}] answer = {t['correct_answer']}")
'''


# ──────────────────────────────────────────────────────────────────────────────
# Прототипы (порядок на странице урока)
# ──────────────────────────────────────────────────────────────────────────────

PROTOTYPES = [
    (1, 'OGE11: G1 — знаки коэффициентов прямой',    'Знаки k, b у y=kx+b',           GEN_T1),
    (2, 'OGE11: G2 — формулы и графики прямых',      'Прямые: y=kx+b (k или b=0)',    GEN_T2),
    (3, 'OGE11: G3 — знаки коэффициентов параболы',  'Знаки a, c у y=ax²+bx+c',       GEN_T3),
    (4, 'OGE11: G4 — смешанные функции',             'Прямая + парабола + гипербола', GEN_T4),
]


class Command(BaseCommand):
    help = "Создаёт «Задание 11» (Графики функций) — 4 ProblemGenerator-а"

    def add_arguments(self, parser):
        parser.add_argument('--clear', action='store_true', help='Снести и пересоздать')

    @transaction.atomic
    def handle(self, *args, **opts):
        try:
            course = Course.objects.get(slug='oge-maths')
        except Course.DoesNotExist:
            self.stdout.write(self.style.ERROR('Курс oge-maths не найден'))
            return

        # Ищем модуль 'Первая часть' по имени, не по order — иначе с
        # появлением модуля 'Задания 1-5' (order=0) можно поймать его и
        # создать дубль урока в чужом модуле.
        module, _ = Module.objects.get_or_create(
            course=course, title='Первая часть',
            defaults={'order': 1, 'description': ''},
        )

        if opts['clear']:
            old = Lesson.objects.filter(module=module, title='Задание 11').first()
            if old:
                ProblemGenerator.objects.filter(assignments__lesson=old).delete()
                old.delete()
                self.stdout.write(self.style.WARNING('Старое «Задание 11» удалено.'))

        lesson, created = Lesson.objects.get_or_create(
            module=module, title='Задание 11',
            defaults={'order': 11, 'lesson_type': 'practice'},
        )
        if not created and lesson.order != 11:
            lesson.order = 11
            lesson.save(update_fields=['order'])
        if created:
            self.stdout.write(self.style.SUCCESS(f'Урок создан: {lesson.title}'))

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
                assign.problem_generator = generator
                assign.assignment_type = 'test'
                assign.answer_type = 'text_input'
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
                    answer_type='text_input',
                    required_correct=3,
                    problem_generator=generator,
                )
                shown_title = asg_title

            self.stdout.write(self.style.SUCCESS(f'  + [{order}] {shown_title}'))

        self.stdout.write(self.style.SUCCESS(
            f'\nГотово: «Задание 11» курса ОГЭ — {len(PROTOTYPES)} прототипов.'
        ))
