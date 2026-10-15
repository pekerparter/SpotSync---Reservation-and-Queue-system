from django.conf import settings


def maps(request):
    return {'GOOGLE_MAPS_BROWSER_API_KEY': settings.GOOGLE_MAPS_BROWSER_API_KEY}
