from bson.objectid import ObjectId
from apscheduler.schedulers.background import BackgroundScheduler
from django.http.response import JsonResponse
from TreasureHuntGame.settings import db, sched, trigger
from django.shortcuts import render

from .function import check_db, check_login, get_user, check_gold_backpack, check_wear, create_user, get_items, obj2str, auto_work

SERVER_ERROR = {
    'error': '服务器有误，请重试',
}

# Create your views here.


@check_login
@check_db
def test_getall_view(request):
    # 获取username, uid, 和user文档
    username, uid, user = get_user(request)

    # 从数据库中获取玩家的items
    wearitems = list(db.item.find({'buid': ObjectId(uid), 'state': 'wear'}))
    backpackitems = list(db.item.find({'$or': [{'buid': ObjectId(
        uid), 'state': 'backpack'}, {'buid': ObjectId(uid), 'state': 'onsale'}]}))

    return JsonResponse({
        'user': obj2str(user),
        'wearitems': obj2str(wearitems),
        'backpackitems': obj2str(backpackitems),
    })


@check_db
def test_user_view(request):
    # 获取json文件内容
    try:
        f, username, password = request.GET['f'], request.GET['username'], request.GET['password']
    except Exception as e:
        print('请使用规定json格式')
        return JsonResponse({'error': '请使用规定json格式'})

    # 判断是注册操作
    if f == 'register':

        # 用户名是否可用
        user = db.user.find_one({'username': username})
        if user is not None:
            return JsonResponse({'error': '用户名重复，请重新输入'})

        # 编写文档，直接存入，密码未hash
        user = create_user(username, password)

        # 向数据库插入数据 要try 防止并发
        try:
            db.user.insert_one(user)

        except Exception as e:
            print('--- concurrent write error! ---')
            return JsonResponse(SERVER_ERROR)

        return JsonResponse({'success': '注册成功，请登录'})

    # 判断是登录操作
    elif f == 'login':

        # 对比数据库用户和密码，然后进入个人界面
        user = db.user.find_one({'username': username})

        # 用户名不存在或密码错误
        if user is None or user['password'] != password:
            return JsonResponse({'error': '用户名或密码错误，请重试'})

        # 登录进入，且设置session
        else:
            request.session['username'] = user['username']
            request.session['uid'] = str(user['_id'])
            return JsonResponse({'success': '登录成功'})

    # 判断是退出登录操作
    elif f == 'logout':
        # 删除session值
        if 'username' in request.session and 'uid' in request.session:
            del request.session['username']
            del request.session['uid']

            return JsonResponse({'success': '退出登录成功'})
        else:
            return JsonResponse({'error': '您尚未登录，请登录'})

    else:
        print('请使用规定json格式')
        return JsonResponse({'error': '请使用规定json格式'})


@check_login
@check_db
def test_work_view(request):

    max_gold = 99999

    # 获取username, uid, 和user文档
    username, uid, user = get_user(request)

    try:
        work = request.GET['work']
    except Exception as e:
        print('请使用规定json格式')
        return JsonResponse({'error': '请使用规定json格式'})

    if work == 'auto':
        if user['auto_work'] == 0:
            try:
                sched.add_job(auto_work, trigger, args=[uid], id=uid)
                db.user.update_one({'_id': user['_id']}, {
                                   '$set': {'auto_work': 1}})
                return JsonResponse({'success': '自动工作开始，将会每10min为您自动工作一次'})
            except Exception as e:
                print('--- concurrent write error! ---')
                return JsonResponse(SERVER_ERROR)
        else:
            return JsonResponse({'error': '您已在自动工作中'})

    elif work == 'manual':
        if user['auto_work'] == 1:
            try:
                sched.remove_job(uid)
                db.user.update_one({'_id': user['_id']}, {
                                   '$set': {'auto_work': 0}})
                return JsonResponse({'success': '自动工作停止'})
            except Exception as e:
                print('--- concurrent write error! ---')
                return JsonResponse(SERVER_ERROR)
        else:
            return JsonResponse({'error': '您并未开启自动工作'})

    elif work == 'once':
        if user['auto_work'] == 0:
            # 更改user数据
            user['gold_num'] += 10 * user['work_efficiency']

            # 金币数量能超过上限
            if user['gold_num'] > max_gold:
                user['gold_num'] = max_gold

            # 更新user数据库
            try:
                db.user.update_one({'_id': ObjectId(uid)}, {
                                   '$set': {'gold_num': user['gold_num']}})
                return JsonResponse({'success': '成功工作，金币增加了'})
            except Exception as e:
                print('--- concurrent write error! ---')
                return JsonResponse(SERVER_ERROR)

        else:
            return JsonResponse({'error': '您正在自动工作无法进行手动工作！'})

    else:
        print('请使用规定json格式')
        return JsonResponse({'error': '请使用规定json格式'})


