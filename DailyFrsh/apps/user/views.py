from django.shortcuts import render, HttpResponse,redirect
from django.core.urlresolvers import reverse
from apps.user.models import User

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
            user.is_active = 0
            user.save()
            return render(request, 'login.html')
        # else:  理解: try--> except--> else  这里else省略了
        else:  # 用户名存在
            return render(request, 'register.html', {'error': '用户名已存在'})

        # return redirect(reverse('goods:index'))