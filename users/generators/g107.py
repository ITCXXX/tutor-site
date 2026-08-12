# -*- coding: utf-8 -*-
# AUTO-GENERATED из ProblemGenerator id=107: OGE13: Тип 1 — линейное
# Пункт 6: генераторы вынесены из БД в репозиторий (без exec).
# random / math / Fraction добавлены в шапку — часть генераторов
# полагалась на инъекцию этих имён старым execute_generator().
import random  # noqa: F401
import math  # noqa: F401
from fractions import Fraction  # noqa: F401



import random


def _interval_str(boundary, sign):
    """Возвращает LaTeX интервала вида (-\\infty;\\ a) или [a;\\ +\\infty)."""
    b = str(boundary)
    if sign == '<':
        return rf"$(-\infty;\ {b})$"
    if sign == r'\leqslant':
        return rf"$(-\infty;\ {b}]$"
    if sign == '>':
        return rf"$({b};\ +\infty)$"
    if sign == r'\geqslant':
        return rf"$[{b};\ +\infty)$"
    raise ValueError(sign)


def _flip(sign):
    return {'<': '>', '>': '<',
            r'\leqslant': r'\geqslant', r'\geqslant': r'\leqslant'}[sign]


def _term(coef):
    """Возвращает LaTeX для коэффициента при x: '3x', '-x', 'x', '-3x'."""
    if coef == 1: return "x"
    if coef == -1: return "-x"
    return f"{coef}x"


def _build_side(coef_x, const):
    """Собирает LaTeX вида 'ax + b', 'ax', 'b'."""
    parts = []
    if coef_x != 0:
        parts.append(_term(coef_x))
    if const != 0 or coef_x == 0:
        if not parts:
            parts.append(str(const))
        else:
            parts.append(("+ " if const > 0 else "- ") + str(abs(const)))
    return " ".join(parts) if parts else "0"


def generate_task():
    """№13 ОГЭ, Тип 1: линейное неравенство ax + b ⋛ cx + d → выбор интервала.

    Параметры подобраны так, чтобы типичная ошибка переноса константы через знак
    неравенства давала граничную точку −x₀, а забытый «переворот» при делении на
    отрицательный коэффициент — обратное направление. 4 варианта = ±x₀ × ±знак.
    """
    while True:
        x0 = random.choice([n for n in range(-9, 10) if n not in (-1, 0, 1)])
        k = random.choice([-5, -4, -3, -2, 2, 3, 4, 5])
        a = random.choice([-3, -2, -1, 1, 2, 3])
        c = a - k
        if c == 0 or c == a:
            continue
        # Из ax + b ⋛ cx + d следует kx ⋛ d − b. Чтобы ответ был x ⋛̃ x₀,
        # нужно d − b = k·x₀. При этом ошибка переноса (не сменили знак)
        # даёт граничную точку −x₀.
        side = random.choice(['left', 'right'])
        if side == 'left':
            b = -k * x0
            d = 0
        else:
            b = 0
            d = k * x0
        if abs(b) > 60 or abs(d) > 60:
            continue
        break

    sign_problem = random.choice(['<', '>', r'\leqslant', r'\geqslant'])
    sign_answer = sign_problem if k > 0 else _flip(sign_problem)

    lhs = _build_side(a, b)
    rhs = _build_side(c, d)
    condition_text = (
        rf"Укажите решение неравенства $${lhs} {sign_problem} {rhs}.$$"
    )

    correct_label = _interval_str(x0, sign_answer)
    options = [
        correct_label,
        _interval_str(-x0, sign_answer),
        _interval_str(x0, _flip(sign_answer)),
        _interval_str(-x0, _flip(sign_answer)),
    ]
    random.shuffle(options)
    correct_pos = options.index(correct_label) + 1

    return {
        "condition_text": condition_text,
        "choices": options,
        "correct_answer": str(correct_pos),
    }


if __name__ == "__main__":
    random.seed(0)
    for i in range(8):
        t = generate_task()
        print(f"--- T1[{i+1}] ---")
        print(t['condition_text'])
        print("choices:")
        for j, ch in enumerate(t['choices'], 1):
            print(f"  {j}) {ch}")
        print(f"correct: {t['correct_answer']}\n")
