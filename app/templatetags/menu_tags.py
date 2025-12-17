from django import template
from ..models import UserMenuPermission 

register = template.Library()

@register.simple_tag
def get_allowed_menus(user):
    if not user.is_authenticated:
        return []
    
    if user.is_superuser:
        return [] 
        
    try:
        menus = UserMenuPermission.objects.filter(user=user).values_list('menu__name', flat=True)
        return list(menus)
    except Exception:
        return []