/**
 * LaTeX-превью под полями ответа.
 *
 * Использование в шаблоне:
 *   <input type="text" class="js-latex-input" id="answerInput">
 *   <div class="js-latex-preview" data-for="answerInput"></div>
 *   <script src="{% static 'js/latex_preview.js' %}"></script>
 *
 * Или: вызвать LatexPreview.attachAll() после динамической вставки полей.
 */
(function () {
  'use strict';

  function escapeHtml(s) {
    return String(s).replace(/[&<>"']/g, c => ({
      '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
    }[c]));
  }

  // Превью показываем ТОЛЬКО если ответ содержит спец-обозначения:
  // слэш (дробь a/b), бэкслэш (LaTeX \frac, \sqrt), степень ^ или знак корня.
  // Для обычных чисел (5, 0,25, -7) превью не нужно.
  const NEEDS_PREVIEW = /[\\/^√]/;

  function renderPreview(input, preview) {
    const raw = (input.value || '').trim();
    if (!raw || !NEEDS_PREVIEW.test(raw)) {
      preview.style.display = 'none';
      preview.innerHTML = '';
      return;
    }
    // Заменяем запятые в десятичных на точки для рендера (для красоты можно и оставить запятые,
    // но MathJax иначе их группирует — оставим запятую, т. к. это российский формат).
    // Оборачиваем в \( ... \) — режим inline-LaTeX.
    preview.style.display = '';
    preview.innerHTML =
      '<span class="latex-preview-label">Превью:</span> ' +
      '<span class="latex-preview-body">\\(' + raw + '\\)</span>';
    if (window.MathJax && window.MathJax.typesetPromise) {
      window.MathJax.typesetPromise([preview]).catch(() => { /* пусть тихо игнорит */ });
    }
  }

  function attach(input) {
    if (input.__latexPreviewAttached) return;
    input.__latexPreviewAttached = true;

    // Находим/создаём div превью
    let preview = document.querySelector(
      '.js-latex-preview[data-for="' + input.id + '"]'
    );
    if (!preview) {
      preview = document.createElement('div');
      preview.className = 'js-latex-preview';
      preview.dataset.for = input.id || '';
      input.parentNode.insertBefore(preview, input.nextSibling);
    }

    // Стили превью (можно переопределить из CSS на странице)
    preview.style.minHeight = '1.5em';
    preview.style.marginTop = '.35rem';
    preview.style.padding = '.25rem .5rem';
    preview.style.fontSize = '1.05rem';
    preview.style.color = '#1f2937';
    preview.style.background = '#f8fafc';
    preview.style.border = '1px dashed #cbd5e1';
    preview.style.borderRadius = '.3rem';
    preview.style.display = 'none';

    input.addEventListener('input', () => renderPreview(input, preview));
    // Сразу отрендерить если уже что-то введено
    if (input.value) renderPreview(input, preview);
  }

  function attachAll() {
    document.querySelectorAll('.js-latex-input').forEach(attach);
  }

  window.LatexPreview = { attach, attachAll };

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', attachAll);
  } else {
    attachAll();
  }
})();
