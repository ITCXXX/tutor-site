if (typeof pdfjsLib !== 'undefined') {
    pdfjsLib.GlobalWorkerOptions.workerSrc =
        'https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.worker.min.js';
}

class PDFViewer {
    constructor(pdfUrl) {
        this.pdfUrl     = pdfUrl;
        this.pdfDoc     = null;
        this.currentPage = 1;
        this.totalPages  = 0;
        this.scale       = 1.0;
        this.canvas      = document.getElementById('pdf-canvas');
        this.ctx         = this.canvas.getContext('2d');
        this.isLoading   = false;
        this.bookmarksMap = new Map();

        this.init();
    }

    // ── Инициализация ──────────────────────────────────────────────────────

    async init() {
        try {
            this.showLoading(true);
            const loadingTask = pdfjsLib.getDocument(this.pdfUrl);
            this.pdfDoc = await loadingTask.promise;
            this.totalPages = this.pdfDoc.numPages;
            this.updatePageCount();
            this.renderThumbnails();
            await this.fitWidth();          // открываем по ширине контейнера
            await this.initBookmarksSystem();
            this.updateBookmarkButton();
            this.showLoading(false);
        } catch (err) {
            console.error('PDF load error:', err);
            this.showError('Не удалось загрузить PDF');
        }
    }

    // ── Рендеринг страницы ─────────────────────────────────────────────────

    async renderPage(pageNum) {
        if (this.isLoading || pageNum < 1 || pageNum > this.totalPages) return;
        try {
            this.isLoading = true;
            this.currentPage = pageNum;

            const page     = await this.pdfDoc.getPage(pageNum);
            const viewport = page.getViewport({ scale: this.scale });

            this.canvas.height = viewport.height;
            this.canvas.width  = viewport.width;

            await page.render({ canvasContext: this.ctx, viewport }).promise;

            this.updatePageUI();
            this.updateActiveThumbnail();
            this.updateBookmarkButton();
        } catch (err) {
            console.error('Render error:', err);
        } finally {
            this.isLoading = false;
        }
    }

    // ── Масштабирование ────────────────────────────────────────────────────

    async fitWidth() {
        if (!this.pdfDoc) return;
        const area = document.getElementById('canvas-area');
        if (!area) return;
        const available = area.clientWidth - 40; // 20px отступ с каждой стороны
        const page      = await this.pdfDoc.getPage(this.currentPage);
        const base      = page.getViewport({ scale: 1.0 });
        this.scale      = Math.max(0.5, available / base.width);
        this.updateZoomUI();
        await this.renderPage(this.currentPage);
    }

    zoomIn() {
        this.scale = Math.min(this.scale + 0.15, 4.0);
        this.updateZoomUI();
        this.renderPage(this.currentPage);
    }

    zoomOut() {
        this.scale = Math.max(this.scale - 0.15, 0.3);
        this.updateZoomUI();
        this.renderPage(this.currentPage);
    }

    // ── Навигация ──────────────────────────────────────────────────────────

    prevPage() {
        if (this.currentPage > 1) this.renderPage(this.currentPage - 1);
    }

    nextPage() {
        if (this.currentPage < this.totalPages) this.renderPage(this.currentPage + 1);
    }

    goToPage(pageNum) {
        pageNum = parseInt(pageNum);
        if (pageNum >= 1 && pageNum <= this.totalPages && pageNum !== this.currentPage) {
            this.renderPage(pageNum);
        }
    }

    // ── Миниатюры ──────────────────────────────────────────────────────────

    async renderThumbnails() {
        const container = document.getElementById('thumbnails-list');
        if (!container) return;
        container.innerHTML = '';

        for (let i = 1; i <= this.totalPages; i++) {
            const item = document.createElement('div');
            item.className = 'thumb-item';
            item.dataset.page = i;

            const thumbCanvas = document.createElement('canvas');
            thumbCanvas.className = 'thumb-canvas';
            item.appendChild(thumbCanvas);

            const label = document.createElement('div');
            label.className = 'thumb-label';
            label.textContent = i;
            item.appendChild(label);

            item.addEventListener('click', () => this.goToPage(i));
            container.appendChild(item);

            if (i <= 30) this.renderThumbnail(i, thumbCanvas);
        }
    }

