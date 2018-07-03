import sys
import os, errno
import time
import csv
import pickle
import urllib.request

import threading

import json

from multiprocessing import Pool
from functools import partial

# 웹 관련
from selenium import webdriver

# 웹 대기 관련
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait

# 웹 키 입력
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains

# 웹 예외처리
from selenium.common.exceptions import TimeoutException
from selenium.common.exceptions import WebDriverException
from selenium.common.exceptions import UnexpectedAlertPresentException
from selenium.common.exceptions import NoAlertPresentException

from utils import printProgress

class Crawler():

    def __init__(self):
        self.dir_path = os.path.dirname(os.path.realpath(__file__))

        self.CHROME_PATH = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
        # self.dir_path + '/chrome_binary_osx'
        self.CHROMEDRIVER_PATH = self.dir_path + '/bin/chromedriver_osx_2_35'
        self.WINDOW_SIZE = "1920,1080"

        chrome_options = webdriver.ChromeOptions()
        prefs = {"profile.default_content_setting_values.notifications" : 2}
        chrome_options.add_experimental_option("prefs",prefs)

        self.chrome_options = chrome_options
        self.pool = Pool(processes=4)

    def open(self):
        self.driver = webdriver.Chrome(self.CHROMEDRIVER_PATH, chrome_options=self.chrome_options)

    def close(self):
        self.driver.close()

    def run(self):
        # Open Chrome
        self.open()

        # File name in subjects_info dir
        collection_names = [
            'bolton',
            'Burlington',
            'Denver',
            'Fels',
            'Forsyth',
            'Iowa',
            'Mathews',
            'Michigan',
            'Oregon'
        ]

        # collection_id is in url
        collection_ids = [
            'CASEBolton',
            'UTBurlington',
            'UOKDenver',
            'WSUFels',
            'Forsyth',
            'UIOWAGrowth',
            'UOPMathews',
            'UMICHGrowth',
            'UOGrowth'
        ]

        # Loop for each file in subjects_info dir
        for c_dix, collection_name in enumerate(collection_names):
            collection_id = collection_ids[c_dix]

            # Getting subject ids from csv file. 
            # This part also can be automated as well.
            subject_ids = []
            with open('./subjects_info/'+collection_name+'.csv', newline='') as csvfile:
                subjects_info = csv.reader(csvfile, delimiter=',', quotechar='|')
                for i, row in enumerate(subjects_info):
                    if i>0:
                        if len(row[0]) > 0:
                            if collection_name == 'Mathews':
                                subject_ids.append(row[0].zfill(3))
                            elif collection_name == 'Michigan':
                                subject_ids.append(row[0].zfill(5))
                            elif collection_name == 'Oregon':
                                if len(row[0]) < 3:
                                    subject_ids.append(row[0].zfill(3))
                                else:
                                    subject_ids.append(row[0])
                            else:
                                subject_ids.append(row[0])

            # Getting data from each subject
            for s_idx, subject_id in enumerate(subject_ids):
                printProgress(s_idx+1, len(subject_ids), collection_name+' 조회중:', '완료', 2, 50)

                # Saving dir
                directory = './data/'+collection_name+'/'+subject_id+"/"

                # Setting image url
                url = 'http://www.aaoflegacycollection.org/aaof_collectionQuickView.html?collectionID='+collection_id+'&subjectID=' + subject_id
                self.driver.get(url)

                # Getting Image Elements
                table_elements = self.driver.find_elements_by_xpath("//table/tbody/tr/td/a/img")

                # Creating Thread for downloading images
                target_urls = []
                for img_idx, e in enumerate(table_elements):
                    # Getting image src
                    img_url = e.get_attribute('src')
                    
                    target_urls.append(img_url)

                # Download image
                def download_img(url,directory,subject_id,img_idx):
                    try:
                        os.makedirs(directory)
                    except OSError as e:
                        if e.errno != errno.EEXIST:
                            raise

                    urllib.request.urlretrieve(img_url, directory+subject_id + "_" + str(img_idx) +".jpg")

                threads = [threading.Thread(target=download_img, args=(url,directory,subject_id,img_idx,)) for img_idx, url in enumerate(target_urls)]
                for thread in threads:
                    # Start Threads
                    thread.start()
                for thread in threads:
                    # Wait for threads to be finished
                    thread.join()

                # Getting Position
                url = 'http://www.aaoflegacycollection.org/aaof_LMTableDisplay.html?collectionID='+collection_id+'&subjectID=' + subject_id
                self.driver.get(url)

                # Get table elements
                table_header = self.driver.find_elements_by_xpath("//div[@id='tabs-L0']/div[@id='data0_wrapper']/div[@class='dataTables_scroll']/div[@class='dataTables_scrollBody']/table/thead/tr/th")
                
                # Get Table Header(Column)
                landmark_headers = []
                for idx, th in enumerate(table_header):
                    _target = th.find_element_by_xpath("./div/div").get_attribute('innerHTML').replace('<span class="DataTables_sort_icon"></span>',"").strip().replace("&nbsp;","")
                    landmark_headers.append(_target)

                # Get Table row (actual data locates)
                table_rows = self.driver.find_elements_by_xpath("//div[@id='tabs-L0']/div[@id='data0_wrapper']/div[@class='dataTables_scroll']/div[@class='dataTables_scrollBody']/table/tbody/tr")

                # Saving Data in json and csv
                subject_data = {}
                subject_data_csv = []
                for idx, r in enumerate(table_rows):
                    tds = r.get_attribute('innerHTML').split('<td class=" dt-body-right">')
                    tds.pop(0)

                    _coords = []
                    _coords_csv = []
                    for i, td in enumerate(tds):
                        td_text = td.replace("</td>", "")
                        _data = {}
                        if i == 0:
                            landmark = td_text

                            _coords_csv.append(td_text)
                        else:
                            _data[landmark_headers[i]] = td_text
                            _coords.append(_data)

                            _coords_csv.append(td_text)

                    subject_data[landmark] = _coords
                    subject_data_csv.append(_coords_csv)

                with open(directory+'landmarks.json', 'w') as outfile:
                    json.dump(subject_data, outfile)

                with open(directory+"landmarks.csv", "w") as f:
                    writer = csv.writer(f)
                    writer.writerows([landmark_headers])
                    writer.writerows(subject_data_csv)
        # Closing Chrome
        self.close()
        exit(0)

            
                
if __name__ == "__main__":
    c = Crawler()
    c.run()