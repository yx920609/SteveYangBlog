from AllDataBase import Model, StringField, BooleanField, FloatField, TextField,IntegerField
import time,uuid
import AllDataBase
import asyncio 

def next_id():
	return '%015d%s000' %(int (time.time() *1000),uuid.uuid4().hex)

class User(Model):
	__table__ = 'users'
	uuid = StringField(primary_key=True, default=next_id(), ddl='varchar(50)')
	email = StringField(ddl='varchar(50)')
	passwd = StringField(ddl='varchar(50)')
	admin = BooleanField(default = False)
	name = StringField(ddl='varchar(50)')
	image = StringField(ddl='varchar(500)' ,default = '')
	created_at = FloatField(default=time.time)

class Blog(Model):
	__table__ = 'blogs'
	uuid = StringField(primary_key=True, default=next_id, ddl='varchar(50)')
	user_id = StringField(ddl='varchar(50)')
	user_name = StringField(ddl='varchar(50)')
	user_image = StringField(ddl='varchar(500)',default='')
	name = StringField(ddl='varchar(50)')
	summary = StringField(ddl='varchar(200)')
	content = TextField()
	created_at = FloatField(default=time.time)

class comment(Model):
	__table__ = 'comments'
	uuid = StringField(primary_key=True,default=next_id,ddl='varchar(100)')
	blog_id = StringField(ddl = 'varchar(50)')
	user_id = StringField(ddl='varchar(50)')
	user_name = StringField(ddl = 'varchar(50)')
	content = TextField()
	created_at = FloatField(default = time.time)
	agreenum = IntegerField()
	user_image = StringField(ddl = 'varchar(500)')
	
@asyncio.coroutine
def initAdminUser(loop):
	yield from AllDataBase.create_pool(loop = loop , user ='root',password ='920609',database ='awesome')
	blog = Blog(user_id='001513663684114e867c3017a7d4afe907bb80d7b0121d5000',user_name='jack_ma',name ='成功学',content='事实上,管理不等于企业管理,正如医学不等于妇产科一样。妇产科是医学的一部分,同理,企业管理是管理的一部分',summary='买买买')
	yield from blog.save()
if __name__ == '__main__':
	loop = asyncio.get_event_loop()
	loop.run_until_complete( asyncio.wait([initAdminUser( loop )]) )  
	# loop.close()
	# if loop.is_closed():
	# 	sys.exit(0)
		