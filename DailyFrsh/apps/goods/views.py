from django.shortcuts import render
from django.views.generic import View
from django_redis import get_redis_connection
from apps.goods.models import GoodsType, IndexGoodsBanner, IndexPromotionBanner, IndexTypeGoodsBanner

# Create your views here.

class IndexView(View):
    # get方式,返回主页面
    def get(self, request):
        # 从数据库读取数据
        # 要读取的数据:
        # 商品的全部分类,(左侧的6个分类);  中间滚动的banner图; 右侧的两张搞活动的图;
        # 1. 商品的全部分类
        types = GoodsType.objects.all()
        # 2. 中间滚动图片
        index_banner = IndexGoodsBanner.objects.all().order_by('index')
        # 3. 右侧两张搞活动的图片
        promotion_banner = IndexPromotionBanner.objects.all().order_by('index')
        # 首页商品分类展示信息
        for type in types:
            # 查询首页展示的文字商品信息
            title_banner = IndexTypeGoodsBanner.objects.filter(type=type, display_type=0).order_by('index')
            # 查询首页展示的图片展示信息
            image_banner = IndexTypeGoodsBanner.objects.filter(type=type, display_type=1).order_by('index')
            type.title_banner = title_banner
            type.image_banner = image_banner

        # 获取用户
        user = request.user
        # 默认的购物车的数量为0, 如果有加入收藏的商品,从数据库中读取,没有为0
        cart_count = 0
        if user.is_authenticated():
            con = get_redis_connection('default')  # 链接redis缓存
            cart_key = 'cart_%d' % user.id
            cart_count = con.hlen(cart_key)  # 取出保存的key的数量
            # 这里保存收藏夹用的是hash  一个用户对应一个hash redis缓存
            # cart_1(goods_id: num, goods_id: num)/ cart_2(goods_id:num, good_id: num)/...
            # hlen  是哈希的一种方法,得到的是 键的个数

        context = {
            'types': types,
            'index_banner': index_banner,
            'promotion_banner': promotion_banner,
            'cart_count': cart_count,
        }
        # 返回主页面
        return render(request, 'index.html', context)