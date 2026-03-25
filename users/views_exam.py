# users/views_exam.py
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.utils import timezone
from django.db import models
from decimal import Decimal, InvalidOperation
from django.views.decorators.http import require_POST
import json
import random
from .models import (
    Assignment, GeneratedProblem, ProblemAttempt, 
    StudentProgress, User, Enrollment
)

@login_required
def assignment_practice(request, assignment_id):
    """
    Страница для решения задач по прототипу (Assignment)
    """
    if request.user.role != 'student':
        return redirect('student_dashboard')
    
    assignment = get_object_or_404(Assignment, id=assignment_id)
    
    # Проверяем, записан ли ученик на курс
    if not Enrollment.objects.filter(
        student=request.user,
        course=assignment.lesson.module.course,
        is_active=True
    ).exists():
        # Если нет - записываем
        Enrollment.objects.create(
            student=request.user,
            course=assignment.lesson.module.course
        )
    
    # Получаем или создаем прогресс ученика
    progress, created = StudentProgress.objects.get_or_create(
        student=request.user,
        assignment=assignment
    )
    
    # Получаем существующую незавершенную задачу
    problem = GeneratedProblem.objects.filter(
        student=request.user,
        assignment=assignment,
        status__in=['new', 'failed']
    ).first()
    
    # Если нет незавершенной задачи, создаем новую
    if not problem:
        try:
            problem = generate_new_problem_for_student(request.user, assignment)
        except IntegrityError:
            # Если произошла ошибка уникальности (маловероятно, но на всякий случай)
            # Получаем последнюю задачу
            problem = GeneratedProblem.objects.filter(
                student=request.user,
                assignment=assignment
            ).order_by('-created_at').first()
    
    # Получаем историю попыток
    attempts = ProblemAttempt.objects.filter(
        problem=problem
    ).order_by('-created_at')[:5]
    
    return render(request, 'users/assignment_practice.html', {
        'assignment': assignment,
        'problem': problem,
        'progress': progress,
        'attempts': attempts,
        'title': f'Практика: {assignment.title}'
    })

@login_required
@require_POST
def check_problem_answer(request, problem_id):
    """
    Проверка ответа на задачу (AJAX запрос)
    """
    problem = get_object_or_404(GeneratedProblem, id=problem_id, student=request.user)
    
    data = json.loads(request.body)
    user_answer = data.get('answer', '').strip()
    
    if not user_answer:
        return JsonResponse({'error': 'Ответ не может быть пустым'}, status=400)
    
    # Проверяем ответ
    is_correct = False
    correct_answer = problem.correct_answer

    # Вариант 1: выбор из 1–4 (старые прототипы)
    if isinstance(correct_answer, (dict, list)) or (
        isinstance(correct_answer, int) and 1 <= correct_answer <= 4
    ):
        try:
            user_choice = int(user_answer)
            if 1 <= user_choice <= 4:
                if isinstance(correct_answer, dict):
                    correct_choice = correct_answer.get('correct_answer', 1)
                else:
                    correct_choice = correct_answer
                is_correct = (user_choice == correct_choice)
        except (ValueError, TypeError):
            is_correct = False

    # Вариант 2: числовой краткий ответ (десятичная дробь)
    else:
        try:
            user_val = Decimal(user_answer.replace(',', '.'))
            correct_val = Decimal(str(correct_answer).replace(',', '.'))
            diff = abs(user_val - correct_val)
            # допуск 0.001
            if diff <= Decimal('0.001'):
                is_correct = True
        except (InvalidOperation, TypeError, AttributeError):
            is_correct = False

    # Создаем запись о попытке
    attempt = ProblemAttempt.objects.create(
        problem=problem,
        student=request.user,
        user_answer=user_answer,
        is_correct=is_correct
    )
    
    # Обновляем статистику задачи
    problem.attempts_count += 1
    if is_correct:
        problem.correct_attempts += 1
        problem.status = 'solved'
    elif problem.attempts_count >= 3:
        problem.status = 'failed'
    
    problem.last_attempt_at = timezone.now()
    problem.save()
    
    # Обновляем прогресс ученика
    progress, created = StudentProgress.objects.get_or_create(
        student=request.user,
        assignment=problem.assignment
    )
    progress.update_progress(is_correct)
    
    return JsonResponse({
        'correct': is_correct,
        'correct_answer': problem.correct_answer,
        'attempts_count': problem.attempts_count,
        'problem_correct_attempts': problem.correct_attempts,
        'progress_correct_attempts': progress.correct_attempts,
        'total_attempts': progress.total_attempts,
        'progress_percentage': progress.get_percentage(),
        'is_completed': progress.is_completed
    })

