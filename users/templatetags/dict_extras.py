from django import template

register = template.Library()


@register.filter
def get_item(value, key):
    """Доступ к элементу словаря по ключу из шаблона: {{ d|get_item:key }}."""
    if value is None:
        return None
    if hasattr(value, "get"):
        return value.get(key)
    try:
        return value[key]
    except (KeyError, IndexError, TypeError):
        return None
