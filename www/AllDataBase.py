import asyncio 
import logging
import aiomysql
# from orm import Model,StringFiled,IntergerField


def log(sql, args=()):
	logging.info('SQL: %s' % sql)

logging.basicConfig(
    level=logging.DEBUG,
    format="[%(asctime)s] %(name)s:%(levelname)s: %(message)s"
)

async def create_pool(loop,**kw):
	logging.info('create connection')
	global __pool
	__pool = await aiomysql.create_pool(
        host=kw.get('host', 'localhost'),
        port=kw.get('port', 3306),
        user=kw['user'],
        password=kw['password'],
        db=kw['database'],
        charset=kw.get('charset', 'utf8'),
        autocommit=kw.get('autocommit', True),
        maxsize=kw.get('maxsize', 10),
        minsize=kw.get('minsize', 1),
        loop=loop
		)

async def destory_pool():
	global __pool
	if __pool is not None :
		__pool.close()
		await __pool.wait_closed()

async def select(sql,args,size=None):				
	print('args=======>%s'% args)
	global __pool
	async with __pool.get() as conn:
		async with conn.cursor(aiomysql.DictCursor) as cur:
			await cur.execute(sql.replace('?','%s'),args or())
			if size:
				rs = await cur.fetchmany(size)
			else:
				rs = await cur.fetchall()

		logging.info('rows returned :%s' % len(rs))
		return rs

async def execute(sql, args, autocommit=True):
	async with __pool.get() as conn:
		if not autocommit:
			await conn.begin()
		try:
			async with conn.cursor(aiomysql.DictCursor) as cur:
				await cur.execute(sql.replace('?', '%s'), args)
				affected = cur.rowcount
			if not autocommit:
				await conn.commit()
		except BaseException as e:
			if not autocommit:
				await conn.rollback()
			raise
	return affected

class Field(object):
	def __init__(self, name, column_type,primary_key,default):
		self.name = name
		self.column_type = column_type
		self.primary_key = primary_key
		self.default = default
	def __str__(self):
		return '<%s, %s:%s>' % (self.__class__.__name__,self.column_type,self.name)

class StringField(Field):

    def __init__(self, name='StringField', primary_key=False, default=None, ddl='varchar(100)'):
        super().__init__(name, ddl, primary_key, default)


class IntegerField(Field):

    def __init__(self, name='IntegerField', primary_key=False, default=0):
        super().__init__(name, 'bigint', primary_key, default)

class BooleanField(Field):
	def __init__(self, name ='BooleanField',primaryKey=False,default =False):
		super().__init__(name,'boolean',primaryKey,default)

class FloatField(Field):

    def __init__(self, name='FloatField', primary_key=False, default=0.0):
        super().__init__(name, 'real', primary_key, default)

class TextField(Field):

	def __init__(self, name='TextField', default=None):
		super().__init__(name, 'text', False, default)		
		
class ModelMetaclass(type):
	def __new__(cls,name,bases,attrs):
		if name == 'Model':
			return type.__new__(cls,name,bases,attrs)

		tableName = attrs.get('__table__',None) or name

		mappings = dict()
		fields = []
		primaryKey = None

		for k,v in attrs.items():
			if isinstance(v,Field):
				mappings[k]=v

				if v.primary_key:
					if primaryKey:
						raise RuntimeError('Duplicate primary key %s' % k)

					primaryKey = k

				else:
					fields.append(k)

		if not primaryKey:
			raise RuntimeError('primary key not found')

		for k in mappings.keys():
			attrs.pop(k)

		escaped_fields = list(map(lambda f:'`%s`' %f,fields ))
		attrs['__mappings__'] = mappings # 保存属性和列的映射关系
		attrs['__table__'] = tableName
		attrs['__primary_key__'] = primaryKey # 主键属性名
		attrs['__fields__'] = fields # 除主键外的属性名
        # 构造默认的SELECT, INSERT, UPDATE和DELETE语句:
		attrs['__select__'] = 'select `%s`, %s from `%s`' % (primaryKey, ', '.join(escaped_fields), tableName)
		attrs['__insert__'] = 'insert into `%s` (%s, `%s`) values (%s)' % (tableName, ', '.join(escaped_fields), primaryKey, create_args_string(len(escaped_fields) + 1))
		attrs['__update__'] = 'update `%s` set %s where `%s`=?' % (tableName, ', '.join(map(lambda f: '`%s`=?' % (mappings.get(f).name or f), fields)), primaryKey)
		attrs['__delete__'] = 'delete from `%s` where `%s`=?' % (tableName, primaryKey)
		return type.__new__(cls, name, bases, attrs)
def create_args_string(num):
	L = []
	for n in range(num):
		L.append('?')
	return ', '.join(L)

class  Model(dict,metaclass=ModelMetaclass):
	def __init__(self, **kw):
		# log(kw)
		super(Model, self).__init__(**kw)
	def __getattr__(self,key):
		try:
			return self[key]
		except KeyError:
			raise AttributeError(r"'Model' object has no atrribute' '%s'" % key)
	def __setattr__(self,key,value):
		self[key]=value

	def getValue(self,key):
		return getattr(self,key,None)

	def getValueOrDefault(self,key):	
		value = getattr(self,key,None)
		if value is None:
			field = self.__mappings__[key]
			if field.default is not None:
				value = field.default() if callable(field.default) else field.default
				
				setattr(self,key, value)
			return value
		else:
			return value

	@classmethod
	async def find(cls,pk):
		rs = await select('%s where `%s`=?' % (cls.__select__, cls.__primary_key__), [pk], 1)
		if len(rs)==0:
			return None
		return cls(**rs[0])

	async def save(self):
		args = list(map(self.getValueOrDefault,self.__fields__))
		print(args)
		args.append(self.getValueOrDefault(self.__primary_key__))
		rows = await execute(self.__insert__,args)
		if rows!=1:
			logging.warn('faild to insert')

	@classmethod
	async def findAll(cls,where = None,args = None,**kw):
		print('where====>%s'%where)


		sql = [cls.__select__]
		if where:
			sql.append('where')
			sql.append(where)
		if args is None:
			args = []
		orderBy = kw.get('orderBy',None)
		if orderBy:
			sql.append('order By')
			sql.append(orderBy)
		limit = kw.get('limit',None)
		if limit is not None:
			sql.append('limit')
			if isinstance(limit,int):
				sql.append('?')
				args.append(limit)
			elif isinstance(limit,tuple) and len(limit)==2:
				sql.append('?,?')
				args.extend(limit)
			else:
				raise ValueError('Invalid limit value:%s'% str(limit))
		rs = await select(' '.join(sql),args)
		return [cls(**r) for r in rs]

	@classmethod
	async def findNumber(cls,selectField,where = None,args = None):
		sql = ['select %s _num_ from `%s`' % (selectField, cls.__table__)]

		if where:
			sql.append('where')
			sql.append(where)

		# rs = await select(''.join(sql),args,1)
		rs = await select(' '.join(sql), args, 1)
		if len(rs) == 0:
			return None

		return rs[0]['_num_']



























