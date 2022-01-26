from bson.objectid import ObjectId
from django.http.response import HttpResponse
from django.shortcuts import render
from django.http import HttpResponseRedirect

from TreasureHuntGame.settings import db

# Create your views here.

# user文档


def create_user(username, password):
    return {
        'username': username,
        'password': password,
        'gold_num': 100,
        'work_efficiency': 1,
        'lucky_value': 1,
        'wear': {
            'tool_num': 0,
            'ornament_num': 0,
            'totipotent_num': 0,
        },
        'backpack': 0,
        'auto_clean': 1,
        'auto_work': 0,
        'finish': 0,
    }


def login_view(request):
    if request.method == 'GET':
        # 如果有session
        if 'username' in request.session and 'uid' in request.session:
            from home.views import home_view
            return home_view(request)

        # 如果没有session
        return render(request, 'user/login.html')

    elif request.method == 'POST':
        # 判断数据库是否连接
        if db is None:
            warning_dic = {'warning': '服务器有误，请重试'}
            return render(request, 'user/login.html', warning_dic)

        # 获取请求中的username和password
        username = request.POST['username']
        password = request.POST['password']

        # 对比数据库用户和密码，然后进入个人界面
        user = db.user.find_one({'username': username})

        # 用户名不存在或密码错误
        if user is None or user['password'] != password:
            warning_dic = {'warning': '用户名或密码错误，请重试'}
            return render(request, 'user/login.html', warning_dic)

        # 登录进入，且设置session
        else:
            request.session['username'] = user['username']
            request.session['uid'] = str(user['_id'])
            return HttpResponseRedirect('/home/')

    else:
        return render(request, 'user/login.html')


def register_view(request):
    if request.method == 'GET':
        return render(request, 'user/register.html')

    elif request.method == 'POST':
        # 获取请求中的username和password
        username = request.POST['username']
        password = request.POST['password']

        # 密码一致性检查，这里忽略
        pass

        # 判断数据库是否连接
        if db is None:
            warning_dic = {'warning': '服务器有误，请重试'}
            return render(request, 'user/register.html', warning_dic)

        # 用户名是否可用
        user = db.user.find_one({'username': username})
        if user is not None:
            warning_dic = {'warning': '用户名重复，请修改用户名'}
            return render(request, 'user/register.html', warning_dic)

        # 编写文档，直接存入，密码未hash
        user = create_user(username, password)

        # 向数据库插入数据 要try 防止并发
        try:
            db.user.insert_one(user)

        except Exception as e:
            print('--- concurrent write error! ---')
            warning_dic = {'warning': '服务器有误，请重试'}
            return render(request, 'user/register.html', warning_dic)

        # 返回时需要退出现登录账号，并跳转到登录界面
        return logout_view(request)

    else:
        return render(request, 'user/register.html')


def logout_view(request):
    # 删除session值
    if 'usrname' in request.session:
        del request.session['username']
    if 'uid' in request.session:
        del request.session['uid']

    return HttpResponseRedirect('/user/')
