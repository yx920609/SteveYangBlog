import re, time, json, logging, hashlib, base64, asyncio

from Network import get, post

from AllTable import User, comment, Blog, next_id

from apis import  Page, APIError,APIValueError,APIResourceNotFoundError,APIPermissiondError



from aiohttp import web

from config_default import configs

_RE_EMAIL = re.compile(r'^[a-z0-9\.\-\_]+\@[a-z0-9\-\_]+(\.[a-z0-9\-\_]+){1,4}$')
_RE_SHA1 = re.compile(r'^[0-9a-f]{40}$')

COOKIE_NAME = 'awesession'
_COOKIE_KEY = configs['session']['secret']

def datetime_filter(t):
    delta = int(time.time() - t)
    logging.info('博客时间==========================>:%s'%delta)
    if delta < 60:
        return u'1分钟前'
    if delta < 3600:
        return u'%s分钟前' % (delta//60)
    if delta<86400:
        return u'%s小时前' % (delta//3600)
    if delta<604800:
        return u'%s天前' %(delta//86400)
    dt = datetime.fromtimestamp(t)
    return u'%s年%s月%s日' %(dt.year, dt.month, dt.day)

def user2cookie(user,max_age):
    expires = str(int(time.time()+max_age))
    s = '%s-%s-%s-%s' %(user.uuid,user.passwd,expires,_COOKIE_KEY)
    L = [user.uuid,expires,hashlib.sha1(s.encode('utf-8')).hexdigest()]
    return '-'.join(L)

def get_page_index(page_str):
    p = 1
    try:
        p = int(page_str)
    except Exception as e:
        logging.info(e.message)
    if p < 1:
        p = 1
    return p 


async def cookie2user(cookie_str):
    if not cookie_str:
        return None

    try:
        L = cookie_str.split('-')
        if len(L) != 3:
            return None
        uid,expires,shastr = L
        if int(expires)<time.time():
            return None
        user = await User.find(uid)
        if not user:
            return None
        s = '%s-%s-%s-%s' % (uid, user.passwd, expires, _COOKIE_KEY)
        if shastr != hashlib.sha1(s.encode('utf-8')).hexdigest():
            logging.info('valid cookie')
            return None
        user.passwd = '******'
        return user
    except Exception as e:
        logging.excepion(e)
        raise e

@get('/')
async def index(request):
    blogs = await Blog.findAll(orderBy='created_at desc')
    logging.info('indexUser=========>%s'% request.__user__)   
    return {
        '__template__':'blogs.html',
        'blogs':blogs,
        '__user__':request.__user__
    }

@get('/api/users')

async def api_get_users(*,page='1'):
    users = await User.findAll(orderBy='created_at desc' ,limit=(0,10))
    for u in users:
        u.passwd='******'
    return dict(users=users)

@post('/api/users')
async def api_regist(*,email,name,passwd):
    if not name or not name.strip():
        raise APIValueError('name')
    if not email:
        raise APIValueError('email')
    if not passwd:
        raise APIValueError('passwd')
    users = await User.findAll('email=?',[email])
    if len(users)>0:
        return APIError('email has exit')
    uid = next_id()

    user = User(uuid = uid,email = email,name=name.strip(),passwd=passwd,image = 'http://www.gravatar.com/avatar/')
    await user.save()

    r = web.Response()
    r.set_cookie(COOKIE_NAME, user2cookie(user, 86400), max_age=86400, httponly=True)
    user.passwd = '******'
    r.content_type = 'application/json'
    r.body = json.dumps(user, ensure_ascii=False).encode('utf-8')
    return r


@get('/regisit')
async def regisit():
    return{
        '__template__':'login.html',
        'login':0,

        'webtitle':'欢迎注册',
        'buttonName':'我要注册'
    }

@get('/signin')
async def signin():
    return{
        '__template__':'login.html',
        'login':1,
        'webtitle':'请登录',
        'buttonName':'我要登录'
    }

@post ('/signin')
async def login(*,email,passwd):
    user = await User.findAll( where='email=?',args = [email])
    if len(user)<1:
        return{
            'error':'no account',
            }
 
    else:

        logging.info('passwd================> %s' % passwd)
        if user[0]['passwd'] == passwd:
            r = web.Response()
            r.set_cookie(COOKIE_NAME,user2cookie(user[0],86400),max_age=86400,httponly = True)
            user[0].passwd = '******'
            r.content_type = 'application/json'
            r.body = json.dumps(user,ensure_ascii = False).encode('utf-8')
            return r
        else :

            return{
            'error':'mimacuowu',
            }
@get('/signout')
async def signout(request):
    # if request.__user__:
    #     r = web.Response()
    #     r.set_cookie(COOKIE_NAME,None)
    #     r.content_type = 
    referer = request.headers.get('Referer')
    r = web.HTTPFound('/')
    r.set_cookie(COOKIE_NAME,'-deleted',max_age =0,httponly=True)
    return r

@get('/edit')
def edit(request):
    return{
    '__template__':'edit.html',
    '__user__':request.__user__
    }



@post('/saveEdit')
async def saveEdit(*,name,summary,content,request):
    logging.info('save=======>')
    uid = next_id()
    user = request.__user__
    blog = Blog(uuid=uid, user_id=user.uuid ,user_name=user.name,user_image=user.image,name=name,summary=summary,content=content)
    await blog.save()
    r = web.Response()
    r.content_type = 'application/json'
    r.body = json.dumps(
    {'msg':'success'},ensure_ascii = True).encode('utf-8')
    return r

@get('/myblogs')
async def getMyblogs(*,page='1',request):
    user = request.__user__
    # r = await Blog.findAll('user_id=?',[user.uuid])

    return {
        '__template__':'myBlogs.html',
        '__user__':request.__user__,
        # 'blogs':r
        'page_index':get_page_index(page)
    }


@get('/api/blogs')
async def api_Blogs(*,page = '1'):
    page_index = get_page_index(page)
    num = await Blog.findNumber('count(uuid)')
    p = Page(num,page_index)
    if num == 0:
        return dict(page = p,blogs=())
    blogs = await Blog.findAll(orderBy= 'created_at desc',limit=(p.offset,p.limit))
    logging.info('blogs==============>%s' % blogs)
    return dict(page = p,blogs = blogs)

@get('/blog/{uuid}')
async def getDetailBlog(uuid,request):
    logging.info('uuid========>%s'% uuid)
    rs = await Blog.findAll('uuid=?',[uuid])

    logging.info('realBlog========>%s' % rs[0])
    blog = rs[0]
    # blog.created_at = app.datetime_filter(blog.created_at)
    return {
    '__template__':'blogDetail.html',
    'blog':blog,
    '__user__':request.__user__
    }

@post('/addConments')
async def saveComments(*,conments,blogId,request):
    logging.info('saveConments======>')
    uid = next_id()
    user = request.__user__
    conment = comment(uuid = uid,blog_id = blogId,user_id = user.uuid,user_name = user.name,user_image = user.image,content = conments )
    rs = await conment.save()
    r = web.Response()
    r.content_type = 'application/json'
    r.body = json.dumps({'msg':'success'},ensure_ascii = True).encode('utf-8')
    return r



@get('/allConments/{blog_uuid}')
async def getAllConmentsByBlogid(blog_uuid,request):
    logging.info('blog_uuid===>%s' % blog_uuid)
    result = await comment.findAll('blog_id=?',[blog_uuid])
    for temp in result:
        temp.created_at = datetime_filter(temp.created_at)
    rs = web.Response()
    rs.content_type = 'application/json'
    rs.body = json.dumps({'contents':result},ensure_ascii = False).encode('utf-8')
    return rs




















    



