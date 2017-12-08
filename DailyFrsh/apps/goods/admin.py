from django.contrib import admin
from apps.goods.models import GoodsType, IndexPromotionBanner, IndexGoodsBanner, GoodsSKU, IndexTypeGoodsBanner


from django.core.cache import cache

# Register your models here.
# 静态页面: 是为了减少与数据库的链接查询次数, 相应速度更快
# 创建静态页面-- 因为静态页面是固定的,是缓存,
# 下面的函数主要说明: 在数据库进行数据操作时, 相应的静态页面也要发生变化
class BaseAdmin(admin.ModelAdmin):
    def save_model(self, request, obj, form, change):
        # 新增或者更新数据库时使用
        # 调用父类的方法, 实现数据库的数据的增加或者更新
        super().save_model(request, obj, form, change)

        # 附加操作, 生成静态页面
        from celery_tasks.tasks import generate_static_index_html  # 生成静态页面
        generate_static_index_html.delay()

        # 更新缓存信息
        cache.delete('index_page_data')   # 在views.py里面,有设置文件的代码,更新缓存,就是: 删除原来的缓存,重新生成一份缓存

    def delete_model(self, request, obj):
        # 删除数据是调用
        # 调用父类的方法, 实现数据的删除
        super().delete_model(request, obj)

        # 附加操作, 生成静态页面的生成
        from celery_tasks.tasks import generate_static_index_html  # 生成静态页面
        generate_static_index_html.delay()

        # 附加操作: 更新缓存信息
        cache.delete('index_page_data')


class GoodsTypeAdmin(BaseAdmin):
    pass

class IndexGoodsBannerAdmin(BaseAdmin):
    pass

class IndexPromotionBannerAdmin(BaseAdmin):
    pass

class IndexTypeGoodsBannerAdmin(BaseAdmin):
    pass

class GoodsSKUAdmin(BaseAdmin):
    search_fields = ['name', 'id']
    actions_on_bottom = True



admin.site.register(GoodsType, BaseAdmin)
admin.site.register(IndexPromotionBanner, BaseAdmin)
admin.site.register(IndexGoodsBanner, BaseAdmin)
admin.site.register(GoodsSKU, GoodsSKUAdmin)
admin.site.register(IndexTypeGoodsBanner, BaseAdmin)
