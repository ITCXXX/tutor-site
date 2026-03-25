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
            
            // === ДОБАВЛЯЕМ ЭТИ ДВЕ СТРОКИ ===
            await this.initBookmarksSystem();
            this.updateBookmarkButton();
            this.initSearch(); // <-- ДОБАВИТЬ ЭТУ СТРОКУ
            // =================================
            
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
            
            // === ДОБАВЛЯЕМ ЭТУ СТРОКУ ===
            this.updateBookmarkButton(); // Обновляем кнопку при смене страницы
            // ============================

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
        
        // === ИЗМЕНЕНИЕ: показываем ВСЕ страницы, а не только 10 ===
        for (let i = 1; i <= this.totalPages; i++) {
            const thumbItem = document.createElement('div');
            thumbItem.className = 'thumbnail-item';
            thumbItem.dataset.page = i;
            
            const thumbCanvas = document.createElement('canvas');
            thumbCanvas.className = 'thumbnail-canvas';
            thumbItem.appendChild(thumbCanvas);
            
            const pageLabel = document.createElement('div');
            pageLabel.className = 'text-center small';
            pageLabel.textContent = `Стр. ${i}`; // Более короткая подпись
            thumbItem.appendChild(pageLabel);
            
            // Обработчик клика
            thumbItem.addEventListener('click', () => {
                this.goToPage(i);
            });
            
            container.appendChild(thumbItem);
            
            // Рендерим миниатюру (но для большого кол-ва страниц можно отложить)
            if (i <= 20) { // Рендерим первые 20 сразу, остальные по необходимости
                this.renderThumbnail(i, thumbCanvas);
            }
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
                'X-CSRFToken': this.getCsrfToken()
            },
            body: JSON.stringify({
                material_id: window.MATERIAL_ID,
                page: pageNum,
                duration: 0
            })
        });
        */
    }
        /**
     * ===== РАСШИРЕННОЕ УПРАВЛЕНИЕ ЗАКЛАДКАМИ =====
     */

    // Хранилище состояния закладок
    bookmarksMap = new Map(); // pageNum -> bookmarkId

    /**
     * Инициализирует систему закладок (вызывать после загрузки PDF)
     */
    async initBookmarksSystem() {
        const bookmarks = await this.loadBookmarks();
        
        // Заполняем карту закладок
        bookmarks.forEach(bookmark => {
            this.bookmarksMap.set(bookmark.page_number, bookmark.id);
            this.updatePageBookmarkIndicator(bookmark.page_number, true);
        });
        
        console.log(`Инициализировано ${bookmarks.length} закладок`);
    }

    /**
     * Сохраняет или удаляет закладку (переключатель)
     */
    async toggleBookmark() {
        const pageNum = this.currentPage;
        const existingBookmarkId = this.bookmarksMap.get(pageNum);
        
        if (existingBookmarkId) {
            // Закладка уже есть — удаляем
            const success = await this.deleteBookmark(existingBookmarkId);
            if (success) {
                this.bookmarksMap.delete(pageNum);
                this.updatePageBookmarkIndicator(pageNum, false);
                this.showNotification('Закладка удалена', 'info');
                this.refreshBookmarksDisplay();
            }
        } else {
            // Закладки нет — создаём
            await this.saveBookmark();
            // После успешного сохранения saveBookmark вызовет refreshBookmarksDisplay
        }
    }

    /**
     * Проверяет, есть ли закладка на текущей странице
     */
    hasBookmarkOnCurrentPage() {
        return this.bookmarksMap.has(this.currentPage);
    }

    /**
     * Обновляет интерфейс кнопки закладки
     */
    updateBookmarkButton() {
        const btn = document.getElementById('add-bookmark');
        if (!btn) return;
        
        const hasBookmark = this.hasBookmarkOnCurrentPage();
        
        if (hasBookmark) {
            btn.innerHTML = '<i class="bi bi-bookmark-check-fill"></i> Убрать';
            btn.classList.remove('btn-outline-success');
            btn.classList.add('btn-success');
            btn.title = 'Убрать закладку с этой страницы';
        } else {
            btn.innerHTML = '<i class="bi bi-bookmark-plus"></i> Закладка';
            btn.classList.remove('btn-success');
            btn.classList.add('btn-outline-success');
            btn.title = 'Добавить закладку на эту страницу';
        }
    }

    /**
     * Добавляет/убирает индикатор закладки на миниатюре страницы
     */
    updatePageBookmarkIndicator(pageNum, hasBookmark) {
        const thumbnail = document.querySelector(`.thumbnail-item[data-page="${pageNum}"]`);
        if (thumbnail) {
            if (hasBookmark) {
                thumbnail.classList.add('has-bookmark');
                // Добавляем иконку закладки к миниатюре
                let icon = thumbnail.querySelector('.bookmark-icon');
                if (!icon) {
                    icon = document.createElement('span');
                    icon.className = 'bookmark-icon ms-1 text-warning';
                    icon.innerHTML = '<i class="bi bi-bookmark-fill"></i>';
                    thumbnail.querySelector('.text-center').appendChild(icon);
                }
            } else {
                thumbnail.classList.remove('has-bookmark');
                const icon = thumbnail.querySelector('.bookmark-icon');
                if (icon) icon.remove();
            }
        }
    }

    /**
     * Обновляет все визуальные элементы закладок
     */
    async refreshBookmarksDisplay() {
        // Перезагружаем данные
        const bookmarks = await this.loadBookmarks();
        
        // Обновляем карту
        this.bookmarksMap.clear();
        bookmarks.forEach(bookmark => {
            this.bookmarksMap.set(bookmark.page_number, bookmark.id);
        });
        
        // Обновляем индикаторы на всех миниатюрах
        for (let pageNum = 1; pageNum <= this.totalPages; pageNum++) {
            this.updatePageBookmarkIndicator(pageNum, this.bookmarksMap.has(pageNum));
        }
        
        // Обновляем кнопку
        this.updateBookmarkButton();
        
        // Если открыто модальное окно — обновляем его
        const modal = document.getElementById('bookmarksModal');
        if (modal && modal.classList.contains('show')) {
            this.showBookmarksPanel();
        }
    }
    /**
     * ===== МЕТОДЫ ДЛЯ РАБОТЫ С API ЗАКЛАДОК =====
     */

    /**
     * Сохраняет закладку на текущей странице
     */
    async saveBookmark() {
        if (!this.currentPage || !window.MATERIAL_ID) {
            console.error('Не хватает данных для сохранения закладки');
            return;
        }

        const payload = {
            material: window.MATERIAL_ID,
            page_number: this.currentPage,
            comment: `Закладка на странице ${this.currentPage}`
        };

        try {
            const response = await fetch('/api/pdf-bookmarks/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': this.getCsrfToken()
                },
                body: JSON.stringify(payload)
            });

            if (response.ok) {
                const data = await response.json();
                this.showNotification('Закладка успешно сохранена!', 'success');
                
                // === НОВЫЙ КОД: Обновляем интерфейс сразу ===
                this.bookmarksMap.set(this.currentPage, data.id);          // 1. Добавляем в карту
                this.updatePageBookmarkIndicator(this.currentPage, true);  // 2. Ставим иконку на миниатюру
                this.updateBookmarkButton();                               // 3. Меняем кнопку на "Убрать"
                // ===========================================
                
                console.log('Закладка сохранена:', data);
                return data;
            } else {
                const error = await response.json();
                this.showNotification(`Ошибка: ${error.detail || 'Не удалось сохранить'}`, 'error');
                throw new Error(error.detail || 'Ошибка сохранения');
            }
        } catch (error) {
            console.error('Ошибка при сохранении закладки:', error);
            // Не показываем уведомление здесь, чтобы не перекрывать успешное
        }
    }

    /**
     * Загружает все закладки для текущего материала
     */
    async loadBookmarks() {
        console.log('Загрузка закладок, MATERIAL_ID:', window.MATERIAL_ID);
        
        if (!window.MATERIAL_ID) {
            console.error('Material ID не определён');
            return [];
        }

        try {
            const url = `/api/pdf-bookmarks/by_material/?material_id=${window.MATERIAL_ID}`;
            console.log('Запрос к URL:', url);
            
            const response = await fetch(url);
            console.log('Статус ответа:', response.status);
            
            if (response.ok) {
                const bookmarks = await response.json();
                console.log('Загруженные закладки:', bookmarks);
                return bookmarks;
            } else {
                console.error('Ошибка HTTP:', response.status);
                return [];
            }
        } catch (error) {
            console.error('Сетевая ошибка в loadBookmarks:', error);
            return []; // Возвращаем пустой массив вместо выброса ошибки
        }
    }

    /**
     * Удаляет закладку
     */
    async deleteBookmark(bookmarkId) {
        try {
            const response = await fetch(`/api/pdf-bookmarks/${bookmarkId}/`, {
                method: 'DELETE',
                headers: {
                    'X-CSRFToken': this.getCsrfToken()
                }
            });

            if (response.ok) {
                this.showNotification('Закладка удалена', 'info');
                return true;
            }
            return false;
        } catch (error) {
            console.error('Ошибка при удалении закладки:', error);
            return false;
        }
    }

    /**
     * Показывает панель с закладками
     */
    async showBookmarksPanel() {
        try {
            const bookmarks = await this.loadBookmarks();
            
            if (bookmarks.length === 0) {
                this.showNotification('У вас пока нет закладок в этом документе', 'info');
                return;
            }

            // Создаём простое модальное окно со списком закладок
            const modalHtml = `
                <div class="modal fade" id="bookmarksModal" tabindex="-1">
                    <div class="modal-dialog">
                        <div class="modal-content">
                            <div class="modal-header">
                                <h5 class="modal-title"><i class="bi bi-bookmarks"></i> Ваши закладки</h5>
                                <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                            </div>
                            <div class="modal-body">
                                <div class="list-group">
                                    ${bookmarks.map(bookmark => `
                                        <div class="list-group-item d-flex justify-content-between align-items-center">
                                            <div>
                                                <strong>Страница ${bookmark.page_number}</strong>
                                                ${bookmark.comment ? `<br><small>${bookmark.comment}</small>` : ''}
                                            </div>
                                            <div class="btn-group">
                                                <button class="btn btn-sm btn-outline-primary goto-bookmark" data-page="${bookmark.page_number}">
                                                    Перейти
                                                </button>
                                                <button class="btn btn-sm btn-outline-danger delete-bookmark" data-id="${bookmark.id}">
                                                    <i class="bi bi-trash"></i>
                                                </button>
                                            </div>
                                        </div>
                                    `).join('')}
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            `;

            // Добавляем модальное окно в DOM и показываем
            const modalContainer = document.createElement('div');
            modalContainer.innerHTML = modalHtml;
            document.body.appendChild(modalContainer);

            // Инициализируем модальное окно Bootstrap
            const modal = new bootstrap.Modal(document.getElementById('bookmarksModal'));
            modal.show();

            // Обработчики для кнопок в модальном окне
            document.querySelectorAll('.goto-bookmark').forEach(btn => {
                btn.addEventListener('click', (e) => {
                    const page = parseInt(e.target.dataset.page);
                    this.goToPage(page);
                    modal.hide();
                });
            });

            document.querySelectorAll('.delete-bookmark').forEach(btn => {
                btn.addEventListener('click', async (e) => {
                    const bookmarkId = e.target.dataset.id;
                    if (await this.deleteBookmark(bookmarkId)) {
                        e.target.closest('.list-group-item').remove();
                        // Если закладок не осталось, закрываем модальное окно
                        if (document.querySelectorAll('.list-group-item').length === 0) {
                            modal.hide();
                        }
                    }
                });
            });
            
        } catch (error) {
            console.error('Ошибка при загрузке закладок для панели:', error);
            // Не показываем уведомление об ошибке, чтобы не перекрывать успешное
        }
    }

    /**
     * Вспомогательная функция для уведомлений
     */
    showNotification(message, type = 'info') {
        // Простой toast-уведомление
        const toast = document.createElement('div');
        toast.className = `toast align-items-center text-bg-${type} border-0`;
        toast.innerHTML = `
            <div class="d-flex">
                <div class="toast-body">${message}</div>
                <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button>
            </div>
        `;
        
        const container = document.getElementById('pdf-container') || document.body;
        container.appendChild(toast);
        
        const bsToast = new bootstrap.Toast(toast, { delay: 3000 });
        bsToast.show();
        
        toast.addEventListener('hidden.bs.toast', () => {
            toast.remove();
        });
    }

    /**
     * Вспомогательная функция для получения CSRF токена
     */
    getCsrfToken() {
        const cookie = document.cookie.match(/csrftoken=([^;]+)/);
        return cookie ? cookie[1] : null;
    }
        /**
     * Поиск по тексту в PDF
     */
    async initSearch() {
        // Используем встроенный поиск PDF.js
        this.pdfFindController = new pdfjsLib.PDFFindController({
            linkService: {
                navigateTo: (dest) => {
                    // Обработка переходов по результатам поиска
                }
            }
        });
        
        // Подключаем поиск к документу
        this.pdfFindController.setDocument(this.pdfDoc);
        
        // Привязываем поле ввода поиска
        const searchInput = document.getElementById('search-input');
        const searchBtn = document.getElementById('search-btn');
        
        if (searchInput && searchBtn) {
            searchBtn.addEventListener('click', () => {
                this.performSearch(searchInput.value);
            });
            
            searchInput.addEventListener('keypress', (e) => {
                if (e.key === 'Enter') {
                    this.performSearch(searchInput.value);
                }
            });
        }
    }
    
    async performSearch(query) {
        if (!query.trim()) return;
        
        try {
            // Выполняем поиск через PDF.js
            const searchResults = await this.pdfFindController.executeCommand('find', {
                query: query,
                caseSensitive: false,
                entireWord: false,
                highlightAll: true,
                findPrevious: false
            });
            
            if (searchResults.count === 0) {
                this.showNotification('Ничего не найдено', 'info');
            } else {
                this.showNotification(`Найдено совпадений: ${searchResults.count}`, 'success');
                // Показываем панель навигации по результатам
                document.getElementById('search-results').classList.remove('d-none');
                document.getElementById('search-status').textContent = 
                    `Найдено: ${searchResults.count}`;
            }
        } catch (error) {
            console.error('Ошибка поиска:', error);
            this.showNotification('Ошибка при поиске', 'error');
        }
    }
}
// Экспортируем класс для использования в основном скрипте
window.PDFViewer = PDFViewer;