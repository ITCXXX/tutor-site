# users/pdf_utils.py
import os
from django.conf import settings
from PIL import Image
import fitz  # PyMuPDF
from io import BytesIO
from django.core.files.base import ContentFile
import tempfile

def get_pdf_info(pdf_path):
    """Получает информацию о PDF файле"""
    try:
        if not os.path.exists(pdf_path):
            return {'page_count': 0, 'size': 0, 'error': 'Файл не найден'}
        
        doc = fitz.open(pdf_path)
        page_count = doc.page_count
        
        # Получаем информацию о первой странице
        first_page = doc.load_page(0)
        page_size = first_page.rect
        width = page_size.width
        height = page_size.height
        
        doc.close()
        
        return {
            'page_count': page_count,
            'size': os.path.getsize(pdf_path),
            'width': width,
            'height': height,
            'orientation': 'landscape' if width > height else 'portrait'
        }
    except Exception as e:
        print(f"Ошибка чтения PDF {pdf_path}: {e}")
        return {'page_count': 0, 'size': 0, 'error': str(e)}

def generate_pdf_thumbnail(pdf_path, material_instance, page_number=0, size=(200, 280)):
    """Генерирует миниатюру для PDF"""
    try:
        if not os.path.exists(pdf_path):
            print(f"Файл не найден: {pdf_path}")
            return False
        
        doc = fitz.open(pdf_path)
        
        if page_number < 0 or page_number >= doc.page_count:
            page_number = 0
        
        page = doc.load_page(page_number)
        
        # Вычисляем матрицу масштабирования для нужного размера
        zoom_x = size[0] / page.rect.width
        zoom_y = size[1] / page.rect.height
        zoom = min(zoom_x, zoom_y) * 0.8  # Немного уменьшаем для отступов
        
        matrix = fitz.Matrix(zoom, zoom)
        pix = page.get_pixmap(matrix=matrix)
        
        # Конвертируем в PIL Image
        img_data = pix.tobytes("png")
        img = Image.open(BytesIO(img_data))
        
        # Сохраняем миниатюру
        thumbnail_name = f"thumbnail_{material_instance.id}_{page_number}.png"
        
        # Создаем временный файл
        with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as temp_file:
            img.save(temp_file, format='PNG', quality=85)
            temp_path = temp_file.name
        
        # Сохраняем в поле thumbnail
        with open(temp_path, 'rb') as f:
            material_instance.thumbnail.save(thumbnail_name, ContentFile(f.read()), save=False)
        
        # Очищаем временный файл
        os.unlink(temp_path)
        
        # Обновляем количество страниц
        material_instance.page_count = doc.page_count
        
        doc.close()
        return True
        
    except Exception as e:
        print(f"Ошибка генерации миниатюры для {pdf_path}: {e}")
        return False

def extract_pdf_text(pdf_path, page_numbers=None):
    """Извлекает текст из PDF"""
    try:
        if not os.path.exists(pdf_path):
            return []
        
        doc = fitz.open(pdf_path)
        texts = []
        
        if page_numbers is None:
            page_numbers = range(doc.page_count)
        
        for page_num in page_numbers:
            if 0 <= page_num < doc.page_count:
                page = doc.load_page(page_num)
                text = page.get_text()
                texts.append({
                    'page': page_num + 1,
                    'text': text[:500] + '...' if len(text) > 500 else text
                })
        
        doc.close()
        return texts
    except Exception as e:
        print(f"Ошибка извлечения текста: {e}")
        return []

def split_pdf_by_pages(pdf_path, output_dir, pages_per_split=10):
    """Разделяет PDF на части по N страниц"""
    try:
        if not os.path.exists(pdf_path):
            return []
        
        doc = fitz.open(pdf_path)
        total_pages = doc.page_count
        output_files = []
        
        for start in range(0, total_pages, pages_per_split):
            end = min(start + pages_per_split, total_pages)
            
            new_doc = fitz.open()
            for page_num in range(start, end):
                new_doc.insert_pdf(doc, from_page=page_num, to_page=page_num)
            
            output_filename = f"part_{(start // pages_per_split) + 1}.pdf"
            output_path = os.path.join(output_dir, output_filename)
            new_doc.save(output_path)
            new_doc.close()
            
            output_files.append({
                'filename': output_filename,
                'path': output_path,
                'pages': f"{start+1}-{end}",
                'page_count': end - start
            })
        
        doc.close()
        return output_files
    except Exception as e:
        print(f"Ошибка разделения PDF: {e}")
        return []

def is_pdf_file(file_path):
    """Проверяет, является ли файл PDF"""
    try:
        if not os.path.exists(file_path):
            return False
        
        # Проверяем расширение
        if not file_path.lower().endswith('.pdf'):
            return False
        
        # Проверяем заголовок файла
        with open(file_path, 'rb') as f:
            header = f.read(4)
            return header == b'%PDF'
    except:
        return False

def get_pdf_metadata(pdf_path):
    """Получает метаданные PDF"""
    try:
        if not os.path.exists(pdf_path):
            return {}
        
        doc = fitz.open(pdf_path)
        metadata = doc.metadata
        doc.close()
        
        return metadata
    except Exception as e:
        print(f"Ошибка получения метаданных: {e}")
        return {}