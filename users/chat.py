# -*- coding: utf-8 -*-
"""Правила переписки в одном месте: кто с кем, что непрочитано, кого можно звать.

Почему отдельный модуль, а не «по месту в видах»: те же правила нужны и
странице списка, и обработчику WebSocket, и значку с числом непрочитанных.
Разъехавшиеся копии одного правила в этом проекте уже случались.

Главное правило доступа простое и одно: доступ есть у того, кто числится
участником ветки. Ни роль, ни то, кто кому преподаёт, здесь роли не играют —
иначе преподаватель, у которого ученика перевели, потерял бы историю разговора.
"""

from django.db import IntegrityError, transaction
from django.db.models import Count, F, Q
from django.utils import timezone

from .models import Message, Thread, ThreadMember, User


# ─────────────────────────── ветки ───────────────────────────

def direct_thread(a, b):
    """Личная переписка двоих. Заводится при первом обращении, одна на пару.

    Гонку двух вкладок ловим не проверкой «а есть ли уже», а ограничением в
    базе: проверка «есть ли» между двумя запросами не спасает, а ограничение —
    спасает. Поймали нарушение — значит ветку успел завести кто-то другой,
    просто берём её.
    """
    ключ = Thread.make_pair_key(a.id, b.id)
    ветка = Thread.objects.filter(kind=Thread.KIND_DIRECT, pair_key=ключ).first()
    if ветка is not None:
        return ветка
    try:
        with transaction.atomic():
            ветка = Thread.objects.create(
                kind=Thread.KIND_DIRECT, pair_key=ключ, owner=a)
            ThreadMember.objects.bulk_create([
                ThreadMember(thread=ветка, user=a),
                ThreadMember(thread=ветка, user=b),
            ])
            return ветка
    except IntegrityError:
        return Thread.objects.get(kind=Thread.KIND_DIRECT, pair_key=ключ)


def create_group(owner, title, users):
    """Собрать группу. Создатель входит в неё сам и остаётся распорядителем."""
    with transaction.atomic():
        ветка = Thread.objects.create(
            kind=Thread.KIND_GROUP, title=(title or '').strip()[:120], owner=owner)
        ThreadMember.objects.create(thread=ветка, user=owner, is_admin=True)
        for u in users:
            if u.id != owner.id:
                ThreadMember.objects.get_or_create(thread=ветка, user=u)
    return ветка


def threads_for(user):
    """Ветки человека, свежие сверху, с числом непрочитанного в каждой."""
    ветки = list(Thread.objects
                 .filter(memberships__user=user)
                 .prefetch_related('memberships__user')
                 .order_by('-updated_at'))
    счёт = unread_by_thread(user)
    for t in ветки:
        t.непрочитано = счёт.get(t.id, 0)
        t.заголовок = t.display_for(user)
    return ветки


# ─────────────────────── непрочитанное ───────────────────────

def unread_by_thread(user):
    """{id ветки: сколько непрочитанного} — одним запросом, а не по ветке за раз.

    Тонкость, которая стоила бы вечера: все условия про memberships собраны в
    ОДИН вызов filter(). Django для связи «много» на каждый отдельный filter()
    делает своё присоединение таблицы — разнеси условия по двум вызовам, и
    «участник — это я» и «прочитано досюда» окажутся про РАЗНЫХ участников.
    Счёт тогда получается правдоподобный и неверный.
    """
    строки = (Message.objects
              .filter(
                  Q(thread__memberships__user=user)
                  & (Q(thread__memberships__last_read_at__isnull=True)
                     | Q(created_at__gt=F('thread__memberships__last_read_at')))
              )
              .exclude(author=user)
              .values('thread_id')
              .annotate(сколько=Count('id')))
    return {r['thread_id']: r['сколько'] for r in строки}


def unread_total(user):
    """Сколько непрочитанного всего — для значка в шапке."""
    return sum(unread_by_thread(user).values())


def mark_read(thread, user, when=None):
    """Отметить, что человек дочитал ветку до текущего момента.

    Указатель не двигаем назад: пришло два сообщения, вкладка обновилась —
    отметка не должна откатиться и снова показать прочитанное непрочитанным.
    """
    when = when or timezone.now()
    return (ThreadMember.objects
            .filter(thread=thread, user=user)
            .filter(Q(last_read_at__isnull=True) | Q(last_read_at__lt=when))
            .update(last_read_at=when))


