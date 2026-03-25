// static/js/pdf-viewer.js

// =========== КРИТИЧЕСКИ ВАЖНО: настройка PDF.js ===========
// Указываем путь к воркеру для распараллеливания задач
if (typeof pdfjsLib !== 'undefined') {
    pdfjsLib.GlobalWorkerOptions.workerSrc =
        'https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.worker.min.js';
}
// =========================================================

/**
 * Основной класс для работы с PDF.js
 * Управляет загрузкой, отображением и навигацией по PDF
 */
class PDFViewer {
    constructor(pdfUrl) {
        // ... остальной код конструктора остается без изменений ...
        this.pdfUrl = pdfUrl;
        this.pdfDoc = null;
        this.currentPage = 1;
        this.totalPages = 0;
        this.scale = 1.0;
        this.canvas = document.getElementById('pdf-canvas');
        this.ctx = this.canvas.getContext('2d');
        this.isLoading = false;
        
        // Инициализируем
        this.init();
    }
    
    /**
     * Инициализация просмотрщика
     */
    async init() {
        try {
            // Показываем индикатор загрузки
            this.showLoading(true);
            
            // Загружаем PDF документ
            const loadingTask = pdfjsLib.getDocument(this.pdfUrl);
            this.pdfDoc = await loadingTask.promise;
            
            this.totalPages = this.pdfDoc.numPages;
            
            // Обновляем UI
            this.updatePageCount();
            this.renderThumbnails();
            
            // Рендерим первую страницу
            await this.renderPage(this.currentPage);
            
            // Скрываем индикатор загрузки
            this.showLoading(false);
            
        } catch (error) {
            console.error('Ошибка загрузки PDF:', error);
            this.showError('Не удалось загрузить PDF документ');
        }
    }
    
    /**
     * Рендеринг конкретной страницы
     * @param {number} pageNum - Номер страницы (начиная с 1)
     */
    async renderPage(pageNum) {
        if (this.isLoading || pageNum < 1 || pageNum > this.totalPages) {
            return;
        }
        
        try {
            this.isLoading = true;
            this.currentPage = pageNum;
            
            // Получаем объект страницы
            const page = await this.pdfDoc.getPage(pageNum);
            
            // Устанавливаем размер viewport (области просмотра)
            const viewport = page.getViewport({ scale: this.scale });
            
            // Устанавливаем размеры canvas
            this.canvas.height = viewport.height;
            this.canvas.width = viewport.width;
            
            // Рендерим страницу на canvas
            const renderContext = {
                canvasContext: this.ctx,
                viewport: viewport
            };
            
            await page.render(renderContext).promise;
            
            // Обновляем UI
            this.updatePageUI();
            this.updateActiveThumbnail();
            
            // Логируем просмотр (для будущей статистики)
            this.logPageView(pageNum);
            
        } catch (error) {
            console.error('Ошибка рендеринга страницы:', error);
        } finally {
            this.isLoading = false;
        }
    }
    
    /**
     * Создание миниатюр всех страниц
     */
    async renderThumbnails() {
        const container = document.getElementById('thumbnails-list');
        if (!container) return;
        
        container.innerHTML = '';
        
        // Создаем миниатюры для первых 10 страниц (для производительности)
        const maxThumbnails = Math.min(this.totalPages, 10);
        
        for (let i = 1; i <= maxThumbnails; i++) {
            const thumbItem = document.createElement('div');
            thumbItem.className = 'thumbnail-item';
            thumbItem.dataset.page = i;
            
            const thumbCanvas = document.createElement('canvas');
            thumbCanvas.className = 'thumbnail-canvas';
            thumbItem.appendChild(thumbCanvas);
            
            const pageLabel = document.createElement('div');
            pageLabel.className = 'text-center small';
            pageLabel.textContent = `Страница ${i}`;
            thumbItem.appendChild(pageLabel);
            
            // Обработчик клика
            thumbItem.addEventListener('click', () => {
                this.goToPage(i);
            });
            
            container.appendChild(thumbItem);
            
            // Асинхронно рендерим миниатюру
            this.renderThumbnail(i, thumbCanvas);
        }
        
        if (this.totalPages > maxThumbnails) {
            const moreText = document.createElement('div');
            moreText.className = 'text-center text-muted small mt-2';
            moreText.textContent = `... и ещё ${this.totalPages - maxThumbnails} страниц`;
            container.appendChild(moreText);
        }
    }
    
