# 处理注册业务使用的模块
from django.shortcuts import render, HttpResponse,redirect
from django.core.urlresolvers import reverse
from apps.user.models import User
from django.views.generic import View
# 处理邮箱激活使用的模块
from itsdangerous import TimedJSONWebSignatureSerializer as Serializer
from django.conf import settings
from itsdangerous import SignatureExpired
from celery_tasks.tasks import send_register_active_email
from django.core.mail import send_mail
# 处理登陆使用的模块(退出模块)
from django.contrib.auth import authenticate, login, logout
# 用户中心页的模块
from utils.mixin import LoginRequiredMixin
from apps.user.models import Address
from apps.goods.models import GoodsSKU
from django_redis import get_redis_connection

# Create your views here.
def register(request):
    if request.method == 'GET':
        # 如果请求方式是GET, 是请求注册页面
        return render(request, 'register.html')
    if request.method == 'POST':
        # 如果请求方式是POST, 是请求注册账户
        # 处理注册,得到用户输入, 判断是否为空,
        # 所有内容/属性 一起判断是否胃口那个,可以用all()方法
        username = request.POST.get('user_name')
        password = request.POST.get('pwd')
        email = request.POST.get('email')
        allow = request.POST.get('allow')  # 用户同意协议,同意是on, 不同意就是None

        if not all([username, password, email]):
            return render(request, 'register.html', {'errmsg': '注册信息不完整'})
        if allow != 'on':  # 用户同意协议; 不同意协议,返回注册页面
            return render(request, 'register.html')
        try:
            # 得到用户输入的用户名,在数据库判断,判断用户名是否存在
            user = User.objects.get(username=username)
        except User.DoesNotExist:  # 如果用户名不存在
            user = None  # user=None
            user = User.objects.create_user(username, email, password)
            # 注释: create_user()方法里面的参数,按照django指定的顺序写,不能错顺序写,会导致数据库内容错乱
            user.is_active = 0
            user.save()
            return render(request, 'login.html')
            # return redirect(reverse('goods:index'))
        # else:  理解: try--> except--> else  这里else省略了
        else:  # 用户名存在
            return render(request, 'register.html', {'error': '用户名已存在'})


class RegisterView(View):
# 类视图: django封装好的, 如果请求方式是GET 就会执行get函数, 如果是POST,执行post函数, 不再需要if判断
# 在进行url匹配时, 正则正常写, 后面函数的调用,用类视图的as_view()方法  --> 匹配正则, 称为 配置路由
    def get(self, request):
        return render(request, 'register.html')

    def post(self, request):
        username = request.POST.get('user_name')
        password = request.POST.get('pwd')
        cpassword = request.POST.get('cpwd')
        email = request.POST.get('email')
        allow = request.POST.get('allow')  # 用户同意协议,同意是on, 不同意就是None

        if not all([username, password, email]):
            return render(request, 'register.html', {'errmsg': '注册信息不完整'})
        if allow != 'on':  # 用户同意协议; 不同意协议,返回注册页面
            return render(request, 'register.html')
        if cpassword != password:
            return render(request, 'register.html', {'errmsg': '两次输入密码不一致'})

        try:
            # 得到用户输入的用户名,在数据库判断,判断用户名是否存在
            user = User.objects.get(username=username)
        except User.DoesNotExist:  # 如果用户名不存在
            user = None  # user=None
            user = User.objects.create_user(username, email, password)
            # 注释: create_user()方法里面的参数,按照django指定的顺序写,不能错顺序写,会导致数据库内容错乱
            user.is_active = 0
            user.save()

            # 用户信息加密, 生成token,发送邮箱激活
            serializer = Serializer(settings.SECRET_KEY, 7200)
            info = {'confirm': user.id}  # 用户的id用字典保存,
            token = serializer.dumps(info)  # dumps() 对信息进行加密, 默认生成的是byte字节流
            token = token.decode()  # 这是把加密的信息解码成字符串格式的 str
            # 想客户端邮箱发送的信息的格式是: user/active/user_id
            # 组织邮件信息
            # 发送信息,找人代发,自己继续响应客户,   异步 使用celery
            # subject = '天天生鲜激活信息'
            # message = ''
            # sender = settings.EMAIL_FROM
            # receiver = [email]
            # html_message = '<h1>%s,欢迎您成为天天生鲜注册会员</h1>请点击以下链接激活您的账号<br/><a href="http://127.0.0.1:8000/user/active/%s">http://127.0.0.1:8000/user/active/%s</a>' % (
            # username, token, token)
            #
            # send_mail(subject, message, sender, receiver, html_message=html_message)
            send_register_active_email.delay(email, username, token)  # delay() 是task装饰器的功能
            # 下面还有详情操作,转celery_tasks.tasks.py
            # 相应, 跳转到登陆页面
            # return render(request, 'login.html')
            return redirect(reverse('goods:index'))

        # else:  理解: try--> except--> else
        else:  # 用户名存在
            return render(request, 'register.html', {'error': '用户名已存在'})


