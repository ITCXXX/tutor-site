# -*- coding: utf-8 -*-
"""
Management command: populate EGE task 3 questions (стереометрия).

Usage:
    python manage.py populate_ege3
    python manage.py populate_ege3 --clear

Lesson order=3 inside module order=1 of course ege-profile-math.
Прототипы сгруппированы по принципу решения, не по «что найти».
"""

from django.core.management.base import BaseCommand
from users.models import Course, Module, Lesson, Assignment, TestQuestion, AnswerOption


# ──────────────────────────────────────────────────────────────────────────────
# SVG-чертежи. Все используют viewBox 320×220, скошенную диметрическую проекцию.
# ──────────────────────────────────────────────────────────────────────────────

# ── 1. Одиночный конус ───────────────────────────────────────────────────────
_SVG_CONE = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 320 220" width="280" height="200" role="img" aria-label="Конус">
  <ellipse cx="160" cy="170" rx="70" ry="18" fill="none" stroke="#1f1f1f" stroke-width="1.5"/>
  <path d="M 90 170 A 70 18 0 0 0 230 170" fill="none" stroke="#1f1f1f" stroke-width="1.5" stroke-dasharray="3,3"/>
  <line x1="90" y1="170" x2="160" y2="30" stroke="#1f1f1f" stroke-width="1.5"/>
  <line x1="230" y1="170" x2="160" y2="30" stroke="#1f1f1f" stroke-width="1.5"/>
  <line x1="160" y1="170" x2="160" y2="30" stroke="#1f1f1f" stroke-width="1.2" stroke-dasharray="3,3"/>
  <line x1="160" y1="170" x2="230" y2="170" stroke="#1f1f1f" stroke-width="1.2" stroke-dasharray="3,3"/>
</svg>"""

# ── 2. Цилиндр с конусом внутри (общее основание и высота) ───────────────────
_SVG_CYL_CONE = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 320 220" width="280" height="200" role="img" aria-label="Цилиндр и конус с общим основанием и высотой">
  <ellipse cx="160" cy="180" rx="65" ry="16" fill="none" stroke="#1f1f1f" stroke-width="1.5"/>
  <path d="M 95 180 A 65 16 0 0 0 225 180" fill="none" stroke="#1f1f1f" stroke-width="1.5" stroke-dasharray="3,3"/>
  <ellipse cx="160" cy="40" rx="65" ry="16" fill="none" stroke="#1f1f1f" stroke-width="1.5"/>
  <line x1="95" y1="40" x2="95" y2="180" stroke="#1f1f1f" stroke-width="1.5"/>
  <line x1="225" y1="40" x2="225" y2="180" stroke="#1f1f1f" stroke-width="1.5"/>
  <line x1="95" y1="180" x2="160" y2="40" stroke="#1f1f1f" stroke-width="1.5"/>
  <line x1="225" y1="180" x2="160" y2="40" stroke="#1f1f1f" stroke-width="1.5"/>
  <line x1="160" y1="180" x2="160" y2="40" stroke="#1f1f1f" stroke-width="1.2" stroke-dasharray="3,3"/>
</svg>"""

# ── 3. Шар, вписанный в цилиндр ──────────────────────────────────────────────
_SVG_SPHERE_IN_CYL = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 320 220" width="280" height="200" role="img" aria-label="Шар, вписанный в цилиндр">
  <ellipse cx="160" cy="180" rx="60" ry="14" fill="none" stroke="#1f1f1f" stroke-width="1.5"/>
  <path d="M 100 180 A 60 14 0 0 0 220 180" fill="none" stroke="#1f1f1f" stroke-width="1.5" stroke-dasharray="3,3"/>
  <ellipse cx="160" cy="60" rx="60" ry="14" fill="none" stroke="#1f1f1f" stroke-width="1.5"/>
  <line x1="100" y1="60" x2="100" y2="180" stroke="#1f1f1f" stroke-width="1.5"/>
  <line x1="220" y1="60" x2="220" y2="180" stroke="#1f1f1f" stroke-width="1.5"/>
  <circle cx="160" cy="120" r="60" fill="none" stroke="#1f1f1f" stroke-width="1.5"/>
  <ellipse cx="160" cy="120" rx="60" ry="14" fill="none" stroke="#1f1f1f" stroke-width="1.2" stroke-dasharray="3,3"/>
