# -*- coding: utf8 -*-

"""
cron: 0 8 * * *
new Env('司机社签到');
环境变量名称：XSIJISHE
直接使用账号密码登录,格式: 账号&密码
多个账号使用@或换行间隔
青龙Python依赖, requests, lxml, selenium, ddddocr
[task_local]
#司机社签到
0 8 * * * https://raw.githubusercontent.com/jzjbyq/AutoCheckIn/main/sijishe.py, tag=司机社签到, enabled=true
[rewrite_local]
https://sijishea.com url script-request-header https://raw.githubusercontent.com/jzjbyq/AutoCheckIn/main/sijishe.py
"""

import os
from lxml import etree
import time
from notify import send
import urllib3
import re
import hashlib
import requests
import random
import ddddocr
import json
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException

# 禁用不安全请求警告
urllib3.disable_warnings()

# 初始化签到状态值
checkIn_content = '今日已签到', '签到成功', 'Cookie失效'
checkIn_status = 2
send_content = ''
cookies = {}

# 签到积分信息页面
sign_url = '/k_misign-sign.html'
formhash = ''
main_url = ''
seccodehash = ''
referer = ''

# 初始化OCR对象
ocr = None

def initialize_webdriver():
    """初始化WebDriver并设置选项"""
    options = webdriver.ChromeOptions()
    options.binary_location = "chrome-win64/chrome.exe"
    options.add_argument('--disable-gpu')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-extensions')
    # 用户代理设置
    options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36')
    
    # 如果需要无头模式，取消下行注释
    # options.add_argument('--headless')
    
    driver = webdriver.Chrome(options=options, executable_path='webdriver/chromedriver.exe')
    # 设置隐式等待
    driver.implicitly_wait(10)
    return driver

def string_to_md5(key):
    """将字符串转换为MD5哈希值"""
    md5 = hashlib.md5()
    md5.update(key.encode("utf-8"))
    return md5.hexdigest()

def getrandom(code_len):
    """生成随机字符串"""
    all_char = 'qazwsxedcrfvtgbyhnujmikolpQAZWSXEDCRFVTGBYHNUJIKOLP'
    index = len(all_char) - 1
    code = ''
    for _ in range(code_len):
        num = random.randint(0, index)
        code += all_char[num]
    return code

def get_new_url():
    """从发布页获取网站地址"""
    global main_url
    url = 'https://47447.net/'
    ot_num = 1
    ot_max_num = 10
    
    while ot_num < ot_max_num:
        try:
            print(f'尝试获取最新网址: 第{ot_num}/{ot_max_num}次')
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36'
            }
            res = requests.get(url, headers=headers, timeout=15)
            rhtml = etree.HTML(res.content.decode('utf-8'))

            urls = checkstatus(rhtml)
            if urls == '0':
                print('所有站点都访问失败, 请检查自身网络')
                exit(0)
            main_url = urls
            # 如果要直接指定网址，可以取消下面这行的注释
            main_url = "https://sijishe.ink"
            print(f'成功获取有效网址: {main_url}')
            return 1
        except Exception as e:
            print('错误内容', e)
            print(f'发布页地址获取失败，正在进行第{ot_num}/{ot_max_num}次重试')
        time.sleep(10)
        ot_num += 1
    exit(0)

def checkstatus(r_xpath):
    """检查发布页中的最新站点并按顺序自动切换"""
    r_xpath_num = r_xpath.xpath('//ul[@class="speedlist"]/li')
    for i in range(1, len(r_xpath_num)+1):
        # 获取地址名称和URL
        url_name = r_xpath.xpath(f'//ul[@class="speedlist"]/li[{i}]/p/span[@class="url"]/text()')
        if not url_name:
            continue
        
        url_name = url_name[0]
        if '地址' in url_name:
            cs_url = r_xpath.xpath(f'//ul[@class="speedlist"]/li[{i}]/span[@class="btn-open"]/a/@href')
            if not cs_url:
                continue
                
            cs_url = cs_url[0]
            try:
                print('检测网址:', cs_url, '(', url_name.strip(), ')')
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36'
                }
                cs_res = requests.get(cs_url, headers=headers, timeout=10)
                if cs_res.status_code == 200:
                    print('网址', cs_url, '有效')
                    return cs_url
            except Exception as e:
                print('网址', cs_url, '失败:', str(e))
    
    print('所有地址检测完毕，没有可用的地址')
    return '0'

