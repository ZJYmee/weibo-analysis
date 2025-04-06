# test/test_read-neo4j.py
import sys
import importlib.util
from pathlib import Path
import unittest
from unittest.mock import MagicMock, patch
import networkx as nx
import json
from io import StringIO
from unittest.mock import mock_open, MagicMock

PROJECT_ROOT = Path(__file__).resolve().parent.parent  # 假设测试文件在test/目录下

sys.path.insert(0, str(PROJECT_ROOT))

try:
    # 1. 准备模块规范
    module_name = "read_neo4j"  # 自定义模块名（使用下划线）
    module_path = PROJECT_ROOT / "read-neo4j.py"  # 原始文件名
    
    # 2. 验证文件存在性
    if not module_path.exists():
        raise FileNotFoundError(f"找不到模块文件: {module_path}")

    # 3. 动态加载模块
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    if spec is None:
        raise ImportError("无法创建模块规范，请检查文件路径")
        
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module  # 注册到全局模块表
    spec.loader.exec_module(module)
    
    # 4. 显式导入函数（解决IDE警告）
    from read_neo4j import (  # type: ignore
        follow_network,
        merge_user_and_post,
        convert_to_nx_graph,
        calculate_association_degree,
        draw_graph,
        draw_tight_graph
    )
except Exception as e:
    print(f"动态导入模块失败: {e}")
    raise

