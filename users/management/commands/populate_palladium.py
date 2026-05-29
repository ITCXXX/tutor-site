# -*- coding: utf-8 -*-
"""
Management command: создаёт курс «Система Палладия» с теоретическим модулем.

Использование:
    python manage.py populate_palladium
    python manage.py populate_palladium --clear   # удалить курс целиком

Идемпотентна: повторный запуск обновляет описание и контент уроков, но не
плодит дубликаты Course/Module/Lesson.

Структура (текущий шаг — только теория-методичка):
    Course 'palladium' (tracking_mode=auto, is_active=True, owner=None)
    └── Module 1: «Теория системы Палладия»
        ├── Lesson 1: Введение и принципы
        ├── Lesson 2: Таблица инициалей
        ├── Lesson 3: Таблица финалей
        ├── Lesson 4: Правила стыковки двуслогов  ← главная глава
        └── Lesson 5: Спорные случаи и исключения

После проверки методички следующим шагом будет добавлен Module 2
«Тренажёр двуслогов» с ProblemGenerator, использующий правила из этой теории
как спецификацию.
"""

from django.core.management.base import BaseCommand
from django.db import transaction

from users.models import Course, Module, Lesson, Assignment, ProblemGenerator
from users.palladium import PALLADIUS, SYLLABLES, join_palladium


COURSE_SLUG = 'palladium'
COURSE_TITLE = 'Система Палладия — транскрипция китайского'
COURSE_SHORT = (
    'Тренировка записи китайских слогов и двусложных слов по транскрипционной '
    'системе Палладия — стандарту русской китаистики.'
)
COURSE_FULL = (
    'Курс содержит методическую часть (правила системы Палладия и стыковки '
    'двуслогов) и тренажёр, который генерирует случайные двусложные комбинации '
    'из пиньиня и проверяет правильность транскрипции.\n\n'
    'Подходит тем, кто изучает китайский и хочет уверенно читать и записывать '
    'имена и топонимы по-русски без обращения к таблицам.'
)


# ──────────────────────────────────────────────────────────────────────────────
# Контент теоретических уроков. HTML внутри content поля, рендерится через
# {{ lesson.content|safe }} в lesson_detail.html.
# Стили классов .ex / .note / .warn / .pinyin / .pld / .arrow определены
# в самом шаблоне lesson_detail.html.
# ──────────────────────────────────────────────────────────────────────────────


LESSON_INTRO = """
<p>
<b>Система Палладия</b> — это официальная транскрипционная система для записи
китайских слов средствами русского алфавита. Названа в честь архимандрита
Палладия (Кафарова), создавшего основу таблицы в XIX веке. Система
зафиксирована в академических справочниках (Концевич, БРЭ) и используется в
российской китаистике, СМИ, картографии.
</p>

<h2>Чем Палладий отличается от пиньиня</h2>
<ul>
  <li>Пиньинь записывает <i>звучание</i> латиницей с тонами
    (<span class="pinyin">xié</span>);</li>
  <li>Палладий записывает <i>тот же звук</i> кириллицей <b>без тонов</b>
    (<span class="pld">се</span>).</li>
</ul>

<div class="note">
<b>Главный принцип.</b> Палладий передаёт не побуквенную транслитерацию
пиньиня, а целые слоги. Поэтому работа всегда идёт через таблицу слогов —
буквы по отдельности «переводить» нельзя.
</div>

<h2>Что мы тренируем в этом курсе</h2>
<p>Курс сосредоточен на главной трудности — <b>стыковке двух слогов
в одном слове</b>. Например:</p>

<div class="ex">
<span class="pinyin">chang + an</span> <span class="arrow">→</span>
<span class="pld">чанъань</span> &nbsp; (твёрдый знак ъ на стыке)<br>
<span class="pinyin">tian + an</span> <span class="arrow">→</span>
<span class="pld">тяньань</span> &nbsp; (мягкий знак ь уже был)<br>
<span class="pinyin">xi + an</span> <span class="arrow">→</span>
<span class="pld">сиань</span> &nbsp; (на стыке гласной и -an)
</div>

<p>Такие пары требуют понимания правил, а не просто памяти таблицы.
Поэтому начинаем с теории, а затем переходим к генератору задач.</p>

<h2>Структура курса</h2>
<ol>
  <li><b>Введение</b> (этот урок).</li>
  <li><b>Инициали</b> — таблица начальных согласных.</li>
  <li><b>Финали</b> — таблица окончаний слога.</li>
  <li><b>Правила стыковки двуслогов</b> — ключевая глава.</li>
  <li><b>Спорные случаи и исключения</b> — традиционные написания
      (Пекин ≠ Бэйцзин), особенности финали <span class="pinyin">-ui</span>,
      инициаль <span class="pinyin">r-</span>, серия с ü.</li>
</ol>
"""


