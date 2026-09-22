from django import template

register = template.Library()

@register.filter(name='dict_lookup')
def dict_lookup(dictionary, key):
    if isinstance(dictionary, dict):
        return dictionary.get(key, key)
    return key