@check_login
@check_db
def test_hunt_view(request):

    # 获取username, uid, 和user文档
    username, uid, user = get_user(request)

    try:
        times = int(request.GET['times'])
        if times > 10:
            return JsonResponse({'error': '连抽次数过多！'})
    except Exception as e:
        print('请使用规定json格式')
        return JsonResponse({'error': '请使用规定json格式'})

    flag, warning = check_gold_backpack(user, 10*times, times)
    if flag is False:
        return JsonResponse({'error': warning})

    # 根据次数和幸运值获取宝物
    items = get_items(times, int(user['lucky_value']))

    # 向数据库插入新的item数据
    for item in items:
        item['buid'] = user['_id']  # 更改属于的用户id
        try:
            db.item.insert_one(item)
        except Exception as e:
            print('--- concurrent write error! ---')
            return JsonResponse(SERVER_ERROR)

    # 更新user数据库
    try:
        db.user.update_one({'_id': ObjectId(uid)},
                           {'$inc': {
                               'gold_num': -10*times,
                               'backpack': 1,
                           }})
    except Exception as e:
        print('--- concurrent write error! ---')
        return JsonResponse(SERVER_ERROR)

    return JsonResponse({
        'success': '成功获得宝物！以下是您获得的宝物：',
        'items': obj2str(items),
    })


@check_login
@check_db
def test_operate_view(request):

    # 获取username, uid, 和user文档
    username, uid, user = get_user(request)

    try:
        f, iid = request.GET['f'], request.GET['iid']
        # 获取iid所对应的item文档
        item = db.item.find_one({'_id': ObjectId(iid)})
    except Exception as e:
        print('请使用规定json格式')
        return JsonResponse({'error': '请使用规定json格式'})

    # 如果没有此宝物 或 判断是否为当前用户操作，防止恶意篡改
    if item is None or str(item['buid']) != str(uid):
        return JsonResponse({'error': '您没有此宝物！'})

    # 如果是佩戴请求
    if f == 'wear':

        # 判断是否还能佩戴
        flag, warning = check_wear(user, item)
        if flag == False:
            return JsonResponse({'error': warning})

        # 判断是否在背包里
        if item['state'] == 'wear':
            return JsonResponse({'error': '您已佩戴此宝物'})
        elif item['state'] == 'onsale':
            return JsonResponse({'error': '此宝物正在挂牌中，无法佩戴'})

        else:
            # 更新数据库
            try:
                db.user.update_one({'_id': ObjectId(uid)},
                                   {'$inc': {
                                       'work_efficiency': item['work_efficiency'],
                                       'lucky_value': item['lucky_value'],
                                       'wear.'+item['type']+'_num': 1,
                                   }})
                db.item.update_one({'_id': ObjectId(iid)}, {
                                   '$set': {'state': 'wear'}})
            except Exception as e:
                print('--- concurrent write error! ---')
                return JsonResponse(SERVER_ERROR)

        return JsonResponse({'success': '佩戴成功！'})

    # 如果是取下请求
    elif f == 'backpack':
        # 判断是否佩戴中
        if item['state'] == 'wear':
            # 更新数据库
            try:
                db.user.update_one({'_id': ObjectId(uid)},
                                   {'$inc': {
                                       'work_efficiency': -item['work_efficiency'],
                                       'lucky_value': -item['lucky_value'],
                                       'wear.'+item['type']+'_num': -1,
                                   }})
                db.item.update_one({'_id': ObjectId(iid)}, {
                                   '$set': {'state': 'backpack'}})
            except Exception as e:
                print('--- concurrent write error! ---')
                return JsonResponse({SERVER_ERROR})
        else:
            return JsonResponse({'error': '此宝物并未佩戴！'})

        return JsonResponse({'success': '取下成功！'})

    # 如果是丢弃请求
    elif f == 'discard':

        # 判断是否在背包中
        if item['state'] == 'wear':
            return JsonResponse({'error': '您已佩戴此宝物，无法丢弃'})
        elif item['state'] == 'onsale':
            return JsonResponse({'error': '此宝物正在挂牌中，无法丢弃'})

        else:
            # 更新数据库
            try:
                db.user.update_one({'_id': ObjectId(uid)}, {
                                   '$inc': {'backpack': -1}})
                db.item.delete_one({'_id': ObjectId(iid)})
            except Exception as e:
                print('--- concurrent write error! ---')
                return JsonResponse(SERVER_ERROR)

        return JsonResponse({'success': '丢弃成功！'})

    else:
        return JsonResponse({'error': '请使用规定json格式'})


