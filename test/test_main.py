import importlib
from pathlib import Path
from unittest.mock import AsyncMock, Mock, call, patch, MagicMock
from aiohttp import ClientSession
import sys
import unittest
from unittest import IsolatedAsyncioTestCase
from aiohttp.test_utils import AioHTTPTestCase, unittest_run_loop
from aiohttp import web
import json

from requests import session

# 设置项目根目录路径
PROJECT_ROOT = str(Path(__file__).parent.parent)
sys.path.insert(0, PROJECT_ROOT)

# 动态导入主模块
main = importlib.import_module('main')
from model import User, Post, Comment  # 使用绝对导入
from main import entry, main as main_func
# 获取测试目标组件
WeiboIDScraper = main.WeiboIDScraper
extract_user = main.extract_user
extract_comment = main.extract_comment
get_user = main.get_user
get_post = main.get_post
get_comments = main.get_comments
get_attitudes = main.get_attitudes
get_reposts = main.get_reposts
run = main.run
WeiboGraph = main.WeiboGraph

# 获取cookies.json的绝对路径
COOKIES_PATH = Path(__file__).parent.parent / "cookies.json"
def load_cookies():
    with open(COOKIES_PATH, 'r', encoding='utf-8') as f:
        return json.load(f)
    
class TestWeiboIDScraper(unittest.TestCase):
    @patch('requests.get')
    def test_get_page_count(self, mock_get):
        mock_response = MagicMock()
        mock_response.content = b'<input name="mp" value="5"/>'
        mock_get.return_value = mock_response

        scraper = WeiboIDScraper('12345', {'cookie': 'test'})
        page_count = scraper.get_page_count()
        self.assertEqual(page_count, 5)

    @patch('requests.get')
    def test_get_weibo_ids_from_page(self, mock_get):
        mock_response = MagicMock()
        mock_response.content = b'<div class="c"><div><a href="/comment/12345?">comment</a></div></div>'
        mock_get.return_value = mock_response

        scraper = WeiboIDScraper('12345', {'cookie': 'test'})
        scraper.get_weibo_ids_from_page(1)
        self.assertIn('12345', scraper.weibo_id_list)

    @patch.object(WeiboIDScraper, 'get_page_count', return_value=3)
    @patch.object(WeiboIDScraper, 'get_weibo_ids_from_page')
    def test_get_all_weibo_ids(self, mock_get_weibo_ids_from_page, mock_get_page_count):
        # 创建 WeiboIDScraper 实例，提供必要的参数
        user_id = 'test_user'
        config = MagicMock()  # 或者使用实际的配置对象
        scraper = WeiboIDScraper(user_id, config)
        scraper.weibo_id_list = []

        # 模拟 get_weibo_ids_from_page 方法
        def mock_get_weibo_ids(page):
            scraper.weibo_id_list.append(f"weibo_id_page_{page}")

        mock_get_weibo_ids_from_page.side_effect = mock_get_weibo_ids

        # 调用 get_all_weibo_ids 方法
        result = scraper.get_all_weibo_ids()

        # 验证 get_page_count 被调用一次
        mock_get_page_count.assert_called_once()

        # 验证 get_weibo_ids_from_page 被调用了正确的次数和参数
        self.assertEqual(mock_get_weibo_ids_from_page.call_count, 3)
        mock_get_weibo_ids_from_page.assert_any_call(1)
        mock_get_weibo_ids_from_page.assert_any_call(2)
        mock_get_weibo_ids_from_page.assert_any_call(3)

        # 验证返回的微博 ID 列表
        expected_result = ['weibo_id_page_1', 'weibo_id_page_2', 'weibo_id_page_3']
        self.assertEqual(result, expected_result)

