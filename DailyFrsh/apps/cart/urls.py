from django.conf.urls import url
from apps.cart.views import CartInfoView, CartAddView, CartUpdateView, CartDeleteView

urlpatterns = [
    url(r'^$', CartInfoView.as_view(), name='show'),  # 购物车首页
    url(r'^add$', CartAddView.as_view(), name='add'),  # 添加购物车
    url(r'^update$', CartUpdateView.as_view(), name='update'),  # 购物车页面的操作， 数量增加/减少，删除等
    url(r'^delete$', CartDeleteView.as_view(), name='delete'),  # 删除购物车内商品





]