LESSON_INITIALS = """
<p>В мандарине 21 инициаль (начальный согласный слога) + «нулевая» инициаль.
Ниже — соответствия пиньинь → Палладий. Запоминать побуквенно не нужно:
правильное произношение возникает при сочетании с финалью (см. следующий урок).</p>

<h2>Губные и переднеязычные</h2>
<table>
<tr><th>Пиньинь</th><th>Палладий</th><th>Примечание</th></tr>
<tr><td><span class="pinyin">b</span></td><td><span class="pld">б</span></td><td>как «б»</td></tr>
<tr><td><span class="pinyin">p</span></td><td><span class="pld">п</span></td><td>придыхательное «п»</td></tr>
<tr><td><span class="pinyin">m</span></td><td><span class="pld">м</span></td><td></td></tr>
<tr><td><span class="pinyin">f</span></td><td><span class="pld">ф</span></td><td></td></tr>
<tr><td><span class="pinyin">d</span></td><td><span class="pld">д</span></td><td></td></tr>
<tr><td><span class="pinyin">t</span></td><td><span class="pld">т</span></td><td>придыхательное «т»</td></tr>
<tr><td><span class="pinyin">n</span></td><td><span class="pld">н</span></td><td></td></tr>
<tr><td><span class="pinyin">l</span></td><td><span class="pld">л</span></td><td></td></tr>
<tr><td><span class="pinyin">g</span></td><td><span class="pld">г</span></td><td></td></tr>
<tr><td><span class="pinyin">k</span></td><td><span class="pld">к</span></td><td>придыхательное «к»</td></tr>
<tr><td><span class="pinyin">h</span></td><td><span class="pld">х</span></td><td></td></tr>
</table>

<h2>Серия j/q/x (палатальные)</h2>
<p>Сочетаются только с гласными переднего ряда <span class="pinyin">i</span> и
<span class="pinyin">ü</span> (последняя в пиньине после j/q/x пишется как <span class="pinyin">u</span>).</p>
<table>
<tr><th>Пиньинь</th><th>Палладий (с i)</th><th>Палладий (с ü)</th></tr>
<tr><td><span class="pinyin">j</span></td><td><span class="pld">цз</span> (<span class="pinyin">ji</span>→<span class="pld">цзи</span>)</td><td><span class="pld">цзю</span> (<span class="pinyin">ju</span>→<span class="pld">цзюй</span>)</td></tr>
<tr><td><span class="pinyin">q</span></td><td><span class="pld">ц</span> (<span class="pinyin">qi</span>→<span class="pld">ци</span>)</td><td><span class="pld">цю</span> (<span class="pinyin">qu</span>→<span class="pld">цюй</span>)</td></tr>
<tr><td><span class="pinyin">x</span></td><td><span class="pld">с</span> (<span class="pinyin">xi</span>→<span class="pld">си</span>)</td><td><span class="pld">сю</span> (<span class="pinyin">xu</span>→<span class="pld">сюй</span>)</td></tr>
</table>

<h2>Шипящие zh / ch / sh / r</h2>
<table>
<tr><th>Пиньинь</th><th>Палладий</th><th>Пример</th></tr>
<tr><td><span class="pinyin">zh</span></td><td><span class="pld">чж</span></td><td><span class="pinyin">zhang</span>→<span class="pld">чжан</span></td></tr>
<tr><td><span class="pinyin">ch</span></td><td><span class="pld">ч</span></td><td><span class="pinyin">chang</span>→<span class="pld">чан</span></td></tr>
<tr><td><span class="pinyin">sh</span></td><td><span class="pld">ш</span></td><td><span class="pinyin">shang</span>→<span class="pld">шан</span></td></tr>
<tr><td><span class="pinyin">r</span></td><td><span class="pld">ж</span></td><td><span class="pinyin">ren</span>→<span class="pld">жэнь</span> (не «р»!)</td></tr>
</table>

<h2>Свистящие z / c / s</h2>
<table>
<tr><th>Пиньинь</th><th>Палладий</th><th>Пример</th></tr>
<tr><td><span class="pinyin">z</span></td><td><span class="pld">цз</span></td><td><span class="pinyin">za</span>→<span class="pld">цза</span>, <span class="pinyin">zi</span>→<span class="pld">цзы</span></td></tr>
<tr><td><span class="pinyin">c</span></td><td><span class="pld">ц</span></td><td><span class="pinyin">ca</span>→<span class="pld">ца</span>, <span class="pinyin">ci</span>→<span class="pld">цы</span></td></tr>
<tr><td><span class="pinyin">s</span></td><td><span class="pld">с</span></td><td><span class="pinyin">sa</span>→<span class="pld">са</span>, <span class="pinyin">si</span>→<span class="pld">сы</span></td></tr>
</table>

<h2>Нулевая инициаль: y / w</h2>
<p>В пиньине нулевая инициаль перед <span class="pinyin">i</span>,
<span class="pinyin">u</span> и <span class="pinyin">ü</span> записывается
буквами <span class="pinyin">y</span> и <span class="pinyin">w</span>. В
Палладии эти буквы не передаются отдельно — слог берётся целиком из таблицы.</p>
<div class="ex">
<span class="pinyin">yi</span>→<span class="pld">и</span> &nbsp;
<span class="pinyin">wu</span>→<span class="pld">у</span> &nbsp;
<span class="pinyin">yu</span>→<span class="pld">юй</span> &nbsp;
<span class="pinyin">yan</span>→<span class="pld">янь</span> &nbsp;
<span class="pinyin">wang</span>→<span class="pld">ван</span> &nbsp;
<span class="pinyin">you</span>→<span class="pld">ю</span> &nbsp;
<span class="pinyin">yong</span>→<span class="pld">юн</span>
</div>

<div class="warn">
<b>Важно:</b> инициаль <span class="pinyin">r</span> даёт <span class="pld">ж</span>,
а не «р». Слово <span class="pinyin">ren</span> («человек») по Палладию —
<span class="pld">жэнь</span>, не «рен».
</div>
"""


