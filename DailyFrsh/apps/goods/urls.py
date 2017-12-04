from django.conf.urls import url
from apps.goods.views import index


urlpatterns = [
    url(r'^$', index, name='index')
]