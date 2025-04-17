import json
import os
import random
import re
import string
import threading
import time
from functools import wraps
from typing import List
from urllib.parse import quote, quote_plus

import requests
import selenium
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.common import exceptions
from selenium.common.exceptions import NoSuchElementException, ElementNotInteractableException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from utils.log_util import logger

# from selenium_stealth import stealth

# from pdlearn.qywx import WeChat  # 使用微信发送二维码图片到手机
# logger.info("测试是否无头模式：{}".format(get_env_or_cfg("addition.Nohead", "Nohead", "False")))
if "False" == "True":
    logger.info("导入pyvirtualdisplay。。。")
    from pyvirtualdisplay import Display

# from pyvirtualdisplay import Display
"""
规避selenium检测：
    selenium_stealth
    测试地址：https://bot.sannysoft.com/
    pypi：https://pypi.org/project/selenium-stealth/
"""


class title_of_login:
    def __call__(self, driver):
        """ 用来结合webDriverWait判断出现的title """
        try:
            is_title1 = bool(EC.title_is(u'我的learn')(driver))
            is_title2 = bool(EC.title_is(u'系统维护中')(driver))
        except Exception as e:
            logger.error("chrome 开启失败")
            logger.error(e, exc_info=True)
            # exit()
            return
        if is_title1 or is_title2:
            return True
        else:
            return False


class KeepCurrentPage(object):
    def __init__(self, driver):
        self.driver = driver

    def __call__(self, func):
        @wraps(func)
        def wrapped_function(*args, **kwargs):
            # log_string = func.__name__ + " was called"
            cur_url = self.driver.current_url
            # self.notify()
            result = func(*args, **kwargs)
            self.driver.get(cur_url)
            return result

        return wrapped_function

    def notify(self):
        # logit只打日志，不做别的
        pass