</svg>"""

# ── 4. Конус, вписанный в шар (R конуса = R шара) ────────────────────────────
_SVG_CONE_IN_SPHERE = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 320 220" width="280" height="200" role="img" aria-label="Конус, вписанный в шар">
  <circle cx="160" cy="115" r="80" fill="none" stroke="#1f1f1f" stroke-width="1.5"/>
  <ellipse cx="160" cy="115" rx="80" ry="18" fill="none" stroke="#1f1f1f" stroke-width="1.2" stroke-dasharray="3,3"/>
  <line x1="80" y1="115" x2="160" y2="35" stroke="#1f1f1f" stroke-width="1.5"/>
  <line x1="240" y1="115" x2="160" y2="35" stroke="#1f1f1f" stroke-width="1.5"/>
  <line x1="160" y1="115" x2="160" y2="35" stroke="#1f1f1f" stroke-width="1.2" stroke-dasharray="3,3"/>
  <line x1="80" y1="115" x2="240" y2="115" stroke="#1f1f1f" stroke-width="1.2" stroke-dasharray="3,3"/>
</svg>"""

# ── 5. Параллелепипед: тетраэдр A,B,C,B1 (4 вершины) ─────────────────────────
# Параллелепипед ABCDA1B1C1D1 в диметрии. Тетраэдр выделен сплошными линиями,
# остальные рёбра параллелепипеда — пунктирные.
_SVG_PARAL_TETR = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 320 220" width="280" height="200" role="img" aria-label="Тетраэдр ABCB1 в параллелепипеде ABCDA1B1C1D1">
  <line x1="60" y1="180" x2="220" y2="180" stroke="#1f1f1f" stroke-width="1" stroke-dasharray="3,3"/>
  <line x1="220" y1="180" x2="260" y2="150" stroke="#1f1f1f" stroke-width="1" stroke-dasharray="3,3"/>
  <line x1="260" y1="150" x2="100" y2="150" stroke="#1f1f1f" stroke-width="1" stroke-dasharray="3,3"/>
  <line x1="100" y1="150" x2="60" y2="180" stroke="#1f1f1f" stroke-width="1" stroke-dasharray="3,3"/>
  <line x1="60" y1="60" x2="220" y2="60" stroke="#1f1f1f" stroke-width="1" stroke-dasharray="3,3"/>
  <line x1="220" y1="60" x2="260" y2="30" stroke="#1f1f1f" stroke-width="1" stroke-dasharray="3,3"/>
  <line x1="260" y1="30" x2="100" y2="30" stroke="#1f1f1f" stroke-width="1" stroke-dasharray="3,3"/>
  <line x1="100" y1="30" x2="60" y2="60" stroke="#1f1f1f" stroke-width="1" stroke-dasharray="3,3"/>
  <line x1="60" y1="180" x2="60" y2="60" stroke="#1f1f1f" stroke-width="1" stroke-dasharray="3,3"/>
  <line x1="260" y1="150" x2="260" y2="30" stroke="#1f1f1f" stroke-width="1" stroke-dasharray="3,3"/>
  <line x1="100" y1="150" x2="100" y2="30" stroke="#1f1f1f" stroke-width="1" stroke-dasharray="3,3"/>
  <line x1="60" y1="180" x2="220" y2="180" stroke="#1f1f1f" stroke-width="1.6"/>
  <line x1="220" y1="180" x2="260" y2="150" stroke="#1f1f1f" stroke-width="1.6"/>
  <line x1="60" y1="180" x2="260" y2="150" stroke="#1f1f1f" stroke-width="1.6"/>
  <line x1="220" y1="180" x2="220" y2="60" stroke="#1f1f1f" stroke-width="1.6"/>
  <line x1="60" y1="180" x2="220" y2="60" stroke="#1f1f1f" stroke-width="1.6"/>
  <line x1="260" y1="150" x2="220" y2="60" stroke="#1f1f1f" stroke-width="1.6"/>
  <text x="48" y="195" font-family="Cambria, Georgia, serif" font-style="italic" font-size="14" fill="#1f1f1f">A</text>
  <text x="219" y="196" font-family="Cambria, Georgia, serif" font-style="italic" font-size="14" fill="#1f1f1f">B</text>
  <text x="263" y="148" font-family="Cambria, Georgia, serif" font-style="italic" font-size="14" fill="#1f1f1f">C</text>
  <text x="86" y="148" font-family="Cambria, Georgia, serif" font-style="italic" font-size="14" fill="#1f1f1f">D</text>
  <text x="46" y="60" font-family="Cambria, Georgia, serif" font-style="italic" font-size="14" fill="#1f1f1f">A</text>
  <text x="55" y="65" font-family="Cambria, Georgia, serif" font-size="10" fill="#1f1f1f">1</text>
  <text x="225" y="58" font-family="Cambria, Georgia, serif" font-style="italic" font-size="14" fill="#1f1f1f">B</text>
  <text x="234" y="63" font-family="Cambria, Georgia, serif" font-size="10" fill="#1f1f1f">1</text>
  <text x="263" y="28" font-family="Cambria, Georgia, serif" font-style="italic" font-size="14" fill="#1f1f1f">C</text>
  <text x="272" y="33" font-family="Cambria, Georgia, serif" font-size="10" fill="#1f1f1f">1</text>
  <text x="86" y="28" font-family="Cambria, Georgia, serif" font-style="italic" font-size="14" fill="#1f1f1f">D</text>
  <text x="95" y="33" font-family="Cambria, Georgia, serif" font-size="10" fill="#1f1f1f">1</text>
