from django.shortcuts import render, HttpResponse,redirect
from django.core.urlresolvers import reverse
from apps.user.models import User
from django.views.generic import View

from itsdangerous import TimedJSONWebSignatureSerializer as Serializer
from django.conf import settings
from itsdangerous import SignatureExpired
from celery_tasks.tasks import send_active_email
from django.core.mail import send_mail

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

            # 用户信息加密, 生成token,发送邮箱激活
            serializer = Serializer(settings.SECRET_KEY, 7200)
            info = {'confirm': user.id}  # 用户的id用字典保存,
            token = serializer.dumps(info)  # dumps() 对信息进行加密, 默认生成的是byte字节流
            token = token.decode()  # 这是把加密的信息解码成字符串格式的 str
            # 想客户端邮箱发送的信息的格式是: user/active/user_id
            # 组织邮件信息
            # 发送信息,找人代发,自己继续响应客户,   异步 使用celery
            subject = '天天生鲜激活信息'
            message = ''
            sender = settings.EMAIL_FROM
            receiver = [email]
            html_message = '<h1>%s,欢迎您成为天天生鲜注册会员</h1>请点击以下链接激活您的账号<br/><a href="http://127.0.0.1:8000/user/active/%s">http://127.0.0.1:8000/user/active/%s</a>' % (
            username, token, token)

            send_mail(subject, message, sender, receiver, html_message=html_message)

            # 相应, 跳转到登陆页面
            return render(request, 'login.html')
            # return redirect(reverse('goods:index'))  # 不能用

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