class MyDriver():

    def __init__(self,
                 noimg=False,
                 nohead=False,
                 remote_driver=None,
                 local_driver=None,
                 remote_chrome=None,
                 ):
        if local_driver is None:
            local_driver = []
        self.display = None
        mydriver_log = ''
        try:
            # ==================== 设置options ====================
            self.options = Options()
            if noimg:
                self.options.add_argument('blink-settings=imagesEnabled=true')  # 不加载图片, 提升速度，但无法显示二维码

            if nohead:
                self.options.add_argument('--headless')
                self.options.add_argument('--disable-gpu')

                self.options.set_capability('unhandledPromptBehavior', 'accept')
                self.options.add_argument("--window-size=1920,1050")
            else:
                self.options.add_argument('--window-size=750,450')
                # self.options.add_argument('--window-size=400,500')
                # self.options.add_argument('--window-size=900,800')
                # self.options.add_argument("--window-size=1920,1050")

            self.options.add_argument('--test-type')
            self.options.add_argument('--disable-dev-shm-usage')
            self.options.add_argument('--disable-software-rasterizer')  # 解决GL报错问题
            self.options.add_argument('--disable-extensions')

            self.options.add_argument('--no-sandbox')
            self.options.add_argument('--mute-audio')  # 关闭声音
            # self.options.add_argument('--window-position=700,0')
            self.options.add_argument('--log-level=3')

            # self.options.add_argument('--proxy-server=http://127.0.0.1:7890')  # 设置代理

            self.options.add_argument(
                '--user-agent={}'.format(
                    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36'))
            if not remote_chrome:  # 不是使用远程浏览器才进行下面的设置
                self.options.add_experimental_option('excludeSwitches', ['enable-automation'])  # 绕过js检测
                # 在chrome79版本之后，上面的实验选项已经不能屏蔽webdriver特征了
                # 屏蔽webdriver特征
                self.options.add_argument("--disable-blink-features")
                self.options.add_argument("--disable-blink-features=AutomationControlled")
                # self.options.add_argument('--remote-debugging-port=13888')

            # self.options.add_experimental_option("excludeSwitches", ["enable-automation"])
            # self.options.add_experimental_option('useAutomationExtension', False)

            self.webdriver = webdriver
            # remote_driver = "http://**.**.**.**:4444/wd/hub"
            if remote_driver:
                self.driver = self.webdriver.Remote(
                    command_executor=remote_driver,
                    options=self.options
                    # desired_capabilities=self.webdriver.DesiredCapabilities.CHROME
                )
            else:
                if remote_chrome:
                    # self.options.add_experimental_option("debuggerAddress", "127.0.0.1:1888")
                    self.options.debugger_address = remote_chrome
                # ==================== 寻找 chrome ====================
                if os.path.exists("./chrome/chrome.exe"):  # win
                    self.options.binary_location = "./chrome/chrome.exe"
                    mydriver_log = '可找到 "./chrome/chrome.exe"'
                elif os.path.exists("/opt/google/chrome/chrome"):  # linux
                    self.options.binary_location = "/opt/google/chrome/chrome"
                    mydriver_log = '可找到 "/opt/google/chrome/chrome"'

                # ==================== 寻找 chromedriver ====================
                chromedriver_paths = [
                    "../../chromedriver.exe",
                    "./app/chrome/chromedriver.exe",  # win
                    "./chromedriver.exe",  # win
                    "./app/chromedriver",  # linux
                    "/xuexi/service-home/chromedriver",  # docker
                    "/usr/bin/chromedriver",  # linux用户安装
                    # raspberry linux （需要包安装chromedriver）
                    "/usr/lib64/chromium-browser/chromedriver",
                    # raspberry linux （需要包安装chromedriver）
                    "/usr/lib/chromium-browser/chromedriver",
                    "/usr/local/bin/chromedriver",  # linux 包安装chromedriver
                ]

                logger.info(f"本地配置的驱动路径：{local_driver}")
                if local_driver and isinstance(local_driver, str):
                    try:
                        local_driver = json.loads(local_driver)
                    except:
                        local_driver = []

                if local_driver and isinstance(local_driver, (list, tuple)):
                    local_driver.extend(chromedriver_paths)
                    chromedriver_paths = local_driver
                logger.info(f"合并后的驱动路径：{chromedriver_paths}")

                if nohead and not remote_driver:
                    self.display = Display(visible=0, size=(1920, 1050))
                    self.display.start()
                have_find = False
                logger.info(f"在目录{os.getcwd()}中查找驱动")
                for one_path in chromedriver_paths:
                    if os.path.exists(one_path):
                        logger.info(f"当前驱动文件路径：{one_path}")
                        self.driver = self.webdriver.Chrome(
                            service=Service(executable_path=one_path),
                            options=self.options)
                        mydriver_log = mydriver_log + '\n可找到 "' + one_path + '"'
                        have_find = True
                        break
                if not have_find:
                    logger.info(f"没有找到驱动文件，使用默认参数启动")
                    self.driver = self.webdriver.Chrome(
                        options=self.options)
                    mydriver_log = mydriver_log + '\n未找到chromedriver，使用默认方法。'
            logger.info("浏览器已打开！！！")
            self.driver.implicitly_wait(20)
            self.driver.set_page_load_timeout(30)
        except Exception as e:
            # logger.error(e, exc_info=True)
            logger.info("=" * 60)
            logger.info(f"""
            Chrome 浏览器初始化失败。信息：
            {mydriver_log}
            您可以检查下：
            1. 是否存在./chrome/chromedriver.exe 或 PATH 中是否存在 chromedriver.exe
            2. 浏览器地址栏输入 chrome://version 看到的chrome版本 和 运行 chromedriver.exe 显示的版本整数部分是否相同
            针对上述问题，请在 https://registry.npmmirror.com/binary.html?path=chromedriver/ 下载对应版本程序并放在合适的位置
            针对上述问题，请在 https://googlechromelabs.github.io/chrome-for-testing/ 较新的测试版可能在这里
            谷歌浏览器linux版本下载地址https://www.google.com/chrome/?platform=linux
            """)
            # https://chromedriver.chromium.org/downloads
            # https://googlechromelabs.github.io/chrome-for-testing/#stable
            logger.info("=" * 60)
            # auto.prompt("按回车键继续......")
            raise e

    def wait_until_visible(self, local, timeout=10, poll_frequency=0.5):
        condition = EC.visibility_of_element_located(self._locator(local))
        WebDriverWait(driver=self.driver, timeout=timeout,
                      poll_frequency=poll_frequency).until(condition)
        return self

    def wait_until_find_element(self, local, timeout=10, poll_frequency=0.5):
        # condition = self.find_element(self._locator(local))
        WebDriverWait(driver=self.driver, timeout=timeout,
                      poll_frequency=poll_frequency).until(lambda driver: driver.find_element(*self._locator(local)))
        return self

    def get_text(self, local, timeout=10, poll_frequency=0.5) -> str:
        condition = EC.visibility_of_element_located(
            self._locator(local))
        WebDriverWait(driver=self.driver, timeout=timeout,
                      poll_frequency=poll_frequency).until(condition)
        return self.find_element(local).text

    def click(self, local, timeout=10, poll_frequency=0.5):
        condition = EC.visibility_of_element_located(self._locator(local))
        WebDriverWait(self.driver, timeout, poll_frequency).until(condition)
        self.find_element(local).click()
        return self

    def check(self, local, timeout=10, poll_frequency=0.5):
        condition = EC.visibility_of_element_located(self._locator(local))
        WebDriverWait(self.driver, timeout, poll_frequency).until(condition)
        finded_element = self.find_element(local)
        if not finded_element.is_selected():
            finded_element.click()
        return self

    def un_check(self, local, timeout=10, poll_frequency=0.5):
        condition = EC.visibility_of_element_located(self._locator(local))
        WebDriverWait(self.driver, timeout, poll_frequency).until(condition)
        finded_element = self.find_element(local)
        if finded_element.is_selected():
            finded_element.click()
        return self

    def input(self, local, text, timeout=10, poll_frequency=0.5):
        condition = EC.visibility_of_element_located(self._locator(local))
        WebDriverWait(self.driver, timeout, poll_frequency).until(condition)
        self.find_element(local).send_keys(text)
        return self

    def _locator(self, local) -> tuple[str, str]:
        local = local.strip()
        if local[:1].upper() in '#.@':
            return (By.CSS_SELECTOR, local)
        elif local[:2] == '//':
            return (By.XPATH, local)

        local_type, local_value = local.split("=", maxsplit=1)
        local_type = local_type.upper()
        if local_type == 'XPATH':
            return (By.XPATH, local_value)
        elif local_type == 'ID':
            return (By.ID, local_value)
        elif local_type == 'CSS':
            return (By.CSS_SELECTOR, local_value)
        elif local_type == 'CLASS':
            return (By.CLASS_NAME, local_value)
        elif local_type == "NAME":
            return (By.NAME, local_value)
        elif local_type == "TAG":
            return (By.TAG_NAME, local_value)
        elif local_type == 'LINK':
            return (By.LINK_TEXT, local_value)
        elif local_type == 'PARTIAL':
            return (By.PARTIAL_LINK_TEXT, local_value)
        else:
            raise ValueError("定位格式不正确：{}".format(local))

    def _find_element(self, local: str, mult_elements=False):
        logger.warning("_find_element只能在selenium<4.0中使用")
        if mult_elements:
            mult_elements = "s"
        else:
            mult_elements = ""

        finder = getattr(self.driver, "find_element{}".format(mult_elements))

        local = local.strip()
        if local[:1].upper() in '#.@':
            return finder(By.CSS_SELECTOR, local)
        elif local[:2] == '//':
            return finder(By.XPATH, local)

        local_type, local_value = local.split("=")
        local_type = local_type.upper()
        if local_type == 'XPATH':
            return finder(By.XPATH, local_value)
        elif local_type == 'ID':
            return finder(By.ID, local_value)
        elif local_type == 'CSS':
            return finder(By.CSS_SELECTOR, local_value)
        elif local_type == 'CLASS':
            return finder(By.CLASS_NAME, local_value)
        elif local_type == "NAME":
            return finder(By.NAME, local_value)
        elif local_type == "TAG":
            return finder(By.TAG_NAME, local_value)
        elif local_type == 'LINK':
            return finder(By.LINK_TEXT, local_value)
        elif local_type == 'PARTIAL':
            return finder(By.PARTIAL_LINK_TEXT, local_value)

    def find_elements(self, local):
        return self.driver.find_elements(*self._locator(local))

    def find_element(self, local) -> WebElement:
        return self.driver.find_element(*self._locator(local))

    def element_location(self, local) -> tuple:
        lt = self.driver.find_element(*self._locator(local)).location
        return (lt['x'], lt['y'])

    def element_size(self, local) -> tuple:
        lt = self.driver.find_element(*self._locator(local)).size
        return (lt['width'], lt['height'])

    def page_contain_element(self, local):
        locator = local

        self.driver.switch_to.default_content()

        if self.find_element(locator):
            return self

        subframes = self.find_elements("xpath://frame|//iframe")
        for frame in subframes:
            self.driver.switch_to.frame(frame)
            found_text = self.find_element(locator)
            self.driver.switch_to.default_content()
            if found_text:
                return self
        raise NoSuchElementException(f"没有找到{local}")

    def page_contain_text(self, text):
        locator = f"xpath=//*[contains(., {text})]"
        self.page_contain_element(locator)
        return self

    def should_be_selected(self, local):
        if not self.find_element(*self._locator(local)).is_selected():
            raise selenium.common.exceptions.NoSuchElementException(f"元素{local}未被选中")
        return self

    def screenshots(self, name):
        # if not isScreenshot:
        #     return
        thread_name = threading.current_thread().name
        try:
            screenshot_dir = os.path.join(os.path.join(Pathutil().project_root_path(), "screenshot"))
            if not os.path.exists(screenshot_dir):
                os.mkdir(screenshot_dir)
            file_name = "{}-{}-{}.png".format(name, thread_name, time.strftime("%Y%m%d-%H%M%S", time.localtime()))
            file_name = os.path.join(screenshot_dir, file_name)
            isSave = self.driver.get_screenshot_as_file(filename=file_name)
            if not isSave:
                file_name = None
                logger.warning("{}  保存失败".format(file_name))
        except Exception as e:
            file_name = None
            logger.error("截图保存失败")
            logger.exception(e)

        try:
            source_path = os.path.join(screenshot_dir,
                                       "页面源码-{}-{}-{}.html".format(thread_name, name,
                                                                       time.strftime("%Y%m%d-%H%M%S",
                                                                                     time.localtime())))
            with open(source_path, 'w', encoding="utf8") as wf:
                wf.write(self.driver.page_source)
        except Exception as e1:
            source_path = None
            logger.exception("源码保存失败：{}".format(e1))
        return file_name, source_path

    def web_log(self, send_log):
        pass
        # self.web.add_message(send_log)

    def get_cookies(self):
        cookies = self.driver.get_cookies()
        return cookies

    def add_cookies(self, cookies:list[dict]):
        for cookie in cookies:
            if cookie.get("name"):
                self.driver.add_cookie(cookie)
        return self

    def title_is(self, title):
        return self.driver.title == title

    def go_url(self, url):
        self.driver.get(url)
        return self

    def go_js(self, js):
        self.driver.execute_script(js)
        return self

    def quit(self):
        try:
            self.driver.delete_all_cookies()
            self.driver.close()
            self.driver.quit()
            logger.info("成功关闭浏览器！")
        except Exception as e:
            logger.info("退出浏览器失败：{}".format(e))

        if self.display:
            try:
                self.display.stop()
                logger.info("已成功关闭虚拟显示器！")
            except Exception as e:
                logger.error("退出虚拟显示器出错！！！{}".format(e))
                logger.exception(e, exc_info=True)
        logger.info("浏览器已经关闭！！！")

    def check_delay(self):
        delay_time = random.randint(2, 5)
        logger.info('等待 ' + str(delay_time) + ' 秒')
        time.sleep(delay_time)

    # 滑块验证
    def swiper_valid(self):
        """
        验证滑块，滑块的定位变了，新的定位还没处理
        @return:
        """
        for j in range(1, 2):
            if not self.find_elements(".nc-mask-display"):
                break
            logger.info(f"开始第{j}次验证滑块")
            self.screenshots("第{}次验证滑块".format(j))

            # slider_button_size = self.element_size("#nc_mask .nc-container .nc_iconfont.btn_slide")
            slider_button_size = self.element_size("#nc_mask .nc-container .nc_iconfont.btn_slide")
            slider_button_location = self.element_location("#nc_mask .nc-container .nc_iconfont.btn_slide")
            slider_button_center = (slider_button_location[0] + slider_button_size[0] / 2,
                                    slider_button_location[1] + slider_button_size[1] / 2)
            slider = self.element_size("#nc_mask .nc-container .scale_text.slidetounlock")
            click_random = random.Random().randint(-20, 1)
            click_y_random = random.Random().randint(-10, 10)
            drag_random = random.Random().randint(1, 3)

            time.sleep(random.randint(3, 5))

            if self.find_elements("#nc_mask .nc-container .nc_iconfont.btn_slide"):
                self.click("#nc_mask .nc-container .nc_iconfont.btn_slide")
                time.sleep(random.randint(3, 5))

            builder = ActionChains(self.driver)
            builder.reset_actions()

            builder.move_to_element(
                self.find_element("#nc_mask .nc-container .nc_iconfont.btn_slide"))
            builder.click_and_hold()
            track = self.move_mouse(slider[0] - slider_button_size[0] / 2 + click_random)
            time.sleep(0.2)
            for i in track:
                builder.move_by_offset(xoffset=i, yoffset=random.Random().randint(-10, 10))
                builder.reset_actions()
                time.sleep(random.random())
            time.sleep(0.1)
            # 释放左键，执行for中的操作
            builder.release().perform()
            time.sleep(5)
            self.screenshots("第{}次验证完滑块".format(j))
            logger.info(f"完成第{j}次验证滑块")

            # # 获取滑块长，宽
            # button = browser.find_element_by_xpath("//span[@id='nc_1_n1z']")
            # small_sliding = button.size
            # # 获取整个div的长，宽
            # big_sliding = browser.find_element_by_xpath("//span[@class='nc-lang-cnt']").size
            # # 滑动的距离
            # sliding_distance = big_sliding.get('width') - small_sliding.get('width')
            # print(sliding_distance)
            # ActionChains(browser).click_and_hold(button).perform()
            # for i in [99, 87, 51, 59]:
            #     ActionChains(browser).move_by_offset(xoffset=i, yoffset=0).perform()
            #     time.sleep(random.random())
            # ActionChains(browser).release().perform()
            # time.sleep(1)
            # browser.find_element_by_xpath("//button[@class='fm-button fm-submit password-login']").click()
        # self.swiper_valid()

    # 鼠标移动
    def move_mouse(self, distance):
        remaining_dist = distance
        moves = []
        a = 0
        # 加速度，速度越来越快...
        while remaining_dist > 0:
            span = random.randint(15, 20)
            a += span
            moves.append(a)
            remaining_dist -= span
            if sum(moves[:-1]) > distance:
                logger.info(f"滑块验证移动距离：{sum(moves)}，移动分步：{moves}")
                break
        return moves


def test_remote_driver():
    driver = webdriver.Remote(command_executor="http://192.168.100.190:4444/wd/hub")
    driver.get("http://www.baidu.com")
    time.sleep(5)
    driver.close()
    driver.quit()


def test_web_driver():
    """
        "C:\Program Files (x86)\Google\Chrome\Application\chrome.exe" --remote-debugging-port=1888 --remote-debugging-address=10.12.196.165 --user-data-dir="C:\myself\chromedata"
        """
    # test_remote_driver()
    driver = MyDriver(
        local_driver=["C:\\myself\\api-test-platform\\server\\chromedriver.exe"],
        remote_chrome="127.0.0.1:1888",
        # remote_chrome="10.12.196.165:1888",
        # remote_driver="http://10.12.196.160:1888"
    )
    driver.go_url("https://testpartner.rta-os.com")
    driver.check("#gray04")
    driver.click("#J_envGroupList > div > div.btns > .confirm")
    driver.input("#account", "xiongjie-hk")
    driver.input("#password", "test1234!1!")
    driver.input("#verifyCode", "11!")
    driver.click("#login", )
    driver.wait_until_find_element("#login")
    time.sleep(2)
    print(driver.get_cookies())
    driver.click(".J_userinfo_cont")
    driver.click("//span[text()='Log out']")
    driver.page_contain_element("#account")
    time.sleep(3)
    driver.go_url("http://www.sogou.com")
    time.sleep(2)
    # driver.go_url("https://www.google.com")
    # time.sleep(3)


def test_hifini():
    driver = MyDriver(
        local_driver=["C:\\myself\\api-test-platform\\server\\chromedriver.exe"],
        remote_chrome="127.0.0.1:1888",
        # remote_chrome="10.12.196.165:1888",
        # remote_driver="http://10.12.196.160:1888"
    )
    driver.go_url("https://www.hifini.com/")
    # driver.click("css=div[id=nav] i[class=icon-user]")
    # driver.input("#email", "panda62")
    # driver.input("#password", "0213xiongjie")
    # driver.click("#submit")

    driver.wait_until_find_element("css=div[id=nav] i[class=icon-user]")
    driver.add_cookies([{"domain": "www.hifini.com", "expiry": 1746063714, "httpOnly": False, "name": "bbs_token", "path": "/", "sameSite": "Lax", "secure": False, "value": "lMyDHpLietNtbsW15B1Fg_2FcbPOzt6XktLYOllEExTJW_2FGw2_2FTzrhxsR0BG9l84OJupordnohruBhcUjoH2V4EdmfkRfaXxdV"}, {"domain": "www.hifini.com", "expiry": 1746063702, "httpOnly": True, "name": "bbs_sid", "path": "/", "sameSite": "Lax", "secure": False, "value": "il8tlgfng868qcjlh3mbva5hov"}])
    driver.driver.refresh()
    driver.wait_until_visible("css=div[id=nav] li[class*=username]")
    cookies = driver.get_cookies()
    print(json.dumps(cookies))
    driver.click("#sign")
    driver.wait_until_find_element("xpath=//div[@id='sign' and text()='已签']", 3)
    time.sleep(2)



if __name__ == "__main__":
    test_hifini()


    # chromeOptions = webdriver.ChromeOptions()
    # chromeOptions.add_argument('--remote-debugging-port=5888')
    # driver = webdriver.Chrome(options=chromeOptions,
    #                           service=Service(executable_path="C:\\myself\\api-test-platform\\server\\chromedriver.exe")
    #                           )

    # chrome_options = webdriver.ChromeOptions()
    # chrome_options.add_experimental_option("debuggerAddress", "127.0.0.1:1888")
    # # chrome_options.debugger_address = "10.12.196.160:1888"
    # driver = webdriver.Chrome(options=chrome_options,
    #                           service=Service(executable_path="C:\\myself\\api-test-platform\\server\\chromedriver.exe")
    #                           )

    # driver.get("http://www.baidu.com")
    # time.sleep(2)
    # driver.get("http://www.sogou.com")
    # time.sleep(2)

    # from selenium import webdriver
    #
    # driver = webdriver.Remote(
    #     command_executor='http://10.12.196.165:1888'
    # )
    #
    # driver.get("http://www.baidu.com")
    # time.sleep(2)
    # driver.get("http://www.sogou.com")
    # time.sleep(2)
