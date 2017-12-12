from django.shortcuts import render, redirect, HttpResponse
from django.views.generic import View
from django_redis import get_redis_connection   # 链接redis数据库
from apps.goods.models import GoodsType, IndexGoodsBanner, IndexPromotionBanner, IndexTypeGoodsBanner, GoodsSKU
from apps.order.models import OrderGoods
from django.core.urlresolvers import reverse

from django.core.cache import cache   # 设置和清楚缓存

from django.core.paginator import Paginator   # 分页使用



# Create your views here.

class IndexView(View):
    # get方式,返回主页面
    def get(self, request):
        # 尝试从缓存读取数据
        context = cache.get('index_page_data')
        if context is None:
            # 设置缓存
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

            context = {
                'types': types,
                'index_banner': index_banner,
                'promotion_banner': promotion_banner
            }

            # 设置缓存,三个参数: 缓存的key(要通过这个key取出缓存), 上下文, 缓存有效期
            cache.set('index_page_data', context, 3600)
        # else:   这里省略了, 表示有缓存, 注意缩进

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
        # 更新上下文, 购物车条目数
        context.update(cart_count=cart_count)

        # 返回主页面
        return render(request, 'index.html', context)

# 前端向后端传递参数的方式:
# 1. url 参数传递 ,正则匹配,匹配到要请求的路径
# 2. get
# 3. post

class DetailView(View):
    # 显示商品详情
    def get(self, request, sku_id):
        # 获取商品详情
        try:
            sku = GoodsSKU.objects.get(id=sku_id)
        except GoodsSKU.DoesNotExist:
            # 商品不存在,跳转到首页
            return redirect(reverse('goods:index'))
        # else: 这里省略了
        # 商品存在
        # 1. 获取和商品同类型的两种新品
        new_skus = GoodsSKU.objects.filter(type=sku.type).order_by('-create_time')[0:2]
        # 2. 获取商品的评论信息
        order_skus = OrderGoods.objects.filter(sku=sku).order_by('-create_time')
        # 3. 获取和商品同一个spu的其他规格商品(比如: 盒装草莓和500g草莓,商品一样,规格不一样)
        same_spu_skus = GoodsSKU.objects.filter(goods=sku.goods).exclude(id=sku.id)  # exclude()不包括自己
        # 4. 获取购物车中的条目数,就是显示购物车内商品数量
        # <1. 获取用户
        user = request.user
        cart_count = 0
        if user.is_authenticated():
            con = get_redis_connection('default')
            cart_key = 'cart_%d' % user.id
            cart_count = con.hlen(cart_key)  # 通过key取到key的长度

            # 浏览记录是用户登陆才有的,用户不登陆是没有记录的,要写在if条件缩进里面
            # 当用户访问详情页面的时候,应该添加客户浏览的历史记录, 用redis列表存储数据
            con = get_redis_connection('default')
            history_key = 'history_%d' % user.id
            # 在客户访问浏览记录里已经有的商品时,应该先移除记录里的数据,然后在从最前面(左侧插入)插入该条商品的id
            # 尝试移除数据, 如果列表没有该数据,不会报错
            con.lrem(history_key, 0, sku_id)
            # 添加新数据
            con.lpush(history_key, sku_id)
            # 保留客户 最新浏览的5个数据
            con.ltrim(history_key, 0, 4)

        # 组织上下文模板
        context = {
            'sku': sku,
            'new_skus': new_skus,
            'order_skus': order_skus,
            'same_spu_skus': same_spu_skus,
            'cart_count': cart_count
        }

        return render(request, 'detail.html', context)


'''
列表页: listview
前端向后台传递:
1. list/种类id/页码/排序方式
2. list/种类id?页码=x&排序方式=x
3. list/种类id/页码?sort=x   这里用的是这种
list/1/1?sort=default  列表页商品种类的id是1, 第一页,按照默认方式排序
'''

# /list/type_id/page?sort=
class ListView(View):

    def get(self, request, type_id, page):
        # 尝试通过请求的type_id 查询数据库,显示分类信息
        try:
            type = GoodsType.objects.get(id=type_id)
        except GoodsType.DoesNotExist:
            # 商品种类不存在
            return redirect(reverse('goods:index'))
        # else:  表示商品种类存在
        # 获取商品的排列方式
        sort = request.GET.get('sort', 'default')  # 如果有排列方式就按照传递的排列方式排列,如果没有就按照默认的排列
        # sort = default(默认, 这里使用id排列);
        # sort = price (价格排列,升序,从低到高)
        # sort = hot (人气, 按照销量, 降序,从高到低)
        if sort == 'price':
            skus = GoodsSKU.objects.filter(type=type).order_by('price')
        elif sort == 'hot':
            skus = GoodsSKU.objects.filter(type=type).order_by('-sales')
        else:
            sort = 'default'
            skus = GoodsSKU.objects.filter(type=type).order_by('-id')

        # 商品过多, 列表页需要分页
        paginator = Paginator(skus, 1)
        # 处理接收到的请求的页码: page
        page = int(page)
        # num_pages  pagintor对象的属性,返回页面的总页数
        if page > paginator.num_pages or page <= 0:
            page = 1  # 如果请求的page数值正确,就默认是第一页

        # 获取page页的实例对象, 就是获取请求的page页的信息对象
        # page()  paginator对象的方法   返回一个Page对象,通过页码,返回页面的对象
        skus_page = paginator.page(page)

        # 获取两个该类的新品的信息
        new_skus = GoodsSKU.objects.filter(type=type).order_by('-create_time')[0:2]

        # 购物车获取条目数
        # 获取用户
        cart_count = 0
        user = request.user
        if user.is_authenticated():
            con = get_redis_connection('default')
            cart_key = 'cart_%d' % user.id
            cart_count = con.hlen(cart_key)
        # 上下文,传递数据,前段继续构造数据
        context = {
            'type': type,
            'skus_page': skus_page,
            'new_skus': new_skus,
            'cart_count': cart_count,
            'sort': sort
        }
        # return HttpResponse('1')
        return render(request, 'list.html', context)