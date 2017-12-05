from django.contrib.auth.decorators import login_required

class LoginRequiredMixin(object):
    @classmethod
    def as_view(cls, **initkwargs):
        # 继续调用父类的as_view
        view = super(LoginRequiredMixin, cls).as_view(**initkwargs)
        return login_required(view)


from django.views.generic import View

class LoginRequiredView(View):
    @classmethod
    def as_view(cls, **initkwargs):
        # 继续调用父类的as_view
        view = super(LoginRequiredView, cls).as_view(**initkwargs)
        return login_required(view)