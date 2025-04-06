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

from neo4j import GraphDatabase
import networkx as nx
from os import getenv
import matplotlib.pyplot as plt
import matplotlib
from dotenv import load_dotenv
import numpy as np
from weibo_follow import Follow
import json
import uuid

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


async def process_user(user_id: str) -> str:
    """
    封装的函数，以 user_id 作为输入参数，爬取互动关系并存入数据库。
    使用示例:
        result = asyncio.run(process_user(123456789))
    """
    graph = WeiboGraph(NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD)
    try:
        async with ClientSession(cookies=cookies) as session:
            await run(session, graph, user_id)
        return "成功爬取用户互动关系，可通过 http://localhost:7474 访问Neo4j Browser界面查看数据"
    except Exception as e:
        logging.error(f"处理用户 {user_id} 时发生错误: {e}")
        return f"失败: {str(e)}"
    




def follow_network(user_id, cookie):
    # 将爬取的关注列表写入network.txt
    fw = Follow(user_id, cookie)    # 调用Weibo类，创建微博实例wb
    fw.get_follow_list()            # 获取关注列表的uid和昵称
    #print(fw.follow_list)           # 输出关注列表的uid
    #print(fw.follow_name_list)      # 输出关注列表的昵称

    # 返回关注关系列表和用户信息
    follow_relations = [(user_id, follow_id) for follow_id in fw.follow_list if user_id != follow_id]
    user_info = {}  # 主用户信息
    for follow_id, follow_name in zip(fw.follow_list, fw.follow_name_list):
        if follow_id == user_id:
            continue  # 跳过主用户
        user_info[follow_id] = {"screen_name": follow_name}  # 关注用户信息

    return follow_relations, user_info

def merge_user_and_post(G):
    nodes_to_remove = []
    edges_to_add = []
    
    for u, v, key, data in list(G.edges(data=True, keys=True)):
        if data.get('label') in {'POSTED', 'REPOSTED', 'COMMENTED'}:
            user_id = u
            post_id = v

            for pred in list(G.predecessors(v)):
                if pred != u:
                    for k, edge_data in G.get_edge_data(pred, v).items():
                        G.add_edge(pred, user_id, key=k, **edge_data)
                G.remove_edge(pred, v)

            for succ in list(G.successors(v)):
                if succ != u:
                    for k, edge_data in G.get_edge_data(v, succ).items():
                        G.add_edge(user_id, succ, key=k, **edge_data)
                G.remove_edge(v, succ)
            
            nodes_to_remove.append(v)
    
    for node in set(nodes_to_remove):
        G.remove_node(node)

    print("用户和贴子节点已成功合并")
    return G

def get_data(tx):
    query = """
    MATCH (n)-[r]->(m)
    RETURN n, r, m, n.id as node1_id, m.id as node2_id
    """
    return list(tx.run(query))


def convert_to_nx_graph(driver):
    with driver.session() as session:
        records = session.execute_read(get_data)

        for record in records:
            node1 = record["n"]
            node2 = record["m"]
            relation = record["r"]
            node1_id = record["node1_id"]
            node2_id = record["node2_id"]

            G.add_node(node1_id, label=node1["label"], properties=node1._properties)
            G.add_node(node2_id, label=node2["label"], properties=node2._properties)
            # 根据关系类型赋予权重
            weight = 0
            if relation.type == "LIKED":
                weight = 1
            elif relation.type == "COMMENTS":
                weight = 2
            elif relation.type == "REPOST_OF":
                weight = 3
            
            G.add_edge(node1_id, node2_id, key=relation.element_id, label=relation.type, properties=relation._properties, weight=weight)

    print("Neo4j数据已成功转换为NetworkX图")

def calculate_association_degree(G, target_node):
    if target_node not in G:
        raise ValueError(f"目标节点 {target_node} 不在图中")

    association_degrees = {}
    for node in G.nodes():
        if node != target_node:
            # 计算从其他节点指向目标节点的边的权重总和
            incoming_edges = G.get_edge_data(node, target_node, default={})
            incoming_weight = sum(edge_data['weight'] for edge_data in incoming_edges.values())

            # 计算从目标节点指向其他节点的边的权重总和
            outgoing_edges = G.get_edge_data(target_node, node, default={})
            outgoing_weight = sum(edge_data['weight'] for edge_data in outgoing_edges.values())

            # 总关联度为双向权重之和
            total_weight = incoming_weight + outgoing_weight
            association_degrees[node] = total_weight

    return association_degrees


