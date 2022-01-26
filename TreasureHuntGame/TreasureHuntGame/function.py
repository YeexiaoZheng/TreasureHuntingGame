from TreasureHuntGame.settings import db
from bson.objectid import ObjectId
from django.http.response import JsonResponse


SERVER_ERROR = {
    'error': '服务器有误，请重试',
}


# user文档格式
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
        'auto_clean': 0,
        'auto_work': 0,
        'finish': 0,
    }

# item文档格式
def create_item(item_type):
    return {
        'buid': '',
        'name': item_type['name'],
        'grade': item_type['grade'],
        'info': item_type['info'],
        'type': item_type['type'],
        'work_efficiency': item_type['work_efficiency'],
        'lucky_value': item_type['lucky_value'],
        'state': 'backpack',
        'price': 0,
    }

# 获得items
def get_items(times, lucky_value):
    import numpy as np
    import random
    import math

    # 构建item资源池
    items_all_num = 100000
    items_poor = []
    item_list = db.item_type.find()
    for item_type in item_list:
        if item_type['myid'] != 0:
            prob = float(item_type['prob'])
            num = int(
                prob * (1+lucky_value*math.exp(item_type['grade'])*0.0005) * items_all_num)  # 可能性算法
            items_poor.extend(list(np.full(num, item_type['myid'])))

    # 用0补充
    if (items_all_num-len(items_poor)) > 0:
        items_poor.extend(list(np.zeros(items_all_num-len(items_poor))))

    # 从item资源池中获取一个item，并封装成item文档
    items = []
    for i in range(times):
        items.append(create_item(db.item_type.find_one(
            {'myid': int(random.choice(items_poor))})))
    return items

# 删除背包中最差的num个宝物
def discard_worst(user, num):
    # 查找最差的num个宝物
    items = list(db.item.aggregate([
        {'$match': {'buid': user['_id'], 'state':'backpack'}},
        {'$project': {'sum': {"$add": ["$work_efficiency", "$lucky_value"]}}},
        {'$sort': {'sum': 1}},
        {'$limit': num},
    ]))

    # 更新数据库
    try:
        # 将items删除
        for item in items:
            db.item.delete_one({'_id': item['_id']})
        # 更新user
        db.user.update_one({'_id': user['_id']}, {'$inc': {'backpack': -num}})
    except:
        print('--- concurrent write error! ---')
        return False, '服务器错误，请重试'

    return True, ''


max_num = 60
# 检查用户金币是否不足或背包是否有空
def check_gold_backpack(user, gold, num):
    # print(user)
    if user['gold_num'] < gold:
        return False, '金币不足'
    if (user['backpack'] + num) > max_num:
        if user['auto_clean'] == 1:
            return discard_worst(user, num)
        else:
            return False, '背包空间不足'

    return True, ''


max_tool, max_ornament, max_totipotent = 2, 2, 1
# 检查用户是否能佩戴宝物
def check_wear(user, item):

    if item['type'] == 'totipotent':
        if user['wear']['tool_num'] > 0 or user['wear']['ornament_num'] > 0:
            return False, '有且只能佩戴一个全能宝物，此时将无法佩戴其他宝物！'
    elif item['type'] == 'tool':
        if user['wear']['tool_num'] >= max_tool:
            return False, '佩戴工具已达上限！'
        elif user['wear']['totipotent_num'] >= max_totipotent:
            return False, '有且只能佩戴一个全能宝物，此时将无法佩戴其他宝物！'
    elif item['type'] == 'ornament':
        if user['wear']['ornament_num'] >= max_tool or user['wear']['totipotent_num'] > max_totipotent:
            return False, '佩戴饰品已达上限！'
        elif user['wear']['totipotent_num'] >= max_totipotent:
            return False, '有且只能佩戴一个全能宝物，此时将无法佩戴其他宝物！'
    else:
        return False, '无效宝物无法佩戴！'

    return True, ''

# 返回username, uid, 和user文档
def get_user(request):
    # 获取session中的username，uid
    username = request.session['username']
    uid = request.session['uid']
    # 从数据库中获取玩家文档
    user = db.user.find_one({'_id': ObjectId(uid)})
    return username, uid, user

# 检查(用户是否已登录/用户是否存在)的装饰器
def check_login(fn):
    def wrap(request, *args, **kwargs):
        if 'username' not in request.session or 'uid' not in request.session:
            return JsonResponse({'global_error': '请先登录'})

        try:
            # 获取session中的username，uid
            username = request.session['username']
            uid = request.session['uid']
            # 从数据库中获取玩家文档
            user = db.user.find_one({'_id': ObjectId(uid)})
            if user is None:
                print('--- No this user!!! ---')
                return JsonResponse({'global_error': '用户不存在'})

        except Exception as e:
            print('--- No this user!!! ---')
            return JsonResponse({'global_error': '用户不存在'})

        return fn(request, *args, **kwargs)
    return wrap

# 检查数据库是否连接的装饰器
def check_db(fn):
    def wrap(request, *args, **kwargs):
        if db is None:
            print('--- database connect error! ---')
            return JsonResponse({'global_error': '服务器有误，数据库未连接，请重试'})
        return fn(request, *args, **kwargs)
    return wrap

# 将字典中的ObjectId转化为str
def obj2str(dic):
    if isinstance(dic, dict):
        for i in dic:
            if isinstance(dic[i], ObjectId):
                dic[i] = str(dic[i])
    elif isinstance(dic, list):
        for dic_i in dic:
            for i in dic_i:
                if isinstance(dic_i[i], ObjectId):
                    dic_i[i] = str(dic_i[i])

    return dic

# 自动工作job
def auto_work(uid):
    max_gold = 99999

    # 获取user文档
    user = db.user.find_one({'_id': ObjectId(uid)})

    # 更改user数据
    user['gold_num'] += 10 * user['work_efficiency']

    # 金币数量能超过上限
    if user['gold_num'] > max_gold:
        user['gold_num'] = max_gold

    # 更新user数据库
    try:
        db.user.update({'_id': ObjectId(uid)}, user)
        # db.user.update_one({'_id':ObjectId(uid)}, {'$inc':{'gold_num':(10*user['work_efficiency'])}})
        print(uid, ' 自动工作一次')
    except Exception as e:
        print('工作失败')
        print('--- concurrent write error! ---')


# # 自动工作schedule
# def auto_work_sched():
#     # 自动工作的定时
#     from apscheduler.schedulers.background import BackgroundScheduler
#     from apscheduler.triggers.interval import IntervalTrigger
#     sched = BackgroundScheduler()
#     try:
#         sched.start()
#         print('sched start success!')
#     except:
#         print('sched start error!')
#     trigger = IntervalTrigger(minutes=10)

#     users = db.user.find({'auto_work':1})
#     for user in users:
#         sched.add_job(auto_work, trigger, args=[str(user['_id'])], id=str(user['_id']))


# # 将数据库的try语句封装，简化代码
# def try_db_func(func, arg1, arg2=None, success_response={'success':'success'}):
#     try:
#         if arg2 is None:
#             func(arg1)
#         else:
#             func(arg1, arg2)
#         return JsonResponse(success_response)
#     except:
#         print('--- concurrent write error! ---')
#         return JsonResponse({'global_error':'服务器有误，请重试'})
