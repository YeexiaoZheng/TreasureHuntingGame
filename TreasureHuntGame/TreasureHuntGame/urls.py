"""TreasureHuntGame URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/2.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from . import views

urlpatterns = [

    # 测试
    path('test/', include('testproject.urls')),

    # 后台管理
    path('admin/', admin.site.urls),
    # 主页/about页
    path('', views.index_view),
    path('index', views.index_view),
    path('index/', views.index_view),

    # 注册/登录/退出登录
    path('user/', include('user.urls')),

    # 个人主界面
    path('home/', include('home.urls')),

    # 商店
    path('market/', include('market.urls')),

    # 工作
    path('work/', include('work.urls')),

    # 寻宝
    path('hunt/', include('hunt.urls')),
]

from django.conf import settings
from django.conf.urls.static import static

urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)