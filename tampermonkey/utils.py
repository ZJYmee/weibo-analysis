#!/usr/bin/env python
# -*- coding: UTF-8 -*-

import codecs
import csv
import json
import math
import os
import random
import sys
import traceback
from collections import OrderedDict
from datetime import datetime, timedelta
from time import sleep

import requests
from lxml import etree
from requests.adapters import HTTPAdapter
from tqdm import tqdm

import nltk
from nltk.corpus import stopwords
from gensim import corpora
from gensim.models import LdaModel
import string
import jieba
import pandas as pd
import matplotlib.pyplot as plt
from wordcloud import WordCloud


class Weibo(object):
    def __init__(self,
                 filter=0,
                 since_date='1900-01-01',
                 mongodb_write=0,
                 mysql_write=0,
                 pic_download=0,
                 video_download=0):
        """Weibo类初始化"""
        if filter != 0 and filter != 1:
            sys.exit(u'filter值应为数字0或1,请重新输入')
        if not self.is_date(since_date):
            sys.exit(u'since_date值应为yyyy-mm-dd形式,请重新输入')
        if mongodb_write != 0 and mongodb_write != 1:
            sys.exit(u'mongodb_write值应为0或1,请重新输入')
        if mysql_write != 0 and mysql_write != 1:
            sys.exit(u'mysql_write值应为0或1,请重新输入')
        if pic_download != 0 and pic_download != 1:
            sys.exit(u'pic_download值应为数字0或1,请重新输入')
        if video_download != 0 and video_download != 1:
            sys.exit(u'video_download值应为0或1,请重新输入')
        self.user_id = ''  # 用户id,如昵称为"Dear-迪丽热巴"的id为'1669879400'
        self.filter = filter  # 取值范围为0、1,程序默认值为0,代表要爬取用户的全部微博,1代表只爬取用户的原创微博
        self.since_date = since_date  # 起始时间，即爬取发布日期从该值到现在的微博，形式为yyyy-mm-dd
        self.mongodb_write = mongodb_write  # 值为0代表不将结果写入MongoDB数据库,1代表写入
        self.mysql_write = mysql_write  # 值为0代表不将结果写入MySQL数据库,1代表写入
        self.pic_download = pic_download  # 取值范围为0、1,程序默认值为0,代表不下载微博原始图片,1代表下载
        self.video_download = video_download  # 取值范围为0、1,程序默认为0,代表不下载微博视频,1代表下载
        self.weibo = []  # 存储爬取到的所有微博信息
        self.user = {}  # 存储目标微博用户信息
        self.got_count = 0  # 爬取到的微博数
        self.weibo_id_list = []  # 存储爬取到的所有微博id
        self.mysql_config = {
        }  # MySQL数据库连接配置，可以不填，当使用者的mysql用户名、密码等与本程序默认值不同时，需要通过mysql_config来自定义

    def is_date(self, since_date):
        """判断日期格式是否正确"""
        try:
            datetime.strptime(since_date, "%Y-%m-%d")
            return True
        except ValueError:
            return False

    def get_json(self, params):
        """获取网页中json数据"""
        url = 'https://m.weibo.cn/api/container/getIndex?'
        r = requests.get(url, params=params)
        return r.json()

    def get_weibo_json(self, page):
        """获取网页中微博json数据"""
        params = {'containerid': '107603' + str(self.user_id), 'page': page}
        js = self.get_json(params)
        return js

    def convert_weibo_number(self, num_input):
        """处理多种输入类型：int/float/str"""
        # 统一转换为字符串处理
        num_str = str(num_input).strip().replace(',', '')
        
        units = {'万': 10000, '亿': 100000000, 'w': 10000, 'm': 1000000}
        for unit in units:
            if unit in num_str:
                number_part = num_str.split(unit)[0]
                return int(float(number_part) * units[unit])
        
        try:
            return int(num_str)
        except ValueError:
            try:  # 处理浮点数情况
                return int(float(num_str))
            except:
                return 0
    
    def get_user_info(self):
        """获取用户信息"""
        params = {'containerid': '100505' + str(self.user_id)}
        js = self.get_json(params)
        if js['ok']:
            info = js['data']['userInfo']
            user_info = {}
            user_info['id'] = self.user_id
            user_info['screen_name'] = info.get('screen_name', '')
            user_info['gender'] = info.get('gender', '')
            user_info['statuses_count'] = info.get('statuses_count', 0)
            user_info['followers_count'] = self.convert_weibo_number(info.get('followers_count', 0))
            user_info['follow_count'] = self.convert_weibo_number(info.get('follow_count', 0))
            user_info['description'] = info.get('description', '')
            user_info['profile_url'] = info.get('profile_url', '')
            user_info['profile_image_url'] = info.get('profile_image_url', '')
            user_info['avatar_hd'] = info.get('avatar_hd', '')
            user_info['urank'] = info.get('urank', 0)
            user_info['mbrank'] = info.get('mbrank', 0)
            user_info['verified'] = info.get('verified', False)
            user_info['verified_type'] = info.get('verified_type', 0)
            user_info['verified_reason'] = info.get('verified_reason', '')
            user = self.standardize_info(user_info)
            self.user = user
            return user

    def get_long_weibo(self, id):
        """获取长微博"""
        url = 'https://m.weibo.cn/detail/%s' % id
        html = requests.get(url).text
        html = html[html.find('"status":'):]
        html = html[:html.rfind('"hotScheme"')]
        html = html[:html.rfind(',')]
        html = '{' + html + '}'
        js = json.loads(html, strict=False)
        weibo_info = js.get('status')
        if weibo_info:
            weibo = self.parse_weibo(weibo_info)
            return weibo

    def get_pics(self, weibo_info):
        """获取微博原始图片url"""
        if weibo_info.get('pics'):
            pic_info = weibo_info['pics']
            pic_list = [pic['large']['url'] for pic in pic_info]
            pics = ','.join(pic_list)
        else:
            pics = ''
        return pics

    def get_video_url(self, weibo_info):
        """获取微博视频url"""
        video_url = ''
        if weibo_info.get('page_info'):
            if weibo_info['page_info'].get('media_info'):
                media_info = weibo_info['page_info']['media_info']
                video_url = media_info.get('mp4_720p_mp4')
                if not video_url:
                    video_url = media_info.get('mp4_hd_url')
                    if not video_url:
                        video_url = media_info.get('mp4_sd_url')
                        if not video_url:
                            video_url = ''
        return video_url


    def get_location(self, selector):
        """获取微博发布位置"""
        location_icon = 'timeline_card_small_location_default.png'
        span_list = selector.xpath('//span')
        location = ''
        for i, span in enumerate(span_list):
            if span.xpath('img/@src'):
                if location_icon in span.xpath('img/@src')[0]:
                    location = span_list[i + 1].xpath('string(.)')
                    break
        return location

    def get_topics(self, selector):
        """获取参与的微博话题"""
        span_list = selector.xpath("//span[@class='surl-text']")
        topics = ''
        topic_list = []
        for span in span_list:
            text = span.xpath('string(.)')
            if len(text) > 2 and text[0] == '#' and text[-1] == '#':
                topic_list.append(text[1:-1])
        if topic_list:
            topics = ','.join(topic_list)
        return topics

    def get_at_users(self, selector):
        """获取@用户"""
        a_list = selector.xpath('//a')
        at_users = ''
        at_list = []
        for a in a_list:
            if '@' + a.xpath('@href')[0][3:] == a.xpath('string(.)'):
                at_list.append(a.xpath('string(.)')[1:])
        if at_list:
            at_users = ','.join(at_list)
        return at_users
    
    def string_to_int(self, string):
        """字符串转换为整数"""
        if isinstance(string, int):
            return string
        elif string.endswith(u'万+'):
            string = int(string[:-2] + '0000')
        elif string.endswith(u'万'):
            string = int(string[:-1] + '0000')
        return int(string)

    def standardize_date(self, created_at):
        """处理多种时间格式"""
        # 格式1: Sat Jan 14 00:38:21 +0800 2012
        try:
            dt = datetime.strptime(created_at, '%a %b %d %H:%M:%S %z %Y')
            return dt.strftime("%Y-%m-%d")
        except ValueError:
            pass
        
        # 格式2: 中文时间（保留原有处理逻辑）
        if u"刚刚" in created_at:
            return datetime.now().strftime("%Y-%m-%d")
        elif u"分钟" in created_at:
            minute = int(created_at[:created_at.find(u"分钟")])
            delta = timedelta(minutes=minute)
            return (datetime.now() - delta).strftime("%Y-%m-%d")
        elif u"小时" in created_at:
            hour = int(created_at[:created_at.find(u"小时")])
            delta = timedelta(hours=hour)
            return (datetime.now() - delta).strftime("%Y-%m-%d")
        elif u"昨天" in created_at:
            delta = timedelta(days=1)
            return (datetime.now() - delta).strftime("%Y-%m-%d")
        else:
            # 其他格式尝试截取前10位
            return created_at[:10] if len(created_at) >=10 else '1970-01-01'

    def standardize_info(self, weibo):
        """标准化信息，去除乱码"""
        for k, v in weibo.items():
            if 'int' not in str(type(v)) and 'long' not in str(
                    type(v)) and 'bool' not in str(type(v)):
                weibo[k] = v.replace(u"\u200b", "").encode(
                    sys.stdout.encoding, "ignore").decode(sys.stdout.encoding)
        return weibo

    def parse_weibo(self, weibo_info):
        weibo = OrderedDict()
        if weibo_info['user']:
            weibo['user_id'] = weibo_info['user']['id']
            weibo['screen_name'] = weibo_info['user']['screen_name']
        else:
            weibo['user_id'] = ''
            weibo['screen_name'] = ''
        weibo['id'] = int(weibo_info['id'])
        weibo['bid'] = weibo_info['bid']
        text_body = weibo_info['text']
        selector = etree.HTML(text_body)
        weibo['text'] = etree.HTML(text_body).xpath('string(.)')
        weibo['pics'] = self.get_pics(weibo_info)
        weibo['video_url'] = self.get_video_url(weibo_info)
        weibo['location'] = self.get_location(selector)
        weibo['created_at'] = self.standardize_date(weibo_info['created_at'])
        weibo['source'] = weibo_info['source']
        weibo['attitudes_count'] = self.string_to_int(
            weibo_info['attitudes_count'])
        weibo['comments_count'] = self.string_to_int(
            weibo_info['comments_count'])
        weibo['reposts_count'] = self.string_to_int(
            weibo_info['reposts_count'])
        weibo['topics'] = self.get_topics(selector)
        weibo['at_users'] = self.get_at_users(selector)
        return self.standardize_info(weibo)

    def print_user_info(self):
        """打印用户信息"""
        print('+' * 100)
        print(u'用户信息')
        print(u'用户id：%s' % self.user['id'])
        print(u'用户昵称：%s' % self.user['screen_name'])
        gender = u'女' if self.user['gender'] == 'f' else u'男'
        print(u'性别：%s' % gender)
        print(u'微博数：%d' % self.user['statuses_count'])
        print(u'粉丝数：%d' % self.user['followers_count'])
        print(u'关注数：%d' % self.user['follow_count'])
        if self.user.get('verified_reason'):
            print(self.user['verified_reason'])
        print(self.user['description'])
        print('+' * 100)

    def print_one_weibo(self, weibo):
        """打印一条微博"""
        print(u'微博id：%d' % weibo['id'])
        print(u'微博正文：%s' % weibo['text'])
        print(u'原始图片url：%s' % weibo['pics'])
        print(u'微博位置：%s' % weibo['location'])
        print(u'发布时间：%s' % weibo['created_at'])
        print(u'发布工具：%s' % weibo['source'])
        print(u'点赞数：%d' % weibo['attitudes_count'])
        print(u'评论数：%d' % weibo['comments_count'])
        print(u'转发数：%d' % weibo['reposts_count'])
        print(u'话题：%s' % weibo['topics'])
        print(u'@用户：%s' % weibo['at_users'])

    def print_weibo(self, weibo):
        """打印微博，若为转发微博，会同时打印原创和转发部分"""
        if weibo.get('retweet'):
            print('*' * 100)
            print(u'转发部分：')
            self.print_one_weibo(weibo['retweet'])
            print('*' * 100)
            print(u'原创部分：')
        self.print_one_weibo(weibo)
        print('-' * 120)

    def get_one_weibo(self, info):
        """获取一条微博的全部信息"""
        try:
            weibo_info = info['mblog']
            weibo_id = weibo_info['id']
            retweeted_status = weibo_info.get('retweeted_status')
            is_long = weibo_info['isLongText']
            if retweeted_status:  # 转发
                retweet_id = retweeted_status['id']
                is_long_retweet = retweeted_status['isLongText']
                if is_long:
                    weibo = self.get_long_weibo(weibo_id)
                    if not weibo:
                        weibo = self.parse_weibo(weibo_info)
                else:
                    weibo = self.parse_weibo(weibo_info)
                if is_long_retweet:
                    retweet = self.get_long_weibo(retweet_id)
                    if not retweet:
                        retweet = self.parse_weibo(retweeted_status)
                else:
                    retweet = self.parse_weibo(retweeted_status)
                retweet['created_at'] = self.standardize_date(
                    retweeted_status['created_at'])
                weibo['retweet'] = retweet
            else:  # 原创
                if is_long:
                    weibo = self.get_long_weibo(weibo_id)
                    if not weibo:
                        weibo = self.parse_weibo(weibo_info)
                else:
                    weibo = self.parse_weibo(weibo_info)
            weibo['created_at'] = self.standardize_date(
                weibo_info['created_at'])
            return weibo
        except Exception as e:
            print("Error: ", e)
            traceback.print_exc()

    def is_pinned_weibo(self, info):
        """判断微博是否为置顶微博"""
        weibo_info = info['mblog']
        title = weibo_info.get('title')
        if title and title.get('text') == u'置顶':
            return True
        else:
            return False

    def get_one_page(self, page):
        """获取一页的全部微博"""
        try:
            js = self.get_weibo_json(page)
            if js['ok']:
                weibos = js['data']['cards']
                for w in weibos:
                    if w['card_type'] == 9:
                        wb = self.get_one_weibo(w)
                        if wb:
                            if wb['id'] in self.weibo_id_list:
                                continue
                            created_at = datetime.strptime(
                                wb['created_at'], "%Y-%m-%d")
                            since_date = datetime.strptime(
                                self.since_date, "%Y-%m-%d")
                            if created_at < since_date:
                                if self.is_pinned_weibo(w):
                                    continue
                                else:
                                    return True
                            if (not self.filter) or (
                                    'retweet' not in wb.keys()):
                                self.weibo.append(wb)
                                self.weibo_id_list.append(wb['id'])
                                self.got_count = self.got_count + 1
                                self.print_weibo(wb)
        except Exception as e:
            print("Error: ", e)
            traceback.print_exc()

    def get_page_count(self):
        """获取微博页数"""
        weibo_count = self.user['statuses_count']
        page_count = int(math.ceil(weibo_count / 10.0))
        return page_count

    def get_write_info(self, wrote_count):
        """获取要写入的微博信息"""
        write_info = []
        for w in self.weibo[wrote_count:]:
            wb = OrderedDict()
            for k, v in w.items():
                if k not in ['user_id', 'screen_name', 'retweet']:
                    if 'unicode' in str(type(v)):
                        v = v.encode('utf-8')
                    wb[k] = v
            if not self.filter:
                if w.get('retweet'):
                    wb['is_original'] = False
                    for k2, v2 in w['retweet'].items():
                        if 'unicode' in str(type(v2)):
                            v2 = v2.encode('utf-8')
                        wb['retweet_' + k2] = v2
                else:
                    wb['is_original'] = True
            write_info.append(wb)
        return write_info

    def get_filepath(self, type):
        """获取结果文件路径"""
        try:
            file_dir = os.path.split(
                os.path.realpath(__file__)
            )[0] + os.sep + 'weibo' + os.sep + self.user['screen_name']
            if type == 'img' or type == 'video':
                file_dir = file_dir + os.sep + type
            if not os.path.isdir(file_dir):
                os.makedirs(file_dir)
            if type == 'img' or type == 'video':
                return file_dir
            file_path = file_dir + os.sep + self.user_id + '.' + type
            return file_path
        except Exception as e:
            print('Error: ', e)
            traceback.print_exc()

    def get_result_headers(self):
        """获取要写入结果文件的表头"""
        result_headers = [
            'id', 'bid', '正文', '原始图片url', '视频url', '位置', '日期', '工具', '点赞数',
            '评论数', '转发数', '话题', '@用户'
        ]
        if not self.filter:
            result_headers2 = ['是否原创', '源用户id', '源用户昵称']
            result_headers3 = ['源微博' + r for r in result_headers]
            result_headers = result_headers + result_headers2 + result_headers3
        return result_headers

    def write_csv(self, wrote_count):
        """将爬到的信息写入csv文件"""
        write_info = self.get_write_info(wrote_count)
        result_headers = self.get_result_headers()
        result_data = [w.values() for w in write_info]
        if sys.version < '3':  # python2.x
            with open(self.get_filepath('csv'), 'ab') as f:
                f.write(codecs.BOM_UTF8)
                writer = csv.writer(f)
                if wrote_count == 0:
                    writer.writerows([result_headers])
                writer.writerows(result_data)
        else:  # python3.x
            with open(self.get_filepath('csv'),
                      'a',
                      encoding='utf-8-sig',
                      newline='') as f:
                writer = csv.writer(f)
                if wrote_count == 0:
                    writer.writerows([result_headers])
                writer.writerows(result_data)
        print(u'%d条微博写入csv文件完毕,保存路径:' % self.got_count)
        print(self.get_filepath('csv'))



    def write_data(self, wrote_count):
        """将爬到的信息写入文件或数据库"""
        if self.got_count > wrote_count:
            self.write_csv(wrote_count)

    def get_pages(self):
        """获取全部微博"""
        self.get_user_info()
        page_count = self.get_page_count()
        wrote_count = 0
        self.print_user_info()
        page1 = 0
        random_pages = random.randint(1, 5)
        for page in tqdm(range(1, page_count + 1), desc='Progress'):
            print(u'第%d页' % page)
            is_end = self.get_one_page(page)
            if is_end:
                break

            if page % 20 == 0:  # 每爬20页写入一次文件
                self.write_data(wrote_count)
                wrote_count = self.got_count

            # 通过加入随机等待避免被限制。爬虫速度过快容易被系统限制(一段时间后限
            # 制会自动解除)，加入随机等待模拟人的操作，可降低被系统限制的风险。默
            # 认是每爬取1到5页随机等待6到10秒，如果仍然被限，可适当增加sleep时间
            if page - page1 == random_pages and page < page_count:
                sleep(random.randint(6, 10))
                page1 = page
                random_pages = random.randint(1, 5)

        self.write_data(wrote_count)  # 将剩余不足20页的微博写入文件
        print(u'微博爬取完成，共爬取%d条微博' % self.got_count)

    def get_user_list(self, file_name):
        """获取文件中的微博id信息"""
        with open(file_name, 'rb') as f:
            lines = f.read().splitlines()
            lines = [line.decode('utf-8') for line in lines]
            user_id_list = [
                line.split(' ')[0] for line in lines
                if len(line.split(' ')) > 0 and line.split(' ')[0].isdigit()
            ]
        return user_id_list

    def initialize_info(self, user_id):
        """初始化爬虫信息"""
        self.weibo = []
        self.user = {}
        self.got_count = 0
        self.user_id = user_id
        self.weibo_id_list = []

    def start(self, user_id_list):
        """运行爬虫"""
        try:
            for user_id in user_id_list:
                self.initialize_info(user_id)
                self.get_pages()
                print(u'信息抓取完毕')
                print('*' * 100)
                if self.pic_download == 1:
                    self.download_files('img')
                if self.video_download == 1:
                    self.download_files('video')
        except Exception as e:
            print('Error: ', e)
            traceback.print_exc()