@login_required
@require_POST
def generate_new_problem(request, assignment_id):
    """
    Генерация новой задачи того же типа (AJAX запрос)
    """
    assignment = get_object_or_404(Assignment, id=assignment_id)
    
    # Создаем новую задачу
    problem = generate_new_problem_for_student(request.user, assignment)
    
    # Формируем HTML для отображения задачи
    task_data = problem.task_data
    
    # Формируем условие с LaTeX
    condition_html = format_problem_for_display(task_data)
    
    return JsonResponse({
        'success': True,
        'problem_id': problem.id,
        'condition_html': condition_html
    })

@login_required
def student_progress(request):
    """
    Статистика прогресса ученика
    """
    if request.user.role != 'student':
        return redirect('student_dashboard')

    progress_qs = StudentProgress.objects.filter(
        student=request.user
    ).select_related(
        'assignment',
        'assignment__lesson',
        'assignment__lesson__module',
        'assignment__lesson__module__course',
    )

    # Общая статистика
    total_assignments = progress_qs.count()
    completed_assignments = progress_qs.filter(is_completed=True).count()

    agg = progress_qs.aggregate(
        total_correct=models.Sum('correct_attempts'),
        total_attempts=models.Sum('total_attempts'),
    )
    total_correct = agg['total_correct'] or 0
    total_attempts = agg['total_attempts'] or 0

    if total_attempts > 0:
        overall_accuracy = round(total_correct / total_attempts * 100)
    else:
        overall_accuracy = 0

    total_time_hours = 0  # пока заглушка

    return render(request, 'users/student_progress.html', {
        'progress_records': progress_qs,
        'title': 'Мой прогресс',
        'total_assignments': total_assignments,
        'completed_assignments': completed_assignments,
        'total_correct': total_correct,
        'total_attempts': total_attempts,
        'overall_accuracy': overall_accuracy,
        'total_time': total_time_hours,
    })

# Вспомогательные функции
def generate_new_problem_for_student(student, assignment):
    """
    Генерирует новую задачу для ученика
    """
    if not assignment.problem_generator:
        # Если нет генератора, создаем тестовую задачу
        task_data = {
            'numbers': [1, 2],
            'denominator': 10,
            'fractions': [(3, 10), (5, 10), (7, 10), (9, 10)],
            'correct_answer': 1
        }
        condition_text = "Тестовая задача (генератор не настроен)"
    else:
        # Выполняем генератор
        task_data = assignment.problem_generator.execute_generator(student)
        condition_text = format_problem_for_display(task_data)
    
    # Добавляем уникальный идентификатор, чтобы task_data всегда был уникальным
    import time
    import random
    task_data['_unique_id'] = f"{time.time()}_{random.randint(1000, 9999)}"
    
    # Создаем запись задачи
    problem = GeneratedProblem.objects.create(
        student=student,
        assignment=assignment,
        task_data=task_data,
        condition_text=condition_text,
        correct_answer=task_data.get('correct_answer', 1),
        status='new'
    )
    
    return problem

def format_problem_for_display(task_data):
    """
    Форматирует данные задачи в HTML с LaTeX
    """
    if 'numbers' in task_data and 'fractions' in task_data:
        a, b = task_data['numbers']
        d = task_data['denominator']
        fractions = task_data['fractions']
        
        html = f'<p>Найдите дробь, которая находится между числами ${a}$ и ${b}$.</p>'
        html += '<ol>'
        
        for i, (num, den) in enumerate(fractions, 1):
            html += f'''
            <li>
                <span class="fraction-number">{i}.</span>
                <span class="fraction-formula">$$\\dfrac{{{num}}}{{{den}}}$$</span>
            </li>
            '''
        
        html += '</ol>'
        return html
    
    return task_data.get('condition_text', 'Условие задачи')