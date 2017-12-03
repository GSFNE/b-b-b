from django.conf.urls import url
from apps.user.views import register, RegisterView

urlpatterns = [
    # url(r'^register$', register),
    url(r'^register$', RegisterView.as_view(), name='register'),  # 类视图的方法, 反向解析
]