def get_cookie_formhash(driver):
    """初始化cookie和页面formhash信息"""
    global formhash, seccodehash, referer, cookies
    formhash = ''
    
    try:
        print("正在获取必要的页面信息...")
        driver.get(main_url + '/home.php?mod=space')
        
        # 等待页面加载完成，等待referer元素出现
        wait = WebDriverWait(driver, 15)
        input_element = wait.until(
            EC.presence_of_element_located((By.XPATH, '//input[@type="hidden" and @name="referer"]'))
        )
        
        referer = input_element.get_attribute('value')
        print('Referer: ' + referer)
        
        # 访问登录页获取formhash和seccodehash
        driver.get(referer)
        cookies = {cookie['name']: cookie['value'] for cookie in driver.get_cookies()}
        
        # 获取formhash
        wait.until(EC.presence_of_element_located((By.NAME, 'formhash')))
        formhash_element = driver.find_element(By.NAME, 'formhash')
        formhash = formhash_element.get_attribute('value')
        print('Formhash: ' + formhash)
        
        # 获取seccodehash
        seccode_element = driver.find_element(By.XPATH, '//span[starts-with(@id, "seccode_")]')
        seccodehash = seccode_element.get_attribute('id').replace('seccode_', '')
        print('Seccodehash: ' + seccodehash)
        
        return True
    except Exception as e:
        print(f"获取页面信息失败: {e}")
        return False

def cookiedict_to_json(Rcookie):
    """将cookie字典转换为json格式"""
    global cookies
    cookies = {cookie['name']: cookie['value'] for cookie in Rcookie}
    
def cookiejar_to_json(Rcookie):
    """将cookiejar转换为json"""
    global cookies
    for item in Rcookie:
        cookies[item.name] = item.value

def crack_captcha():
    """识别验证码"""
    global captcha, cookies
    
    url = main_url + '/misc.php?mod=seccode&update=' + str(random.randint(10000, 99999)) + '&idhash=' + seccodehash
    print('获取验证码的cookie:', cookies)
    
    response = requests.get(url, cookies=cookies, headers={
            'referer': referer,
            'user-agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/101.0.4951.54 Safari/537.36 Edg/101.0.1210.39'
        })
        
    cookiejar_to_json(response.cookies)

    # 将返回的二进制内容写入文件
    with open("captcha.png", 'wb') as f:
        f.write(response.content)
	
    # 重新以二进制读取方式打开刚刚保存的文件
    with open('captcha.png', 'rb') as fr:
        captcha_data = fr.read()
	
    captcha = ocr.classification(captcha_data)
    print(f'识别的验证码: {captcha}')
    
    # 校验验证码
    check_url = main_url + '/misc.php?mod=seccode&action=check&inajax=1&modid=member::logging&idhash=' + seccodehash + '&secverify=' + captcha
    
    response = requests.get(check_url, cookies=cookies, headers={
            'referer': referer,
            'user-agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/101.0.4951.54 Safari/537.36 Edg/101.0.1210.39'
        })
    print('验证码校验结果：', response.text)

def login(username, password):
    """登录函数"""
    global cookies
    max_retry = 10  # 最大重试次数
    retry_count = 0
    
    while retry_count < max_retry:
        data = {
            'formhash': formhash,
            'referer': referer,
            'username': username,
            'password': password,
            'questionid': '0',
            'answer': '',
            'seccodehash': seccodehash,
            'seccodemodid': 'member::logging',
            'seccodeverify': captcha,
            'cookietime': '2592000'
        }
        
        headers = {
            'content-type': 'application/x-www-form-urlencoded',
            'referer': referer,
            'user-agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/101.0.4951.54 Safari/537.36 Edg/101.0.1210.39'
        }

        login_url = main_url + '/member.php?mod=logging&action=login&loginsubmit=yes&frommessage&loginhash=L' + getrandom(4) + '&inajax=1'
        
        try:
            print(f'尝试登录: {username}')
            print(f'登录URL: {login_url}')
            
            response = requests.post(login_url, cookies=cookies, headers=headers, data=data)
            
            if '欢迎您回来' in response.text:
                cookiejar_to_json(response.cookies)
                print(f'账号 {username} 登录成功!')
                return 1
            else:
                print(f'账号 {username} 登录失败，可能是验证码问题，回应内容: {response.text}')
        except Exception as e:
            print(f'登录过程中出现异常: {str(e)}')
        
        retry_count += 1
        print(f'登录失败，正在进行第 {retry_count}/{max_retry} 次重试...')
        
        # 如果验证码错误，重新执行识别验证码的方法
        crack_captcha()
        
    print(f'账号 {username} 登录失败，已达到最大尝试次数。')
    return 0
    
