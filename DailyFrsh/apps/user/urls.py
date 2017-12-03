from django.conf.urls import url
from apps.user.views import register, deal_register

urlpatterns = [
    url(r'^register$', register),

]