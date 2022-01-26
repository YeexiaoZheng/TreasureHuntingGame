from django.http.response import JsonResponse
from django.core.paginator import Paginator
from django.shortcuts import render
from bson.objectid import ObjectId

from TreasureHuntGame.function import SERVER_ERROR, check_login, check_wear, get_user, check_db
from TreasureHuntGame.settings import db

# Create your views here.


@check_login
@check_db
def home_view(request):

    # 获取username, uid, 和user文档
    username, uid, user = get_user(request)

    return render(request, 'home/home.html', user)


@check_login
@check_db
def my_view(request):

    # 获取username, uid, 和user文档
    username, uid, user = get_user(request)

    if request.method == 'GET':

        page_num = int(request.GET.get('page', 1))

        # 从数据库中获取玩家的items
        wearitems = list(db.item.find(
            {'buid': ObjectId(uid), 'state': 'wear'}))
        for item in wearitems:
            item['iid'] = item['_id']

        backpackitems = list(db.item.find({'$or': [{'buid': ObjectId(
            uid), 'state': 'backpack'}, {'buid': ObjectId(uid), 'state': 'onsale'}]}))
        for item in backpackitems:
            item['iid'] = item['_id']
            # item['buid'] = str(item['buid'])

        paginator = Paginator(backpackitems, 8)

        page_num = max(page_num, 1)
        page_num = min(page_num, paginator.num_pages)

        backpackitems_page = paginator.page(page_num)

        user['uid'] = user['_id']  # 便于前端访问

        return render(request, 'home/my.html', dict({'wearitems': wearitems, 'backpackitems': backpackitems_page, 'page_range': paginator.page_range, 'page_num': page_num}, **user))

    elif request.method == 'POST':
        # 获取操作和itemid
        try:
            f, iid = request.POST['f'], request.POST['iid']
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
                    if item['grade'] == 6:
                        db.user.update_one({'_id': ObjectId(uid)},
                                           {'$set': {
                                               'finish': 1,
                                           }})
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
                    if item['grade'] == 6:
                        db.user.update_one({'_id': ObjectId(uid)},
                                           {'$set': {
                                               'finish': 0,
                                           }})
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