def do_sign_in(driver):
    """使用Selenium执行签到操作"""
    global checkIn_status
    
    try:
        print("正在执行签到操作...")
        
        # 访问签到页面
        sign_page_url = f"{main_url}{sign_url}"
        print(f"访问签到页面: {sign_page_url}")
        # 设置cookie
        for cookie_name, cookie_value in cookies.items():
            driver.add_cookie({'name': cookie_name, 'value': cookie_value})
        
        # 访问签到页面
        driver.get(sign_page_url)
        
        # 等待页面加载完成
        wait = WebDriverWait(driver, 15)
        wait.until(EC.presence_of_element_located((By.ID, 'JD_sign')))
        
        # 检查是否已经签到
        page_source = driver.page_source
        if "今日已签" in page_source or "您今天已经签到过了" in page_source:
            print("今日已签到")
            checkIn_status = 0
            return True
        
        # 点击签到按钮
        sign_button = driver.find_element(By.ID, 'JD_sign')
        print("找到签到按钮，准备点击")
        
        # 在点击前截图
        driver.save_screenshot("before_sign.png")
        
        # 执行点击
        sign_button.click()
        print("已点击签到按钮")
        
        # 等待签到结果
        time.sleep(2)
        
        # 在点击后截图
        driver.save_screenshot("after_sign.png")
        
        # 检查签到结果
        new_page_source = driver.page_source
        if "今日已签" in new_page_source or "您今天已经签到过了" in new_page_source:
            print("签到成功，页面显示今日已签到")
            checkIn_status = 0
            return True
        elif "签到成功" in new_page_source:
            print("签到成功")
            checkIn_status = 1
            return True
        else:
            print("签到后页面未显示成功信息，可能签到失败")
            
            # 尝试刷新页面再次检查
            driver.refresh()
            time.sleep(2)
            
            # 检查刷新后的页面
            refresh_page_source = driver.page_source
            if "今日已签" in refresh_page_source or "您今天已经签到过了" in refresh_page_source:
                print("刷新后确认签到成功")
                checkIn_status = 0
                return True
            
            checkIn_status = 2
            return False
            
    except Exception as e:
        print(f"签到过程中出现异常: {str(e)}")
        checkIn_status = 2
        return False

def printUserInfo(driver):
    """获取用户信息"""
    global send_content, checkIn_status
    
    try:
        print("准备获取用户信息...")
        
        # 打开签到页面获取签到信息
        print(f"访问签到页面: {main_url}{sign_url}")
        driver.get(f'{main_url}{sign_url}')
        
        # 使用显式等待确保页面加载完成
        wait = WebDriverWait(driver, 20)
        
        # 等待并获取签到相关信息
        wait.until(EC.presence_of_element_located((By.ID, 'qiandaobtnnum')))
        
        # 获取签到信息
        qiandao_num = driver.find_element(By.ID, 'qiandaobtnnum').get_attribute('value')
        lxdays = driver.find_element(By.ID, 'lxdays').get_attribute('value')
        lxtdays = driver.find_element(By.ID, 'lxtdays').get_attribute('value')
        lxlevel = driver.find_element(By.ID, 'lxlevel').get_attribute('value')
        lxreward = driver.find_element(By.ID, 'lxreward').get_attribute('value')
        
        # 修改：检查签到状态
        try:
            # 检查页面上是否有签到成功的信息
            page_content = driver.page_source
            if "今日已签" in page_content or "您今天已经签到过了" in page_content:
                print("页面显示今日已签到")
                checkIn_status = 0
            elif "签到成功" in page_content:
                print("页面显示签到成功")
                checkIn_status = 1
        except:
            # 如果无法检查，保持当前状态
            pass
        
        # 格式化签到信息内容
        lxqiandao_content = f'签到排名：{qiandao_num}\n签到等级：Lv.{lxlevel}\n连续签到：{lxdays} 天\n签到总数：{lxtdays} 天\n签到奖励：{lxreward}\n'
        
        # 打开个人主页获取用户信息
        print(f"访问个人主页: {main_url}/home.php?mod=space")
        driver.get(f'{main_url}/home.php?mod=space')
        
        try:
            # 等待页面加载完成，确保用户名元素存在
            wait.until(EC.presence_of_element_located((By.XPATH, '//*[@id="ct"]')))
            
            # 截图保存当前页面（调试用）
            driver.save_screenshot("profile_page.png")
            
            # 尝试获取用户名，使用多种可能的XPath
            xm = None
            xpaths = [
                '//*[@id="ct"]/div/div[2]/div/div[1]/div[1]/h2',
                '//div[contains(@class, "h")]/h2',
                '//h2[contains(@class, "mt")]',
                '//div[contains(@id, "profile")]//h2'
            ]
            
            for xpath in xpaths:
                try:
                    elements = driver.find_elements(By.XPATH, xpath)
                    if elements:
                        xm = elements[0].text.strip()
                        print(f"找到用户名: {xm}")
                        break
                except:
                    continue
            
            if not xm:
                # 如果无法获取用户名，可能是页面结构变化
                print("警告: 无法获取用户名，将使用默认值")
                xm = "未知用户"
            
            # 获取各项数据，使用更灵活的方法
            jf = ww = cp = gx = "未知"
            
            try:
                # 尝试按照常规布局查找统计信息
                stats_container = driver.find_element(By.ID, "psts")
                stats = stats_container.find_elements(By.TAG_NAME, "li")
                
                # 遍历所有li元素查找统计信息
                for stat in stats:
                    stat_text = stat.text.lower()
                    if "积分" in stat_text:
                        jf = stat_text
                    elif "威望" in stat_text:
                        ww = stat_text
                    elif "车票" in stat_text:
                        cp = stat_text
                    elif "贡献" in stat_text:
                        gx = stat_text
            except:
                # 备用方法：尝试通过其他方式获取
                try:
                    all_elements = driver.find_elements(By.XPATH, "//*[contains(text(), '积分') or contains(text(), '威望') or contains(text(), '车票') or contains(text(), '贡献')]")
                    
                    for element in all_elements:
                        text = element.text.lower()
                        if "积分" in text:
                            jf = text
                        elif "威望" in text:
                            ww = text
                        elif "车票" in text:
                            cp = text
                        elif "贡献" in text:
                            gx = text
                except Exception as e:
                    print(f"无法获取详细统计信息: {str(e)}")
            
            # 格式化输出内容并居中
            xm = "账户【" + xm + "】"
            xm = xm.center(24, '=')
            
            info_text = (
                f'{xm}\n'
                f'签到状态: {checkIn_content[checkIn_status]} \n'
                f'{lxqiandao_content} \n'
                f'当前积分: {jf}\n'
                f'当前威望: {ww}\n'
                f'当前车票: {cp}\n'
                f'当前贡献: {gx}\n\n'
            )
            
            print(info_text)
            send_content += info_text
            return True
            
        except TimeoutException:
            print("获取用户信息超时")
            # 截图当前页面以便调试
            driver.save_screenshot("timeout_error.png")
            print("页面源码:", driver.page_source)
            send_content += f'获取用户信息超时，请检查网络或站点状态\n\n'
            return False
            
    except Exception as e:
        print(f'获取用户信息失败: {str(e)}')
        # 保存屏幕截图以便调试
        try:
            driver.save_screenshot("error_screenshot.png")
            print("保存错误截图到 error_screenshot.png")
        except:
            pass
        send_content += f'获取用户信息失败: {str(e)}\n\n'
        return False

