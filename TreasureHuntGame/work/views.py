from bson.objectid import ObjectId
from django.http.response import HttpResponseRedirect, JsonResponse
from django.shortcuts import render

from TreasureHuntGame.function import SERVER_ERROR, check_db, check_login, get_user

from TreasureHuntGame.settings import db, auto_work, sched, trigger

# Create your views here.

@check_login
@check_db
def work_view(request):

    # 获取username, uid, 和user文档
    username, uid, user = get_user(request)

    if request.method == 'GET':
        ####### 如果work使用单独页面可以在此修改 ########
        return HttpResponseRedirect('/home')

    elif request.method == 'POST':

        max_gold = 99999

        try:
            work = request.POST['work']
        except Exception as e:
            print('请使用规定json格式')
            return JsonResponse({'error':'请使用规定json格式'})

        if work == 'auto':
            if user['auto_work'] == 0:
                try:
                    sched.add_job(auto_work, trigger, args=[uid], id=uid)
                    db.user.update_one({'_id':user['_id']}, {'$set':{'auto_work':1}})
                    return JsonResponse({'success':'自动工作开始，将会每10min为您自动工作一次'})
                except Exception as e:
                    print('--- concurrent write error! ---')
                    return JsonResponse(SERVER_ERROR)
            else:
                return JsonResponse({'error':'您已在自动工作中'})
        
        elif work == 'manual':
            if user['auto_work'] == 1:
                try:
                    sched.remove_job(uid)
                    db.user.update_one({'_id':user['_id']}, {'$set':{'auto_work':0}})
                    return JsonResponse({'success':'自动工作停止'})
                except Exception as e:
                    print('--- concurrent write error! ---')
                    return JsonResponse(SERVER_ERROR)
            else:
                return JsonResponse({'error':'您并未开启自动工作'})
            
        elif work == 'once':
            if user['auto_work'] == 0:
                # 更改user数据
                user['gold_num'] += 10 * user['work_efficiency']

                # 金币数量能超过上限
                if user['gold_num'] > max_gold:
                    user['gold_num'] = max_gold

                # 更新user数据库
                try:
                    db.user.update({'_id':ObjectId(uid)}, user)
                    # db.user.update_one({'_id':ObjectId(uid)}, {'$inc':{'gold_num':(10*user['work_efficiency'])}})
                    return JsonResponse({'success':'成功工作，金币增加了'})
                except Exception as e:
                    print('--- concurrent write error! ---')
                    return JsonResponse(SERVER_ERROR)

            else:
                return JsonResponse({'error':'您正在自动工作无法进行手动工作！'})
        
        else:
            print('请使用规定json格式')
            return JsonResponse({'error':'请使用规定json格式'})

    else:

        return HttpResponseRedirect('/home')