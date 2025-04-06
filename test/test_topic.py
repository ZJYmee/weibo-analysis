import os
import unittest
from gensim.models import LdaModel
from gensim.corpora.dictionary import Dictionary
import pandas as pd
import matplotlib
matplotlib.use('Agg')  # 使用非交互式后端
import matplotlib.pyplot as plt
from wordcloud import WordCloud
import jieba
import sys
import importlib
from pathlib import Path
# 设置项目根目录路径
PROJECT_ROOT = str(Path(__file__).parent.parent)
sys.path.insert(0, PROJECT_ROOT)

# 动态导入主模块
topic = importlib.import_module('main')
from topic import load_stopwords, preprocess

class TestTopicModeling(unittest.TestCase):

    def setUp(self):
        """准备测试环境"""
        # 创建临时CSV文件和停用词文件
        self.csv_file = "test_data.csv"
        self.stopwords_file = "test_stopwords.txt"
        self.font_path = "simhei.ttf"  # 确保你有一个支持中文的字体文件

        # 创建测试数据
        test_csv_content = """正文
微博内容1，这是一个测试。
微博内容2，这是另一个测试。
微博内容3，主题建模很有趣。"""
        with open(self.csv_file, 'w', encoding='utf-8') as f:
            f.write(test_csv_content)

        # 创建测试停用词文件
        test_stopwords_content = """这是
一个
测试"""
        with open(self.stopwords_file, 'w', encoding='utf-8') as f:
            f.write(test_stopwords_content)

    def tearDown(self):
        """清理测试环境"""
        if os.path.exists(self.csv_file):
            os.remove(self.csv_file)
        if os.path.exists(self.stopwords_file):
            os.remove(self.stopwords_file)

    def test_load_stopwords(self):
        """测试加载停用词功能"""
        stopwords = load_stopwords(self.stopwords_file)
        print(f"\n加载的停用词：{stopwords}")
        self.assertIsInstance(stopwords, set)
        self.assertIn("这是", stopwords)
        self.assertNotIn("微博", stopwords)

    def test_preprocess(self):
        """测试文本预处理功能"""
        text = "微博内容1，这是一个测试。"
        stopwords = load_stopwords(self.stopwords_file)
        tokens = preprocess(text, stopwords)
        print(f"\n预处理后的分词结果：{tokens}")
        self.assertIsInstance(tokens, list)
        self.assertNotIn("这是", tokens)
        self.assertIn("微博", tokens)

    def test_lda_model_training(self):
        """测试LDA模型训练"""
        # 加载测试数据
        df = pd.read_csv(self.csv_file)
        documents = df['正文'].dropna().tolist()
        stopwords = load_stopwords(self.stopwords_file)
        processed_docs = [preprocess(doc, stopwords) for doc in documents]

        # 创建词典和语料库
        dictionary = Dictionary(processed_docs)
        corpus = [dictionary.doc2bow(doc) for doc in processed_docs]

        # 训练LDA模型
        num_topics = 2
        lda_model = LdaModel(corpus, num_topics=num_topics, id2word=dictionary, passes=10)

        # 输出主题关键词
        topics = lda_model.print_topics(num_words=5)
        print("\n训练的LDA主题：")
        for i, topic in enumerate(topics):
            print(f"主题 {i} 的关键词：{topic[1]}")

        # 验证主题数量是否正确
        self.assertEqual(len(topics), num_topics)

    def test_wordcloud_generation(self):
        """测试词云生成"""
        text = "微博 内容 主题 建模 很 有趣"
        wordcloud = WordCloud(font_path=self.font_path, width=800, height=400, background_color='white')
        wc = wordcloud.generate(text)
        print("\n生成的词云图：")
        
        # 显示词云图
        plt.figure(figsize=(8, 4))
        plt.imshow(wc, interpolation='bilinear')
        plt.axis("off")
        plt.title("词云图展示")
        plt.show()

        # 保存词云图为图片文件
        output_image_path = "wordcloud_output.png"  # 图片保存路径
        wc.to_file(output_image_path)
        print(f"词云图已保存为 {output_image_path}")
        # plt.close()  # 关闭图像窗口
        self.assertIsNotNone(wc)


if __name__ == "__main__":
    try:
        unittest.main()
    except Exception as e:
        print(f"发生错误：{e}")