    async renderThumbnail(pageNum, canvas) {
        try {
            const page     = await this.pdfDoc.getPage(pageNum);
            const viewport = page.getViewport({ scale: 0.18 });
            canvas.height  = viewport.height;
            canvas.width   = viewport.width;
            await page.render({ canvasContext: canvas.getContext('2d'), viewport }).promise;
        } catch (err) {
            // тихо игнорируем ошибки миниатюр
        }
    }

    updateActiveThumbnail() {
        document.querySelectorAll('.thumb-item').forEach(el => el.classList.remove('active'));
        const active = document.querySelector(`.thumb-item[data-page="${this.currentPage}"]`);
        if (active) {
            active.classList.add('active');
            active.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
        }
    }

    // ── Обновление UI ─────────────────────────────────────────────────────

    updatePageUI() {
        const inp = document.getElementById('page-num');
        if (inp) { inp.value = this.currentPage; inp.max = this.totalPages; }
    }

    updatePageCount() {
        const el = document.getElementById('page-count');
        if (el) el.textContent = this.totalPages;
    }

    updateZoomUI() {
        const el = document.getElementById('zoom-level');
        if (el) el.textContent = Math.round(this.scale * 100) + '%';
    }

    showLoading(show) {
        const indicator = document.getElementById('loading-indicator');
        if (indicator) indicator.style.display = show ? 'block' : 'none';
        if (this.canvas) this.canvas.style.display = show ? 'none' : 'block';
    }

    showError(message) {
        const area = document.getElementById('canvas-area');
        if (area) area.innerHTML = `
            <div class="text-center text-light p-5">
                <i class="bi bi-exclamation-triangle fs-1 d-block mb-3"></i>
                <p>${message}</p>
                <button class="btn btn-outline-light btn-sm" onclick="location.reload()">
                    Перезагрузить
                </button>
            </div>`;
    }

    // ── Закладки ───────────────────────────────────────────────────────────

    async initBookmarksSystem() {
        const bookmarks = await this.loadBookmarks();
        bookmarks.forEach(b => {
            this.bookmarksMap.set(b.page_number, b.id);
            this.updateThumbBookmarkIcon(b.page_number, true);
        });
    }

    async toggleBookmark() {
        const pageNum = this.currentPage;
        const existing = this.bookmarksMap.get(pageNum);
        if (existing) {
            const ok = await this.deleteBookmark(existing);
            if (ok) {
                this.bookmarksMap.delete(pageNum);
                this.updateThumbBookmarkIcon(pageNum, false);
                this.updateBookmarkButton();
                this.showNotification('Закладка удалена', 'secondary');
            }
        } else {
            await this.saveBookmark();
        }
    }

    updateBookmarkButton() {
        const btn = document.getElementById('add-bookmark');
        if (!btn) return;
        const has = this.bookmarksMap.has(this.currentPage);
        if (has) {
            btn.innerHTML = '<i class="bi bi-bookmark-check-fill"></i><span class="d-none d-sm-inline ms-1">Убрать</span>';
            btn.classList.replace('btn-outline-secondary', 'btn-warning');
        } else {
            btn.innerHTML = '<i class="bi bi-bookmark-plus"></i><span class="d-none d-sm-inline ms-1">Закладка</span>';
            btn.classList.replace('btn-warning', 'btn-outline-secondary');
        }
    }

    updateThumbBookmarkIcon(pageNum, add) {
        const item = document.querySelector(`.thumb-item[data-page="${pageNum}"]`);
        if (!item) return;
        const existing = item.querySelector('.thumb-bookmark');
        if (add && !existing) {
            const icon = document.createElement('span');
            icon.className = 'thumb-bookmark';
            icon.innerHTML = ' <i class="bi bi-bookmark-fill" style="color:#ffc107;font-size:0.65rem;"></i>';
            item.querySelector('.thumb-label').appendChild(icon);
        } else if (!add && existing) {
            existing.remove();
        }
    }

