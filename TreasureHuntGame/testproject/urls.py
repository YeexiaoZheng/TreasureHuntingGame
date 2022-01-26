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
from django.urls import path
from . import views

urlpatterns = [
    # 返回用户及其所有物品
    path('getall/', views.test_getall_view),
    # 注册/登录/注销 测试
    path('user/', views.test_user_view),
    # 赚钱(工作) 测试
    path('work/', views.test_work_view),
    # 寻宝测试
    path('hunt/', views.test_hunt_view),
    # 佩戴/取下/丢弃 测试
    path('operate/', views.test_operate_view),
    # 市场(购买/出售/回收) 测试
    path('market/', views.test_market_view),
    # 自动删除宝物 测试
    path('settings/', views.test_settings_view),
]