LESSON_FINALS = """
<p>Финаль — это всё, что идёт после инициали (или весь слог, если инициаль
нулевая). Финалей в мандарине 35. Ниже — основные группы.</p>

<h2>Простые финали</h2>
<table>
<tr><th>Пиньинь</th><th>Палладий</th><th>Пример</th></tr>
<tr><td><span class="pinyin">-a</span></td><td><span class="pld">-а</span></td><td><span class="pinyin">ma</span>→<span class="pld">ма</span></td></tr>
<tr><td><span class="pinyin">-o</span></td><td><span class="pld">-о</span></td><td><span class="pinyin">bo</span>→<span class="pld">бо</span></td></tr>
<tr><td><span class="pinyin">-e</span></td><td><span class="pld">-э</span> / <span class="pld">-е</span></td>
    <td><span class="pinyin">ge</span>→<span class="pld">гэ</span>, но <span class="pinyin">de</span>→<span class="pld">дэ</span>; после j/q/x с -ie: <span class="pinyin">xie</span>→<span class="pld">се</span></td></tr>
<tr><td><span class="pinyin">-i</span></td><td><span class="pld">-и</span> / <span class="pld">-ы</span></td>
    <td>после z/c/s и zh/ch/sh/r → ы (<span class="pinyin">zi</span>→<span class="pld">цзы</span>, <span class="pinyin">chi</span>→<span class="pld">чи</span> — здесь и); иначе и</td></tr>
<tr><td><span class="pinyin">-u</span></td><td><span class="pld">-у</span></td><td><span class="pinyin">bu</span>→<span class="pld">бу</span></td></tr>
<tr><td><span class="pinyin">-ü</span> (после j/q/x пишется как u)</td><td><span class="pld">-юй</span></td>
    <td><span class="pinyin">qu</span>→<span class="pld">цюй</span></td></tr>
</table>

<h2>Дифтонги и трифтонги</h2>
<table>
<tr><th>Пиньинь</th><th>Палладий</th><th>Пример</th></tr>
<tr><td><span class="pinyin">-ai</span></td><td><span class="pld">-ай</span></td><td><span class="pinyin">bai</span>→<span class="pld">бай</span></td></tr>
<tr><td><span class="pinyin">-ei</span></td><td><span class="pld">-эй</span></td><td><span class="pinyin">bei</span>→<span class="pld">бэй</span>, <span class="pinyin">mei</span>→<span class="pld">мэй</span></td></tr>
<tr><td><span class="pinyin">-ao</span></td><td><span class="pld">-ао</span></td><td><span class="pinyin">bao</span>→<span class="pld">бао</span></td></tr>
<tr><td><span class="pinyin">-ou</span></td><td><span class="pld">-оу</span></td><td><span class="pinyin">dou</span>→<span class="pld">доу</span></td></tr>
<tr><td><span class="pinyin">-ia</span></td><td><span class="pld">-я</span></td><td><span class="pinyin">jia</span>→<span class="pld">цзя</span></td></tr>
<tr><td><span class="pinyin">-ie</span></td><td><span class="pld">-е</span></td><td><span class="pinyin">xie</span>→<span class="pld">се</span>, <span class="pinyin">tie</span>→<span class="pld">те</span></td></tr>
<tr><td><span class="pinyin">-iao</span></td><td><span class="pld">-яо</span></td><td><span class="pinyin">xiao</span>→<span class="pld">сяо</span></td></tr>
<tr><td><span class="pinyin">-iu</span> (= -iou)</td><td><span class="pld">-ю</span></td><td><span class="pinyin">liu</span>→<span class="pld">лю</span>, <span class="pinyin">jiu</span>→<span class="pld">цзю</span></td></tr>
<tr><td><span class="pinyin">-ua</span></td><td><span class="pld">-уа</span></td><td><span class="pinyin">hua</span>→<span class="pld">хуа</span></td></tr>
<tr><td><span class="pinyin">-uo</span></td><td><span class="pld">-о</span> / <span class="pld">-уо</span></td>
    <td><span class="pinyin">duo</span>→<span class="pld">до</span>, <span class="pinyin">guo</span>→<span class="pld">го</span>; после шипящих <span class="pinyin">shuo</span>→<span class="pld">шо</span></td></tr>
<tr><td><span class="pinyin">-ui</span> (= -uei)</td><td><span class="pld">-уй</span> / <span class="pld">-уэй</span></td>
    <td><span class="pinyin">gui</span>→<span class="pld">гуй</span>, но <span class="pinyin">hui</span>→<span class="pld">хуэй</span> (особый случай, см. урок 5)</td></tr>
<tr><td><span class="pinyin">-uai</span></td><td><span class="pld">-уай</span></td><td><span class="pinyin">kuai</span>→<span class="pld">куай</span></td></tr>
<tr><td><span class="pinyin">-üe</span> (после j/q/x — ue)</td><td><span class="pld">-юэ</span></td><td><span class="pinyin">xue</span>→<span class="pld">сюэ</span></td></tr>
</table>

<h2>Носовые финали (-n и -ng)</h2>
<div class="warn">
<b>Различение -n и -ng — главная развилка Палладия.</b> Финаль на
<span class="pinyin">-n</span> передаётся как <b>-нь</b> (мягкий знак),
финаль на <span class="pinyin">-ng</span> — как <b>-н</b> (без мягкого знака).
</div>
<table>
<tr><th>Пиньинь</th><th>Палладий</th><th>Пример</th></tr>
<tr><td><span class="pinyin">-an</span></td><td><span class="pld">-ань</span></td><td><span class="pinyin">san</span>→<span class="pld">сань</span></td></tr>
<tr><td><span class="pinyin">-ang</span></td><td><span class="pld">-ан</span></td><td><span class="pinyin">sang</span>→<span class="pld">сан</span></td></tr>
<tr><td><span class="pinyin">-en</span></td><td><span class="pld">-энь</span></td><td><span class="pinyin">ben</span>→<span class="pld">бэнь</span></td></tr>
<tr><td><span class="pinyin">-eng</span></td><td><span class="pld">-эн</span></td><td><span class="pinyin">beng</span>→<span class="pld">бэн</span></td></tr>
<tr><td><span class="pinyin">-in</span></td><td><span class="pld">-инь</span></td><td><span class="pinyin">lin</span>→<span class="pld">линь</span></td></tr>
<tr><td><span class="pinyin">-ing</span></td><td><span class="pld">-ин</span></td><td><span class="pinyin">ling</span>→<span class="pld">лин</span></td></tr>
<tr><td><span class="pinyin">-ian</span></td><td><span class="pld">-янь</span></td><td><span class="pinyin">tian</span>→<span class="pld">тянь</span></td></tr>
<tr><td><span class="pinyin">-iang</span></td><td><span class="pld">-ян</span></td><td><span class="pinyin">xiang</span>→<span class="pld">сян</span></td></tr>
<tr><td><span class="pinyin">-uan</span></td><td><span class="pld">-уань</span></td><td><span class="pinyin">guan</span>→<span class="pld">гуань</span></td></tr>
<tr><td><span class="pinyin">-uang</span></td><td><span class="pld">-уан</span></td><td><span class="pinyin">guang</span>→<span class="pld">гуан</span></td></tr>
<tr><td><span class="pinyin">-un</span> (= -uen)</td><td><span class="pld">-унь</span></td><td><span class="pinyin">lun</span>→<span class="pld">лунь</span>, <span class="pinyin">sun</span>→<span class="pld">сунь</span></td></tr>
<tr><td><span class="pinyin">-ong</span></td><td><span class="pld">-ун</span></td><td><span class="pinyin">long</span>→<span class="pld">лун</span></td></tr>
<tr><td><span class="pinyin">-iong</span></td><td><span class="pld">-юн</span></td><td><span class="pinyin">xiong</span>→<span class="pld">сюн</span></td></tr>
<tr><td><span class="pinyin">-üan</span> (после j/q/x — uan)</td><td><span class="pld">-юань</span></td><td><span class="pinyin">quan</span>→<span class="pld">цюань</span></td></tr>
<tr><td><span class="pinyin">-ün</span> (после j/q/x — un)</td><td><span class="pld">-юнь</span></td><td><span class="pinyin">jun</span>→<span class="pld">цзюнь</span></td></tr>
</table>

<div class="note">
<b>Мнемоническое правило:</b> мягкий знак (ь) появляется только там, где в
пиньине стоит <i>одиночное</i> <span class="pinyin">n</span> в конце слога.
Если на конце <span class="pinyin">ng</span> — мягкого знака нет.
</div>
"""


