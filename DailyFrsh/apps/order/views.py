from django.shortcuts import render, redirect
from django.core.urlresolvers import reverse
from django.http import JsonResponse
from django.views.generic import View
from django_redis import get_redis_connection
from apps.goods.models import GoodsSKU
from apps.user.models import Address
from apps.order.models import OrderInfo, OrderGoods
from datetime import datetime

# Create your views here.
# 提交订单页面显示
# /order/place
class OrderPlaceView(View):
    # 提交订单，要显示的页面，就是 去结算要跳转的页面
    def post(self, request):
        # 接收参数
        # 在传递参数时， 请求 会自动把要传递的name和value,以键值对的形式传递过去
        # 传递是， 一个属性，对应多个值， 要用getlist，得到一个列表
        sku_ids = request.POST.getlist('sku_ids')
        if not all(sku_ids):
            # 没有接收到数据
            return redirect(reverse('cart:show'))
        # 获取用户
        user = request.user
        con = get_redis_connection('default')
        cart_key = 'cart_%d' % user.id

        skus = []
        total_count = 0
        total_price = 0
        # 开始处理数据
        for sku_id in sku_ids:
            sku = GoodsSKU.objects.get(id=sku_id)
            # 获取用户要购买的商品的数目
            count = con.hget(cart_key, sku_id)
            # 计算商品的小计
            amount = sku.price * int(count)
            # 动态给sku增加属性count和amount
            sku.count = count
            sku.amount = amount

            # 添加商品
            skus.append(sku)
            # 累加计算商品的全部件数和金额
            total_count += int(count)
            total_price += amount

        # 云覅  //  运费的子系统，  这里写死了￥10
        transit_price = 10
        # 实付款：
        total_pay = total_price + transit_price

        # 获取用户的收货地址
        addrs = Address.objects.filter(user=user)

        # 组织上下文
        sku_ids = ','.join(sku_ids)  # sku_ids 本身是一个列表， join之后变成一个字符串，把列表里的元素以逗号分割
        # 前段需要的， 都要通过上下文进行传递
        context = {
            'sku_ids': sku_ids,
            'total_count': total_count,
            'total_price': total_price,
            'transit_price': transit_price,
            'total_pay': total_pay,
            'skus': skus,
            'addrs': addrs
        }

        return render(request, 'place_order.html', context)


# /order/commit
# ajax  post
# 前端要向后端传递的数据： 商品的id sku_id , 收货地址 address，  付款方式 pay_method
class OrderCommitView(View):
    # 创建订单
    def post(self, request):
        user = request.user
        if not user.is_authenticated():
            return JsonResponse({'res': 0, 'errmsg': '请先登陆'})

        # 接收参数：
        sku_ids = request.POST.get('sku_ids')
        pay_method = request.POST.get('pay_method')
        addr_id = request.POST.get('addr_id')

        # 校验参数
        if not all([sku_ids, pay_method, addr_id]):
            return JsonResponse({'res': 1, 'errmsg': '数据不完整'})
        # 校验地址
        try:
            address = Address.objects.get(id=addr_id)
        except Address.DoesNotExist:
            return JsonResponse({'res': 2, 'errmsg': '地址信息错误'})
        # 校验支付方式
        if pay_method not in OrderInfo.PAY_METHODS.keys():

            return ({'res': 3, 'errmsg': '支付方式无效'})

        # 业务处理，开始创建订单
        # 组织订单需要的参数：
        # 订单id   # 20171212171315+id
        order_id = datetime.now().strftime('%Y%m%d%H%M%S') + str(user.id)
        print(order_id)
        # 运费
        transit_price = 10
        # 总金额和总数量
        total_count = 0
        total_price = 0

        # 向df_order_info表中添加一条订单信息,
        order = OrderInfo.objects.create(
            order_id=order_id,
            user=user,
            addr=address,
            pay_method=pay_method,
            total_count=total_count,
            total_price=total_price,
            transit_price=transit_price
        )

        con = get_redis_connection('default')
        cart_key = 'cart_%d' % user.id
        # 用户订单中有有几种商品，就应该在商品订单表(df_order_goods) 添加几条数据
        sku_ids = sku_ids.split(',')  # 字符串分割成列表，
        for sku_id in sku_ids:
            # 根据商品的id获取商品信息
            try:
                sku = GoodsSKU.objects.get(id=sku_id)
            except GoodsSKU.DoesNotExist:
                return JsonResponse({'res': 4, 'errmsg': '商品信息错误'})

            # 获取购买的商品的数目
            count = con.hget(cart_key, sku_id)

            # 向df_order_goods商品表中添加一条信息
            OrderGoods.objects.create(
                order=order,
                sku=sku,
                count=count,
                price=sku.price
            )

            # 减少商品的库存， 增加商品的销量
            sku.stock -= int(count)
            sku.sales += int(count)
            sku.save()

            # 累加计算商品的总数量和总金额
            total_count += int(count)
            total_price += sku.price * int(count)

        # 更新order的price和count
        order.total_price = total_price
        order.total_count = total_count
        order.save()

        # 购买成功，删除购物车记录
        con.hdel(cart_key, *sku_ids)  # *sku_ids  可以删除多个

        # 返回应答
        return JsonResponse({'res': 5, 'msg': '订单创建成功'})