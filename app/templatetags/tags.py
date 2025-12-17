from django import template
import os

register = template.Library()

@register.filter
def kv_bind(key,value):
    return key[value]


@register.filter
def split_string(value):
    value = str(value)
    return value.split('|')


@register.filter
def split_path(value):
    """
    Splits the given path into segments for breadcrumb navigation.
    Returns a list of dictionaries with 'name' and 'path' keys.
    """
    if not value:
        return []

    segments = value.strip("/").split("/")
    path_accum = ""
    breadcrumb = []

    for segment in segments:
        path_accum = f"{path_accum}/{segment}" if path_accum else segment
        breadcrumb.append({"name": segment, "path": path_accum})

    return breadcrumb

@register.filter
def nan(value, keywar):
    if value == 'nan' or value == None or value == 'None':
        value = keywar
    return value

@register.filter
def roundval(value):
    if value:
        value = round(value,2)
    return value

@register.filter
def dot_access(dictionary, key):
    try:
        value = dictionary[key]
        return value
    except KeyError:
        return None
    
@register.filter
def percentage(value, arg):
    try:
        result = (float(value) / float(arg)) * 100
        return round(result, 2)  # Round to 2 decimal places if needed
    except (ValueError, ZeroDivisionError):
        return 0

@register.filter(name='divide')
def divide(bcc, tcc):
    try:
        calc = float(bcc) / float(tcc)
        return calc
    except Exception as er:
        print(er,"++++++++++")
        return 0
    
@register.filter(name='sumval')
def sumval(val1,val2):
    try:
        total = val1 + val2
    except Exception as er:
        print(er,"++++++++++")
        total = 0
    return total

@register.filter(name='mulval')
def mulval(val1,val2):
    try:
        total = round(val1 * val2, 2)
    except Exception as er:
        print(er,"++++++++++")
        total = 0
    return total

@register.filter(name='meanval')
def meanval(val1, val2):
    try:
        if val1 == 0 and val2 == 0:
            return 0  # return 0 when both values are zero
        total = (val1 + val2) / 2
        return total
    except Exception as er:
        print(er,"++++++++++")
        return 0
