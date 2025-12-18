from django import template

register = template.Library()

@register.filter
def startswith(value, prefix):
    if value is None:
        return False
    return str(value).startswith(prefix)