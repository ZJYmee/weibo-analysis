import pytest
import tempfile
import os
import sys
from datetime import datetime
from unittest.mock import patch, MagicMock

import sys
import importlib
from pathlib import Path
# 设置项目根目录路径
PROJECT_ROOT = str(Path(__file__).parent.parent)
sys.path.insert(0, PROJECT_ROOT)

# 动态导入主模块
weibo = importlib.import_module('main')
from weibo import Weibo
@pytest.fixture
def weibo_instance():
    """创建测试用的Weibo实例"""
    return Weibo(
        filter=1,
        since_date='2023-01-01',
        mongodb_write=0,
        mysql_write=0,
        pic_download=0,
        video_download=0
    )

@pytest.fixture
def mock_user_info():
    """模拟用户信息数据"""
    return {
        'id': '123456',
        'screen_name': '测试用户',
        'statuses_count': 100,
        'followers_count': '500万',
        'follow_count': '200'
    }

@pytest.fixture
def mock_weibo_data():
    """模拟微博数据"""
    return {
        'mblog': {
            'id': '789012',
            'bid': 'test_bid',  # 添加缺失的bid字段
            'text': '测试微博内容',
            'created_at': '2023-06-01',
            'user': {'id': '123456', 'screen_name': '测试用户'},
            'attitudes_count': 100,
            'comments_count': 50,
            'reposts_count': 30,
            'source': '测试客户端',
            'isLongText': False
        }
    }

class TestWeiboClass:
    def test_initialization(self, weibo_instance):
        """测试类初始化"""
        assert weibo_instance.filter == 1
        assert weibo_instance.since_date == '2023-01-01'
        assert weibo_instance.user_id == ''

    def test_is_date_valid(self, weibo_instance):
        """测试日期验证"""
        assert weibo_instance.is_date('2023-01-01') is True
        assert weibo_instance.is_date('invalid-date') is False

    @patch('weibo.requests.get')
    def test_get_json(self, mock_get, weibo_instance):
        """测试获取JSON数据"""
        mock_response = MagicMock()
        mock_response.json.return_value = {'ok': True, 'data': {}}
        mock_get.return_value = mock_response
        
        result = weibo_instance.get_json({'test': 'param'})
        assert result == {'ok': True, 'data': {}}

    @patch('weibo.Weibo.get_json')
    def test_get_user_info(self, mock_get_json, weibo_instance, mock_user_info):
        """测试获取用户信息"""
        mock_get_json.return_value = {
            'ok': True,
            'data': {'userInfo': mock_user_info}
        }
        
        weibo_instance.user_id = '123456'
        user_info = weibo_instance.get_user_info()
        
        assert user_info['screen_name'] == '测试用户'
        assert user_info['followers_count'] == 5000000

    def test_convert_weibo_number(self, weibo_instance):
        """测试微博数量转换"""
        assert weibo_instance.convert_weibo_number('100') == 100
        assert weibo_instance.convert_weibo_number('1.2万') == 12000
        assert weibo_instance.convert_weibo_number('invalid') == 0

    def test_parse_weibo(self, weibo_instance, mock_weibo_data):
        """测试解析微博数据"""
        parsed = weibo_instance.parse_weibo(mock_weibo_data['mblog'])
        assert parsed['id'] == 789012
        assert parsed['text'] == '测试微博内容'
        assert parsed['attitudes_count'] == 100

    @patch('weibo.Weibo.get_json')
    def test_get_weibo_json(self, mock_get_json, weibo_instance):
        """测试获取微博JSON"""
        mock_get_json.return_value = {'ok': True, 'data': {'cards': []}}
        
        weibo_instance.user_id = '123456'
        result = weibo_instance.get_weibo_json(1)
        assert result == {'ok': True, 'data': {'cards': []}}

    def test_standardize_date(self, weibo_instance):
        """测试日期标准化"""
        assert weibo_instance.standardize_date('2023-06-01') == '2023-06-01'
        
        # 使用动态年份断言
        current_year = str(datetime.now().year)
        assert weibo_instance.standardize_date('1分钟前').startswith(current_year)

    @patch('weibo.Weibo.get_user_info')
    @patch('weibo.Weibo.get_pages')
    def test_start_method(self, mock_get_pages, mock_get_user_info, weibo_instance):
        """测试start方法"""
        mock_get_user_info.return_value = {
            'id': '123456',
            'screen_name': '测试用户'
        }
        
        weibo_instance.start(['123456'])
        mock_get_pages.assert_called_once()

    def test_write_csv(self, weibo_instance, tmp_path):
        """测试写入CSV文件"""
        weibo_instance.user = {'id': '123456', 'screen_name': '测试用户'}
        weibo_instance.weibo = [{
            'id': 789012,
            'text': '测试微博内容',
            'created_at': '2023-06-01'
        }]
        
        # 确保目录存在
        csv_dir = tmp_path / "weibo" / "测试用户"
        csv_dir.mkdir(parents=True, exist_ok=True)
        csv_path = csv_dir / "123456.csv"
        
        with patch('weibo.Weibo.get_filepath', return_value=str(csv_path)):
            weibo_instance.write_csv(0)
            assert csv_path.exists()

    @pytest.mark.skipif(sys.version_info < (3, 6), reason="需要Python 3.6+")
    @patch('pymongo.MongoClient')
    def test_info_to_mongodb(self, mock_mongo, weibo_instance, mock_user_info):
        """测试写入MongoDB"""
        weibo_instance.info_to_mongodb('user', [mock_user_info])
        mock_mongo.return_value.__getitem__.assert_called_with('weibo')

@pytest.mark.skipif(sys.version_info < (3, 6), reason="需要Python 3.6+")
class TestIntegration:
    """集成测试类"""
    
    @pytest.fixture(autouse=True)
    def setup(self, tmp_path):
        """创建测试数据文件"""
        self.user_list_file = tmp_path / "user_list.txt"
        with open(self.user_list_file, 'w', encoding='utf-8') as f:
            f.write("123456 测试用户\n")
        
        self.weibo = Weibo(
            filter=1,
            since_date='2023-01-01',
            mongodb_write=0,
            mysql_write=0,
            pic_download=0,
            video_download=0
        )
    
    @patch('weibo.Weibo.get_pages')
    def test_get_user_list(self, mock_get_pages):
        """测试从文件读取用户列表"""
        user_list = self.weibo.get_user_list(str(self.user_list_file))
        assert user_list == ['123456']
        
        self.weibo.start(user_list)
        mock_get_pages.assert_called_once()