    async saveBookmark() {
        if (!window.MATERIAL_ID) return;
        try {
            const res = await fetch('/api/pdf-bookmarks/', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'X-CSRFToken': this.csrfToken() },
                body: JSON.stringify({ material: window.MATERIAL_ID, page_number: this.currentPage, comment: '' })
            });
            if (res.ok) {
                const data = await res.json();
                this.bookmarksMap.set(this.currentPage, data.id);
                this.updateThumbBookmarkIcon(this.currentPage, true);
                this.updateBookmarkButton();
                this.showNotification('Закладка сохранена', 'success');
            }
        } catch (err) {
            console.error('Bookmark save error:', err);
        }
    }

    async loadBookmarks() {
        if (!window.MATERIAL_ID) return [];
        try {
            const res = await fetch(`/api/pdf-bookmarks/by_material/?material_id=${window.MATERIAL_ID}`);
            return res.ok ? await res.json() : [];
        } catch {
            return [];
        }
    }

    async deleteBookmark(id) {
        try {
            const res = await fetch(`/api/pdf-bookmarks/${id}/`, {
                method: 'DELETE',
                headers: { 'X-CSRFToken': this.csrfToken() }
            });
            return res.ok;
        } catch {
            return false;
        }
    }

    async showBookmarksPanel() {
        const bookmarks = await this.loadBookmarks();
        if (!bookmarks.length) {
            this.showNotification('Нет закладок в этом документе', 'secondary');
            return;
        }

        // Убираем старое модальное окно если есть
        document.getElementById('bookmarksModal')?.remove();

        const div = document.createElement('div');
        div.innerHTML = `
            <div class="modal fade" id="bookmarksModal" tabindex="-1">
                <div class="modal-dialog modal-sm">
                    <div class="modal-content">
                        <div class="modal-header py-2">
                            <h6 class="modal-title mb-0">
                                <i class="bi bi-bookmarks"></i> Закладки
                            </h6>
                            <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                        </div>
                        <div class="modal-body p-2">
                            <div class="list-group list-group-flush">
                                ${bookmarks.map(b => `
                                    <div class="list-group-item d-flex justify-content-between align-items-center px-2 py-1">
                                        <button class="btn btn-sm btn-link p-0 text-decoration-none goto-bm"
                                                data-page="${b.page_number}">
                                            Страница ${b.page_number}
                                        </button>
                                        <button class="btn btn-sm btn-outline-danger del-bm py-0 px-1"
                                                data-id="${b.id}">
                                            <i class="bi bi-trash"></i>
                                        </button>
                                    </div>`).join('')}
                            </div>
                        </div>
                    </div>
                </div>
            </div>`;
        document.body.appendChild(div);

        const modal = new bootstrap.Modal(document.getElementById('bookmarksModal'));
        modal.show();

        div.querySelectorAll('.goto-bm').forEach(btn => btn.addEventListener('click', () => {
            this.goToPage(parseInt(btn.dataset.page));
            modal.hide();
        }));
        div.querySelectorAll('.del-bm').forEach(btn => btn.addEventListener('click', async () => {
            if (await this.deleteBookmark(btn.dataset.id)) {
                btn.closest('.list-group-item').remove();
                const pageNum = [...this.bookmarksMap.entries()]
                    .find(([, id]) => id == btn.dataset.id)?.[0];
                if (pageNum) {
                    this.bookmarksMap.delete(pageNum);
                    this.updateThumbBookmarkIcon(pageNum, false);
                    this.updateBookmarkButton();
                }
                if (!div.querySelectorAll('.list-group-item').length) modal.hide();
            }
        }));
    }

    // ── Вспомогательные ────────────────────────────────────────────────────

    showNotification(message, type = 'info') {
        const toast = document.createElement('div');
        toast.className = `toast align-items-center text-bg-${type} border-0 position-fixed`;
        toast.style.cssText = 'bottom:20px;right:20px;z-index:9999;min-width:220px;';
        toast.innerHTML = `
            <div class="d-flex">
                <div class="toast-body">${message}</div>
                <button type="button" class="btn-close btn-close-white me-2 m-auto"
                        data-bs-dismiss="toast"></button>
            </div>`;
        document.body.appendChild(toast);
        const bsToast = new bootstrap.Toast(toast, { delay: 2500 });
        bsToast.show();
        toast.addEventListener('hidden.bs.toast', () => toast.remove());
    }

    csrfToken() {
        const m = document.cookie.match(/csrftoken=([^;]+)/);
        return m ? m[1] : '';
    }
}

window.PDFViewer = PDFViewer;
