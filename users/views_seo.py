"""robots.txt и sitemap.xml — чтобы сайт находился поиском.

Зачем это здесь. Ученик, потерявший ссылку, набрал название в поисковике — и не
нашёл ничего: сайта нет в выдаче. Проверено запросом с фамилией и доменом,
выпадают чужие репетиторские каталоги. Запретов индексации при этом не было:
robots.txt просто отсутствовал (404), а без него часть роботов ведёт себя
осторожнее и обходит сайт реже.

Отдаём два файла:

  robots.txt  — «заходите, вот карта; личные разделы не трогайте»;
  sitemap.xml — список публичных страниц.

Личные разделы закрываем от обхода не ради безопасности (они и так под входом,
см. @login_required), а чтобы роботы не тратили обходы на страницы, с которых
всё равно получат перенаправление на вход.

Готовый механизм django.contrib.sitemaps не берём: он требует правки
INSTALLED_APPS, а settings.py сейчас занят чужой незавершённой работой по
лаборатории. Своих страниц немного, поэтому проще собрать список руками.
"""

from django.http import HttpResponse
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.cache import cache_control
from django.views.decorators.http import require_GET

# Публичные страницы: открываются без входа и имеют смысл в поиске.
# priority — относительная важность внутри сайта, changefreq — подсказка
# роботу, как часто заглядывать. Обе величины совещательные.
PUBLIC_PAGES = [
    ('home', '1.0', 'weekly'),
    ('courses_list', '0.8', 'weekly'),
    ('materials_list', '0.8', 'weekly'),
]

# Разделы за входом: роботу там делать нечего — он получит перенаправление.
PRIVATE_PREFIXES = ['/admin/', '/api/', '/board/', '/games/', '/media/', '/login/', '/logout/']


def _origin(request):
    """Адрес сайта так, как его видит посетитель (с учётом nginx)."""
    return '%s://%s' % ('https' if request.is_secure() else 'http', request.get_host())


@require_GET
@cache_control(max_age=86400)
def robots_txt(request):
    строки = ['User-agent: *']
    строки += ['Disallow: ' + p for p in PRIVATE_PREFIXES]
    строки += ['', 'Sitemap: %s/sitemap.xml' % _origin(request), '']
    return HttpResponse('\n'.join(строки), content_type='text/plain; charset=utf-8')


@require_GET
@cache_control(max_age=86400)
def sitemap_xml(request):
    сегодня = timezone.localdate().isoformat()
    корень = _origin(request)
    куски = ['<?xml version="1.0" encoding="UTF-8"?>',
             '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for имя, приоритет, частота in PUBLIC_PAGES:
        куски.append(
            '<url><loc>%s%s</loc><lastmod>%s</lastmod>'
            '<changefreq>%s</changefreq><priority>%s</priority></url>'
            % (корень, reverse(имя), сегодня, частота, приоритет)
        )
    куски.append('</urlset>')
    return HttpResponse('\n'.join(куски), content_type='application/xml; charset=utf-8')