class TestReadNeo4j(unittest.TestCase):
    def setUp(self):
        # 创建基本的测试图
        self.G = nx.MultiDiGraph()
        self.G.add_node(1, label="USER", properties={"screen_name": "User1"})
        self.G.add_node(2, label="USER", properties={"screen_name": "User2"})
        self.G.add_node(3, label="POST", properties={"content": "Test post"})
        self.G.add_edge(1, 2, key="edge1", label="FOLLOWS", weight=5)
        self.G.add_edge(1, 3, key="edge2", label="POSTED", weight=3)
        self.G.add_edge(2, 3, key="edge3", label="COMMENTED", weight=2)

        # 配置Neo4j模拟数据
        self.mock_records = []
        self.mock_node1 = MagicMock()
        self.mock_node1["label"] = "USER"
        self.mock_node1._properties = {"id": 1, "screen_name": "User1"}
        self.mock_node1["id"] = 1
        
        self.mock_node2 = MagicMock()
        self.mock_node2["label"] = "USER"
        self.mock_node2._properties = {"id": 2, "screen_name": "User2"}
        self.mock_node2["id"] = 2
        
        self.mock_relation = MagicMock()
        self.mock_relation.type = "FOLLOWS"
        self.mock_relation._properties = {}
        self.mock_relation.element_id = "rel1"

        self.mock_record = {
            "n": self.mock_node1,
            "m": self.mock_node2,
            "r": self.mock_relation,
            "node1_id": 1,
            "node2_id": 2
        }
        self.mock_records.append(self.mock_record)

    @patch("neo4j.Session")
    @patch("neo4j.Driver")
    @patch("weibo_follow.Follow")
    def test_follow_network(self, mock_follow, mock_driver, mock_session):
        """测试正常关注网络"""
        # 创建模拟的 Follow 实例
        mock_instance = MagicMock()
        mock_instance.follow_list = [12345, 67890]
        mock_instance.follow_name_list = ["Alice", "Bob"]
        mock_instance.get_follow_list = MagicMock()
        mock_instance.get_page_num = MagicMock(return_value=1)
        mock_instance.get_one_page = MagicMock()

        # 模拟 deal_html 返回的 selector，假设 selector 有 xpath 方法
        mock_selector = MagicMock()
        mock_selector.xpath.return_value = ["Alice"]  # 返回非空列表，避免 IndexError
        mock_instance.deal_html = MagicMock(return_value=mock_selector)

        # 设置 Follow 类的构造函数返回模拟实例
        mock_follow.return_value = mock_instance

        # 执行被测试函数
        relations, info = follow_network(7563705897, {})

        # 添加断言，确保返回值符合预期
        self.assertIsInstance(relations, list)
        self.assertIsInstance(info, dict)

    @patch('weibo_follow.Follow')
    def test_follow_network_with_self_reference(self, mock_follow):
        """测试包含自引用的关注网络"""
        mock_instance = MagicMock()
        mock_instance.follow_list = [7563705897, 12345]  # 包含自身ID
        mock_instance.follow_name_list = ["Self", "Alice"]
        mock_follow.return_value = mock_instance

        relations, info = follow_network(7563705897, {})
        self.assertEqual(len(relations), 1)  # 自引用被过滤
        self.assertNotIn(7563705897, info)

    def test_merge_user_and_post(self):
        # 创建测试图
        G = nx.MultiDiGraph()
        # 用户节点
        G.add_node(1, label="USER", properties={"screen_name": "User1"})
        G.add_node(2, label="USER", properties={"screen_name": "User2"})
        # 帖子节点
        G.add_node(101, label="POST", properties={"content": "Post1"})
        # 用户到帖子的边
        G.add_edge(1, 101, key="edge1", label="POSTED", weight=3)
        # 用户到用户的边
        G.add_edge(2, 1, key="edge2", label="FOLLOWS", weight=5)
        # 用户到帖子的边
        G.add_edge(2, 101, key="edge3", label="COMMENTED", weight=2)
        
        # 执行合并
        merged_G = merge_user_and_post(G)
        
        # 验证结果 - 帖子节点应该被移除，相关边应该被重新连接
        self.assertNotIn(101, merged_G.nodes())
        self.assertIn((2, 1), [(u, v) for u, v, k in merged_G.edges(keys=True)])
        self.assertEqual(len(merged_G.edges()), 2)  # FOLLOWS边和新的COMMENTED边

    @patch('neo4j.GraphDatabase.driver')
    def test_convert_to_nx_graph(self, mock_driver):
        # 配置模拟驱动和会话
        mock_session = MagicMock()
        mock_driver.return_value.session.return_value.__enter__.return_value = mock_session
        mock_session.execute_read.return_value = self.mock_records
        
        # 测试前重置G
        G = nx.MultiDiGraph()
        
        # 注入全局变量G
        with patch('read_neo4j.G', G):
            convert_to_nx_graph(mock_driver.return_value)
        
        # 验证结果
        self.assertIn(1, G.nodes())
        self.assertIn(2, G.nodes())
        self.assertEqual(G.nodes[1]['properties'], {"id": 1, "screen_name": "User1"})
        self.assertTrue(G.has_edge(1, 2))
        edge_data = G.get_edge_data(1, 2)["rel1"]
        self.assertEqual(edge_data['label'], "FOLLOWS")

    def test_calculate_association_degree(self):
        # 创建测试图
        G = nx.MultiDiGraph()
        G.add_node(1, label="USER", properties={"screen_name": "User1"})
        G.add_node(2, label="USER", properties={"screen_name": "User2"})
        G.add_node(3, label="USER", properties={"screen_name": "User3"})
        
        # 添加带权重的边
        G.add_edge(1, 2, key="edge1", label="FOLLOWS", weight=5)
        G.add_edge(2, 1, key="edge2", label="FOLLOWS", weight=3)
        G.add_edge(3, 1, key="edge3", label="COMMENTS", weight=2)
        
        # 计算关联度
        target_node = 1
        association_degrees = calculate_association_degree(G, target_node)
        
        # 验证结果
        self.assertEqual(association_degrees[2], 8)  # 5 + 3
        self.assertEqual(association_degrees[3], 2)  # 只有一条边

    def test_calculate_association_degree_invalid_node(self):
        # 测试目标节点不在图中的情况
        with self.assertRaises(ValueError):
            calculate_association_degree(self.G, 999)

    @patch('matplotlib.pyplot.show')
    @patch('networkx.spring_layout')
    @patch('networkx.draw')
    @patch('networkx.draw_networkx_edge_labels')
    def test_draw_graph(self, mock_draw_edge_labels, mock_draw, mock_spring_layout, mock_show):
        # 配置模拟函数
        mock_spring_layout.return_value = {1: (0, 0), 2: (1, 1), 3: (0.5, 0.5)}
        
        # 调用绘图函数
        draw_graph(self.G)
        
        # 验证函数调用
        mock_spring_layout.assert_called_once()
        mock_draw.assert_called_once()
        mock_draw_edge_labels.assert_called_once()
        mock_show.assert_called_once()

    @patch('matplotlib.pyplot.show')
    @patch('networkx.spring_layout')
    @patch('networkx.draw_networkx_nodes')
    @patch('networkx.draw_networkx_labels')
    @patch('networkx.draw_networkx_edges')
    @patch('matplotlib.pyplot.annotate')
    def test_draw_tight_graph(self, mock_annotate, mock_draw_edges, mock_draw_labels, 
                             mock_draw_nodes, mock_spring_layout, mock_show):
        # 配置模拟函数
        mock_spring_layout.return_value = {1: (0, 0), 2: (1, 1)}
        
        # 调用绘图函数
        target_node = 1
        association_degrees = {2: 8}  # 高于阈值
        draw_tight_graph(self.G, target_node, association_degrees)
        
        # 验证函数调用
        mock_spring_layout.assert_called_once()
        self.assertEqual(mock_draw_nodes.call_count, 2)  # 一次对所有节点，一次对目标节点
        mock_draw_labels.assert_called_once()
        mock_draw_edges.assert_called_once()
        mock_show.assert_called_once()

    @patch('json.load')
    @patch('builtins.open', new_callable=mock_open, read_data='{"key": "value"}')
    def test_json_loading(self, mock_file, mock_json_load):
        # 创建模拟数据
        mock_json_load.return_value = {"cookie": "test_cookie"}
        
        # 调用open和json.load
        with open("cookies.json", "r") as f:
            cookies = json.load(f)
        
        # 验证调用
        mock_file.assert_called_once_with("cookies.json", "r")
        mock_json_load.assert_called_once()
        self.assertEqual(cookies, {"cookie": "test_cookie"})

    @patch('networkx.selfloop_edges')
    def test_remove_selfloops(self, mock_selfloop_edges):
        # 模拟自环边
        mock_selfloop_edges.return_value = [(1, 1, "self_edge")]
        G = self.G.copy()
        G.add_edge(1, 1, key="self_edge", label="SELF", weight=1)
        
        # 调用移除自环的函数
        G.remove_edges_from(nx.selfloop_edges(G))
        
        # 验证调用和结果
        mock_selfloop_edges.assert_called_once_with(G)
        self.assertFalse(G.has_edge(1, 1))


