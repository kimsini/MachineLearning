
# coding: utf-8

# In[4]:

# 이 스크립트는 전국의 zone code를 저장하기 위함이므로 단 한 번만 실행 후 DB에 저장한다.
# 그리고 zone code를 통해 날씨를 알고 싶을 때 DB에서 지역을 검색하여 zone code를 추출한다.


from bs4 import BeautifulSoup
import urllib.request
from selenium import webdriver
from selenium.webdriver.support.ui import Select
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
import time
from pymongo import MongoClient

#PhantomJS 드라이버를 통해 빠른 웹 자동화 
driver = webdriver.PhantomJS('C:\Users\llewyn\phantomjs\bin\phantomjs.exe')
driver.get('http://www.kma.go.kr/weather/lifenindustry/sevice_rss.jsp')

#seletion과 search 의 xpath 를 변수에 저장
selection1, search1 = './/*[@id="search_area"]','.//*[@id="content_weather"]/table[1]/tbody/tr/td[1]/form/fieldset/input[1]'
selection2, search2 = './/*[@id="search_area2"]','.//*[@id="content_weather"]/table[1]/tbody/tr/td[1]/form/fieldset/input[2]'
selection_id3 = "search_area3"        

#기상청 홈페이지의 지역 선택 옵션을 하나 하나 눌러서 전국의 zone code를 crawling하는 클래스
class Scraping:
    
    #xpath를 미리 설정
    def __init__(self,select_xpath1,search_xpath1,select_xpath2,search_xpath2):
        
        self.search_xpath1 = search_xpath1
        self.select_xpath1 = select_xpath1
        
        self.search_xpath2 = search_xpath2
        self.select_xpath2 = select_xpath2
    
    #마지막 select의 zonecode를 모두 가져오는 함수
    def select_areas(self,select_id):
    
        html = driver.page_source
        soup = BeautifulSoup(html,"lxml")
        select =  soup.find_all('select',{'id': select_id})

        return select
    
    #데이터 정리하는 함수
    def clean(self,selects):
        names=[] ; values = []
        
        for select in selects:
            names.extend([r.text.strip() for r in select.contents if r != '\n'])
            values.extend([r.attrs.get("value") for r in select.contents if r != '\n'])
            
        return names,values
    
    #selection을 하나하나 클릭해가면서 모든 zonecode를 가져오는 함수
    def selections_scrap(self,select_id):
        
        select1 = Select(driver.find_element_by_xpath(self.select_xpath1))
        option1_len = len(select1.options)
        options1_xpaths = ['.//*[@id="search_area"]/option[%s]'%o for o in range(1,option1_len+1)]
        button1 = driver.find_element_by_xpath(self.search_xpath1)
        
        option2_select_ids = []
        

        for option1_xpath in options1_xpaths:               

            option1 = WebDriverWait(driver, 20).until(EC.element_to_be_clickable((By.XPATH, option1_xpath)))
            option1.click()

            driver.implicitly_wait(20)

            button1 = driver.find_element_by_xpath(self.search_xpath1).click()

            driver.implicitly_wait(20)

            select2 = Select(driver.find_element_by_xpath(self.select_xpath2))
            option2_len = len(select2.options)
            options2_xpaths = ['.//*[@id="search_area2"]/option[%s]'%r for r in range(1,option2_len+1)]
                
            time.sleep(10)
                
            for option2_xpath in options2_xpaths:
                    
                option2 = WebDriverWait(driver, 20).until(EC.element_to_be_clickable((By.XPATH, option2_xpath)))
                option2.click()

                driver.implicitly_wait(20)   

                button2 = driver.find_element_by_xpath(self.search_xpath2).click()

                option2_select_ids.extend(self.select_areas(select_id))
                
            time.sleep(10)
            driver.implicitly_wait(20)                 

        return option2_select_ids
    
    #몽고 DB는 데이터 안의 '.'을 거부하므로 만든 함수
    def dot(self,name):
        for dot in name:
            if dot == '.':
                name = name.replace('.','_')
        return name
    

if __name__ == "__main__":
    #메인 함수
    scrap = Scraping(selection1,search1,selection2,search2)
    selects = scrap.selections_scrap(selection_id3)
    
    final_dict = {}
    list_ = []
    names,values = scrap.clean(selects)
    names = [scrap.dot(w) for w in names]
    
    for name,value in zip(names,values):
        dic = {'name' : name , 'value': value }
        list_.append(dic)
        
    #zone code를 몽고 DB에 저장
    client = MongoClient()
    db = client.database
    locations = db.locations
    insert = locations.save(list_)