# read_watermark отсюда убран намеренно. Он сводил отметки участников к одному
# ответу «прочитано всеми или нет», и после того как страница научилась
# показывать, КТО именно прочитал, остался вторым способом считать то же самое.
# Два способа на один вопрос в этом проекте уже расходились — с правилом зачёта.
# Отметки отдаёт consumers._read_state, решение принимает страница.


# ─────────────────────── кого можно звать ────────────────────

def addressable_for(user):
    """Кому этот человек вправе писать и кого звать в группу.

    Преподавателю — своих учеников и других преподавателей. Ученику — своего
    преподавателя, и только его. Без этого ограничения ученик пишет любому
    человеку с сайта, зная лишь номер: это не придирка, а обычная дыра в чатах.
    """
    if user.role == 'teacher':
        свои = User.objects.filter(student_profile__teacher=user, role='student')
        коллеги = User.objects.filter(role='teacher').exclude(pk=user.pk)
        return list(свои) + list(коллеги)
    профиль = getattr(user, 'student_profile', None)
    наставник = профиль.teacher if профиль else None
    return [наставник] if наставник else []


def may_talk_to(user, other):
    return any(o.id == other.id for o in addressable_for(user))


# ─────────────────── вопрос по задаче ────────────────────

def _наставник(student):
    профиль = getattr(student, 'student_profile', None)
    return профиль.teacher if профиль else None


def question_of(student, assignment):
    """Открытый вопрос ученика по этой задаче — или None.

    Открытый значит «ещё не отвечен»: как только преподаватель ответил на
    сообщение, оно закрывается само, и пометка в домашке гаснет вместе с ним.
    """
    наставник = _наставник(student)
    if наставник is None:
        return None
    ветка = Thread.objects.filter(
        kind=Thread.KIND_DIRECT,
        pair_key=Thread.make_pair_key(student.id, наставник.id)).first()
    if ветка is None:
        return None
    return (Message.objects
            .filter(thread=ветка, author=student, about_assignment=assignment,
                    is_question=True, answered_at__isnull=True)
            .order_by('-created_at').first())


def ask_question(student, assignment):
    """Пометить задачу вопросом. Возвращает (сообщение, завели_ли_новое).

    Текста нет намеренно: пометка должна стоить ОДНО нажатие. Ученик, который
    затрудняется, чаще всего не может и объяснить, что именно не выходит, —
    заставлять его писать значит получить пустую галочку вместо сигнала.
    Захочет объяснить — рядом есть «Спросить по задаче», она ведёт в переписку.
    """
    уже = question_of(student, assignment)
    if уже is not None:
        return уже, False
    наставник = _наставник(student)
    if наставник is None:
        return None, False
    ветка = direct_thread(student, наставник)
    m = Message.objects.create(
        thread=ветка, author=student, text='',
        about_assignment=assignment, is_question=True)
    Thread.objects.filter(pk=ветка.id).update(updated_at=m.created_at)
    return m, True


def withdraw_question(student, assignment):
    """Снять пометку. Удаляем ТОЛЬКО пустую — ту, что поставлена кнопкой.

    Если ученик успел написать словами, сообщение остаётся: стереть его значило
    бы молча выбросить чужой текст из переписки, где вторая сторона его уже,
    возможно, прочитала.
    """
    m = question_of(student, assignment)
    if m is None:
        return False
    if (m.text or '').strip():
        return False
    m.delete()
    return True


def open_questions_for(teacher):
    """Открытые вопросы всех учеников этого преподавателя, свежие сверху.

    Нужны на экране проверки работ: вопрос чаще всего задают по задаче, которую
    ещё НЕ сдали, — значит в списке сдач его не будет вовсе, и без отдельной
    полки преподаватель о нём не узнает.
    """
    return list(Message.objects
                .filter(is_question=True, answered_at__isnull=True,
                        about_assignment__isnull=False,
                        author__student_profile__teacher=teacher)
                .select_related('author', 'author__student_profile', 'thread',
                                'about_assignment',
                                'about_assignment__lesson',
                                'about_assignment__lesson__module__course')
                .order_by('-created_at')[:50])


def may_manage(thread, user):
    """Кто вправе звать в группу и переименовывать её: только распорядитель."""
    if thread.kind != Thread.KIND_GROUP:
        return False
    return ThreadMember.objects.filter(
        thread=thread, user=user, is_admin=True).exists()
