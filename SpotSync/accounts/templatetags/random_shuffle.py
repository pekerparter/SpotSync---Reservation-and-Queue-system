from django import template

register = template.Library()

@register.filter(name='random_shuffle')
def random_shuffle(queryset):
    return list(queryset.order_by('?'))