class ActiveView(View):
    # 用户邮箱激活
    def get(self, request, token):
        # 解密token, 获取要解密的客户的信息
        # 解密: 这里的token参数,是从url路径中解析得到的, 表示的 要取到请求的路径
        serializer = Serializer(settings.SECRET_KEY, 7200)
        # Serializer()两个参数,第一个:   第二个是时间,以秒为单位, 表示激活过期时间
        try:
            # 尝试捕获异常, 如果没有异常就表示没有过期,
            info = serializer.loads(token)  # loads() 解密方法,
            user_id = info['confirm']
            # 因为给用户发过去的是 user/active/user_id
            # 最后一个是用户的id,字典形式{'confirm': id}, 通过字典的key取得用户的id
            # 取到id, 激活该用户,is_active 状态改为 1
            user = User.objects.get(id=user_id)
            user.is_active = 1
            user.save()

            return HttpResponse('用户激活成功')
        except SignatureExpired:
            # 激活过期了,这里限定的是7200s = 2h  2个小时
            return HttpResponse('激活链接过期')

# 在用户登陆时, 使用redis作为django和session的缓存, 配置缓存 settis.py
class LoginView(View):
    # 模型类,django封装好的,get post两种请求方式,自动调用各自的函数
    # get 方式,请求登陆页面
    def get(self, request):
        # 判断上次登陆有没有设置记住用户名/密码, 尝试从cookie中读取username
        if 'username' in request.COOKIES:
            username = request.COOKIES['username']
            checked = 'checked'
        else:
            username = ''
            checked = ''

        return render(request, 'login.html', {'username': username, 'checked': checked})

    # post 请求,提交登陆数据
    # post 请求, 需要确认的事情:
    # 1.用户输入(用户名/密码)是否为空;
    # 2.登陆校验,用户名,密码是否正确(authenticate()方法进行校验)
    # 3.用户状态是否激活(is_active=1)
    # 4.判断是否记住用户名和密码(设置cookie,  通过Httpresponse对象, set_cookie()方法)
    #  删cookie信息  Httpresponse对象,调用delete_cookie()方法
    def post(self,request):
        username = request.POST.get('username')
        password = request.POST.get('pwd')
        remember = request.POST.get('remember')

        if not all([username, password]):
            return HttpResponse('用户名和密码输入不能为空')
        # if --> else  这里else省略了
        # 输入不为空, 开始处理业务
        # 登陆校验
        user = authenticate(username=username, password=password)
        if user is not None:
            # 有这个用户,登陆用户名和密码都正确
            # 验证了用户名密码正确,开始处理登陆页面的其他功能
            # 用户是否激活: 激活返回登陆成功的页面,未激活返回登陆失败,要求先激活
            if user.is_active:  # 用户已经激活了
                login(request, user)  # 保存用户的登陆状态
                # 然后判断是否点击了 记住用户名
                # 需要调用Httpresponse对象,来操作set_cookie()方法
                next_url = request.GET.get('next', reverse('goods:index'))
                # print(next_url)
                response = redirect(next_url)
                if remember == 'on':  # 记住用户名
                    response.set_cookie('username', username, max_age=7*24*3600)
                    # 参数:键值对: key, value,   max_age 是用户名的最长时间,以秒为单位, 这里是一个星期
                else:
                    response.delete_cookie('username')  # 删除cookie信息, 只需要传入key

                return response
            else:
                return HttpResponse('用户未激活,请先激活')
        else:
            return HttpResponse('用户名或密码不正确')