class TestExtractFunctions(unittest.TestCase):
    def test_extract_user(self):
        user_data = {
            "id": "123",
            "location": "Beijing",
            "screen_name": "test_user",
            "followers_count": 100,
            "friends_count": 50,
            "gender": "m",
            "description": "Test description"
        }
        
        user = extract_user(user_data)
        
        self.assertEqual(str(user.id), "123")
        self.assertEqual(user.location, "Beijing")
        self.assertEqual(user.screen_name, "test_user")
        self.assertEqual(user.followers_count, 100)
        self.assertEqual(user.friends_count, 50)
        self.assertEqual(user.gender, "m")
        self.assertEqual(user.description, "Test description")
    
    def test_extract_comment(self):
        comment_data = {
            "id": "456",
            "text_raw": "Test comment",
            "source": "Test source",
            "created_at": "2023-01-01"
        }
        
        comment = extract_comment(comment_data)
        
        self.assertEqual(str(comment.id), "456")
        self.assertEqual(comment.text_raw, "Test comment")
        self.assertEqual(comment.source, "Test source")
        self.assertEqual(comment.created_at, "2023-01-01")
    
    def test_extract_comment_no_source(self):
        comment_data = {
            "id": "456",
            "text_raw": "Test comment",
            "created_at": "2023-01-01"
        }
        
        comment = extract_comment(comment_data)
        
        self.assertEqual(str(comment.id), "456")
        self.assertEqual(comment.text_raw, "Test comment")
        self.assertEqual(comment.source, "未知")
        self.assertEqual(comment.created_at, "2023-01-01")

class TestAsyncFunctions(IsolatedAsyncioTestCase):
    async def test_get_user(self):
        user_id = "123456"
        user_data = {
            "data": {
                "user": {
                    "id": user_id,
                    "location": "Beijing",
                    "screen_name": "test_user",
                    "followers_count": 100,
                    "friends_count": 50,
                    "gender": "m",
                    "description": "This is a test user"
                }
            }
        }
        
        # 创建模拟的 session
        session = AsyncMock()
        mock_response = AsyncMock()
        mock_response.json.return_value = user_data
        session.get.return_value = mock_response
        
        # 调用被测试的函数
        user = await get_user(session, user_id)
        
        # 验证结果
        self.assertEqual(str(user.id), user_id)
        self.assertEqual(user.location, "Beijing")
        self.assertEqual(user.screen_name, "test_user")
        self.assertEqual(user.followers_count, 100)
        self.assertEqual(user.friends_count, 50)
        self.assertEqual(user.gender, "m")
        self.assertEqual(user.description, "This is a test user")
        
        # 验证 session.get 被正确调用
        session.get.assert_called_once_with(f"https://weibo.com/ajax/profile/info?uid={user_id}")

    @patch('main.get_user', new_callable=AsyncMock)
    async def test_get_post(self, mock_get_user):
        # 模拟 get_user 的返回值
        mock_get_user.return_value = User(
            id='123', 
            location='test', 
            screen_name='test', 
            followers_count=0, 
            friends_count=0, 
            gender='m', 
            description='test'
        )
        
        # 模拟 post 数据
        post_data = {
            'id': '12345',
            'text_raw': 'test post',
            'created_at': '2023-01-01',
            'user': {
                'id': '123', 
                'location': 'test', 
                'screen_name': 'test', 
                'followers_count': 0, 
                'friends_count': 0, 
                'gender': 'm', 
                'description': 'test'
            }
        }
        
        # 创建模拟的 session
        session = AsyncMock()
        mock_response = AsyncMock()
        mock_response.json.return_value = post_data
        session.get.return_value = mock_response
        
        # 调用被测试的函数
        user, post = await get_post(session, '12345')
        
        # 验证结果
        self.assertEqual(str(post.id), '12345')
        self.assertEqual(post.text_raw, 'test post')
        self.assertEqual(str(user.id), '123')
        
        # 验证调用
        session.get.assert_called_once_with(
            "https://weibo.com/ajax/statuses/show?id=12345&locale=zh-CN&isGetLongText=true"
        )
        mock_get_user.assert_called_once_with(session, '123')

    async def test_get_comments(self):
        # 模拟评论数据
        comments_data = {
            'data': [
                {
                    'id': '12345', 
                    'text_raw': 'test comment', 
                    'created_at': '2023-01-01', 
                    'source': 'test source',
                    'user': {
                        'id': '123', 
                        'location': 'test', 
                        'screen_name': 'test', 
                        'followers_count': 0, 
                        'friends_count': 0, 
                        'gender': 'm', 
                        'description': 'test'
                    }
                }
            ],
            'total_number': 1,
            'max_id': ''
        }
        
        # 创建模拟的 session
        session = AsyncMock()
        mock_response = AsyncMock()
        mock_response.json.return_value = comments_data
        session.get.return_value = mock_response
        
        # 调用被测试的函数
        comments = await get_comments(session, '12345')
        
        # 验证结果
        self.assertEqual(len(comments), 1)
        self.assertEqual(str(comments[0][1].id), '12345')
        self.assertEqual(comments[0][1].text_raw, 'test comment')
        self.assertEqual(str(comments[0][0].id), '123')
        
        # 验证调用
        session.get.assert_called_once()

    async def test_get_attitudes(self):
        # 模拟点赞数据
        attitudes_data = {
            'data': [
                {
                    'user': {
                        'id': '123', 
                        'location': 'test', 
                        'screen_name': 'test', 
                        'followers_count': 0, 
                        'friends_count': 0, 
                        'gender': 'm', 
                        'description': 'test'
                    }
                }
            ],
            'total_number': 1
        }
        
        # 创建模拟的 session
        session = AsyncMock()
        mock_response = AsyncMock()
        mock_response.json.return_value = attitudes_data
        session.get.return_value = mock_response
        
        # 调用被测试的函数
        users = await get_attitudes(session, '12345')
        
        # 验证结果
        self.assertEqual(len(users), 1)
        self.assertEqual(str(users[0].id), '123')
        
        # 验证调用
        session.get.assert_called_once()

    @patch('main.get_post', new_callable=AsyncMock)
    async def test_get_reposts(self, mock_get_post):
        # 模拟 get_post 的返回值
        mock_get_post.return_value = (
            User(
                id='123', 
                location='test', 
                screen_name='test', 
                followers_count=0, 
                friends_count=0, 
                gender='m', 
                description='test'
            ),
            Post(
                id='12345', 
                text_raw='test post', 
                created_at='2023-01-01'
            )
        )
        
        # 模拟转发数据
        reposts_data = {
            'data': [
                {'mblogid': '12345'}
            ],
            'total_number': 1
        }
        
        # 创建模拟的 session
        session = AsyncMock()
        mock_response = AsyncMock()
        mock_response.json.return_value = reposts_data
        session.get.return_value = mock_response
        
        # 模拟 sleep 函数避免实际等待
        with patch('main.sleep', new_callable=AsyncMock) as mock_sleep:
            # 调用被测试的函数
            reposts = await get_reposts(session, '67890')
            
            # 验证结果
            self.assertEqual(len(reposts), 1)
            self.assertEqual(reposts[0][0], '12345')
            self.assertEqual(str(reposts[0][1].id), '123')
            self.assertEqual(str(reposts[0][2].id), '12345')
            
            # 验证调用
            session.get.assert_called_once()
            mock_get_post.assert_called_once_with(session, '12345')
            mock_sleep.assert_called()

