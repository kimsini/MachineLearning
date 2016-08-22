#!/usr/bin/env python
#-*- coding: utf-8 -*-

# In[4]:

from collections import defaultdict
import imp
import sys
import telepot
import subprocess
from telepot.delegate import per_chat_id, create_open
from selenium import webdriver
from selenium.webdriver.support.ui import Select
from pymongo import MongoClient
from bs4 import BeautifulSoup
import urllib.request
import datetime
import time


#네이버 뉴스를 crawling 해서 딕셔너리 형태로 만드는 class
class news:

    #네이버 뉴스를 끌어와 beautifulSoup을 통해 원하는 element 뽑는 함수
    def make_soup(self,url = 'http://news.naver.com/main/ranking/popularDay.nhn?rankingType=popular_day'):
        html = urllib.request.urlopen(url)
        soup = BeautifulSoup(html,'lxml')
        rankings = soup.find_all('div',{'class' : "content"})
        return rankings[0]

    #정치,경제,IT 등 8가지 부문의 뉴스를 골라내는 함수
    def divide(self):
        tmp = []
        soup = self.make_soup()

        for i in range(0,8):
            tmp.append(soup.find_all('h4')[i].find_previous())
        return tmp

    # 8가지 부문의 5가지 핫 이슈의 링크를 뽑아내는 함수
    def links(self,html):
        links = ['http://news.naver.com%s'%w.get('href') for w in html.find_all('a',href = True)]
        return links[1:6]

    #각 부문의 5가지 핫이슈의 타이틀을 뽑아내는 함수
    def titles(self,html):
        fixed = ''
        titles = [ w.get('title') for w in html.find_all('a',href = True) if w.get('title') != None]

        for title in titles:
            i = titles.index(title)
            for dot in title:
                if dot == '.':
                    changed_title = title.replace('.','')
                else:
                    continue
                titles[i] = titles[i].replace(title,changed_title)

        return titles[1:6]

    #타이틀과 링크를 알맞게 묶어 현재 시간과 하나의 딕셔너리로 만드는 함수
    def make_dict(self):
        htmls = self.divide()
        tmp = []; date = datetime.datetime.now()
        today =[date.strftime("%y/%m/%d/%H:%M")]
        tmp.append([dict(zip(self.titles(r),self.links(r))) for r in htmls])
        dictionary = dict(zip(today,tmp))
        return tmp,dictionary


#오늘의 전반적인 날씨와 입력한 위치의 날씨를 crawling하는 class
class weather:

    #기상청에서 준 rss의 정보를 뽑는 함수
    def weather_data(self,data):

        hour = data[0].text
        temp = data[2].text
        pty = data[6].text #① 0 : 없음 ② 1 : 비 ③ 2 : 비/눈 ④ 3 : 눈/비 ⑤ 4 : 눈
        wf = data[7].text
        pop = data[9].text
        r12 = data[10].text
        s12 = data[11].text
        reh = data[16].text

        return hour,temp,pty,wf,pop,r12,s12,reh

    #자신의 위치의 날씨 데이터를 리턴하는 함수
    def weather_html(self,zone):

        html = urllib.request.urlopen("http://www.kma.go.kr/wid/queryDFSRSS.jsp?zone="+ zone)
        soup = BeautifulSoup(html, "lxml")

        today = soup.header.tm.text
        today_year = today[:4]
        today_month = today[4:6]
        today_day = today[6:8]
        today_time = today[8:10]

        today_data = [o for o in soup.find_all('day') if o.text == '0' or o.text == '1']
        today_data = [r.parent() for r in today_data]
        data = [ self.weather_data(o) for o in today_data]

        return data

    #몽고 DB에서 원하는 지역 코드를 가져오는 함수
    def zone_code(self):
        zone_codes = [];zone_names = []
        client = MongoClient()
        db = client.database
        cursors = db.locations.find()

        for zone in cursors:
            zone_codes.append(zone)
        for names in cursors:
            for name in names:
                zone_names.append(name)

        return zone_codes,zone_names

    #weatheri라는 홈페이지에서 오늘의 전반적인 날씨를 뽑아오는 함수
    def today_weather(self,url = 'http://www.weatheri.co.kr/forecast/forecast01.php?mNum=1&sNum=1'):

        html =  urllib.request.urlopen(url)
        naver_weather = urllib.request.urlopen('http://weather.naver.com/rgn/cityWetrMain.nhn')
        soup =  BeautifulSoup(html, "lxml")
        soup_naver = BeautifulSoup(naver_weather, "lxml")

        data = defaultdict(list); count = 0 ; keys = [] ; values = [] ; value = []; tds = [];text = []; before_12h = 0

        tds = soup.findAll("td")
        weather_table = soup.body.find('table',id='t1')
        rows = weather_table.find_all('tr')

        caution_table = weather_table.previousSibling.previousSibling
        caution_tr = caution_table.findAll('tr')[1]
        caution_td = [o.text.strip() for o in caution_tr.findAll('td')]
        caution = caution_td[0].split('\t')[-1]

        data["주의"] = caution

        del rows[0]

        for row in rows:
            for row_child in row.find_all('td'):
                if count == 0 and row_child.text.strip() != '':
                    keys.append(row_child.text.strip())
                    count = count + 1
                else:
                    value.append(row_child.text.strip())
            values.append(value)
            count = 0
            value = []

        for search in values:
            if '12h' in search:
                boundary = search.index('12h')
                before_12h = 1
                break
            else:
                continue

        for key,values in zip(keys,values):
            data[key].append(values)

        weather_li = soup_naver.body.findAll('li')
        weathers= [x.text for x in weather_li if x.attrs.get('class')==['nm']]

        if before_12h == 1:
            data['날씨'][0][:boundary+1] = [x.replace('',weathers[0]) for x in data['날씨'][0][:boundary+1]]
            data['날씨'][0][boundary+1:] = [x.replace('',weathers[1]) for x in data['날씨'][0][boundary+1:]]
        else:
            data['날씨'][0][:] = [x.replace('',weathers[1]) for x in data['날씨'][0][boundary+1:]]

        return data


