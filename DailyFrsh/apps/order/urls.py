from django.conf.urls import url
from apps.order.views import OrderPlaceView, OrderCommitView, OrderPayView

urlpatterns = [
    url(r'^place$', OrderPlaceView.as_view(), name='place'),  # 提交订单， 要跳转的页面
    url(r'^commit$', OrderCommitView.as_view(), name='commit'),  # 订单创建
    url(r'', OrderPayView.as_view(), name='pay'),   # 订单支付
]