</svg>"""

# ── 6. Параллелепипед: пирамида A,B,C,D,A1 (5 вершин) ────────────────────────
_SVG_PARAL_PYR = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 320 220" width="280" height="200" role="img" aria-label="Пирамида с основанием ABCD и вершиной A1 в параллелепипеде">
  <line x1="60" y1="180" x2="220" y2="180" stroke="#1f1f1f" stroke-width="1" stroke-dasharray="3,3"/>
  <line x1="220" y1="180" x2="260" y2="150" stroke="#1f1f1f" stroke-width="1" stroke-dasharray="3,3"/>
  <line x1="260" y1="150" x2="100" y2="150" stroke="#1f1f1f" stroke-width="1" stroke-dasharray="3,3"/>
  <line x1="100" y1="150" x2="60" y2="180" stroke="#1f1f1f" stroke-width="1" stroke-dasharray="3,3"/>
  <line x1="60" y1="60" x2="220" y2="60" stroke="#1f1f1f" stroke-width="1" stroke-dasharray="3,3"/>
  <line x1="220" y1="60" x2="260" y2="30" stroke="#1f1f1f" stroke-width="1" stroke-dasharray="3,3"/>
  <line x1="260" y1="30" x2="100" y2="30" stroke="#1f1f1f" stroke-width="1" stroke-dasharray="3,3"/>
  <line x1="100" y1="30" x2="60" y2="60" stroke="#1f1f1f" stroke-width="1" stroke-dasharray="3,3"/>
  <line x1="220" y1="180" x2="220" y2="60" stroke="#1f1f1f" stroke-width="1" stroke-dasharray="3,3"/>
  <line x1="260" y1="150" x2="260" y2="30" stroke="#1f1f1f" stroke-width="1" stroke-dasharray="3,3"/>
  <line x1="100" y1="150" x2="100" y2="30" stroke="#1f1f1f" stroke-width="1" stroke-dasharray="3,3"/>
  <line x1="60" y1="180" x2="220" y2="180" stroke="#1f1f1f" stroke-width="1.6"/>
  <line x1="220" y1="180" x2="260" y2="150" stroke="#1f1f1f" stroke-width="1.6"/>
  <line x1="260" y1="150" x2="100" y2="150" stroke="#1f1f1f" stroke-width="1.6"/>
  <line x1="100" y1="150" x2="60" y2="180" stroke="#1f1f1f" stroke-width="1.6"/>
  <line x1="60" y1="180" x2="60" y2="60" stroke="#1f1f1f" stroke-width="1.6"/>
  <line x1="60" y1="60" x2="220" y2="180" stroke="#1f1f1f" stroke-width="1.6"/>
  <line x1="60" y1="60" x2="260" y2="150" stroke="#1f1f1f" stroke-width="1.6"/>
  <line x1="60" y1="60" x2="100" y2="150" stroke="#1f1f1f" stroke-width="1.6"/>
  <text x="48" y="195" font-family="Cambria, Georgia, serif" font-style="italic" font-size="14" fill="#1f1f1f">A</text>
  <text x="219" y="196" font-family="Cambria, Georgia, serif" font-style="italic" font-size="14" fill="#1f1f1f">B</text>
  <text x="263" y="148" font-family="Cambria, Georgia, serif" font-style="italic" font-size="14" fill="#1f1f1f">C</text>
  <text x="86" y="148" font-family="Cambria, Georgia, serif" font-style="italic" font-size="14" fill="#1f1f1f">D</text>
  <text x="46" y="60" font-family="Cambria, Georgia, serif" font-style="italic" font-size="14" fill="#1f1f1f">A</text>
  <text x="55" y="65" font-family="Cambria, Georgia, serif" font-size="10" fill="#1f1f1f">1</text>
  <text x="225" y="58" font-family="Cambria, Georgia, serif" font-style="italic" font-size="14" fill="#1f1f1f">B</text>
  <text x="234" y="63" font-family="Cambria, Georgia, serif" font-size="10" fill="#1f1f1f">1</text>
  <text x="263" y="28" font-family="Cambria, Georgia, serif" font-style="italic" font-size="14" fill="#1f1f1f">C</text>
  <text x="272" y="33" font-family="Cambria, Georgia, serif" font-size="10" fill="#1f1f1f">1</text>
  <text x="86" y="28" font-family="Cambria, Georgia, serif" font-style="italic" font-size="14" fill="#1f1f1f">D</text>
  <text x="95" y="33" font-family="Cambria, Georgia, serif" font-size="10" fill="#1f1f1f">1</text>
</svg>"""