def get_str_with_id(id):
    try:
        # 以下是程序配置信息，可以根据自己需求修改
        filter = 1  # 值为0表示爬取全部微博（原创微博+转发微博），值为1表示只爬取原创微博
        since_date = '2025-01-01'  # 起始时间，即爬取发布日期从该值到现在的微博，形式为yyyy-mm-dd
        """mongodb_write值为0代表不将结果写入MongoDB数据库,1代表写入；若要写入MongoDB数据库，
        请先安装MongoDB数据库和pymongo，pymongo安装方法为命令行运行:pip install pymongo"""
        mongodb_write = 0
        """mysql_write值为0代表不将结果写入MySQL数据库,1代表写入;若要写入MySQL数据库，
        请先安装MySQL数据库和pymysql，pymysql安装方法为命令行运行:pip install pymysql"""
        mysql_write = 0
        pic_download = 0 # 值为0代表不下载微博原始图片,1代表下载微博原始图片
        video_download = 0  # 值为0代表不下载微博视频,1代表下载微博视频

        wb = Weibo(filter, since_date, mongodb_write, mysql_write,
                   pic_download, video_download)

        # 下面是自定义MySQL数据库连接配置(可选)
        """因为操作MySQL数据库需要用户名、密码等参数，本程序默认为:
        mysql_config = {
            'host': 'localhost',
            'port': 3306,
            'user': 'root',
            'password': '123456',
            'charset': 'utf8mb4'
        }
        大家的参数配置如果和默认值不同，可以将上面的参数值替换成自己的，
        然后添加如下代码，使修改生效，如果你的参数和默认值相同则不需要下面的代码:
        wb.change_mysql_config(mysql_config)"""

        # 下面是配置user_id_list
        """user_id_list包含了要爬的目标微博id，可以是一个，也可以是多个，也可以从文件中读取
        爬单个微博，user_id_list如下所示，可以改成任意合法的用户id
        user_id_list = ['1669879400']
        爬多个微博，user_id_list如下所示，可以改成任意合法的用户id
        user_id_list = ['1669879400', '1729370543']
        也可以在文件中读取user_id_list，文件中可以包含很多user_id，
        每个user_id占一行，也可以在user_id后面加注释，如用户昵称，user_id和注释之间必需要有空格，
        文件名任意，类型为txt，位置位于本程序的同目录下，文件内容可以为如下形式：
        1223178222 胡歌
        1669879400 迪丽热巴
        1729370543 郭碧婷
        比如文件可以叫user_id_list.txt，读取文件中的user_id_list如下所示:
        user_id_list = wb.get_user_list('user_id_list.txt')"""
        user_id_list = [f'{str(id)}']

        wb.start(user_id_list)
    except Exception as e:
        print('Error: ', e)
        traceback.print_exc()

