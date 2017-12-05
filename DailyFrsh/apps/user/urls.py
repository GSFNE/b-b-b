from django.conf.urls import url
from apps.user.views import register, RegisterView, ActiveView, LoginView, LogoutView

urlpatterns = [
    # url(r'^register$', register),
    url(r'^register$', RegisterView.as_view(), name='register'),  # 类视图的方法, 反向解析
    url(r'^active/(?P<token>.*)$', ActiveView.as_view(), name='active'),  # 激活 用户信息
    url(r'^login$', LoginView.as_view(), name='login'),  # 用户登陆

    url(r'^logout$', LogoutView.as_view(), name='logout'), # 用户退出
]