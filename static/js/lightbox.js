// Глобальный лайтбокс. Любой клик по элементу с атрибутом data-lightbox-src
// открывает картинку из этого атрибута на полный экран. Закрытие — кнопкой ×,
// кликом по фону или клавишей Esc. Работает даже на динамически добавленных
// элементах (через делегирование событий на document).
(function () {
    const lb = document.getElementById('lightbox');
    if (!lb) return;
    const lbImg = lb.querySelector('#lightbox-img');
    const lbClose = lb.querySelector('#lightbox-close');

    function openLb(src) {
        lbImg.src = src;
        lb.classList.add('open');
        document.body.style.overflow = 'hidden';
    }
    function closeLb() {
        lb.classList.remove('open');
        lbImg.src = '';
        document.body.style.overflow = '';
    }

    document.addEventListener('click', function (e) {
        const trigger = e.target.closest('[data-lightbox-src]');
        if (trigger) {
            e.preventDefault();
            openLb(trigger.dataset.lightboxSrc);
        }
    });
    if (lbClose) lbClose.addEventListener('click', closeLb);
    lb.addEventListener('click', function (e) {
        if (e.target === lb) closeLb();
    });
    document.addEventListener('keydown', function (e) {
        if (e.key === 'Escape' && lb.classList.contains('open')) closeLb();
    });
})();
