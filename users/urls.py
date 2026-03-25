# users/urls.py

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views
from . import views_exam  # <-- Добавляем импорт

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
    path('parent/', views.parent_dashboard, name='parent_dashboard'),
    path('courses/', views.courses_list, name='courses_list'),
    path('courses/<slug:slug>/', views.course_detail, name='course_detail'),
    path('enroll/<int:course_id>/', views.enroll_to_course, name='enroll_to_course'),
    path('student/courses/', views.student_courses, name='student_courses'),
    path('materials/', views.materials_list, name='materials_list'),
    path('materials/<slug:slug>/', views.material_category_detail, name='material_category_detail'),
    path('material/view/<int:material_id>/', views.material_view, name='material_view'),
    
    # --- ПРОФИЛЬ ПОЛЬЗОВАТЕЛЯ ---
    path('profile/', views.user_profile, name='user_profile'),
    path('profile/update/', views.update_profile, name='update_profile'),
    
    # --- ПОИСК И СКАЧИВАНИЕ ---
    path('search/', views.search_materials, name='search_materials'),
    path('material/download/<int:material_id>/', views.download_material, name='download_material'),
    path('material/toggle/<int:material_id>/', views.toggle_material_access, name='toggle_material_access'),
    
    # --- API ДЛЯ PDF ---
    path('api/material/<int:material_id>/thumbnails/', views.get_material_thumbnails, name='get_material_thumbnails'),
    path('api/material/save-settings/', views.save_material_settings, name='save_material_settings'),
    
    # --- ОТПИСКА ОТ КУРСА ---
    path('unenroll/<int:enrollment_id>/', views.unenroll_from_course, name='unenroll_from_course'),
    
    # ===== НОВЫЕ МАРШРУТЫ ДЛЯ ЭКЗАМЕНАЦИОННОЙ ПОДГОТОВКИ =====
    path('assignment/<int:assignment_id>/practice/', views_exam.assignment_practice, name='assignment_practice'),
    path('exam/check/<int:problem_id>/', views_exam.check_problem_answer, name='check_problem_answer'),
    path('exam/generate-new/<int:assignment_id>/', views_exam.generate_new_problem, name='generate_new_problem'),
    path('progress/', views_exam.student_progress, name='student_progress'),
    
    # --- ДОПОЛНИТЕЛЬНЫЕ МАРШРУТЫ ДЛЯ БУДУЩЕГО РАСШИРЕНИЯ ---
    # path('exam/course/<int:course_id>/', views_exam.exam_course_detail, name='exam_course_detail'),
    # path('exam/prototype/<int:prototype_id>/', views_exam.prototype_detail, name='prototype_detail'),
    # path('exam/statistics/', views_exam.student_statistics, name='exam_statistics'),
]

# ===== 3. ОБРАБОТЧИКИ ОШИБОК =====
handler404 = views.handler404
handler500 = views.handler500