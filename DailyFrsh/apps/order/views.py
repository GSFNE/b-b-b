from django.shortcuts import render, redirect
from django.core.urlresolvers import reverse
from django.http import JsonResponse
from django.views.generic import View
from django_redis import get_redis_connection
from apps.goods.models import GoodsSKU
from apps.user.models import Address
from apps.order.models import OrderInfo, OrderGoods
from datetime import datetime
from django.db import transaction   # 这个是应用到mysql的事务， 一组mysql语句，要么成功，要么失败 回滚
from alipay import AliPay   # 订单支付， 跳转支付宝页面，需要链接支付宝接口
import os
from django.conf import settings

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


# 订单的并发处理： 好多用户同时购买同一个商品时， 后台出现的错误，数据库出现的数据不正确
# 处理并发问题： 乐观锁和悲观锁
# 悲观锁： object.select_for_update()
# /order/commit
# ajax  post
# 前端要向后端传递的数据： 商品的id sku_id , 收货地址 address，  付款方式 pay_method
class OrderCommitView1(View):
    # 这个是悲观锁的写法， 在冲突比较多的时候使用
    # 创建订单
    # mysql的事务： 要么全部执行，要么全不执行； begin 开启事务， rollback(回滚)或者commit(提交) 结束事务
    # rollback  commit  rollbackto回滚到某个保存的节点 sid = transaction.savepoint()
    @transaction.atomic
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

        # 保存节点，前面的代码都只是判断， 并没有sql语句的操作，这里保存节点，后面方便回滚
        sid = transaction.savepoint()

        try:
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
                # select_for_update(), 是objects的方法，悲观锁， 在多个用户同时购买同一件商品时使用
                # 针对用户比较多，冲突比较多的时候使用， 一个人拿到锁，下一个人要等待拿到锁的人释放了才能拿
                try:
                    sku = GoodsSKU.objects.select_for_update().get(id=sku_id)
                except GoodsSKU.DoesNotExist:
                    return JsonResponse({'res': 4, 'errmsg': '商品信息错误'})

                # 获取购买的商品的数目
                count = con.hget(cart_key, sku_id)

                # 判断商品库存
                if int(count) > sku.stock:
                    transaction.rollback(sid)
                    return JsonResponse({'res': 6, 'errmsg': '商品库存不足'})

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
        except Exception as e:
            transaction.rollback(sid)
            return JsonResponse({'res': 7, 'errmsg': '下单失败'})

        # 释放之前保存的节点
        transaction.savepoint_commit(sid)

        # 购买成功，删除购物车记录
        con.hdel(cart_key, *sku_ids)  # *sku_ids  可以删除多个

        # 返回应答
        return JsonResponse({'res': 5, 'msg': '订单创建成功'})