def generate_topic_pic(id):
    def find_specific_csv(target_filename, search_dir="./weibo"):
        """
        在指定目录及其子目录中查找特定名称的CSV文件
        
        :param target_filename: 目标文件名（如 "101.csv"）
        :param search_dir: 搜索的根目录，默认为 "./weibo"
        :return: 匹配文件的完整路径列表
        """
        matched_files = []
        
        for root, _, files in os.walk(search_dir):
            for file in files:
                if file == target_filename:
                    matched_files.append(os.path.join(root, file))
        
        return matched_files
    def load_stopwords(file_path):
        with open(file_path, 'r', encoding='utf-8') as f:
            stopwords = set(line.strip() for line in f if line.strip())
        return stopwords

    # 文本预处理
    def preprocess(text, stopwords):
        # 使用 jieba 分词
        tokens = jieba.lcut(text)
        # 去除停用词和空格
        tokens = [word for word in tokens if word not in stopwords and len(word.strip()) > 0]
        return tokens

    # 下载nltk的停用词表（如果尚未下载）
    nltk.download('stopwords')

    # 读取 CSV 文件并提取 '正文' 列
    csv_file = find_specific_csv(f'{id}.csv') # 替换为你的 CSV 文件路径
    df = pd.read_csv(csv_file[0])

    # 检查是否包含 '正文' 列
    if '正文' not in df.columns:
        raise ValueError("CSV 文件中缺少 '正文' 列")

    # 提取 '正文' 列作为文档集合
    documents = df['正文'].dropna().tolist()  # 去除空值并转换为列表

    # 加载停用词表
    stopwords_file = "stopwords_full.txt"  # 停用词文件路径
    stopwords = load_stopwords(stopwords_file)

    # 对文档进行预处理
    processed_docs = [preprocess(doc, stopwords) for doc in documents]

    # 创建词典和语料库
    dictionary = corpora.Dictionary(processed_docs)
    corpus = [dictionary.doc2bow(doc) for doc in processed_docs]

    # 训练LDA模型
    num_topics = 10  # 设置主题数量
    lda_model = LdaModel(corpus, num_topics=num_topics, id2word=dictionary, passes=50)



    # 输出每个主题的关键词
    #print("每个主题的关键词：")
    topics = lda_model.print_topics(num_words=5)  # 每个主题显示5个关键词
    #for topic in topics:
    #    print(topic)

    for topic_id in range(num_topics):
        print(f"\n主题 {topic_id} 的关键词：{topics[topic_id][1]}")  # 输出主题的关键词
        
        # 获取每条文档的主题分布
        topic_documents = []
        for i, doc_bow in enumerate(corpus):
            topic_distribution = lda_model.get_document_topics(doc_bow, minimum_probability=0.01)
            # 找到当前文档在当前主题上的概率
            topic_prob = dict(topic_distribution).get(topic_id, 0)
            topic_documents.append((i, topic_prob))  # (文档索引, 主题概率)
        
        # 按主题概率降序排序
        topic_documents.sort(key=lambda x: x[1], reverse=True)

        print(f"主题 {topic_id} 的典型文本：")
        # 输出最多 3 条典型文本
        count = 0
        for doc_index, prob in topic_documents:
            if prob > 0:  # 只输出有概率的文档
                if count < 3:  # 最多输出 3 条
                    print(f"微博 {doc_index+1}：{documents[doc_index]}")
                count += 1
        print(f"主题 {topic_id} 相关的微博条数：{count}")


    # 对所有文档进行预处理并合并成一个字符串
    all_tokens = []
    for doc in documents:
        tokens = preprocess(doc, stopwords)
        all_tokens.extend(tokens)

    # 将所有词语组合成一个大字符串
    text = ' '.join(all_tokens)

    # 生成词云图
    wordcloud = WordCloud(font_path='simhei.ttf',  # 设置字体路径，支持中文
                        width=800, height=400,  # 设置图片大小
                        background_color='white',  # 背景颜色
                        max_words=100,  # 显示的最大单词数量
                        contour_width=3, contour_color='steelblue').generate(text)

    # 显示词云图
    plt.figure(figsize=(10, 5))
    plt.imshow(wordcloud, interpolation='bilinear')
    plt.axis('off')  # 不显示坐标轴
    plt.title(f"{id}")
    plt.savefig(f"./pic/{id}.png", dpi=300, bbox_inches='tight')  # 保存词云图


if __name__ == '__main__':
    generate_topic_pic(1669879400)
