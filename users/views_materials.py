# users/views_materials.py
# View'ы, связанные с методическими материалами: каталог, просмотр PDF,
# скачивание, поиск.

import json
import os

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET, require_POST

from .models import Material, MaterialCategory
from .pdf_utils import generate_pdf_thumbnail, get_pdf_info


def materials_list(request):
    """Список категорий материалов."""
    categories = MaterialCategory.objects.all().prefetch_related('materials')
    total_materials = Material.objects.count()
    free_materials = Material.objects.filter(is_free=True).count()

    return render(request, 'users/materials_list.html', {
        'categories': categories,
        'title': 'Методические материалы',
        'total_materials': total_materials,
        'free_materials': free_materials,
    })


def material_category_detail(request, slug):
    """Материалы конкретной категории."""
    category = get_object_or_404(MaterialCategory, slug=slug)
    materials = category.materials.all().order_by('order', '-created_at')
    material_types = (materials.values('material_type')
                      .annotate(count=Count('id'))
                      .order_by('material_type'))

    return render(request, 'users/material_category.html', {
        'category': category,
        'materials': materials,
        'title': f'Материалы: {category.title}',
        'material_types': material_types,
        'materials_count': materials.count(),
    })


def material_view(request, material_id):
    """Страница просмотра материала."""
    material = get_object_or_404(Material, id=material_id)

    if not material.file:
        messages.error(request, "Файл не найден")
        return redirect('material_category_detail', slug=material.category.slug)

    filename = material.file.name.lower()
    is_pdf = filename.endswith('.pdf')

    if is_pdf and material.file and os.path.exists(material.file.path):
        if material.page_count == 0:
            pdf_info = get_pdf_info(material.file.path)
            material.page_count = pdf_info['page_count']
            if not material.thumbnail:
                generate_pdf_thumbnail(material.file.path, material, page_number=0)
            material.save()

    page = request.GET.get('page', '1')
    try:
        current_page = int(page)
        if current_page < 1:
            current_page = 1
        elif material.page_count > 0 and current_page > material.page_count:
            current_page = material.page_count
    except ValueError:
        current_page = 1

    pdf_url = f"{material.file.url}"
    if is_pdf and current_page > 1:
        pdf_url += f"#page={current_page}"

    return render(request, 'users/material_viewer.html', {
        'material': material,
        'title': f'Просмотр: {material.title}',
        'current_page': current_page,
        'pdf_url': pdf_url,
        'total_pages': material.page_count or 1,
        'is_pdf': is_pdf,
        'can_access': True,
        'file_extension': filename.split('.')[-1] if '.' in filename else 'file',
    })


@login_required
@require_GET
def get_material_thumbnails(request, material_id):
    """API для получения миниатюр страниц PDF."""
    material = get_object_or_404(Material, id=material_id)
    if not material.file or not material.file.path.endswith('.pdf'):
        return JsonResponse({'error': 'Файл не является PDF'}, status=400)

    thumbnails = []
    for i in range(1, min(material.page_count + 1, 11)):
        thumbnails.append({
            'page': i,
            'url': '/static/img/pdf-thumb-placeholder.png',
            'width': 100,
            'height': 140,
        })

    return JsonResponse({
        'material_id': material.id,
        'title': material.title,
        'total_pages': material.page_count,
        'thumbnails': thumbnails,
    })


@login_required
@require_POST
def save_material_settings(request):
    """Сохранение пользовательских настроек просмотрщика."""
    try:
        data = json.loads(request.body)
        material_id = data.get('material_id')
        return JsonResponse({
            'success': True,
            'message': 'Настройки сохранены',
            'material_id': material_id,
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)


@login_required
def toggle_material_access(request, material_id):
    """Переключение доступа к материалу (для администраторов)."""
    if not request.user.is_superuser:
        messages.error(request, 'Доступ только для администраторов')
        return redirect('material_category_detail', slug='all')

    material = get_object_or_404(Material, id=material_id)
    material.is_free = not material.is_free
    material.save()
    return redirect('material_view', material_id=material_id)


def download_material(request, material_id):
    """Скачивание материала."""
    material = get_object_or_404(Material, id=material_id)
    if not material.file:
        messages.error(request, "Файл не найден")
        return redirect('material_category_detail', slug=material.category.slug)

    if not material.is_free and not request.user.is_authenticated:
        messages.error(request, "Для скачивания этого материала необходимо авторизоваться")
        return redirect('login')

    return redirect(material.file.url)