class LogoutView(View):
    # 退出
    def get(self, request):
        logout(request)  # 退出,清除保存的session数据, 退出登陆状态
        return redirect(reverse('goods:index'))  # 跳转到首页


# /user/  直接链接的就是用户中心
class UserinfoView(LoginRequiredMixin, View):
    '''
    要进行的处理:
    前提: 就是需要用户先登陆, 判断用户是否登陆
    1. 要显示用户的信息: 用户名,联系电话,用户地址
    2. 显示用户的浏览历史记录
    '''
    def get(self, request):
        # 获取登陆用户
        # django框架会给request对象增加一个属性user,通过属性,可以得到,该用户对象
        user = request.user
        # 获取用户的默认地址:
        address = Address.objects.get_default_address(user)
        #            类  .  对象   .     方法
        # 这里Address是模型类, objects是AddressManager()类的一个对象,对象调用方法
        # 得到的address 是一个 默认地址的用户对象,   是一个对象


        # 获取用的历史浏览记录:
        # 链接redis数据库,在settings里面配置, 用django-redis包里面的get_redis_connection()方法连接
        conn = get_redis_connection('default')
        # 浏览历史,是在用户点击商品进行查看详情的时候,添加的记录, 所以添加商品记录是在商品模型类
        # 而读取记录, 是在用户查看个人中心时, 进行读取的
        # 这里用列表保存浏览记录, 列表保存的是  浏览的商品的id
        history_key = 'history_%d' % user.id
        # 获取用户最新浏览的五个数据  lrange(key, start, end)
        sku_ids = conn.lrange(history_key, 0, 4)
        skus = []  # 建立空列表,接收通过id查询到的商品对象
        for sku_id in sku_ids:
            # 遍历,通过id查找 商品对象
            sku = GoodsSKU.objects.get(id=sku_id)
            skus.append(sku)

        # 组织上下文
        context = {
            'page': 'user',
            'address': address,
            'skus': skus
        }

        return render(request, 'user_center_info.html', context)


class UserorderView(LoginRequiredMixin, View):
    def get(self,request):
        # get方式请求, 显示订单页面
        return render(request, 'user_center_order.html', {'page': 'order'})


class UseraddressView(LoginRequiredMixin, View):
    def get(self,request):
        user = request.user
        address = Address.objects.get_default_address(user)  # 读取默认地址

        return render(request, 'user_center_site.html', {'page': 'address', 'address': address})

    def post(self,request):

        receiver = request.POST.get('receiver')
        addr = request.POST.get('addr')
        zip_code = request.POST.get('zip_code')
        phone = request.POST.get('phone')

        if not all([receiver, addr, phone]):
            return render(request, 'user_center_site.html', {'error': '提交内容不能为空'})

        user = request.user
        address = Address.objects.get_default_address(user)  # 读取默认地址
        # 设置默认地址, 如果有默认地址了, 新加入的地址,就不设置默认地址,is_default为False
        if address:
            is_default = False
        else:
            is_default = True

        Address.objects.create(
            user = user,
            receiver = receiver,
            addr = addr,
            zip_code = zip_code,
            phone = phone,
            is_default = is_default
        )
        return redirect(reverse('user:address'))