# bot 만드는 클래스
class Bot(telepot.helper.ChatHandler,weather,news):
    YES = '1. OK'
    NO = '2. NO'
    MENU0 = '홈으로'
    MENU1 = '1. 날씨 검색'
    MENU1_1 = '지역 검색'
    MENU1_2 = '날씨 검색'
    MENU2 = '2. 현재 핫 뉴스 검색'
    MENU2_1 = '뉴스 검색'
    mode = ''

    # 메뉴 버튼 생성
    def menu(self):
        mode = ''
        show_keyboard = {'keyboard': [[self.MENU1], [self.MENU2], [self.MENU0]]}
        self.sender.sendMessage("안녕하세요. 메뉴를 선택해주세요.", reply_markup=show_keyboard)

    # 예 , 아니오 , 홈으로 버튼 생성
    def yes_or_no(self, comment):
        show_keyboard = {'keyboard': [[self.YES, self.NO], [self.MENU0]]}
        self.sender.sendMessage(comment, reply_markup=show_keyboard)

    #날씨 검색 시 지역 검색
    def get_keyword(self):
        self.mode = self.MENU1_1
        self.sender.sendMessage('지역을 검색하세요.')

    def get_category(self):
        self.mode = self.MENU2_1
        tmp = [['정치'],['경제'],['사회'],['생활/문화'],['세계'],['IT/과학'],['TV연예'],['스포츠']]

        show_keyboard = {'keyboard': self.put_menu_button(tmp)}
        self.sender.sendMessage('뉴스 카테고리를 아래에서 선택하세요.', reply_markup=show_keyboard)


    #유사 지역 검색 결과를 메뉴에 올림
    def put_menu_button(self, l):
        menulist = [self.MENU0]
        l.append(menulist)
        return l

    def get_location(self,keyword):
        self.mode = self.MENU1_2
        self.sender.sendMessage('검색중..')
        client = MongoClient()
        db = client.database

        tmp = []
        for location in db.locations.find({},{"name" : 1})[:]:
            if keyword in location['name']:
                tmp.append([location['name']])
        if not db.locations.find({},{"name" : 1 })[:]:
            self.sender.sendMessage('검색결과가 없습니다. 다시 입력하세요.')
            self.mode = self.MENU1_1
            return

        show_keyboard = {'keyboard': self.put_menu_button(tmp)}
        self.sender.sendMessage('아래에서 선택하세요.', reply_markup=show_keyboard)

    def clean(self,data):
        for title,url in zip(data.keys(),data.values()):
            msg = title+":"+url
            self.sender.sendMessage(msg)

    def show_news(self,category):
        self.mode = self.MENU2_1
        list_,dictionary = self.make_dict()
        if category == '정치':
            self.clean(list_[0][0])
        elif category == '경제':
            self.clean(list_[0][1])
        elif category == '사회':
            self.clean(list_[0][2])
        elif category == '생활/문화':
             self.clean(list_[0][3])
        elif category == '세계':
            self.clean(list_[0][4])
        elif category == 'IT/과학':
            self.clean(list_[0][5])
        elif category == 'TV연예':
            self.clean(list_[0][6])
        elif category == '스포츠':
            self.clean(list_[0][7])

    def show_weather(self,location):
        client = MongoClient()
        db = client.database
        zone = db.locations.find({"name":location})
        for code in zone:
            zone_code = code['value']
        data = self.weather_html(zone_code)
        self.sender.sendMessage(self.today_weather()['주의'])
        for words in data:
            msg = words[0] + '시 : \n'+ words[1]+'℃\n' +words[3]+'\n'+words[4]+'%의 강수확률\n' + words[7]+'%의 습도'
            self.sender.sendMessage(msg)

    def handle_command(self, command):
        if command == self.MENU0:
            self.menu()
        elif command == self.MENU1:
            self.get_keyword()
        elif command == self.MENU2:
            self.get_category()
        elif self.mode == self.MENU1_1:  # Get location
            self.get_location(command)
        elif self.mode == self.MENU1_2:
            self.show_weather(command)
        elif self.mode == self.MENU2_1 or command in CTG:
            self.show_news(command)

    def on_message(self, msg):
        content_type, chat_type, chat_id = telepot.glance(msg)
        # Check ID
        if not str(chat_id) in VALID_USERS:
            print("Permission Denied")
            return

        if content_type is 'text':
            self.handle_command(msg['text'])
            return

        print("E")
        self.sender.sendMessage('인식하지 못했습니다')

    def on_close(self, exception):
        pass

def getConfig():
    global TOKEN
    global VALID_USERS
    global CTG
    TOKEN = ''
    VALID_USERS = ''
    CTG = ['정치','경제','사회','생활/문화','세계','IT/과학','TV연예','스포츠']

getConfig()
bot = telepot.DelegatorBot(TOKEN, [
(per_chat_id(), create_open(Bot, timeout=10)),])
bot.setWebhook()
bot.message_loop(run_forever=True)
