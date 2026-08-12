# -*- coding: utf-8 -*-
# AUTO-GENERATED из ProblemGenerator id=123: OGE11: G3 — знаки коэффициентов параболы
# Пункт 6: генераторы вынесены из БД в репозиторий (без exec).
# random / math / Fraction добавлены в шапку — часть генераторов
# полагалась на инъекцию этих имён старым execute_generator().
import random  # noqa: F401
import math  # noqa: F401
from fractions import Fraction  # noqa: F401



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