class OrderCommitView(View):
    # 这个是 乐观锁的写法， 是在冲突比较少的时候使用
    @transaction.atomic
    def post(self, request):
        user = request.user
        if not user.is_authenticated():
            return JsonResponse({'res': 0, 'errmsg': '请先登陆'})

        # 接收参数
        addr_id = request.POST.get('addr_id')
        pay_method = request.POST.get('pay_method')
        sku_ids = request.POST.get('sku_ids')

        # 校验参数
        if not all([addr_id, pay_method, sku_ids]):
            return JsonResponse({'res': 1, 'errmsg': '数据不完整'})

        # 校验地址
        try:
            addr = Address.objects.get(id=addr_id)
        except Address.DoesNotExist:
            # 地址不存在
            return JsonResponse({'res': 2, 'errmsg': '地址信息错误'})

        # 校验支付方式
        if pay_method not in OrderInfo.PAY_METHODS.keys():
            # 支付方式无效
            return JsonResponse({'res': 3, 'errmsg': '支付方式无效'})

        # 业务处理：订单创建
        # 组织参数
        # 订单id(order_id): 20171211123130+用户的id
        order_id = datetime.now().strftime('%Y%m%d%H%M%S') + str(user.id)

        # 运费
        transit_price = 10

        # 总数目和总金额
        total_count = 0
        total_price = 0

        # 设置保存点
        sid = transaction.savepoint()

        try:
            # todo: 向df_order_info表中添加一条记录
            order = OrderInfo.objects.create(order_id=order_id,
                                             user=user,
                                             addr=addr,
                                             pay_method=pay_method,
                                             total_count=total_count,
                                             total_price=total_price,
                                             transit_price=transit_price)

            conn = get_redis_connection('default')
            cart_key = 'cart_%d' % user.id
            # todo: 用户的订单中包含几个商品，就应该向df_order_goods中添加几条记录
            sku_ids = sku_ids.split(',')  # [1,4]
            for sku_id in sku_ids:
                for i in range(3):
                    # 根据sku_id获取商品的信息
                    try:
                        # select * from df_goods_sku where id=sku_id;
                        sku = GoodsSKU.objects.get(id=sku_id)
                    except GoodsSKU.DoesNotExist:
                        transaction.savepoint_rollback(sid)
                        return JsonResponse({'res': 4, 'errmsg': '商品信息错误'})

                    # 获取用户要购买的商品的数目
                    count = conn.hget(cart_key, sku_id)

                    # todo: 判断商品库存
                    if int(count) > sku.stock:
                        transaction.savepoint_rollback(sid)
                        return JsonResponse({'res': 6, 'errmsg': '商品库存不足'})

                    # todo: 减少商品的库存，增加销量
                    origin_stock = sku.stock
                    new_stock = origin_stock - int(count)
                    new_sales = sku.sales + int(count)

                    # print('user:%d i:%d stock:%d'%(user.id, i, origin_stock))
                    # import time
                    # time.sleep(10)
                    # 返回更新的行数
                    # update df_goods_sku set stock=new_stock, sales=new_sales
                    # where id=sku_id and stock=origin_stock
                    res = GoodsSKU.objects.filter(id=sku_id, stock=origin_stock).update(stock=new_stock,
                                                                                        sales=new_sales)
                    if res == 0:
                        # 更新失败
                        if i == 2:
                            # 已经尝试了3次，下单失败
                            transaction.savepoint_rollback(sid)
                            return JsonResponse({'res': 7, 'errmsg': '下单失败2'})
                        continue

                    # todo: 向df_order_goods中添加一条记录
                    OrderGoods.objects.create(order=order,
                                              sku=sku,
                                              count=count,
                                              price=sku.price)

                    # todo: 累加计算商品的总件数和总金额
                    total_count += int(count)
                    total_price += sku.price * int(count)

                    # 更新成功之后跳出循环
                    break

            # todo: 更新order的total_count和total_price
            order.total_count = total_count
            order.total_price = total_price
            order.save()
        except Exception as e:
            transaction.savepoint_rollback(sid)
            return JsonResponse({'res': 7, 'errmsg': '下单失败'})

        # 释放保存点
        transaction.savepoint_commit(sid)

        # todo: 删除购物车对应记录信息
        conn.hdel(cart_key, *sku_ids)  # 1,4

        # 返回应答
        return JsonResponse({'res': 5, 'message': '订单创建成功'})


# 订单支付页面
# /order/pay   采用ajax post请求  传递的参数： 订单id  order_id
class OrderPayView(View):
    def post(self, request):
        # 登陆用户
        user = request.user
        if not user.is_authenticated():
            return JsonResponse({'res': 0, 'errmsg': '请先登陆'})
        # 接收参数
        order_id = request.POST.get('order_id')
        if not order_id:
            return JsonResponse({'res': 1, 'errmsg': '订单编号错误'})
        try:
            order = OrderInfo.objects.get(
                order_id=order_id,
                user=user,
                pay_method=3,
                order_status=1,
            )
        except Exception as e:
            return JsonResponse({'res': 2, 'errmsg': '订单不存在'})

        # 开始处理订单： 调用支付宝的接口，跳转支付宝页面， SDK
        alipay = AliPay(
            appid='2016082600314756',   # 应用id， 沙箱环境，固定的appid，实际开发，要自己申请应用， 有一个唯一的id
            app_notify_url=None,   # 默认的回调函数
            app_private_key_path=os.path.join(settings.BASE_DIR, 'apps/order/app_private_key.pem'),
            alipay_public_key_path=os.path.join(settings.BASE_DIR, 'apps/order/alipay_public_key.pem'),
            sign_type='RSA2',   # 签名， 使用RSA或者RSA2
            debug=True  # 默认是False, true是在测试阶段
        )

        total_amount = order.total_price + order.transit_price
        # 调用api接口， 跳转到支付宝的链接页面
        order_string = alipay.api_alipay_trade_page_pay(
            out_trade_no=order_id,  # 订单编号
            total_amount=str(total_amount),  # 订单总金额
            subject='dailyfresh_%s' % order_id,  # 订单标题
            return_url=None,  #
            notify_url=None   # 执行的回调函数， 可以不写，
        )

        pay_url = "https://openapi.alipaydev.com/gateway.do?" + order_string

        return JsonResponse({'res': 3, 'pay_url': pay_url})