# ── 7. Призма: тетраэдр A,B,C,C1 (4 вершины) ─────────────────────────────────
_SVG_PRIZMA_TETR = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 320 220" width="280" height="200" role="img" aria-label="Тетраэдр ABCC1 в правильной треугольной призме">
  <line x1="80" y1="180" x2="220" y2="180" stroke="#1f1f1f" stroke-width="1" stroke-dasharray="3,3"/>
  <line x1="220" y1="180" x2="170" y2="135" stroke="#1f1f1f" stroke-width="1" stroke-dasharray="3,3"/>
  <line x1="170" y1="135" x2="80" y2="180" stroke="#1f1f1f" stroke-width="1" stroke-dasharray="3,3"/>
  <line x1="80" y1="60" x2="220" y2="60" stroke="#1f1f1f" stroke-width="1" stroke-dasharray="3,3"/>
  <line x1="220" y1="60" x2="170" y2="15" stroke="#1f1f1f" stroke-width="1" stroke-dasharray="3,3"/>
  <line x1="170" y1="15" x2="80" y2="60" stroke="#1f1f1f" stroke-width="1" stroke-dasharray="3,3"/>
  <line x1="80" y1="180" x2="80" y2="60" stroke="#1f1f1f" stroke-width="1" stroke-dasharray="3,3"/>
  <line x1="220" y1="180" x2="220" y2="60" stroke="#1f1f1f" stroke-width="1" stroke-dasharray="3,3"/>
  <line x1="170" y1="135" x2="170" y2="15" stroke="#1f1f1f" stroke-width="1" stroke-dasharray="3,3"/>
  <line x1="80" y1="180" x2="220" y2="180" stroke="#1f1f1f" stroke-width="1.6"/>
  <line x1="220" y1="180" x2="170" y2="135" stroke="#1f1f1f" stroke-width="1.6"/>
  <line x1="170" y1="135" x2="80" y2="180" stroke="#1f1f1f" stroke-width="1.6"/>
  <line x1="170" y1="135" x2="170" y2="15" stroke="#1f1f1f" stroke-width="1.6"/>
  <line x1="80" y1="180" x2="170" y2="15" stroke="#1f1f1f" stroke-width="1.6"/>
  <line x1="220" y1="180" x2="170" y2="15" stroke="#1f1f1f" stroke-width="1.6"/>
  <text x="68" y="195" font-family="Cambria, Georgia, serif" font-style="italic" font-size="14" fill="#1f1f1f">A</text>
  <text x="222" y="195" font-family="Cambria, Georgia, serif" font-style="italic" font-size="14" fill="#1f1f1f">B</text>
  <text x="174" y="134" font-family="Cambria, Georgia, serif" font-style="italic" font-size="14" fill="#1f1f1f">C</text>
  <text x="65" y="60" font-family="Cambria, Georgia, serif" font-style="italic" font-size="14" fill="#1f1f1f">A</text>
  <text x="74" y="65" font-family="Cambria, Georgia, serif" font-size="10" fill="#1f1f1f">1</text>
  <text x="222" y="60" font-family="Cambria, Georgia, serif" font-style="italic" font-size="14" fill="#1f1f1f">B</text>
  <text x="231" y="65" font-family="Cambria, Georgia, serif" font-size="10" fill="#1f1f1f">1</text>
  <text x="174" y="14" font-family="Cambria, Georgia, serif" font-style="italic" font-size="14" fill="#1f1f1f">C</text>
  <text x="183" y="19" font-family="Cambria, Georgia, serif" font-size="10" fill="#1f1f1f">1</text>