LESSON_JUNCTIONS = """
<p>Это центральный урок курса. Когда два слога стоят в одном слове, между ними
могут возникать стыки, которые правильно записываются только по специальным
правилам. Большинство ошибок русских транскрипций — именно здесь.</p>

<h2>Правило 1. Базовая склейка</h2>
<p>Если на стыке нет конфликта — слоги Палладия просто склеиваются.</p>
<div class="ex">
<span class="pinyin">xie + zhang</span> <span class="arrow">→</span>
<span class="pld">се + чжан</span> <span class="arrow">→</span>
<span class="pld">сечжан</span><br>
<span class="pinyin">mao + dun</span> <span class="arrow">→</span>
<span class="pld">мао + дунь</span> <span class="arrow">→</span>
<span class="pld">маодунь</span><br>
<span class="pinyin">shi + jin</span> <span class="arrow">→</span>
<span class="pld">ши + цзинь</span> <span class="arrow">→</span>
<span class="pld">шицзинь</span>
</div>

<h2>Правило 2. Твёрдая согласная + гласная: разделительный ъ</h2>
<p>Если первый палладий-слог оканчивается на <b>твёрдую согласную</b>
(их в системе всего две — <b>«н»</b> от пиньинь-финали <span class="pinyin">-ng</span>
и <b>«р»</b> от слога <span class="pinyin">er</span>),
а следующий слог в Палладии начинается с гласной — между ними ставится
<b>твёрдый знак ъ</b>.</p>

<h3>2.1. -ng + гласная</h3>
<div class="ex">
<span class="pinyin">chang + an</span> <span class="arrow">→</span>
<span class="pld">чан + ань</span> <span class="arrow">→</span>
<span class="pld">чанъань</span><br>
<span class="pinyin">peng + you</span> <span class="arrow">→</span>
<span class="pld">пэн + ю</span> <span class="arrow">→</span>
<span class="pld">пэнъю</span><br>
<span class="pinyin">dong + e</span> <span class="arrow">→</span>
<span class="pld">дун + э</span> <span class="arrow">→</span>
<span class="pld">дунъэ</span><br>
<span class="pinyin">chang + yao</span> <span class="arrow">→</span>
<span class="pld">чан + яо</span> <span class="arrow">→</span>
<span class="pld">чанъяо</span>
</div>

<h3>2.2. er + гласная (то же правило)</h3>
<p>Слог <span class="pinyin">er</span> даёт твёрдое <b>«эр»</b>, поэтому
работает то же правило: перед гласной следующего слога ставится ъ.
Логика та же, что в русских словах «подъезд», «съел».</p>
<div class="ex">
<span class="pinyin">er + yao</span> <span class="arrow">→</span>
<span class="pld">эр + яо</span> <span class="arrow">→</span>
<span class="pld">эръяо</span><br>
<span class="pinyin">er + yue</span> <span class="arrow">→</span>
<span class="pld">эр + юэ</span> <span class="arrow">→</span>
<span class="pld">эръюэ</span> &nbsp;(二月 «февраль»)<br>
<span class="pinyin">er + yi</span> <span class="arrow">→</span>
<span class="pld">эр + и</span> <span class="arrow">→</span>
<span class="pld">эръи</span>
</div>
<p>Но если после <span class="pinyin">er</span> идёт согласная — никакого ъ:</p>
<div class="ex">
<span class="pinyin">er + shi</span> <span class="arrow">→</span>
<span class="pld">эрши</span> &nbsp;(二十 «двадцать»)<br>
<span class="pinyin">er + duo</span> <span class="arrow">→</span>
<span class="pld">эрдо</span> &nbsp;(耳朵 «ухо»)<br>
<span class="pinyin">er + hou</span> <span class="arrow">→</span>
<span class="pld">эрхоу</span> &nbsp;(而后 «после того как»)
</div>

<h2>Правило 3. -n + гласная: ничего не вставляем</h2>
<p>Если первый слог в пиньине оканчивается на <span class="pinyin">-n</span>
(в Палладии уже стоит мягкий знак <b>-нь</b>), разделитель не нужен:
мягкий знак сам делает работу.</p>
<div class="ex">
<span class="pinyin">tian + an</span> <span class="arrow">→</span>
<span class="pld">тянь + ань</span> <span class="arrow">→</span>
<span class="pld">тяньань</span><br>
<span class="pinyin">xi + an</span> <span class="arrow">→</span>
<span class="pld">си + ань</span> <span class="arrow">→</span>
<span class="pld">сиань</span><br>
<span class="pinyin">tian'anmen</span> <span class="arrow">→</span>
<span class="pld">тянь + ань + мэнь</span> <span class="arrow">→</span>
<span class="pld">тяньаньмэнь</span>
</div>

<div class="note">
<b>Запомните разницу:</b><br>
&nbsp;&nbsp;<span class="pinyin">chang'an</span> (тут <span class="pinyin">-ng</span>)
<span class="arrow">→</span> <span class="pld">чан<b>ъ</b>ань</span><br>
&nbsp;&nbsp;<span class="pinyin">xi'an</span> (тут <span class="pinyin">xi</span> — нет ng)
<span class="arrow">→</span> <span class="pld">сиань</span><br>
&nbsp;&nbsp;<span class="pinyin">tian'an</span> (тут <span class="pinyin">-n</span>)
<span class="arrow">→</span> <span class="pld">тяньань</span>
</div>

<h2>Правило 4. Апостроф пиньиня в Палладии не передаётся</h2>
<p>Апостроф в пиньине (<span class="pinyin">Xi'an</span>,
<span class="pinyin">Chang'an</span>) — это служебный знак слогораздела
для латиницы. В Палладии его не пишут: разделение видно по мягкому знаку или
твёрдому знаку, либо просто по гласной начала второго слога.</p>

<h2>Правило 5. Дефис в Палладии (только для имён)</h2>
<p>В традиции некоторых старых переводов имена собственные записывают через
дефис (<span class="pinyin">Mao Ze-dong</span> →
<span class="pld">Мао Цзэ-дун</span>). В современной норме это
необязательно. В нашем тренажёре имена пишутся <b>слитно</b>:
<span class="pld">маоцзэдун</span>.</p>

<h2>Сводная схема (главная развилка)</h2>
<table>
<tr><th>Конец 1-го палладий-слога</th><th>Начало 2-го</th><th>Что вставляем</th><th>Пример</th></tr>
<tr><td>твёрдое <b>«н»</b> (от пиньинь -ng)</td><td>гласная</td><td><b>ъ</b></td>
    <td><span class="pinyin">chang+an</span> → <span class="pld">чан<b>ъ</b>ань</span></td></tr>
<tr><td>твёрдое <b>«р»</b> (от пиньинь er)</td><td>гласная</td><td><b>ъ</b></td>
    <td><span class="pinyin">er+yao</span> → <span class="pld">эр<b>ъ</b>яо</span></td></tr>
<tr><td>мягкое <b>«нь»</b> (от пиньинь -n)</td><td>гласная</td><td>—</td>
    <td><span class="pinyin">tian+an</span> → <span class="pld">тяньань</span></td></tr>
<tr><td>гласная</td><td>гласная</td><td>—</td>
    <td><span class="pinyin">xi+an</span> → <span class="pld">сиань</span></td></tr>
<tr><td>любое</td><td>согласная</td><td>—</td>
    <td><span class="pinyin">xie+zhang</span> → <span class="pld">сечжан</span></td></tr>
</table>

<div class="warn">
<b>Что НЕ нужно делать:</b><br>
&nbsp;✗ не вставляйте ъ после <span class="pinyin">-n</span> (мягкий знак уже есть);<br>
&nbsp;✗ не вставляйте ь там, где идёт <span class="pinyin">-ng</span> + согласная
(например, <span class="pinyin">chang+shu</span> → <span class="pld">чаншу</span>, не «чаньшу»);<br>
&nbsp;✗ не сохраняйте апостроф пиньиня — в Палладии его нет.
</div>
"""


