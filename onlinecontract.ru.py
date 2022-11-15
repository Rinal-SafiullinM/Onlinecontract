# -*- coding: utf-8 -*-
import json
import os
import re
import sys
import time
from datetime import datetime, timedelta

import requests
from lxml import html
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as ec
from selenium.webdriver.support.wait import WebDriverWait
from seleniumrequests import Chrome

currentdir = os.path.dirname(os.path.realpath(__file__))
base_path = os.path.dirname(currentdir)
sys.path.append(base_path)
sys.path.append('/home/manage_report')
# from Send_report.Utils import send_to_api
# from Send_report.mywrapper import magicDB

class Parser:
    def __init__(self):
        self.name = 'onlinecontract.ru'
        self.session = requests.Session()
        self.browser = None
        self.ads_count = 0
        self.last_item_date = None
        self.url = None
        self.sid = None
        self.mode = 'prod'

    def init_browser(self):
        options = Options()
        options.headless = True
        options.add_argument('--headless')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--blink-settings=imagesEnabled=false')

        options.add_argument('--disable-infobars')
        options.add_argument('--disable-browser-side-navigation')
        options.add_argument('--disable-gpu')

        options.add_argument('--log-level=3')

        if self.mode == 'dev':
            self.browser = Chrome(
                executable_path=os.path.realpath('/chromedriver.exe'.format(base_path)),
                options=options,
            )
        else:
            self.browser = Chrome(
                executable_path='/chromedriver.exe',
                options=options,
            )

    def auth(self):
        login = 'gmx836190380'
        password = '092128134546'

        try:
            self.browser.get('https://onlinecontract.ru/otp/signin')
            # self.browser.find_ele('Login')
            WebDriverWait(self.browser, 3).until(
                ec.presence_of_element_located((By.XPATH, "//input[@name='Login']"))
            ).send_keys(login)

            WebDriverWait(self.browser, 3).until(
                ec.presence_of_element_located((By.XPATH, "//input[@name='Pass']"))
            ).send_keys(password)

            WebDriverWait(self.browser, 3).until(
                ec.presence_of_element_located((By.XPATH, "//button[@name='Submit']"))
            ).click()

            time.sleep(10)

            return True

        except Exception as e:
            print(e)

        return False

    def get_sid(self):
        try:
            html_string = WebDriverWait(self.browser, 3).until(
                ec.presence_of_element_located((By.XPATH, "//html"))
            ).get_attribute('innerHTML')
            tree = html.document_fromstring(html_string)
            scripts = ''.join(tree.xpath("//script/text()"))

            sid_match = re.search(r'getProcedureListSID":"([a-zA-Z0-9]+)"', scripts)
            self.sid = sid_match.group(1)

            return True

        except Exception as e:
            print(e)

        return False

    def get_data(self, item):
        item_url = 'https://onlinecontract.ru/otp/index.phtml?sid={}'.format(item['procedureSID'])

        item_data = {
            'fz': 'Коммерческие',
            'purchaseNumber': item['id'],
            'url': 'https://onlinecontract.ru/tenders/{}'.format(item['id']),
            'title': item['name'].strip(),
            'purchaseType': item['type']['long'],

            'customer': {
                'factAddress': '',
                'fullName': item['owner']['name'],
                # 'inn': '',
                # 'kpp': '',
            },
            'contactPerson': {},

            'procedureInfo': {
                'startDate': '',
                'endDate': item['offerStop'],
                'biddingDate': item['rebiddingStart'],
            },

            'lots': [
                {
                    'price': re.sub('[^\d,]', '', item['price']),
                    'customerRequirements': [
                        {
                            'obesp_z': '',
                            # 'obesp_i': '',
                            # 'sumInPercents': sum_in_percents,
                            'kladrPlaces': [],
                        }
                    ],
                    # 'lotItems': self.get_lot_items(lot, response.json()['short_trade_procedure']),
                }
            ],

            'ETP': {
                'name': 'Online Contract',
                'url': 'https://onlinecontract.ru/',
            },

            'attachments': [],
        }

        self.browser.get(item_url)
        html_string = WebDriverWait(self.browser, 3).until(
            ec.presence_of_element_located((By.XPATH, "//html"))
        ).get_attribute('innerHTML')
        # print(html_string)

        tree = html.document_fromstring(html_string)
        # item_data['customer']['factAddress'] = ''.join(tree.xpath("//script[@class='r_table']"))
        try:
            adress = ''.join(tree.xpath("//script[@id='OTP-state']"))
            print(adress.partition("owner&q;:{&q;id&q;:")[2].split(",")[0])
            #print(adress)
        except Exception as e:
            print(e)

        deliveryAddress = ''.join(tree.xpath(
            "/html/body/div[2]/table[2]/tbody/tr[2]/td[2]/table[1]/tbody/tr/td/table/tbody/tr/td[1]/table/tbody/tr[20]/td[3]/span/text()"
        ))
        print('deliveryAddress', deliveryAddress)
        item_data['lots'][0]['customerRequirements'][0]['kladrPlaces'].append({
            'deliveryPlace': deliveryAddress,
        })

        contact = ''.join(tree.xpath(
            "/html/body/div[2]/table[2]/tbody/tr[2]/td[2]/table[1]/tbody/tr/td/table/tbody/tr/td[1]/table/tbody/tr[16]/td[3]/span/text()"
        ))

        if contact == '':
            contact = ''.join(tree.xpath(
                "/html/body/div[2]/table[2]/tbody/tr[2]/td[2]/table[1]/tbody/tr/td/table/tbody/tr/td[1]/table/tbody/tr[12]/td[3]/span/text()"
            ))

        contact_item_num = 0
        for contact_item in contact.split(','):
            if 'должность' in contact_item.lower():
                continue

            if contact_item_num == 0:
                fio = ' '.join(re.findall(r'[а-яА-Я]+', contact_item))

                if fio != '':
                    fio_item_num = 0
                    for fio_item in ['lastName', 'firstName', 'middleName']:

                        try:
                            item_data['contactPerson'][fio_item] = fio.split(' ')[fio_item_num]
                        except:
                            pass

                        fio_item_num += 1

            if 'contactPhone' not in item_data['contactPerson'] or item_data['contactPerson']['contactPhone'] == '':
                item_data['contactPerson']['contactPhone'] = re.sub(r'[^\d]', '', contact_item)

            item_data['contactPerson']['contactEMail'] = ','.join(re.findall(
                r'([\w0-9-._]+@[\w0-9-.]+[\w0-9]{2,3})', contact_item)
            )

        elements = tree.xpath("/html/body/div[2]/table[2]/tbody/tr[2]/td[2]/table[1]/tbody/tr/td/table/tbody/tr/td[1]/table/tbody/tr[3]/td[3]//a")
        for element in elements:
            html_string = html.tostring(
                element, encoding='unicode', method='html', with_tail=False
            )
            element_tree = html.document_fromstring(html_string)
            item_data['attachments'].append({
                'docDescription': ''.join(element_tree.xpath("//text()")).strip(),
                'url': re.sub(
                    '\./', '/',
                    'https://onlinecontract.ru/otp{}'.format(''.join(element_tree.xpath("//@href")))
                ),
            })
        print(item_url)
        print(item_data)
        return item_data

    def close_browser(self):
        try:
            self.browser.close()
        except Exception as e:
            print(e)

        try:
            self.browser.quit()
        except Exception as e:
            print(e)

    # @magicDB
    def run(self):
        self.init_browser()

        if self.auth() is not True:
            self.ads_count = 'Произошла ошибка авторизации. На данном ресурсе она является обязательной.'
            self.close_browser()

            return

        if self.get_sid() is not True:
            self.ads_count = 'Произошла ошибка авторизации. На данном ресурсе она является обязательной.'
            self.close_browser()

            return

        required_date = (datetime.now() - timedelta(days=1)).date()
        page_num = 1

        ads = []
        found_items = False
        while True:
            found_matching_items = False

            try:
                print('page {}'.format(page_num))
                url = 'https://onlinecontract.ru/Ajax.php?sid={}&PageNum={}'.format(self.sid, page_num)
                self.browser.get(url)
                time.sleep(5)

                html_string = WebDriverWait(self.browser, 3).until(
                    ec.presence_of_element_located((By.XPATH, "//pre"))
                ).get_attribute('innerHTML')

                if len(json.loads(html_string)['procedureList']) > 0 and page_num == 1:
                    found_items = True

                for item in json.loads(html_string)['procedureList']:
                    item_date = datetime.strptime(item['published'].split('T')[0], '%Y-%m-%d').date()
                    print(str(required_date), str(item_date))

                    if item_date > required_date:
                        found_matching_items = True

                        continue

                    if self.last_item_date is None or self.last_item_date > item_date:
                        self.last_item_date = item_date

                    if item_date != required_date:
                        continue

                    found_matching_items = True

                    item_data = self.get_data(item)
                    if item_data is None:
                        continue

                    # print(item_data)

                    ads.append(item_data)
                    self.ads_count += 1

                page_num += 1

            except Exception as e:
                print(e)

            if found_matching_items is False:
                break

        self.close_browser()

        data = {'name': 'onlinecontractru',
                'data': ads}										
        #send_to_api(data)
        return data


if __name__ == '__main__':
    parser = Parser()

    try:
        print('Запуск парсера {}'.format(parser.name))
        parser.run()

        msg = '{}: {}\n'.format(parser.name, parser.ads_count)

    except Exception as e:
        #print(msg)
        print(e)
        msg = parser.name + ": ошибка" + "\n"
    print(msg)
    print('End:', print(datetime.now()))