def draw_tight_graph(G, target_node, association_degrees):
    # 筛选出与目标节点关联度大的节点
    threshold = 5  # 根据需要调整这个阈值
    relevant_nodes = [node for node, degree in association_degrees.items() if degree >= threshold]
    relevant_nodes.append(target_node)  # 确保目标节点也在子图中

    # 创建子图
    subgraph = G.subgraph(relevant_nodes)

    # 获取子图中的边
    subgraph_edges = list(subgraph.edges(keys=True, data=True))

    # 绘制子图
    pos = nx.spring_layout(subgraph, weight='weight', k=1, iterations=20)
    node_labels = {node: data.get('properties', {}).get('screen_name', node) for node, data in subgraph.nodes(data=True)}

    # 绘制节点
    nx.draw_networkx_nodes(subgraph, pos, node_size=500, node_color="skyblue")
    nx.draw_networkx_labels(subgraph, pos, labels=node_labels, font_size=10, font_weight="bold")

    # 处理多重边
    edge_weights = {}  # 用于存储每对节点之间的总权重
    edge_labels = {}  # 用于存储每对节点之间的标签

    for (u, v, key, data) in subgraph_edges:
        edge_key = tuple(sorted((u, v)))  # 确保(u, v)和(v, u)被视为同一对节点
        label = data.get('label', '')
        weight = data.get('weight', 1)  # 获取边的权重，如果没有则默认为 1

        if edge_key not in edge_weights:
            edge_weights[edge_key] = weight
            edge_labels[edge_key] = label
        else:
            edge_weights[edge_key] += weight  # 累加权重
            edge_labels[edge_key] += f" + {label}"  # 将标签相连接

    # 绘制边
    for (u, v), weight in edge_weights.items():
        edge_color = 'black'  # 默认边的颜色
        alpha = 0.5  # 边的透明度

        # 绘制边，使用不同的颜色或透明度来区分多重边
        nx.draw_networkx_edges(subgraph, pos, edgelist=[(u, v)], arrows=True, edge_color=edge_color, alpha=alpha)

        # 获取边的方向向量
        source = pos[u]
        target = pos[v]
        edge_vector = np.array(target) - np.array(source)
        edge_length = np.linalg.norm(edge_vector)
        edge_direction = edge_vector / edge_length

        # 计算标签的位置
        label_position = source + edge_direction * edge_length * 0.5  # 标签放在边的中间位置
        label_offset = edge_direction * 0.05  # 标签的偏移量，可以根据需要调整

        # 沿着边的方向显示标签
        label = edge_labels[(u, v)]
        plt.annotate(label, xy=label_position, xytext=label_offset, textcoords='offset points',
                     fontsize=5, color='red', ha='center', va='center', rotation=np.degrees(np.arctan2(edge_direction[1], edge_direction[0])))

    # 标注目标节点
    nx.draw_networkx_nodes(subgraph, pos, nodelist=[target_node], node_color='red', node_size=500)

    plt.axis('off')  # 关闭坐标轴
    return plt

def get_social_network(target_node):
    # 设置matplotlib支持中文
    matplotlib.rcParams['font.sans-serif'] = ['SimHei']  # 使用黑体
    matplotlib.rcParams['font.family'] = 'sans-serif'
    matplotlib.rcParams['axes.unicode_minus'] = False  # 正确显示负号

    # 配置Neo4j连接
    load_dotenv()
    NEO4J_URI = getenv("NEO4J_URI")
    NEO4J_USER = getenv("NEO4J_USER")
    NEO4J_PASSWORD = getenv("NEO4J_PASSWORD")

    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))

    # 创建NetworkX多重有向图
    G = nx.MultiDiGraph()

    convert_to_nx_graph(driver)
    driver.close()
    G = merge_user_and_post(G)

    with open("cookies.json", "r") as f:
        cookies = json.load(f)

    follow_relations, user_info = follow_network(target_node, cookies)

    # 将用户节点添加到图中
    for user_id, user_data in user_info.items():
        if user_id not in G.nodes:
            G.add_node(int(user_id), label="USER", properties=user_data)


    # 将关注关系添加到图中
    for user_id, follow_id in follow_relations:
        edge_key = str(uuid.uuid4())  # 生成随机的唯一键
        G.add_edge(int(user_id), int(follow_id), key=edge_key, label="FOLLOWS", weight=5)

    G.remove_edges_from(nx.selfloop_edges(G))
    #print(G.nodes(data=True))
    #print(G.edges(data=True, keys=True))

    # 计算与目标节点的关联度
    association_degrees = calculate_association_degree(G, target_node)

    # 输出关联度
    for node, degree in association_degrees.items():
        print(f"节点 {node} 与节点 {target_node} 的关联度为: {degree}")


    TG=draw_tight_graph(G, target_node, association_degrees)
    return TG
