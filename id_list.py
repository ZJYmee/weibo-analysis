import requests
from lxml import etree
import json

class WeiboIDScraper:
    def __init__(self, user_id, cookie):
        """
        初始化
        :param user_id: 目标用户的微博用户 ID
        :param cookie: 登录后的微博 Cookie
        """
        self.user_id = user_id
        self.cookie = cookie
        self.weibo_id_list = []  # 存储爬取到的微博 ID

    def get_page_count(self):
        """
        获取微博总页数
        """
        url = f"https://weibo.cn/u/{self.user_id}?filter=0&page=1"
        response = requests.get(url, cookies=self.cookie)
        selector = etree.HTML(response.content)
        if selector.xpath("//input[@name='mp']"):
            return int(selector.xpath("//input[@name='mp']")[0].attrib['value'])
        return 1

    def get_weibo_ids_from_page(self, page):
        """
        从单页中提取微博 ID
        :param page: 页面编号
        """
        url = f"https://weibo.cn/u/{self.user_id}?filter=0&page={page}"
        response = requests.get(url, cookies=self.cookie)
        selector = etree.HTML(response.content)
        link_list = selector.xpath("//div[@class='c']/div/a/@href")
        for link in link_list:
            if "comment" in link:
                weibo_id = link.split("/")[-1].split("?")[0]
                if weibo_id not in self.weibo_id_list:
                    self.weibo_id_list.append(weibo_id)

    def get_all_weibo_ids(self):
        """
        获取所有微博 ID
        """
        page_count = self.get_page_count()
        print(f"微博总页数：{page_count}")
        for page in range(1, 1 + 1):
            print(f"正在爬取第 {page} 页")
            self.get_weibo_ids_from_page(page)
        print(f"共获取到 {len(self.weibo_id_list)} 条微博 ID")
        return self.weibo_id_list


if __name__ == "__main__":
    user_id = "2549228714"  # 替换为目标用户的微博 ID
    with open("cookies.json", "r") as f:
        cookie = json.load(f)
    scraper = WeiboIDScraper(user_id, cookie)
    weibo_ids = scraper.get_all_weibo_ids()
    print("微博 ID 列表：")
    print(weibo_ids)