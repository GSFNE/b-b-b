# 使用celery
from django.conf import settings
from django.core.mail import send_mail
from celery import Celery

# 初始化django运行所依赖的环境
import os
import django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "DailyFrsh.settings")
django.setup()

# 创建一个Celery类的实例对象
app = Celery('celery_tasks.tasks', broker='redis://127.0.0.1:6379/6')
# 这里broker的ip地址,写broker所在的主机的ip


# 定义任务函数
@app.task
def send_register_active_email(to_email, username, token):
    '''发送激活邮件'''
    # 组织邮件信息
    subject = '天天生鲜账号激活'
    message = ''
    sender = settings.EMAIL_FROM
    receiver = [to_email]
    html_message = '<h1>%s, 欢迎您成为天天生鲜注册会员</h1>请在两个小时内点击链接激活您的账号<br/><a href="http://192.168.102.131:8000/user/active/%s">http://192.168.102.131:8000/user/active/%s</a>'%(username, token, token)
                                                                #  账号链接跳转的ip地址,写服务器所在的ip
    # 发送邮件
    import time
    time.sleep(5)
    # 模拟send_mail执行了5s
    send_mail(subject, message, sender, receiver, html_message=html_message)


'''
在views调用这个中间人执行发送邮件操作,celery的实例对象制定的中间人,也要有一份代码,了解怎么执行,要复制一份到中间人所在的主机
然后启动中间人开始执行命令:
中间人也要在虚拟环境中, 要有celery模块
cd到代码文件夹
命令: celery -A x worker -l info
// 注释: 这里的x表示中间人要执行的任务所在的文件路径 ; 这个项目路径就是: celery_tasks.tasks
celery -A celery_tasks.tasks worker -l info

启动之后会报错,因为会用到django的函数/方法,worker识别不了, 报错
就需要初始化 环境:( 注释: 这个初始环境, 要在worker端启动, 这边不需要)
 初始化django运行所依赖的环境
 import os
 import django
 os.environ.setdefault("DJANGO_SETTINGS_MODULE", "dailyfresh.settings")
 django.setup()
'''