</svg>"""

# ── 8. Призма: 5-вершинник B,C,A1,B1,C1 ──────────────────────────────────────
_SVG_PRIZMA_5V = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 320 220" width="280" height="200" role="img" aria-label="Многогранник BCA1B1C1 в правильной треугольной призме">
  <line x1="80" y1="180" x2="220" y2="180" stroke="#1f1f1f" stroke-width="1" stroke-dasharray="3,3"/>
  <line x1="220" y1="180" x2="170" y2="135" stroke="#1f1f1f" stroke-width="1" stroke-dasharray="3,3"/>
  <line x1="170" y1="135" x2="80" y2="180" stroke="#1f1f1f" stroke-width="1" stroke-dasharray="3,3"/>
  <line x1="80" y1="60" x2="220" y2="60" stroke="#1f1f1f" stroke-width="1" stroke-dasharray="3,3"/>
  <line x1="220" y1="60" x2="170" y2="15" stroke="#1f1f1f" stroke-width="1" stroke-dasharray="3,3"/>
  <line x1="170" y1="15" x2="80" y2="60" stroke="#1f1f1f" stroke-width="1" stroke-dasharray="3,3"/>
  <line x1="80" y1="180" x2="80" y2="60" stroke="#1f1f1f" stroke-width="1" stroke-dasharray="3,3"/>
  <line x1="220" y1="60" x2="170" y2="15" stroke="#1f1f1f" stroke-width="1.6"/>
  <line x1="170" y1="15" x2="80" y2="60" stroke="#1f1f1f" stroke-width="1.6"/>
  <line x1="220" y1="60" x2="80" y2="60" stroke="#1f1f1f" stroke-width="1.6"/>
  <line x1="220" y1="180" x2="220" y2="60" stroke="#1f1f1f" stroke-width="1.6"/>
  <line x1="170" y1="135" x2="170" y2="15" stroke="#1f1f1f" stroke-width="1.6"/>
  <line x1="220" y1="180" x2="170" y2="135" stroke="#1f1f1f" stroke-width="1.6"/>
  <line x1="220" y1="180" x2="80" y2="60" stroke="#1f1f1f" stroke-width="1.6"/>
  <line x1="170" y1="135" x2="80" y2="60" stroke="#1f1f1f" stroke-width="1.6"/>
  <text x="68" y="195" font-family="Cambria, Georgia, serif" font-style="italic" font-size="14" fill="#1f1f1f">A</text>
  <text x="222" y="195" font-family="Cambria, Georgia, serif" font-style="italic" font-size="14" fill="#1f1f1f">B</text>
  <text x="174" y="134" font-family="Cambria, Georgia, serif" font-style="italic" font-size="14" fill="#1f1f1f">C</text>
  <text x="65" y="60" font-family="Cambria, Georgia, serif" font-style="italic" font-size="14" fill="#1f1f1f">A</text>
  <text x="74" y="65" font-family="Cambria, Georgia, serif" font-size="10" fill="#1f1f1f">1</text>
  <text x="222" y="60" font-family="Cambria, Georgia, serif" font-style="italic" font-size="14" fill="#1f1f1f">B</text>
  <text x="231" y="65" font-family="Cambria, Georgia, serif" font-size="10" fill="#1f1f1f">1</text>
  <text x="174" y="14" font-family="Cambria, Georgia, serif" font-style="italic" font-size="14" fill="#1f1f1f">C</text>
  <text x="183" y="19" font-family="Cambria, Georgia, serif" font-size="10" fill="#1f1f1f">1</text>
</svg>"""

# ── 9. Призма со средней линией основания и сечением ─────────────────────────
_SVG_PRIZMA_SREDN = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 320 220" width="280" height="200" role="img" aria-label="Треугольная призма с сечением через среднюю линию основания">
  <line x1="80" y1="180" x2="220" y2="180" stroke="#1f1f1f" stroke-width="1.5"/>
  <line x1="220" y1="180" x2="170" y2="135" stroke="#1f1f1f" stroke-width="1.5"/>
  <line x1="170" y1="135" x2="80" y2="180" stroke="#1f1f1f" stroke-width="1.5"/>
  <line x1="80" y1="60" x2="220" y2="60" stroke="#1f1f1f" stroke-width="1.5"/>
  <line x1="220" y1="60" x2="170" y2="15" stroke="#1f1f1f" stroke-width="1.5"/>
  <line x1="170" y1="15" x2="80" y2="60" stroke="#1f1f1f" stroke-width="1.5"/>
  <line x1="80" y1="180" x2="80" y2="60" stroke="#1f1f1f" stroke-width="1.5"/>
  <line x1="220" y1="180" x2="220" y2="60" stroke="#1f1f1f" stroke-width="1.5"/>
  <line x1="170" y1="135" x2="170" y2="15" stroke="#1f1f1f" stroke-width="1.5"/>
  <line x1="125" y1="158" x2="195" y2="157" stroke="#1565c0" stroke-width="1.6"/>
  <line x1="125" y1="38" x2="195" y2="37" stroke="#1565c0" stroke-width="1.6" stroke-dasharray="3,3"/>
  <line x1="125" y1="158" x2="125" y2="38" stroke="#1565c0" stroke-width="1.4" stroke-dasharray="3,3"/>
  <line x1="195" y1="157" x2="195" y2="37" stroke="#1565c0" stroke-width="1.4" stroke-dasharray="3,3"/>
