from django.core.files.storage import Storage
from django.conf import settings
from fdfs_client.client import Fdfs_client


# 重写_open和_save方法
# 重写,定义的类,继承Storage这个类
class FDFSStorage(Storage):
    # 文件存储类
    def __init__(self, client_conf=None, Nginx_url=None):
        if client_conf is None:
            client_conf = settings.FDFS_CLIENT_CONF
        self.client_conf = client_conf

        if Nginx_url is None:
            Nginx_url = settings.FDFS_NGINX_URL
        self.nginx_url = Nginx_url

    def _open(self, name, mod='rb'):
        # 打开文件
        pass

    def _save(self, name, content):
        # 保存文件:  name 是上传文件的名称,  content 是上传文件内容的File对象
        # 上传文件到 fdfs系统中
        client = Fdfs_client(self.client_conf)
        # {
        #     'Group name': group_name,
        #     'Remote file_id': remote_file_id,
        #     'Status': 'Upload successed.',
        #     'Local file name': '',
        #     'Uploaded size': upload_size,
        #     'Storage IP': storage_ip
        # }
        # 获取上传内容
        content = content.read()
        # 调用upload_by_buffer()方法
        res = client.upload_by_buffer(content)
        # 判断是否上传成功
        # if res['Status'] != 'Upload successd.':
        #     raise Exception('上传文件到FDFS失败')
        file_id = res['Remote file_id']
        # 返回文件的id
        return file_id

    def exists(self, name):
        # 判断文件在本地系统中是否存在
        return False

    def url(self, name):
        # 返回可访问到的name文件的url路径
        return self.nginx_url + name