def start(postdata):
    """主函数，处理账号信息并执行签到"""
    global send_content, ocr, cookies
    
    try:
        # 初始化OCR
        ocr = ddddocr.DdddOcr()
        
        # 初始化WebDriver
        driver = initialize_webdriver()
        
        try:
            # 账号数据按格式分割
            payload = re.split('@|\n', postdata)
            print('发现', len(payload), '个账号信息\n')
            send_content += f'发现 {len(payload)} 个账号信息\n'
        except Exception as e:
            print(f'环境变量格式错误: {str(e)}, 程序退出')
            exit(0)
        
        for i in payload:
            try:
                u = i.split('&')
                # 读取账号到变量，密码直接使用原始密码
                name = u[0]
                pwd = u[1]  # 不再使用MD5加密，因为Selenium需要使用原始密码
                print(f'处理账号: {name}')
            except:
                print('账号参数格式错误')
                send_content += "账号参数格式错误\n\n"
                continue

            # 刷新cookie和formhash值，用作登录
            if not get_cookie_formhash(driver):
                send_content += f'账号{name}获取登录页面失败\n\n'
                continue
                
            # 识别验证码
            crack_captcha()
            
            # 使用Selenium登录
            if not login(name, pwd):
                send_content += f'账号{name}登录失败,请检查账号密码\n\n'
                continue
                
            # 使用Selenium执行签到
            do_sign_in(driver)
            
            # 获取用户信息
            printUserInfo(driver)
            
            # 每个账号处理完毕后等待一段时间
            time.sleep(3)
        
        # 关闭WebDriver
        driver.quit()
        
        # 发送通知
        send('司机社签到', send_content)
        
    except Exception as e:
        print(f'执行过程中发生错误: {str(e)}')
        send_content += f'执行过程中发生错误: {str(e)}\n'
        send('司机社签到', send_content)

# 阿里云函数入口
def handler(event, context):
    try:
        _postdata = "账号&密码"
    except Exception:
        print('未设置环境变量 XSIJISHE')
        exit(0)
        
    # 添加随机延时
    delay = random.randint(0, 1)  # 随机延时0-1秒
    time.sleep(delay)
    
    # 获取网站地址并执行签到
    if get_new_url():
        start(_postdata)
    exit(0)

if __name__ == '__main__':
    handler('', '')