LESSON_EDGE_CASES = """
<p>Палладий — система с несколькими «зашитыми» исключениями и спорными
зонами. Их полезно знать, чтобы не путаться при чтении текстов.</p>

<h2>Традиционные написания (вне системы)</h2>
<p>Некоторые топонимы и имена закрепились в русском языке задолго до
введения Палладия и не подчиняются его правилам:</p>
<table>
<tr><th>Пиньинь</th><th>Привычное русское</th><th>«Чистый» Палладий</th></tr>
<tr><td><span class="pinyin">Beijing</span></td><td>Пекин</td><td>(было бы <i>Бэйцзин</i>)</td></tr>
<tr><td><span class="pinyin">Nanjing</span></td><td>Нанкин</td><td>(было бы <i>Наньцзин</i>)</td></tr>
<tr><td><span class="pinyin">Hongkong</span></td><td>Гонконг</td><td>(юж. диалект, не путунхуа)</td></tr>
<tr><td><span class="pinyin">Guangzhou</span></td><td>Гуанчжоу</td><td>(совпадает с Палладием)</td></tr>
<tr><td><span class="pinyin">Confucius / Kongzi</span></td><td>Конфуций</td><td>(латинизированная форма)</td></tr>
</table>
<div class="note">
В тренажёре мы тренируем чистые слоги, без исключений-топонимов. Поэтому
ответ всегда подчиняется правилам системы.
</div>

<h2>Особая финаль -ui</h2>
<p>Стандартный Палладий: <span class="pinyin">-ui</span> → <span class="pld">-уй</span>
(<span class="pinyin">gui</span>→<span class="pld">гуй</span>,
<span class="pinyin">kui</span>→<span class="pld">куй</span>).
<b>Исключение:</b> после <span class="pinyin">h</span> финаль передаётся как
<span class="pld">-уэй</span>:</p>
<div class="ex">
<span class="pinyin">hui</span> <span class="arrow">→</span>
<span class="pld">хуэй</span> &nbsp;(а не «хуй»)
</div>

<h2>Серия с инициалью r-</h2>
<p>Самая частая ошибка новичков — записывать <span class="pinyin">r-</span>
как «р». В Палладии это <b>ж</b>:</p>
<div class="ex">
<span class="pinyin">ren</span>→<span class="pld">жэнь</span> &nbsp;
<span class="pinyin">ru</span>→<span class="pld">жу</span> &nbsp;
<span class="pinyin">rou</span>→<span class="pld">жоу</span> &nbsp;
<span class="pinyin">ri</span>→<span class="pld">жи</span> &nbsp;
<span class="pinyin">rao</span>→<span class="pld">жао</span>
</div>

<h2>Шипящие + i: ы или и?</h2>
<table>
<tr><th>После</th><th>Финаль -i</th><th>Пример</th></tr>
<tr><td><span class="pinyin">z, c, s</span></td><td><span class="pld">-ы</span></td>
    <td><span class="pinyin">zi</span>→<span class="pld">цзы</span>, <span class="pinyin">si</span>→<span class="pld">сы</span></td></tr>
<tr><td><span class="pinyin">zh, ch, sh, r</span></td><td><span class="pld">-и</span></td>
    <td><span class="pinyin">zhi</span>→<span class="pld">чжи</span>, <span class="pinyin">ri</span>→<span class="pld">жи</span></td></tr>
<tr><td>все остальные</td><td><span class="pld">-и</span></td>
    <td><span class="pinyin">li</span>→<span class="pld">ли</span>, <span class="pinyin">ji</span>→<span class="pld">цзи</span></td></tr>
</table>

<h2>Нулевая инициаль (y/w) и ü</h2>
<p>После j/q/x пиньинь экономит на знаках и пишет <span class="pinyin">u</span>
вместо <span class="pinyin">ü</span>. В Палладии разницы нет — берём слог целиком:</p>
<div class="ex">
<span class="pinyin">ju</span>→<span class="pld">цзюй</span> &nbsp;
<span class="pinyin">qu</span>→<span class="pld">цюй</span> &nbsp;
<span class="pinyin">xu</span>→<span class="pld">сюй</span> &nbsp;
<span class="pinyin">jue</span>→<span class="pld">цзюэ</span> &nbsp;
<span class="pinyin">quan</span>→<span class="pld">цюань</span> &nbsp;
<span class="pinyin">xun</span>→<span class="pld">сюнь</span>
</div>
<p>Только после <span class="pinyin">l</span> и <span class="pinyin">n</span>
пиньинь различает u и ü (потому что бывают оба):</p>
<div class="ex">
<span class="pinyin">lu</span>→<span class="pld">лу</span> vs.
<span class="pinyin">lü</span>→<span class="pld">люй</span><br>
<span class="pinyin">nu</span>→<span class="pld">ну</span> vs.
<span class="pinyin">nü</span>→<span class="pld">нюй</span>
</div>

<h2>Слоги, которых не существует</h2>
<p>Не во всех «логичных» комбинациях есть реальные мандарин-слоги. Например,
нет слогов <span class="pinyin">fi, fou, dia, ki, gi, ji-без-у/и</span>.
Тренажёр генерирует только реально существующие слоги из стандартной таблицы.</p>

<h2>Что мы решили зафиксировать в этом курсе</h2>
<ol>
  <li>Тренируем <b>пиньинь без тонов</b> → Палладий.</li>
  <li>Двуслоги пишутся <b>слитно</b> (<span class="pld">чанъань</span>,
      не «Чанъ-ань»).</li>
  <li>Все стыки прогоняются через правила урока 4.</li>
  <li>Исключения-топонимы (Пекин, Нанкин и т.п.) в тренажёр не входят.</li>
  <li>Финаль <span class="pinyin">hui</span> → <span class="pld">хуэй</span>
      (закреплённое исключение).</li>
</ol>
"""


