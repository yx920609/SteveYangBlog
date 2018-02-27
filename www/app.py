#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import logging;logging.basicConfig(level=logging.INFO)
import asyncio,os,json,time
import Network,AllDataBase
from Network import add_routes,add_static
from datetime import datetime
from aiohttp import web
from AllTable import User,Blog,comment
from flask import render_template,Flask
from jinja2 import Environment,FileSystemLoader
from handles import cookie2user, COOKIE_NAME


def init_jinja2(app,**kw):
	logging.info('init jinja2...')
	options = dict(
		autoescape = kw.get('autoescape',True),
		block_start_string = kw.get('block_start_string','{%'),
		block_end_string = kw.get('block_end_string','%}'),
		variable_start_string = kw.get('variable_start_string', '{{'),
		variable_end_string = kw.get('variable_end_string','}}'),
		auto_reload = kw.get('auto_reload',True)

	)

	path = kw.get('path',None)
	if path is None:
		path = os.path.join(os.path.dirname(os.path.abspath(__file__)),'templates')

	logging.info('set jinja2 template path:%s'%path)
	env = Environment(loader=FileSystemLoader(path), **options)
	filters = kw.get('filters', None)
	if filters is not None:
		for name,f in filters.items():
			env.filters[name] = f

	app['__templating__'] = env

async def logger_factory(app, handler):
	async def logger(request):
		logging.info('Request: %s %s' % (request.method, request.path))
        # await asyncio.sleep(0.3)
		return (await handler(request))
	return logger

async def auth_factory(app,handler):
	async def auth(request):
		logging.info('check user:%s %s' % (request.method,request.path))
		request.__user__ = None
		cookie_str = request.cookies.get(COOKIE_NAME)
		if cookie_str:
			logging.info('cookies:==============>%s' % cookie_str)
			user = await cookie2user(cookie_str)
			logging.info ('cookie user========>%s' % user)
			request.__user__ = user
			if user:
				logging.info('set currunt user :%s' % user.email)
		if request.path.startswith('/manage/') and (request.__user__ is None or not request.__user__.admin):
			return web.HTTPFound('/signin')
		return (await handler(request))
	return auth


async def data_factory(app, handler):
	async def parse_data(request):
		if request.method == 'POST':
			if request.content_type.startswith('application/json'):
				request.__data__ = await request.json()
				logging.info('request json: %s' % str(request.__data__))
			elif request.content_type.startswith('application/x-www-form-urlencoded'):
				request.__data__ = await request.post()
				logging.info('request form: %s' % str(request.__data__))
		return (await handler(request))
	return parse_data

async def response_factory(app,handler):
	async def response(request):

		r = await handler(request)

		if isinstance(r,web.StreamResponse):
			logging.info('webresponse:===========>%s' % r)

			return r
		if isinstance(r,bytes):
			logging.info('bytes:===========>%s' % r)

			resp = web.Response(body = r)
			resp.content_type = 'application/octet-stream'
			return resp
		if isinstance(r,str):
			logging.info('str:===========>%s' % r)

			if r.startswith('redirect:'):
				return web.HTTPFound(r[9:])
			resp = web.Response(body=r.encode('utf-8'))
			resp.content_type = 'text/html;charset=utf-8'
			return resp
		if isinstance(r,dict):
			print('字典:%s' % r)
			template = r.get('__template__')
			
			if template is None:
				resp = web.Response(body=json.dumps(r, ensure_ascii=False, default=lambda o: o.__dict__).encode('utf-8'))
				resp.content_type = 'application/json;charset=utf-8'
				return resp
			else:
				resp = web.Response(body=app['__templating__'].get_template(template).render(**r).encode('utf-8'))
				resp.content_type = 'text/html;charset=utf-8'
				return resp

		if isinstance(r,int) and r>= 100 and r < 600:
			logging.info('int:===========>%s' % r)

			return web.Response(r)
		if isinstance(r, tuple) and len(r) == 2:
			logging.info('tuple:===========>%s' % r)
			t, m = r
			if isinstance(t, int) and t >= 100 and t < 600:
				return web.Response(t, str(m))
		resp = web.Response(body=str(r).encode('utf-8'))
		resp.content_type = 'text/plain;charset=utf-8'
		return resp
	return response

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



async def init(loop):
	await AllDataBase.create_pool(loop = loop , user ='root',password ='920609',database ='awesome')
	app = web.Application(loop=loop,middlewares=[
			logger_factory,auth_factory,response_factory
		])
	init_jinja2(app,filters=dict(datetime=datetime_filter))
	add_routes(app,'handles')
	add_static(app)
	srv = await loop.create_server(app.make_handler(),'127.0.0.1',9000)
	logging.info('server started at http://127.0.0.1:9000...')
	return srv


loop = asyncio.get_event_loop()
loop.run_until_complete(init(loop))
loop.run_forever()