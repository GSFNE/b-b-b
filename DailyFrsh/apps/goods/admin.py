from django.contrib import admin
from apps.goods.models import GoodsType, IndexPromotionBanner, IndexGoodsBanner

# Register your models here.

admin.site.register(GoodsType)
admin.site.register(IndexPromotionBanner)
admin.site.register(IndexGoodsBanner)
