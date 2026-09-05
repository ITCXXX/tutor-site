# -*- coding: utf-8 -*-
"""Переписка: страницы. Сообщения ходят по WebSocket (users/consumers.py).

Здесь только показ и разрешение доступа. Историю страница не тянет: её отдаёт
обработчик при подключении — иначе первые полсотни сообщений пришли бы дважды,
из шаблона и из сокета.

Правила «кто кому вправе писать» лежат не здесь, а в users/chat.py: тем же
правилам подчиняется обработчик сокета, и две копии разошлись бы.
"""

from django.contrib import messages as django_messages
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from .chat import (addressable_for, ask_question, create_group, direct_thread,
                   may_manage, may_talk_to, question_of, threads_for,
                   withdraw_question)
from .models import Assignment, Thread, ThreadMember, User


@login_required
def chat_home(request):
    """Список переписок: и личные, и группы, свежие сверху.

    Ученика больше не уносим сразу в разговор с преподавателем: у него теперь
    может быть и группа, и перекинуть его мимо списка значит спрятать её.
    """
    user = request.user
    ветки = threads_for(user)

    # С кем переписки ещё не было. Без этого список пуст в самом начале, и
    # непонятно, кому вообще можно написать.
    занятые = set()
    for t in ветки:
        if t.kind == Thread.KIND_DIRECT:
            другой = t.other_side(user)
            if другой:
                занятые.add(другой.id)
    новые = [u for u in addressable_for(user) if u.id not in занятые]

    return render(request, 'users/chat_list.html', {
        'title': 'Переписка',
        'threads': ветки,
        'новые': новые,
        'может_группу': user.role == 'teacher',
        'нет_собеседников': not ветки and not новые,
    })


@login_required
def chat_start(request, user_id):
    """Открыть личную переписку с человеком (заводя её при первом обращении)."""
    другой = get_object_or_404(User, pk=user_id)
    if not may_talk_to(request.user, другой):
        # Не «нельзя», а 404: перебор номеров не должен подсказывать, кто есть.
        raise Http404
    return redirect('chat_thread', thread_id=direct_thread(request.user, другой).id)


@login_required
def chat_thread(request, thread_id):
    """Одна лента переписки."""
    thread = (Thread.objects
              .prefetch_related('memberships__user')
              .filter(pk=thread_id).first())
    if thread is None or not thread.has_access(request.user):
        # Не «нет доступа», а именно 404: чужая переписка не должна выдавать
        # даже факт своего существования.
        raise Http404

    # Пришли по кнопке «спросить по задаче» — цитата подставится в поле ввода.
    задание = None
    сырое = request.GET.get('about')
    if сырое:
        from .views import _can_access_lesson
        з = (Assignment.objects
             .filter(pk=сырое)
             .select_related('lesson', 'lesson__module', 'lesson__module__course')
             .first())
        # Проверяем ТОЙ ЖЕ проверкой, что и страница урока: два разных правила
        # доступа к одному уроку — заявка на дыру.
        if з is not None and _can_access_lesson(request.user, з.lesson):
            задание = з

    участники = list(thread.memberships.all())
    return render(request, 'users/chat.html', {
        'title': 'Переписка · %s' % thread.display_for(request.user),
        'thread': thread,
        'заголовок': thread.display_for(request.user),
        'участники': [m.user for m in участники],
        'управляю': may_manage(thread, request.user),
        # Через json_script, а не в разметку: название задачи пишет человек, и
        # вставлять его в исходник страницы руками — это дыра.
        'предзаполнение': ({'id': задание.id, 'title': задание.title}
                           if задание else {}),
    })


@login_required
def chat_group_new(request):
    """Собрать группу. Собирает только преподаватель и только из своих.

    Иначе ученик заводит группу с кем угодно, зная лишь номер, — обычная дыра
    в чатах, а не выдуманная опасность.
    """
    if request.user.role != 'teacher':
        raise Http404

    кандидаты = addressable_for(request.user)
    if request.method == 'POST':
        название = (request.POST.get('title') or '').strip()
        отмечены = set(request.POST.getlist('members'))
        выбранные = [u for u in кандидаты if str(u.id) in отмечены]
        if not название:
            django_messages.error(request, 'У группы должно быть название.')
        elif not выбранные:
            django_messages.error(request, 'Выберите хотя бы одного участника.')
        else:
            ветка = create_group(request.user, название, выбранные)
            return redirect('chat_thread', thread_id=ветка.id)

    return render(request, 'users/chat_group_new.html', {
        'title': 'Новая группа',
        'кандидаты': кандидаты,
    })