    /**
     * Рендеринг миниатюры страницы
     */
    async renderThumbnail(pageNum, canvas) {
        try {
            const page = await this.pdfDoc.getPage(pageNum);
            const viewport = page.getViewport({ scale: 0.15 }); // Маленький масштаб для миниатюры
            
            canvas.height = viewport.height;
            canvas.width = viewport.width;
            
            const ctx = canvas.getContext('2d');
            const renderContext = {
                canvasContext: ctx,
                viewport: viewport
            };
            
            await page.render(renderContext).promise;
            
        } catch (error) {
            console.error('Ошибка рендеринга миниатюры:', error);
        }
    }
    
    /**
     * Навигация по страницам
     */
    prevPage() {
        if (this.currentPage > 1) {
            this.goToPage(this.currentPage - 1);
        }
    }
    
    nextPage() {
        if (this.currentPage < this.totalPages) {
            this.goToPage(this.currentPage + 1);
        }
    }
    
    goToPage(pageNum) {
        pageNum = parseInt(pageNum);
        if (pageNum >= 1 && pageNum <= this.totalPages && pageNum !== this.currentPage) {
            this.renderPage(pageNum);
        }
    }
    
    /**
     * Масштабирование
     */
    zoomIn() {
        this.scale = Math.min(this.scale + 0.1, 3.0); // Максимум 300%
        this.renderPage(this.currentPage);
        this.updateZoomUI();
    }
    
    zoomOut() {
        this.scale = Math.max(this.scale - 0.1, 0.5); // Минимум 50%
        this.renderPage(this.currentPage);
        this.updateZoomUI();
    }
    
    resetZoom() {
        this.scale = 1.0;
        this.renderPage(this.currentPage);
        this.updateZoomUI();
    }
    
    /**
     * Обновление UI
     */
    updatePageUI() {
        // Обновляем номер страницы в поле ввода
        const pageInput = document.getElementById('page-num');
        if (pageInput) {
            pageInput.value = this.currentPage;
            pageInput.max = this.totalPages;
        }
        
        // Обновляем информацию о текущей странице
        const pageCountSpan = document.getElementById('page-count');
        if (pageCountSpan) {
            pageCountSpan.textContent = this.totalPages;
        }
        
        // Обновляем информацию внизу
        const docPageCount = document.getElementById('doc-page-count');
        if (docPageCount) {
            docPageCount.textContent = this.totalPages;
        }
    }
    
    updatePageCount() {
        const pageCountSpan = document.getElementById('page-count');
        if (pageCountSpan) {
            pageCountSpan.textContent = this.totalPages;
        }
    }
    
    updateZoomUI() {
        const zoomLevel = document.getElementById('zoom-level');
        if (zoomLevel) {
            zoomLevel.textContent = Math.round(this.scale * 100) + '%';
        }
    }
    
    updateActiveThumbnail() {
        // Убираем активный класс у всех миниатюр
        document.querySelectorAll('.thumbnail-item').forEach(item => {
            item.classList.remove('active');
        });
        
        // Добавляем активный класс текущей странице
        const activeThumb = document.querySelector(`.thumbnail-item[data-page="${this.currentPage}"]`);
        if (activeThumb) {
            activeThumb.classList.add('active');
            
            // Прокручиваем к активной миниатюре
            activeThumb.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
        }
    }
    
    /**
     * Вспомогательные методы
     */
    showLoading(show) {
        const indicator = document.getElementById('loading-indicator');
        if (indicator) {
            indicator.style.display = show ? 'block' : 'none';
        }
        // ДОБАВЛЯЕМ ПРОВЕРКУ СУЩЕСТВОВАНИЯ CANVAS
        if (this.canvas) {
            this.canvas.style.display = show ? 'none' : 'block';
        }
    }
    
    showError(message) {
        const container = document.getElementById('pdf-container');
        if (container) {
            container.innerHTML = `
                <div class="alert alert-danger m-4">
                    <h5>Ошибка</h5>
                    <p>${message}</p>
                    <button class="btn btn-sm btn-outline-danger" onclick="window.location.reload()">
                        Перезагрузить
                    </button>
                </div>
            `;
        }
    }
    
    /**
     * Логирование просмотра страницы (для будущей статистики)
     */
    logPageView(pageNum) {
        // В Этапе 2 здесь будет отправка данных на сервер Django
        console.log(`Пользователь просматривает страницу ${pageNum}`);
        
        // Пример будущей реализации:
        /*
        fetch('/api/log-page-view/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCsrfToken()
            },
            body: JSON.stringify({
                material_id: window.MATERIAL_ID, // Нужно будет передать из Django
                page: pageNum,
                duration: 0 // В будущем будем считать время
            })
        });
        */
    }
}

// Вспомогательная функция для получения CSRF токена (понадобится позже)
function getCsrfToken() {
    const cookie = document.cookie.match(/csrftoken=([^;]+)/);
    return cookie ? cookie[1] : null;
}

// Экспортируем класс для использования в основном скрипте
window.PDFViewer = PDFViewer;