</svg>"""


# ──────────────────────────────────────────────────────────────────────────────
# Прототипы
# ──────────────────────────────────────────────────────────────────────────────

# ── Прототип 1: Изменение параметров конуса ──────────────────────────────────
# V_конуса = (1/3)·π·R²·h. Если R или h меняется в k раз — меняется V.

TYPE_IZM_PARAMETROV = [
    (
        r"Во сколько раз уменьшится объём конуса, если его высота уменьшится в \(9\) раз, "
        r"а радиус основания останется прежним?",
        "9",
        _SVG_CONE,
    ),
    (
        r"Во сколько раз увеличится объём конуса, если радиус его основания увеличится "
        r"в \(11\) раз, а высота останется прежней?",
        "121",
        _SVG_CONE,
    ),
]


# ── Прототип 2: Цилиндр и конус — общее основание и высота, ОБЪЁМ ────────────
# V_конуса = (1/3)·V_цилиндра.

TYPE_CYL_CONE_V = [
    (
        r"Цилиндр и конус имеют общие основание и высоту. Объём цилиндра равен \(30\). "
        r"Найдите объём конуса.",
        "10",
        _SVG_CYL_CONE,
    ),
    (
        r"Цилиндр и конус имеют общие основание и высоту. Объём конуса равен \(6\). "
        r"Найдите объём цилиндра.",
        "18",
        _SVG_CYL_CONE,
    ),
]


# ── Прототип 3: Цилиндр и конус — общее основание, h=R, ПЛОЩАДЬ ──────────────
# При h=R: S_бок_цилиндра = 2πR², S_бок_конуса = πR·R√2 = πR²√2.
# Отношение: S_конуса = S_цилиндра · √2/2.

TYPE_CYL_CONE_S = [
    (
        r"Цилиндр и конус имеют общие основание и высоту. Высота цилиндра равна радиусу основания. "
        r"Площадь боковой поверхности цилиндра равна \(5\sqrt{2}\). "
        r"Найдите площадь боковой поверхности конуса.",
        "5",
        _SVG_CYL_CONE,
    ),
    (
        r"Цилиндр и конус имеют общие основание и высоту. Высота цилиндра равна радиусу основания. "
        r"Площадь боковой поверхности конуса равна \(3\sqrt{2}\). "
        r"Найдите площадь боковой поверхности цилиндра.",
        "6",
        _SVG_CYL_CONE,
    ),
]


# ── Прототип 4: Шар, вписанный в цилиндр ─────────────────────────────────────
# При шаре, вписанном в цилиндр: h_цил = 2R, R_шара = R_цил.
# V_цил = 2πR³, V_шара = (4/3)πR³ → V_шара/V_цил = 2/3.
# S_полн_цил = 6πR², S_шара = 4πR² → S_шара/S_полн_цил = 2/3.

TYPE_SHAR_V_CYL = [
    (
        r"Шар, объём которого равен \(18\), вписан в цилиндр. Найдите объём цилиндра.",
        "27",
        _SVG_SPHERE_IN_CYL,
    ),
    (
        r"Шар вписан в цилиндр. Площадь полной поверхности цилиндра равна \(30\). "
        r"Найдите площадь поверхности шара.",
        "20",
        _SVG_SPHERE_IN_CYL,
    ),
]


# ── Прототип 5: Конус, вписанный в шар (R конуса = R шара) ───────────────────
# Если R_конуса = R_шара, то центр шара лежит в основании конуса, и h_конуса = R_шара.
# V_конуса = (1/3)·π·R³, V_шара = (4/3)·π·R³ → V_шара = 4·V_конуса.
# Образующая l = √(R² + h²) = √(R² + R²) = R√2.

TYPE_CONE_V_SHAR = [
    (
        r"Конус вписан в шар. Радиус основания конуса равен радиусу шара. "
        r"Объём шара равен \(60\). Найдите объём конуса.",
        "15",
        _SVG_CONE_IN_SPHERE,
    ),
    (
        r"Около конуса описана сфера (сфера содержит окружность основания конуса и его вершину). "
        r"Центр сферы находится в центре основания конуса. Радиус сферы равен \(84\sqrt{2}\). "
        r"Найдите длину образующей конуса.",
        "168",
        _SVG_CONE_IN_SPHERE,
    ),
]


# ── Прототип 6: Многогранник из вершин параллелепипеда ───────────────────────
# Объём многогранника, образованного вершинами параллелепипеда, считается
# как объём пирамиды/тетраэдра: V = (1/3)·S_осн·h, где h — расстояние от
# вершины до плоскости основания.

TYPE_PARAL = [
    (
        r"В прямоугольном параллелепипеде \(ABCDA_1B_1C_1D_1\) известно, что \(AB = 6\), "
        r"\(BC = 5\), \(AA_1 = 4\). Найдите объём многогранника, вершинами которого "
        r"являются точки \(A\), \(B\), \(C\), \(B_1\).",
        "20",
        _SVG_PARAL_TETR,
    ),
    (
        r"В прямоугольном параллелепипеде \(ABCDA_1B_1C_1D_1\) известно, что \(AB = 3\), "
        r"\(AD = 9\), \(AA_1 = 4\). Найдите объём многогранника, вершинами которого "
        r"являются точки \(A\), \(B\), \(C\), \(D\), \(A_1\).",
        "36",
        _SVG_PARAL_PYR,
    ),
]


# ── Прототип 7: Многогранник из вершин правильной треугольной призмы ─────────
# Аналогично: V = (1/3)·S_осн·h. Боковое ребро призмы — высота нужной пирамиды.
# Иногда многогранник = призма − тетраэдр (тогда вычитаем).

TYPE_PRIZMA_VERTICES = [
    (
        r"Найдите объём многогранника, вершинами которого являются вершины \(A\), \(B\), \(C\), "
        r"\(C_1\) правильной треугольной призмы \(ABCA_1B_1C_1\), площадь основания которой "
        r"равна \(6\), а боковое ребро равно \(9\).",
        "18",
        _SVG_PRIZMA_TETR,
    ),
    (
        r"Найдите объём многогранника, вершинами которого являются вершины \(B\), \(C\), \(A_1\), "
        r"\(B_1\), \(C_1\) правильной треугольной призмы \(ABCA_1B_1C_1\), площадь основания "
        r"которой равна \(4\), а боковое ребро равно \(6\).",
        "16",
        _SVG_PRIZMA_5V,
    ),
]


# ── Прототип 8: Сечение призмы средней линией основания ──────────────────────
# Через среднюю линию основания призмы проводится плоскость, параллельная
# боковому ребру. Отсечённая призма имеет:
#   • основание подобное исходному с коэффициентом 1/2,
#   • V_отсеч = V_исх / 4 (площади оснований относятся как 1:4),
#   • S_бок_отсеч = S_бок_исх / 2 (периметр основания вдвое меньше).

TYPE_SREDN_LINIYA = [
    (
        r"Через среднюю линию основания треугольной призмы, объём которой равен \(52\), "
        r"проведена плоскость, параллельная боковому ребру. "
        r"Найдите объём отсечённой треугольной призмы.",
        "13",
        _SVG_PRIZMA_SREDN,
    ),
    (
        r"Площадь боковой поверхности треугольной призмы равна \(24\). "
        r"Через среднюю линию основания призмы проведена плоскость, параллельная боковому ребру. "
        r"Найдите площадь боковой поверхности отсечённой треугольной призмы.",
        "12",
        _SVG_PRIZMA_SREDN,
    ),
]


# ──────────────────────────────────────────────────────────────────────────────
# Список прототипов
# ──────────────────────────────────────────────────────────────────────────────

ASSIGNMENTS = [
    {
        "title": "Изменение параметров конуса/цилиндра",
        "order": 1,
        "description": (
            r"Объём конуса/цилиндра: \(V = \pi R^2 h\) или \(V = \tfrac{1}{3}\pi R^2 h\). "
            r"При изменении высоты в \(k\) раз объём меняется в \(k\) раз; "
            r"при изменении радиуса в \(k\) раз — в \(k^2\) раз."
        ),
        "required_correct": 2,
        "questions": TYPE_IZM_PARAMETROV,
    },
    {
        "title": "Цилиндр и конус с общим основанием и высотой: объём",
        "order": 2,
        "description": (
            r"Если у цилиндра и конуса общие основание и высота, то "
            r"\(V_{\text{конуса}} = \tfrac{1}{3} V_{\text{цилиндра}}\)."
        ),
        "required_correct": 2,
        "questions": TYPE_CYL_CONE_V,
    },
    {
        "title": "Цилиндр и конус с общим основанием при \\(h = R\\): площадь",
        "order": 3,
        "description": (
            r"При высоте, равной радиусу: \(S_{\text{бок.цил}} = 2\pi R^2\), "
            r"\(S_{\text{бок.конуса}} = \pi R \cdot R\sqrt{2} = \pi R^2\sqrt{2}\). "
            r"Отношение \(\dfrac{S_{\text{конуса}}}{S_{\text{цил}}} = \dfrac{\sqrt{2}}{2}\)."
        ),
        "required_correct": 2,
        "questions": TYPE_CYL_CONE_S,
    },
    {
        "title": "Шар, вписанный в цилиндр",
        "order": 4,
        "description": (
            r"При шаре, вписанном в цилиндр: \(h_{\text{цил}} = 2R\), \(R_{\text{шара}} = R_{\text{цил}}\). "
            r"Тогда \(\dfrac{V_{\text{шара}}}{V_{\text{цил}}} = \dfrac{2}{3}\) и "
            r"\(\dfrac{S_{\text{шара}}}{S_{\text{полн.цил}}} = \dfrac{2}{3}\)."
        ),
        "required_correct": 2,
        "questions": TYPE_SHAR_V_CYL,
    },
    {
        "title": "Конус, вписанный в шар (\\(R\\) конуса \\(=\\) \\(R\\) шара)",
        "order": 5,
        "description": (
            r"Если радиус основания конуса равен радиусу шара, то центр шара лежит в основании конуса, "
            r"а высота конуса \(h = R\). "
            r"Тогда \(V_{\text{шара}} = 4 V_{\text{конуса}}\), а образующая \(l = R\sqrt{2}\)."
        ),
        "required_correct": 2,
        "questions": TYPE_CONE_V_SHAR,
    },
    {
        "title": "Многогранник из вершин параллелепипеда",
        "order": 6,
        "description": (
            r"Объём пирамиды: \(V = \tfrac{1}{3} S_{\text{осн}} \cdot h\), где \(h\) — расстояние "
            r"от вершины до плоскости основания. "
            r"Если основание — треугольник на грани, то \(S_{\text{осн}} = \tfrac{1}{2}\) от площади грани. "
            r"Если 6 вершин — это половина параллелепипеда: \(V = \tfrac{1}{2} V_{\text{паралл}}\)."
        ),
        "required_correct": 2,
        "questions": TYPE_PARAL,
    },
    {
        "title": "Многогранник из вершин правильной треугольной призмы",
        "order": 7,
        "description": (
            r"Аналогично параллелепипеду: \(V = \tfrac{1}{3} S_{\text{осн}} \cdot h\). "
            r"Боковое ребро призмы — это высота возможной пирамиды. "
            r"Если многогранник имеет 5 вершин (без одной из шести): "
            r"\(V_{\text{мн.}} = V_{\text{призмы}} - V_{\text{отсечённого тетраэдра}}\)."
        ),
        "required_correct": 2,
        "questions": TYPE_PRIZMA_VERTICES,
    },
    {
        "title": "Сечение призмы через среднюю линию основания",
        "order": 8,
        "description": (
            r"Плоскость через среднюю линию основания, параллельная боковому ребру, "
            r"отсекает призму, подобную исходной с коэффициентом \(\tfrac{1}{2}\). "
            r"Объёмы относятся как \(1 : 4\): \(V_{\text{отсеч}} = \tfrac{1}{4} V_{\text{исх}}\). "
            r"Боковая поверхность относится как \(1 : 2\) (по периметру основания): "
            r"\(S_{\text{бок.отсеч}} = \tfrac{1}{2} S_{\text{бок.исх}}\)."
        ),
        "required_correct": 2,
        "questions": TYPE_SREDN_LINIYA,
    },
]


class Command(BaseCommand):
    help = "Populate EGE Task 3 questions (стереометрия)"

    def add_arguments(self, parser):
        parser.add_argument(
            "--clear",
            action="store_true",
            help="Delete existing EGE-3 lesson before inserting",
        )

    def handle(self, *args, **options):
        course = Course.objects.filter(slug="ege-profile-math").first()
        if not course:
            self.stdout.write(self.style.ERROR("Course 'ege-profile-math' not found."))
            return

        module, _ = Module.objects.get_or_create(
            course=course,
            order=1,
            defaults={
                "title": "Первая часть",
                "description": "Задачи первой части профильного ЕГЭ.",
            },
        )

        if options["clear"]:
            deleted, _ = Lesson.objects.filter(module=module, order=3).delete()
            self.stdout.write(self.style.WARNING(
                f"Deleted existing lesson (order=3): {deleted} objects"
            ))

        lesson, created = Lesson.objects.get_or_create(
            module=module,
            order=3,
            defaults={
                "title": "Задание 3",
                "lesson_type": "practice",
            },
        )
        if not created:
            self.stdout.write(self.style.WARNING(
                "Lesson already exists (use --clear to reset)."
            ))

        total_q = 0
        for data in ASSIGNMENTS:
            assignment, created = Assignment.objects.get_or_create(
                lesson=lesson,
                order=data["order"],
                defaults={
                    "title": data["title"],
                    "description": data["description"],
                    "answer_type": "decimal_input",
                    "required_correct": data["required_correct"],
                },
            )
            if not created:
                self.stdout.write(self.style.WARNING(
                    f"  Assignment already exists: {assignment.title} -- skipping"
                ))
                continue

            for idx, item in enumerate(data["questions"]):
                if len(item) == 3:
                    q_text, answer, image_svg = item
                else:
                    q_text, answer = item
                    image_svg = ""
                question = TestQuestion.objects.create(
                    assignment=assignment,
                    question_text=q_text,
                    order=idx + 1,
                    image_svg=image_svg,
                )
                AnswerOption.objects.create(
                    question=question,
                    text=answer,
                    is_correct=True,
                )
                total_q += 1

        self.stdout.write(self.style.SUCCESS(
            f"Done! Lesson: Zadacha 3, {total_q} questions added."
        ))