@login_required
def chat_group_add(request, thread_id):
    """Позвать в группу ещё людей. Только распорядитель и только своих."""
    thread = get_object_or_404(Thread, pk=thread_id)
    if not may_manage(thread, request.user):
        raise Http404

    if request.method == 'POST':
        уже = set(thread.memberships.values_list('user_id', flat=True))
        отмечены = set(request.POST.getlist('members'))
        добавили = 0
        for u in addressable_for(request.user):
            if str(u.id) in отмечены and u.id not in уже:
                ThreadMember.objects.create(thread=thread, user=u)
                добавили += 1
        название = (request.POST.get('title') or '').strip()
        if название and название != thread.title:
            thread.title = название[:120]
            thread.save(update_fields=['title'])
        if добавили:
            django_messages.success(
                request, 'Добавлено участников: %d.' % добавили)
        return redirect('chat_thread', thread_id=thread.id)

    уже = set(thread.memberships.values_list('user_id', flat=True))
    return render(request, 'users/chat_group_edit.html', {
        'title': 'Состав группы',
        'thread': thread,
        'участники': [m.user for m in thread.memberships.select_related('user')],
        'кандидаты': [u for u in addressable_for(request.user) if u.id not in уже],
    })


@login_required
def chat_ask_about(request, assignment_id):
    """«Спросить по задаче»: ведёт в ОБЩУЮ переписку с цитатой задания.

    Именно в общую, а не в отдельную ветку при домашке. Разговор про учёбу
    должен лежать в одном месте: иначе человек потом ищет, где он спрашивал, —
    и находит три ленты, в каждой по половине разговора.
    """
    from .views import _can_access_lesson
    задание = get_object_or_404(
        Assignment.objects.select_related('lesson', 'lesson__module',
                                          'lesson__module__course'),
        pk=assignment_id)
    if not _can_access_lesson(request.user, задание.lesson):
        raise Http404

    собеседник = None
    if request.user.role == 'student':
        профиль = getattr(request.user, 'student_profile', None)
        собеседник = профиль.teacher if профиль else None
    else:
        # Преподаватель спрашивает по задаче — значит пишет владельцу курса,
        # если это не он сам; такое бывает при совместных курсах.
        владелец = задание.lesson.module.course.owner
        собеседник = владелец if владелец and владелец.id != request.user.id else None

    if собеседник is None:
        django_messages.error(
            request, 'Некому написать: преподаватель ещё не назначен.')
        return redirect('lesson_detail', lesson_id=задание.lesson_id)

    ветка = direct_thread(request.user, собеседник)
    адрес = reverse('chat_thread', args=[ветка.id])
    return redirect('%s?about=%d' % (адрес, задание.id))


@login_required
@require_POST
def chat_toggle_question(request, assignment_id):
    """Пометить задачу вопросом или снять пометку. Одно нажатие, без текста.

    Хранится это ТЕМ ЖЕ сообщением-вопросом, что и вопрос из переписки, и это
    главное решение здесь. Заведи мы отдельную табличку «вопрос по домашке» —
    и «есть вопрос» стало бы жить в двух местах: одно погасло бы после ответа
    в чате, второе осталось бы висеть. Правило зачёта в этом проекте уже
    разъехалось ровно так.
    """
    from .views import _can_access_lesson
    задание = get_object_or_404(
        Assignment.objects.select_related('lesson', 'lesson__module',
                                          'lesson__module__course'),
        pk=assignment_id)
    if request.user.role != 'student' or not _can_access_lesson(request.user, задание.lesson):
        raise Http404

    if question_of(request.user, задание) is not None:
        снято = withdraw_question(request.user, задание)
        django_messages.success(
            request,
            'Пометка снята.' if снято
            else 'Вы уже написали об этом в переписке — пометка останется там.')
    else:
        m, завели = ask_question(request.user, задание)
        if m is None:
            django_messages.error(
                request, 'Некому сообщить: преподаватель ещё не назначен.')
        else:
            django_messages.success(
                request, 'Преподаватель увидит, что здесь вопрос.')

    # Возвращаем ровно туда, откуда нажали.
    назад = request.META.get('HTTP_REFERER')
    return redirect(назад or reverse('lesson_detail', args=[задание.lesson_id]))