LESSONS = [
    {
        'order': 0,
        'title': 'Введение и принципы',
        'content': LESSON_INTRO,
    },
    {
        'order': 1,
        'title': 'Инициали — таблица начальных согласных',
        'content': LESSON_INITIALS,
    },
    {
        'order': 2,
        'title': 'Финали — окончания слога',
        'content': LESSON_FINALS,
    },
    {
        'order': 3,
        'title': 'Правила стыковки двуслогов',
        'content': LESSON_JUNCTIONS,
    },
    {
        'order': 4,
        'title': 'Спорные случаи и исключения',
        'content': LESSON_EDGE_CASES,
    },
]


# ──────────────────────────────────────────────────────────────────────────────
# Модуль 2: тренажёр двуслогов.
# Один Assignment с типом text_input + ProblemGenerator, который через
# users.palladium берёт два случайных слога и склеивает.
# Код генератора держим максимально коротким, словарь и правила живут в
# users/palladium.py — это источник истины для всего курса.
# ──────────────────────────────────────────────────────────────────────────────

GENERATOR_NAME = 'Палладий: случайные двуслоги'
GENERATOR_CODE = '''\
import random
from users.palladium import SYLLABLES, join_palladium

def generate_task():
    s1 = random.choice(SYLLABLES)
    s2 = random.choice(SYLLABLES)
    answer = join_palladium(s1, s2)
    return {
        "condition_text": (
            "Запишите по системе Палладия двусложное слово (слитно, "
            "без пробелов, без тонов):<br><br>"
            f"<b style=\\"font-size:1.4em;\\">{s1} {s2}</b>"
        ),
        "correct_answer": answer,
        "pinyin1": s1,
        "pinyin2": s2,
    }
'''


