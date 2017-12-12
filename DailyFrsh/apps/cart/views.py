from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.core.urlresolvers import reverse
from utils.mixin import LoginRequiredMixin

from django.views.generic import View
from django_redis import get_redis_connection
from apps.goods.models import GoodsSKU

# Create your views here.
# 购物车: 跳转到购物车页面; 添加购物车
# 1 跳转购物车页面 页面需要用户先登陆才能跳转 /cart/
# 自动跳转登录页面， loginrequired() 这个函数做了
class CartInfoView(LoginRequiredMixin, View):
    def get(self, request):
        # 显示购物车页面
        # 获取登陆用户
        user = request.user
        # 从redis中获取用户购物车记录信息   cart_id {sku_id:num, sku_id:num, ...}
        con = get_redis_connection('default')
        cart_key = 'cart_%d' % user.id
        cart_dict = con.hgetall(cart_key)  # hgetall得到的是字典{sku_id:num, skku_id:num, ...}, 保存有商品id和数量

        skus = []  # 购物车的商品组成的列表
        total_count = 0  # 假设初始总数量为0
        total_price = 0  # 初始价格为0
        # cart_dict.items() 方法 得到的是字典的键值对组成的元组,元组组成的列表; 如果用两个变量接收, 就可以得到对应的键和值
        for sku_id, count in cart_dict.items():
            # 根据商品id获取商品信息
            sku = GoodsSKU.objects.get(id=sku_id)
            # 计算商品的小计  数量*单价
            amount = sku.price * int(count)
            # 动态给sku增加属性 count 和 amount, 分别保存购物车的商品数量和商品的小计
            sku.count = count
            sku.amount = amount

            # 追加sku
            skus.append(sku)

            # 累计叠加商品的数量和商品的价格
            total_count += int(count)
            total_price += amount

            # 上下文,模板和后台传递参数
        context = {
            'total_count': total_count,
            'total_price': total_price,
            'skus': skus
        }

        return render(request, 'cart.html', context)


# get 从服务器获取数据 //  post 涉及到数据库的修改(增加,修改, 删除)  --> 这里用post
# ajax请求操作,局部刷新, 只有购物车刷新,不是全部页面的刷新,
# ajax请求, 后台返回的是json数据
# 传递的参数: 商品的id(sku_id), 商品的数量(count)
# 匹配路径 /cart/add
class CartAddView(View):
    # 添加购物车
    def post(self, request):
        # 获取用户:
        user = request.user
        if not user.is_authenticated():
            # 用户未登录
            return JsonResponse({'res': 0, 'errmsg': '请先登陆'})
        # else:  表示用户已经登陆, 省略了, 注意缩进
        # 接收参数: 用户提交的收藏数据: sku_id, count
        sku_id= request.POST.get('sku_id')
        count = request.POST.get('count')

        # 校验接收到的参数
        if not all([sku_id, count]):
            return JsonResponse({'res': 1, 'errmsg': '数据不完整'})
        # 数据完整了,要校验商品的id  sku_id
        try:
            sku = GoodsSKU.objects.get(id=sku_id)
        except GoodsSKU.DoesNotExist:
            return JsonResponse({'res': 2, 'errmsg': '商品不存在'})
        # 校验数量:
        try:
            count = int(count)
        except Exception as e:
            return JsonResponse({'res': 3, 'errmsg': '商品数量不正确'})
        # else:
        if count <= 0:
            return JsonResponse({'res': 3, 'errmsg': '商品数量不正确'})

        # 都正确了，下面开始处理业务逻辑
        # sku_id 已经存在的商品，对商品的数量进行那个增加， 如果不存在，就新增加商品的sku_id
        con = get_redis_connection('default')
        cart_key = 'cart_%d' % user.id
        # 取出sku_id的值， hget()方法，
        cart_count = con.hget(cart_key, sku_id)
        # 如果能通过sku_id 取到cart_count, 就表示该商品已经加入购物车了
        if cart_count:
            count += int(cart_count)
        # 已经加入购物车的商品再次添加时进行该商品数量上的添加， 要判断库存
        #判断库存
        if count > sku.stock:
            return JsonResponse({'res': 4, 'errmsg': '该商品库存不足'})

        # 设置sku_id 对应的值
        con.hset(cart_key, sku_id, count)
        # 获取购物车中商品的条目数
        cart_count = con.hlen(cart_key)

        # 返回应答 json数据
        return JsonResponse({'res': 5, 'cart_count': cart_count, 'msg': '添加成功'})


# 在购物车页面进行的操作， 增加/减少，修改，删除
# 一部分不设计前后段交互的操作，可以直接前段jQ操作， 前面的勾选商品，是否全选， 后面的商品数量的增加减少， 都不涉及后端交互
# 设计前后段交互的要使用ajax请求  局部刷新    涉及后端交互的操作： 后面的删除，

class CartUpdateView(View):
    # 涉及到数据库的操作，post请求
    def post(self, request):
        user = request.user
        if not user.is_authenticated():
            return JsonResponse({'res': 0, 'errmsg': '请先登陆'})

        # 接收参数
        sku_id = request.POST.get('sku_id')
        count = request.POST.get('count')
        # 对接收到的参数进行校验： 完整性， 有效性
        if not all([sku_id, count]):
            return JsonResponse({'res': 1, 'errmsg': '数据不完整'})
        # 校验商品的id
        try:
            sku = GoodsSKU.objects.get(id=sku_id)
        except GoodsSKU.DoesNotExist:
            return JsonResponse({'res': 2, 'errmsg': '商品不存在'})
        # 校验商品的数目
        try:
            count = int(count)
        except Exception as e:
            return JsonResponse({'res': 3, 'errmsg': '商品数量不合法'})
        if count < 0:
            return JsonResponse({'res': 3, 'errmsg': '商品数量不合法'})

        # 业务处理， 更新购物车记录
        con = get_redis_connection('default')
        cart_key = 'cart_%d' % user.id

        # 判断库存
        if count > sku.stock:
            return JsonResponse({'res': 4, 'errmsg': '商品库存不足'})

        # 更新redis数据库中的商品的数量
        con.hset(cart_key, sku_id, count)

        # 计算购物车中商品的总件数
        total_count = 0
        vals = con.hvals(cart_key, sku_id)
        for val in vals:
            total_count += int(val)

        return JsonResponse({'res': 5, 'total_count': total_count, 'msg': '更新成功'})

# 删除用户购物车商品
# 需要传递的参数： 商品的id
class CartDeleteView(View):
    # 删除购物车
    def post(self, request):
        user = request.user
        if not user.is_authenticated():
            return JsonResponse({'res': 0, 'errmsg': '请先登陆'})
        sku_id = request.POST.get('sku_id')
        if not sku_id:
            return JsonResponse({'res': 1, 'errmsg': '数据不完整'})
        try:
            sku = GoodsSKU.objects.get(id=sku_id)
        except Exception as e:
            return JsonResponse({'res': 2, 'errmsg': '商品不存在'})

        # 处理业务
        con = get_redis_connection('default')
        cart_key = "cart_%d" % user.id

        # 通过商品id删除信息
        con.hdel(cart_key, sku_id)

        # 计算用户购物车中商品的总数
        total_count = 0
        vals = con.hvals(cart_key)
        for val in vals:
            total_count += int(val)

        return JsonResponse({'res': 3, 'total_count': total_count, 'msg': '删除成功'})
