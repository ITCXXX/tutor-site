# users/urls.py

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views
from . import views_exam
from . import views_materials
from . import views_oge1_5

# ===== 1. СОЗДАЕМ РОУТЕР ДЛЯ API =====
router = DefaultRouter()
router.register(r'pdf-bookmarks', views.PDFBookmarkViewSet, basename='pdf-bookmark')
router.register(r'pdf-annotations', views.PDFAnnotationViewSet, basename='pdf-annotation')

# ===== 2. ОПРЕДЕЛЯЕМ МАРШРУТЫ =====
urlpatterns = [
    # --- ПОДКЛЮЧАЕМ API ПЕРВЫМИ ---
    path('api/', include(router.urls)),
    
    # --- ОСНОВНЫЕ МАРШРУТЫ ---
    path('', views.home_view, name='home'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('student/', views.student_dashboard, name='student_dashboard'),
    path('teacher/', views.teacher_dashboard, name='teacher_dashboard'),
    path('teacher/course/<slug:slug>/', views.teacher_course_progress, name='teacher_course_progress'),
    path('teacher/course/<slug:slug>/student/<int:student_id>/',
         views.teacher_student_workbook, name='teacher_student_workbook'),
    path('teacher/toggle-mark/', views.teacher_toggle_mark, name='teacher_toggle_mark'),
    path('teacher/student/new/', views.teacher_student_new, name='teacher_student_new'),
    path('teacher/student/<int:student_id>/', views.teacher_student_detail, name='teacher_student_detail'),
    path('teacher/student/<int:student_id>/enroll/',
         views.teacher_student_enroll, name='teacher_student_enroll'),
    path('teacher/workbook/new/', views.teacher_workbook_new, name='teacher_workbook_new'),
    path('teacher/hw-course/new/', views.teacher_hw_course_new, name='teacher_hw_course_new'),
    path('teacher/hw-course/<slug:slug>/new-lesson/',
         views.teacher_hw_lesson_new, name='teacher_hw_lesson_new'),
    path('teacher/hw-course/<slug:slug>/lesson/<int:lesson_id>/edit/',
         views.teacher_hw_lesson_edit, name='teacher_hw_lesson_edit'),
    path('teacher/hw-course/<slug:slug>/lesson/<int:lesson_id>/delete/',
         views.teacher_hw_lesson_delete, name='teacher_hw_lesson_delete'),
    path('teacher/hw-course/<slug:slug>/lesson/<int:lesson_id>/duplicate/',
         views.teacher_hw_lesson_duplicate, name='teacher_hw_lesson_duplicate'),
    path('teacher/hw-course/<slug:slug>/lesson/<int:lesson_id>/export/',
         views.teacher_hw_lesson_export, name='teacher_hw_lesson_export'),
    path('teacher/hw-course/<slug:slug>/import-lesson/',
         views.teacher_hw_lesson_import, name='teacher_hw_lesson_import'),
    path('exam/hw-check/<int:assignment_id>/', views.check_hw_answer, name='check_hw_answer'),
    path('exam/hw-submit/<int:assignment_id>/', views.submit_hw_solution, name='submit_hw_solution'),
    path('teacher/submissions/', views.teacher_submissions, name='teacher_submissions'),
    path('teacher/submissions/<int:sub_id>/review/',
         views.teacher_review_submission, name='teacher_review_submission'),
    path('courses/', views.courses_list, name='courses_list'),
    path('courses/<slug:slug>/', views.course_detail, name='course_detail'),
    path('enroll/<int:course_id>/', views.enroll_to_course, name='enroll_to_course'),
    path('student/courses/', views.student_courses, name='student_courses'),
    path('student/courses/<slug:slug>/progress/',
         views.student_course_progress, name='student_course_progress'),
    path('materials/', views_materials.materials_list, name='materials_list'),
    path('materials/<slug:slug>/', views_materials.material_category_detail, name='material_category_detail'),
    path('material/view/<int:material_id>/', views_materials.material_view, name='material_view'),
    
    # --- ПРОФИЛЬ ПОЛЬЗОВАТЕЛЯ ---
    
    path('material/download/<int:material_id>/', views_materials.download_material, name='download_material'),
    path('material/toggle/<int:material_id>/', views_materials.toggle_material_access, name='toggle_material_access'),
    
    # --- API ДЛЯ PDF ---
    path('api/material/<int:material_id>/thumbnails/', views_materials.get_material_thumbnails, name='get_material_thumbnails'),
    path('api/material/save-settings/', views_materials.save_material_settings, name='save_material_settings'),
    
    # --- ОТПИСКА ОТ КУРСА ---
    path('unenroll/<int:enrollment_id>/', views.unenroll_from_course, name='unenroll_from_course'),
    
    # --- ТЕОРЕТИЧЕСКИЙ УРОК (методичка) ---
    path('lesson/<int:lesson_id>/', views.lesson_detail, name='lesson_detail'),
    path('lesson/<int:lesson_id>/mark-read/', views.mark_lesson_read, name='mark_lesson_read'),

    # ===== НОВЫЕ МАРШРУТЫ ДЛЯ ЭКЗАМЕНАЦИОННОЙ ПОДГОТОВКИ =====
    path('assignment/<int:assignment_id>/practice/', views_exam.assignment_practice, name='assignment_practice'),
    path('exam/check/<int:problem_id>/', views_exam.check_problem_answer, name='check_problem_answer'),
    path('exam/db-check/<int:assignment_id>/<int:question_id>/',
         views_exam.check_db_question_answer, name='check_db_question_answer'),
    path('exam/db-reset/<int:assignment_id>/',
         views_exam.reset_db_assignment, name='reset_db_assignment'),
    path('exam/generate-new/<int:assignment_id>/', views_exam.generate_new_problem, name='generate_new_problem'),
    path('lesson/<int:lesson_id>/practice/',
         views_exam.lesson_practice, name='lesson_practice'),
    path('lesson/<int:lesson_id>/next/',
         views_exam.lesson_next_problem, name='lesson_next_problem'),
    path('lesson/<int:lesson_id>/set-active-generators/',
         views_exam.lesson_set_active_generators, name='lesson_set_active_generators'),

    # --- ОГЭ №1-5: блочные группы (TaskGroup) ---
    path('task-group/<int:group_id>/',
         views_oge1_5.task_group_practice, name='task_group_practice'),
    path('task-group/<int:group_id>/submit/',
         views_oge1_5.task_group_submit, name='task_group_submit'),

    # --- ДОПОЛНИТЕЛЬНЫЕ МАРШРУТЫ ДЛЯ БУДУЩЕГО РАСШИРЕНИЯ ---
    # path('exam/course/<int:course_id>/', views_exam.exam_course_detail, name='exam_course_detail'),
    # path('exam/prototype/<int:prototype_id>/', views_exam.prototype_detail, name='prototype_detail'),
    # path('exam/statistics/', views_exam.student_statistics, name='exam_statistics'),
]

# ===== 3. ОБРАБОТЧИКИ ОШИБОК =====
handler404 = views.handler404
handler500 = views.handler500