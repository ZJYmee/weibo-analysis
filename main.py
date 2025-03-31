import logging
from argparse import ArgumentParser
from asyncio import Queue, Runner, sleep
from asyncstdlib.functools import cache
from os import getenv

from aiohttp import ClientSession
from dotenv import load_dotenv

from graph import WeiboGraph
from model import Comment, Post, User
import json

import requests
from lxml import etree

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
        for page in range(1, page_count + 1):
            print(f"正在爬取第 {page} 页")
            self.get_weibo_ids_from_page(page)
        print(f"共获取到 {len(self.weibo_id_list)} 条微博 ID")
        return self.weibo_id_list

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)


# Load env
load_dotenv()
NEO4J_URI = getenv("NEO4J_URI")
NEO4J_USER = getenv("NEO4J_USER")
NEO4J_PASSWORD = getenv("NEO4J_PASSWORD")

with open("cookies.json", "r") as f:
    cookies = json.load(f)


def extract_user(data) -> User:
    user = User(
        id=data["id"],
        location=data["location"],
        screen_name=data["screen_name"],
        followers_count=data["followers_count"],
        friends_count=data["friends_count"],
        gender=data["gender"],
        description=data["description"],
    )

    return user


def extract_comment(data) -> Comment:
    comment = Comment(
        id=data["id"],
        text_raw=data["text_raw"],
        source=data.get("source", "未知"),
        created_at=data["created_at"],
    )

    return comment


async def get_reposts(session: ClientSession, id: str) -> list[tuple[str, User, Post]]:
    page = 1
    count = 0
    reposts = []
    logging.info(f"Fetching reposts for post ID: {id}")
    while True:
        resp = await session.get(
            f"https://weibo.com/ajax/statuses/repostTimeline?id={id}&page={page}&moduleID=feed&count=10"
        )
        data = await resp.json()

        if len(data["data"]) == 0:
            break

        total = data["total_number"]

        for item in data["data"]:
            try:
                post = await get_post(session, item["mblogid"])
                reposts.append((item["mblogid"], *post))
            except Exception as e:
                logging.error(e)

            await sleep(1)

        count += len(data["data"])

        logging.info(
            f"Fetched {len(data['data'])} reposts on page {page} (total so far: {count}/{total})"
        )

        if count >= total:
            break

        page += 1

        await sleep(1)

    return reposts


async def get_user(session: ClientSession, id: str) -> User:
    logging.info(f"Fetching user details for user ID: {id}")

    @cache
    async def _get_user(id: str):
        resp = await session.get(f"https://weibo.com/ajax/profile/info?uid={id}")
        data = await resp.json()

        data = data["data"]["user"]

        user = User(
            id=id,
            location=data["location"],
            screen_name=data["screen_name"],
            followers_count=data["followers_count"],
            friends_count=data["friends_count"],
            gender=data["gender"],
            description=data["description"],
        )

        return user

    return await _get_user(id)


async def get_post(session: ClientSession, id: str) -> tuple[User, Post]:
    logging.info(f"Fetching post details for post ID: {id}")
    resp = await session.get(
        f"https://weibo.com/ajax/statuses/show?id={id}&locale=zh-CN&isGetLongText=true"
    )
    data = await resp.json()

    await sleep(0.5)
    user = await get_user(session, data["user"]["id"])
    post = Post(id=data["id"], text_raw=data["text_raw"], created_at=data["created_at"])

    return user, post


async def get_comments(session: ClientSession, id: str) -> list[tuple[User, Comment]]:
    max_id = ""
    count = 0
    comments = []
    logging.info(f"Fetching comments for post ID: {id}")
    while True:

        resp = await session.get(
            f"https://weibo.com/ajax/statuses/buildComments?is_reload=1&id={id}&is_show_bulletin=2&is_mix=0&count=10&fetch_level=0&locale=zh-CN&max_id={max_id}"
        )
        data = await resp.json()

        if len(data["data"]) == 0:
            break

        total = data["total_number"]

        for item in data["data"]:
            comments.append((extract_user(item["user"]), extract_comment(item)))

        count += len(data["data"])

        logging.info(
            f"Fetched {len(data['data'])} comments (total so far: {count}/{total})"
        )

        if count >= total:
            break

        max_id = data["max_id"]

        await sleep(1)

    return comments


async def get_attitudes(session: ClientSession, id: str) -> list[User]:
    page = 1
    count = 0
    users = []
    logging.info(f"Fetching attitudes for post ID: {id}")
    while True:
        resp = await session.get(
            f"https://weibo.com/ajax/statuses/likeShow?id={id}&attitude_type=0&attitude_enable=1&page={page}&count=10"
        )
        data = await resp.json()

        if len(data["data"]) == 0:
            break

        total = data["total_number"]

        for item in data["data"]:
            users.append(extract_user(item["user"]))

        count += len(data["data"])

        logging.info(
            f"Fetched {len(data['data'])} attitudes on page {page} (total so far: {count}/{total})"
        )

        if count >= total:
            break

        page += 1

        await sleep(1)

    return users


async def entry(session: ClientSession, graph: WeiboGraph, id: str, entriesq: Queue):
    logging.info(f"Processing entry ID: {id}")

    # Process the post self
    user, post = await get_post(session, id)
    await graph.create_user(user)
    await graph.create_post(post, user.id)

    # Process the reposts
    reports = await get_reposts(session, post.id)
    for mblogid, user, report in reports:
        await graph.create_user(user)
        await graph.create_post(report, user.id)
        await graph.create_repost_relationship(user.id, report.id, post.id)
        await entriesq.put(mblogid)

    # Process the attitudes
    users = await get_attitudes(session, post.id)
    for user in users:
        await graph.create_user(user)
        await graph.create_like_relationship(user.id, post.id)

    # Process the comments
    comments = await get_comments(session, post.id)
    for user, comment in comments:
        await graph.create_user(user)
        await graph.create_comment(comment, user.id, post.id)

    logging.info(f"Finished processing entry ID: {id}")


async def run(session: ClientSession, graph: WeiboGraph, user_id: str):
    scraper = WeiboIDScraper(user_id, cookies)
    weibo_ids = scraper.get_all_weibo_ids()
    entriesq = Queue()
    for item in weibo_ids:
        await entriesq.put(item)

    while not entriesq.empty():
        id = await entriesq.get()

        logging.info(f"Starting processing for entry ID: {id}")
        await entry(session, graph, id, entriesq)

    logging.info("All tasks completed.")


async def main():
    parser = ArgumentParser()
    parser.add_argument(
        "-u", "--user", type=str, help="The user ID", required=True
    )
    args = parser.parse_args()

    user_id = args.user

    graph = WeiboGraph(NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD)
    async with ClientSession(cookies=cookies) as session:
        await run(session, graph, user_id)


if __name__ == "__main__":
    with Runner() as runner:
        runner.run(main())
