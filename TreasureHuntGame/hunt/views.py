import threading
from bson.objectid import ObjectId
import math
from django.http.response import HttpResponseRedirect, JsonResponse
from django.shortcuts import render

from TreasureHuntGame.function import SERVER_ERROR, get_user, check_login, check_db, check_gold_backpack, obj2str
from TreasureHuntGame.settings import db

# Create your views here.


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


def get_items(times, lucky_value):
    import numpy as np
    import random

    # 构建item资源池
    items_all_num = 100000
    items_poor = []
    item_list = db.item_type.find()
    for item_type in item_list:
        if item_type['myid'] != 0:
            prob = float(item_type['prob'])
            num = int(
                prob * (1+lucky_value*math.exp(item_type['grade'])*0.0005) * items_all_num)  # 可能性算法
            # print(num)
            items_poor.extend(list(np.full(num, item_type['myid'])))

    # print(len(items_poor))

    # 用0补充
    if (items_all_num-len(items_poor)) > 0:
        items_poor.extend(list(np.zeros(items_all_num-len(items_poor))))

    # 从item资源池中获取一个item，并封装成item文档
    items = []
    for i in range(times):
        items.append(create_item(db.item_type.find_one(
            {'myid': int(random.choice(items_poor))})))
    return items


lock = threading.RLock()


@check_login
@check_db
def hunt_view(request):

    # 获取username, uid, 和user文档
    username, uid, user = get_user(request)

    if request.method == 'GET':

        ####### 如果hunt使用单独页面可以在此修改 ########
        return HttpResponseRedirect('/home')

    elif request.method == 'POST':

        try:
            times = int(request.POST['times'])
            if times > 10:
                return JsonResponse({'error': '连抽次数过多！'})
        except Exception as e:
            print('请使用规定json格式')
            return JsonResponse({'error': '请使用规定json格式'})

        lock.acquire()
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

        lock.release()

        return JsonResponse({
            'success': '成功获得宝物！以下是您获得的宝物：',
            'items': obj2str(items),
        })