ASSIGNMENT_TITLE = 'Двусложное слово по Палладию'
ASSIGNMENT_DESCRIPTION = (
    'Тренажёр генерирует случайные пары слогов мандарина и просит записать '
    'двусложное слово по правилам системы Палладия. Ответ вводите строчными '
    'буквами, слитно, без пробелов и без тонов. '
    'Если первый слог в Палладии оканчивается на твёрдую согласную '
    '(н от -ng или р от er), а второй начинается с гласной — между ними '
    'ставится твёрдый знак ъ (chang an → чанъань, er yao → эръяо).'
)


# ──────────────────────────────────────────────────────────────────────────────


# ──────────────────────────────────────────────────────────────────────────────


class Command(BaseCommand):
    help = 'Создаёт/обновляет курс «Система Палладия» с теоретическим модулем.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--clear', action='store_true',
            help='Удалить курс целиком (Course + все модули, уроки, прогресс).',
        )

    @transaction.atomic
    def handle(self, *args, **options):
        if options['clear']:
            qs = Course.objects.filter(slug=COURSE_SLUG)
            n = qs.count()
            qs.delete()
            self.stdout.write(self.style.WARNING(
                f'Удалено курсов: {n}'
            ))
            return

        course, created = Course.objects.update_or_create(
            slug=COURSE_SLUG,
            defaults={
                'title': COURSE_TITLE,
                'short_description': COURSE_SHORT,
                'full_description': COURSE_FULL,
                'is_active': True,
                'order': 100,
                'tracking_mode': Course.TRACKING_AUTO,
                'owner': None,
            },
        )
        self.stdout.write(self.style.SUCCESS(
            ('Создан' if created else 'Обновлён') + f' курс: {course.title}'
        ))

        module, m_created = Module.objects.update_or_create(
            course=course, order=0,
            defaults={
                'title': 'Теория системы Палладия',
                'description': (
                    'Методическая часть курса. Прочитайте все пять уроков '
                    'перед тем, как переходить к тренажёру двуслогов.'
                ),
            },
        )
        self.stdout.write(
            ('  + создан модуль ' if m_created else '  · обновлён модуль ')
            + module.title
        )

        for entry in LESSONS:
            lesson, l_created = Lesson.objects.update_or_create(
                module=module, order=entry['order'],
                defaults={
                    'title': entry['title'],
                    'content': entry['content'].strip(),
                    'lesson_type': 'text',
                    'is_free': True,
                    'duration': 0,
                    'video_url': '',
                },
            )
            self.stdout.write(
                ('    + создан урок ' if l_created else '    · обновлён урок ')
                + lesson.title
            )

        # ── Модуль 2: тренажёр двуслогов ───────────────────────────────────
        practice_module, pm_created = Module.objects.update_or_create(
            course=course, order=1,
            defaults={
                'title': 'Тренажёр двуслогов',
                'description': (
                    'Случайные пары слогов из стандартной таблицы мандарина. '
                    'Тренируем правила стыковки из четвёртого урока теории.'
                ),
            },
        )
        self.stdout.write(
            ('  + создан модуль ' if pm_created else '  · обновлён модуль ')
            + practice_module.title
        )

        practice_lesson, pl_created = Lesson.objects.update_or_create(
            module=practice_module, order=0,
            defaults={
                'title': 'Случайные двусложные слова',
                'lesson_type': 'practice',
                'is_free': True,
                'duration': 0,
                'video_url': '',
                'content': '',
            },
        )
        self.stdout.write(
            ('    + создан урок ' if pl_created else '    · обновлён урок ')
            + practice_lesson.title
        )

        # ProblemGenerator: один на курс. Имя — стабильный идентификатор.
        generator, g_created = ProblemGenerator.objects.update_or_create(
            name=GENERATOR_NAME,
            defaults={
                'generator_type': 'python_function',
                'python_code': GENERATOR_CODE,
                'config': {},
            },
        )
        self.stdout.write(
            ('      + создан генератор ' if g_created else '      · обновлён генератор ')
            + generator.name
        )

        # Assignment: один на урок-тренажёр. Привязка к генератору.
        assignment, a_created = Assignment.objects.update_or_create(
            lesson=practice_lesson, order=0,
            defaults={
                'title': ASSIGNMENT_TITLE,
                'description': ASSIGNMENT_DESCRIPTION,
                'assignment_type': 'text_input',
                'answer_type': 'text_input',
                'points': 1,
                'required_correct': 20,
                'problem_generator': generator,
            },
        )
        self.stdout.write(
            ('        + создан Assignment ' if a_created else '        · обновлён Assignment ')
            + assignment.title
        )

        # ── Подведём итог: проверим, что весь словарь импортируем. ────────
        self.stdout.write('')
        self.stdout.write(
            f'Словарь PALLADIUS: {len(PALLADIUS)} слогов '
            f'({len(SYLLABLES)} канонических для генератора)'
        )

        self.stdout.write(self.style.SUCCESS(
            f'\nГотово. Открой /courses/{COURSE_SLUG}/'
        ))