@check_login
@check_db
def test_market_view(request):

    # 获取username, uid, 和user文档
    username, uid, user = get_user(request)

    try:
        f = request.GET['f']

        # 如果只是浏览市场
        if f == 'view':
            items = list(db.item.find(
                {'buid': {'$ne': ObjectId(uid)}, 'state': 'onsale'}))
            return JsonResponse({
                'success': '以下为商城中正在出售的宝物：',
                'items': obj2str(items)
            })

        iid = request.GET['iid']
        # 获取iid所对应的item文档
        item = db.item.find_one({'_id': ObjectId(iid)})
    except Exception as e:
        print('请使用规定json格式')
        return JsonResponse({'error': '请使用规定json格式'})

    # 如果没有此宝物
    if item is None:
        return JsonResponse({'error': '此宝物不存在！'})

    # 购买请求
    if f == 'buy':
        # # 判断是否为当前用户操作，防止自己购买自己的宝物
        # if str(item['buid']) == str(uid):
        #     return JsonResponse({'error':'这是您自己的宝物！'})

        # 判断是否onsale
        if item['state'] == 'onsale':

            # 判断是否能购买
            flag, warning = check_gold_backpack(user, item['price'], 1)
            if flag is False:
                return JsonResponse({'error': warning})

            # 更新数据库
            try:
                # 更新卖家
                db.user.update_one({'_id': ObjectId(item['buid'])},
                                   {'$inc': {
                                       'gold_num': item['price'],
                                       'backpack': -1,
                                   }})
                # 更新买家
                db.user.update({'_id': ObjectId(uid)},
                               {'$inc': {
                                   'gold_num': -item['price'],
                                   'backpack': 1,
                               }})
                # 更新item信息
                db.item.update({'_id': ObjectId(iid)},
                               {'$set': {
                                   'buid': ObjectId(uid),
                                   'state': 'backpack',
                                   'price': 0,
                               }})
            except Exception as e:
                print('--- concurrent write error! ---')
                return JsonResponse(SERVER_ERROR)

            return JsonResponse({
                'success': '成功购买宝物！快去佩戴吧！',
                'item': obj2str(item),
            })

        # 若不是onsale
        else:
            return JsonResponse({'error': '此宝物并没有挂牌出售！'})

    # 出售请求
    elif f == 'sell':
        # 判断是否为当前用户操作，防止恶意篡改
        if str(item['buid']) != str(uid):
            return JsonResponse({'error': '您没有此宝物！'})

        # 获取挂牌价格
        try:
            price = int(request.GET['price'])
        except Exception as e:
            print('--- 价格输入有误 ---')
            return JsonResponse({'error': '输入价格有误！'})

        # 判断是否在背包中(或者正在售卖，此时为更新价格)
        if item['state'] == 'backpack' or item['state'] == 'onsale':

            # 更新数据库
            try:
                db.item.update({'_id': ObjectId(iid)},
                               {'$set': {
                                   'state': 'onsale',
                                   'price': price,
                               }})
            except Exception as e:
                print('--- concurrent write error! ---')
                return JsonResponse(SERVER_ERROR)

            return JsonResponse({'success': '成功挂牌宝物！等待有缘人购买吧！'})

        # 如果宝物状态是佩戴中则无法挂牌出售
        else:
            return JsonResponse({'error': '您正在佩戴此宝物！无法挂牌出售！'})

    # 回收请求
    elif f == 'retrieve':
        # 判断是否为本人操作，防止恶意篡改
        if str(item['buid']) != str(uid):
            return JsonResponse({'error': '您没有此宝物！'})

        # 判断是否在onsale中
        if item['state'] == 'onsale':

            # 更新数据库
            try:
                db.item.update({'_id': ObjectId(iid)},
                               {'$set': {
                                   'state': 'backpack',
                                   'price': 0,
                               }})
            except Exception as e:
                print('--- concurrent write error! ---')
                return JsonResponse(SERVER_ERROR)

            return JsonResponse({'success': '成功回收挂牌宝物！'})

        # 如果宝物状态不是onsale
        else:
            return JsonResponse({'error': '此宝物并未挂牌出售！'})

    else:
        print('请使用规定json格式')
        return JsonResponse({'error': '请使用规定json格式'})


@check_login
@check_db
def test_settings_view(request):

    # 获取username, uid, 和user文档
    username, uid, user = get_user(request)

    try:
        setting = request.GET['setting']
        operate = request.GET['operate']
    except Exception as e:
        print('请使用规定json格式')
        return JsonResponse({'error': '请使用规定json格式'})

    # 如果设置的是自动删除功能
    if setting == 'auto_clean':

        # 判断操作是自动还是手动并改动
        if operate == 'auto':
            # 更新数据库
            try:
                db.user.update_one({'_id': ObjectId(uid)}, {
                                   '$set': {'auto_clean': 1}})
                return JsonResponse({'success': '设置自动删除宝物成功！'})
            except Exception as e:
                print('--- concurrent write error! ---')
                return JsonResponse(SERVER_ERROR)

        elif operate == 'manual':
            # 更新数据库
            try:
                db.user.update_one({'_id': ObjectId(uid)}, {
                                   '$set': {'auto_clean': 0}})
                return JsonResponse({'success': '设置手动删除宝物成功！'})
            except Exception as e:
                print('--- concurrent write error! ---')
                return JsonResponse(SERVER_ERROR)

        else:
            return JsonResponse({'error': '请使用规定json格式'})

    else:
        return JsonResponse({'error': '请使用规定json格式'})