class TestRunFunction(IsolatedAsyncioTestCase):
    @patch('main.WeiboIDScraper')
    @patch('main.entry', new_callable=AsyncMock)
    async def test_run(self, mock_entry, MockWeiboIDScraper):
        # 模拟 WeiboIDScraper 和 get_all_weibo_ids
        mock_scraper = MagicMock()
        mock_scraper.get_all_weibo_ids.return_value = ['12345', '67890']
        MockWeiboIDScraper.return_value = mock_scraper
        
        # 创建模拟的 session 和 graph
        session = AsyncMock()
        graph = AsyncMock()
        
        # 调用被测试的函数
        await run(session, graph, '12345')
        
        # 验证调用
        MockWeiboIDScraper.assert_called_once_with('12345', main.cookies)
        mock_scraper.get_all_weibo_ids.assert_called_once()
        self.assertEqual(mock_entry.call_count, 2)
        
        # 验证 entry 被调用的参数
        expected_calls = [
            unittest.mock.call(session, graph, '12345', unittest.mock.ANY),
            unittest.mock.call(session, graph, '67890', unittest.mock.ANY)
        ]
        mock_entry.assert_has_calls(expected_calls, any_order=True)

class TestEntryFunction(IsolatedAsyncioTestCase):
    @patch('main.get_comments', new_callable=AsyncMock)
    @patch('main.get_attitudes', new_callable=AsyncMock)
    @patch('main.get_reposts', new_callable=AsyncMock)
    @patch('main.get_post', new_callable=AsyncMock)
    async def test_entry(self, mock_get_post, mock_get_reposts, mock_get_attitudes, mock_get_comments):
        # 1. 定义所有需要的变量
        post_id = '12345'
        
        # 主用户和帖子
        user = User(
            id='123',
            location='test',
            screen_name='test',
            followers_count=0,
            friends_count=0,
            gender='m',
            description='test'
        )
        post = Post(
            id=post_id,
            text_raw='test post',
            created_at='2023-01-01'
        )
        
        # 转发相关
        repost_user = User(
            id='456',
            location='test2',
            screen_name='test2',
            followers_count=0,
            friends_count=0,
            gender='f',
            description='test2'
        )
        repost_post = Post(
            id='67890',
            text_raw='repost content',
            created_at='2023-01-02'
        )
        
        # 点赞用户
        attitude_user = User(
            id='789',
            location='test3',
            screen_name='test3',
            followers_count=0,
            friends_count=0,
            gender='m',
            description='test3'
        )
        
        # 评论相关
        comment_user = User(
            id='101112',
            location='test4',
            screen_name='test4',
            followers_count=0,
            friends_count=0,
            gender='f',
            description='test4'
        )
        comment = Comment(
            id='13579',
            text_raw='comment content',
            source='test source',
            created_at='2023-01-03'
        )

        # 2. 配置mock返回值
        mock_get_post.return_value = (user, post)
        mock_get_reposts.return_value = [('67890', repost_user, repost_post)]
        mock_get_attitudes.return_value = [attitude_user]
        mock_get_comments.return_value = [(comment_user, comment)]

        # 3. 创建测试依赖
        session = AsyncMock()
        graph = AsyncMock()
        entries_queue = AsyncMock()

        # 4. 执行测试
        from main import entry
        await entry(session, graph, post_id, entries_queue)

        # 5. 验证断言（使用已定义的变量）
        graph.create_user.assert_any_await(user)
        graph.create_user.assert_any_await(repost_user)
        graph.create_user.assert_any_await(attitude_user)
        graph.create_user.assert_any_await(comment_user)
        
        graph.create_repost_relationship.assert_awaited_once_with(
            repost_user.id,
            repost_post.id,
            post.id
        )
