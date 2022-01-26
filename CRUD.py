
from bson.objectid import ObjectId
import pymongo
DBNAME = 'treasurehuntgame'
db = None
try:
    client = pymongo.MongoClient("mongodb://localhost:27017/")
    db = client[DBNAME]
except Exception as e:
    print('--- connect to database error! ---')

user={}
item={}
num=1, uid=0, iid=0

# 插入用户/宝物
db.user.insert_one(user)
db.item.insert_one(item)

# 删除背包最差的num个宝物（较难）
items = list(db.item.aggregate([
    {'$match': {'buid': user['_id'], 'state':'backpack'}},
    {'$project': {'sum': {"$add": ["$work_efficiency", "$lucky_value"]}}},
    {'$sort': {'sum': 1}},
    {'$limit': num},
]))
# 将items删除
for item in items:
    db.item.delete_one({'_id': item['_id']})
# 更新user
db.user.update_one({'_id': user['_id']}, {'$inc': {'backpack': -num}})


# 佩戴宝物
db.user.update_one({'_id': ObjectId(uid)},
                   {'$inc': {
                    'work_efficiency': item['work_efficiency'],
                    'lucky_value': item['lucky_value'],
                    'wear.'+item['type']+'_num': 1,
                    }})
db.item.update_one({'_id': ObjectId(iid)}, {'$set': {'state': 'wear'}})

# 取下宝物
db.user.update_one({'_id': ObjectId(uid)},
                   {'$inc': {
                    'work_efficiency': -item['work_efficiency'],
                    'lucky_value': -item['lucky_value'],
                    'wear.'+item['type']+'_num': -1,
                    }})
db.item.update_one({'_id': ObjectId(iid)}, {'$set': {'state': 'backpack'}})

# 丢弃宝物（这里可以将丢弃 改成 把item的state改成invalid，便于回溯）
db.user.update_one({'_id': ObjectId(uid)}, {'$inc': {'backpack': -1}})
db.item.delete_one({'_id': ObjectId(iid)})

# 工作（由于金币我设置了上限，未了解MongoDB关于某一属性的范围，因此是直接set）
db.user.update_one({'_id': ObjectId(uid)},
                   {'$set': {
                       'gold_num': user['gold_num']
                   }})


# 寻宝（更新用户信息，宝物插入见第一条）
db.user.update_one({'_id': ObjectId(uid)},
                   {'$inc': {
                       'gold_num': -10*times,
                       'backpack': 1,
                   }})

# 购买操作（较为复杂）
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

# 出售操作（只需设置宝物状态和价格即可）
db.item.update({'_id': ObjectId(iid)},
               {'$set': {
                   'state': 'onsale',
                   'price': price,
               }})

# 回收操作
db.item.update({'_id': ObjectId(iid)},
               {'$set': {
                   'state': 'backpack',
                   'price': 0,
               }})

# 开启/关闭自动清理
db.user.update_one({'_id': ObjectId(uid)}, {
    '$set': {'auto_clean': 0}})

# 开启/关闭自动工作
db.user.update_one({'_id': user['_id']}, {
    '$set': {'auto_work': 1}})