class TestIntegration(unittest.TestCase):
    @patch('weibo_follow.Follow')
    @patch('networkx.spring_layout')
    @patch('matplotlib.pyplot.show')
    @patch('neo4j.GraphDatabase.driver')
    @patch('builtins.open', new_callable=mock_open, read_data='{"cookie":"test"}')
    @patch('json.load')
    def test_main_workflow(self, mock_json_load, mock_file, mock_driver, 
                          mock_show, mock_spring_layout, mock_follow):
        # 配置所有模拟对象
        mock_json_load.return_value = {"cookie": "test_cookie"}
        mock_session = MagicMock()
        mock_driver.return_value.session.return_value.__enter__.return_value = mock_session
        
        # 模拟Neo4j记录
        mock_node1 = MagicMock()
        mock_node1["label"] = "USER"
        mock_node1._properties = {"id": 1, "screen_name": "User1"}
        mock_node1["id"] = 1
        
        mock_node2 = MagicMock()
        mock_node2["label"] = "USER"
        mock_node2._properties = {"id": 2, "screen_name": "User2"}
        mock_node2["id"] = 2
        
        mock_relation = MagicMock()
        mock_relation.type = "FOLLOWS"
        mock_relation._properties = {}
        mock_relation.element_id = "rel1"
        
        mock_record = {
            "n": mock_node1,
            "m": mock_node2,
            "r": mock_relation,
            "node1_id": 1,
            "node2_id": 2
        }
        mock_session.execute_read.return_value = [mock_record]
        
        # 模拟Follow类
        mock_follow_instance = mock_follow.return_value
        mock_follow_instance.follow_list = [101, 102]
        mock_follow_instance.follow_name_list = ["Name1", "Name2"]
        
        # 模拟布局
        mock_spring_layout.return_value = {1: (0, 0), 2: (1, 1), 101: (0.5, 0.5), 102: (1.5, 1.5)}
        
        # 创建输出捕获器
        captured_output = StringIO()
        sys.stdout = captured_output
        
        # 执行主要工作流
        G = nx.MultiDiGraph()
        
        # 模拟convert_to_nx_graph
        with patch('read_neo4j.G', G):
            convert_to_nx_graph(mock_driver.return_value)
        
        # 模拟merge_user_and_post
        G = merge_user_and_post(G)
        
        # 模拟follow_network
        target_node = 1676593803
        follow_relations, user_info = follow_network(target_node, {"cookie": "test_cookie"})
        
        # 添加用户和关注关系
        for user_id, user_data in user_info.items():
            if user_id not in G.nodes:
                G.add_node(int(user_id), label="USER", properties=user_data)
        
        for user_id, follow_id in follow_relations:
            G.add_edge(int(user_id), int(follow_id), key="test_edge", label="FOLLOWS", weight=5)
        
        # 计算关联度
        association_degrees = calculate_association_degree(G, target_node)
        
        # 还原标准输出
        sys.stdout = sys.__stdout__
        
        # 验证输出包含预期消息
        self.assertIn("Neo4j数据已成功转换为NetworkX图", captured_output.getvalue())
        self.assertIn("用户和贴子节点已成功合并", captured_output.getvalue())


if __name__ == '__main__':
    unittest.main()