class TestMainFunction(IsolatedAsyncioTestCase):
    @patch('main.ClientSession')  # 调整为第4个参数
    @patch('main.run', new_callable=AsyncMock)  # 第3个参数
    @patch('main.ArgumentParser')  # 第2个参数
    @patch('main.WeiboGraph', autospec=True)  # 调整为第1个参数，添加 autospec
    async def test_main(self, 
                      mock_weibo_graph_cls: MagicMock,  # 来自第1个@patch
                      mock_arg_parser: MagicMock,       # 来自第2个@patch
                      mock_run: AsyncMock,             # 来自第3个@patch
                      mock_client_session):  # 来自第4个@patch
        # ===== A. 修复导入 =====
        from main import main  # 直接导入函数
        
        # ===== B. 配置 Mock =====
        # 1. ArgumentParser 配置
        mock_args = MagicMock()
        mock_args.user = '12345'
        mock_parser_instance = MagicMock()
        mock_parser_instance.parse_args.return_value = mock_args
        mock_arg_parser.return_value = mock_parser_instance  # 关联 parser 实例
        
        # 2. WeiboGraph 初始化配置
        mock_graph_instance = MagicMock()
        mock_weibo_graph_cls.return_value = mock_graph_instance
        
        # 3. ClientSession 上下文管理器配置
        async def session_context(_):
            return AsyncMock()
        mock_session_instance = AsyncMock(name="ClientSessionInstance")
        mock_client_session.return_value = AsyncMock(__aenter__=AsyncMock(return_value=mock_session_instance),__aexit__=AsyncMock(return_value=None))
        # ===== C. 获取实际 cookies =====
        cookies = load_cookies()
        
        # ===== D. 执行主函数 =====
        await main()  # 调用异步函数

        # ===== E. 验证调用 =====
        # 1. 验证 ArgumentParser 配置
        expected_parser_calls = [
            call.add_argument("-u", "--user", 
                            type=str, 
                            help="The user ID", 
                            required=True),
            call.parse_args()
        ]
        mock_parser_instance.assert_has_calls(expected_parser_calls)
        
        # 2. 验证 WeiboGraph 初始化
        expected_neo4j_args = (
            "bolt://localhost:7687",  # 与实际代码中的NEO4J_URI常量保持一致
            "neo4j",
            "12345678"
        )
        mock_weibo_graph_cls.assert_called_once_with(*expected_neo4j_args)
        
        # 3. 验证 ClientSession 创建
        mock_client_session.assert_called_once_with(cookies=cookies)
        
        # 验证 run 函数调用参数
        mock_run.assert_awaited_once_with(
            mock_session_instance,  # 使用直接配置的session实例
            mock_graph_instance,
            '12345'
        )

if __name__ == '__main__':
    unittest.main()
