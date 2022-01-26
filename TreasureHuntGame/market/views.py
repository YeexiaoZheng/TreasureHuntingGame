from bson.objectid import ObjectId
from django.http.response import JsonResponse
from django.shortcuts import render

from TreasureHuntGame.function import SERVER_ERROR, check_db, obj2str, check_login, check_gold_backpack, get_user

from TreasureHuntGame.settings import db

# Create your views here.


def items_counting(items):
    total, tool, ornament, totipotent = 0, 0, 0, 0
    for item in items:
        total += 1
        if item['type'] == 'totipotent':
            totipotent += 1
        if item['type'] == 'tool':
            tool += 1
        if item['type'] == 'ornament':
            ornament += 1

    return total, tool, ornament, totipotent


@check_login
@check_db
def market_view(request):

    # 获取username, uid, 和user文档
    username, uid, user = get_user(request)

    if request.method == 'GET':

        # 判断有没有?f=xxx请求，此时跳转到f对应的界面
        if 'f' in request.GET:
            # 如果f是sell请求
            if request.GET['f'] == 'sell':
                # 从数据库中获取items数据(所有属于此用户的在背包中的宝物，不包含佩戴中)
                items = list(db.item.find({'$or': [{'buid': ObjectId(uid), 'state': 'backpack'}, {
                             'buid': ObjectId(uid), 'state': 'onsale'}]}))

                total, tool, ornament, totipotent = items_counting(items)

                for item in items:
                    # 增加此字段仅方便前端访问(受django模板层限制变量不能以下划线开头)
                    item['iid'] = item['_id']
                    item['buid'] = str(item['buid'])

                user['uid'] = str(user['_id'])

                dic = {'f': '出售',  'total': total, 'tool': tool,
                       'ornament': ornament, 'totipotent': totipotent, 'items': items}
                return render(request, 'market/market.html', dict(dic, **user))

        # 没有f默认返回购买页面
        else:
            # 从数据库中获取items数据(所有不等于此前uid的onsale宝物)
            items = list(db.item.find(
                {'buid': {'$ne': ObjectId(uid)}, 'state': 'onsale'}))

            total, tool, ornament, totipotent = items_counting(items)

            for item in items:
                # 增加此字段仅方便前端访问(受django模板层限制变量不能以下划线开头)
                item['iid'] = item['_id']
                item['buid'] = str(item['buid'])

            user['uid'] = str(user['_id'])

            dic = {'f': '购买', 'total': total, 'tool': tool,
                   'ornament': ornament, 'totipotent': totipotent, 'items': items}
            return render(request, 'market/market.html', dict(dic, **user))

    elif request.method == 'POST':

        # 获取宝物id和操作
        try:
            f = request.POST['f']
            iid = request.POST['iid']
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
            # 判断是否为当前用户操作，防止自己购买自己的宝物
            if str(item['buid']) == str(uid):
                return JsonResponse({'error': '这是您自己的宝物！'})

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
                price = int(request.POST['price'])
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
