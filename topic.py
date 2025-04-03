import nltk
from nltk.corpus import stopwords
from gensim import corpora
from gensim.models import LdaModel
import string
import jieba
import pandas as pd
import matplotlib.pyplot as plt
from wordcloud import WordCloud


# 数据预处理
# 从文件中加载停用词表
def load_stopwords(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        stopwords = set(line.strip() for line in f if line.strip())
    return stopwords

# 文本预处理
def preprocess(text, stopwords):
    # 使用 jieba 分词
    tokens = jieba.lcut(text)
    # 去除停用词和空格
    tokens = [word for word in tokens if word not in stopwords and len(word.strip()) > 0]
    return tokens

# 下载nltk的停用词表（如果尚未下载）
nltk.download('stopwords')

# 读取 CSV 文件并提取 '正文' 列
csv_file = "6500819234.csv"  # 替换为你的 CSV 文件路径
df = pd.read_csv(csv_file)

# 检查是否包含 '正文' 列
if '正文' not in df.columns:
    raise ValueError("CSV 文件中缺少 '正文' 列")

# 提取 '正文' 列作为文档集合
documents = df['正文'].dropna().tolist()  # 去除空值并转换为列表

# 加载停用词表
stopwords_file = "stopwords_full.txt"  # 停用词文件路径
stopwords = load_stopwords(stopwords_file)

# 对文档进行预处理
processed_docs = [preprocess(doc, stopwords) for doc in documents]

# 创建词典和语料库
dictionary = corpora.Dictionary(processed_docs)
corpus = [dictionary.doc2bow(doc) for doc in processed_docs]

# 训练LDA模型
num_topics = 10  # 设置主题数量
lda_model = LdaModel(corpus, num_topics=num_topics, id2word=dictionary, passes=50)



# 输出每个主题的关键词
#print("每个主题的关键词：")
topics = lda_model.print_topics(num_words=5)  # 每个主题显示5个关键词
#for topic in topics:
#    print(topic)

for topic_id in range(num_topics):
    print(f"\n主题 {topic_id} 的关键词：{topics[topic_id][1]}")  # 输出主题的关键词
    
    # 获取每条文档的主题分布
    topic_documents = []
    for i, doc_bow in enumerate(corpus):
        topic_distribution = lda_model.get_document_topics(doc_bow, minimum_probability=0.01)
        # 找到当前文档在当前主题上的概率
        topic_prob = dict(topic_distribution).get(topic_id, 0)
        topic_documents.append((i, topic_prob))  # (文档索引, 主题概率)
    
    # 按主题概率降序排序
    topic_documents.sort(key=lambda x: x[1], reverse=True)

    print(f"主题 {topic_id} 的典型文本：")
    # 输出最多 3 条典型文本
    count = 0
    for doc_index, prob in topic_documents:
        if prob > 0:  # 只输出有概率的文档
            if count < 3:  # 最多输出 3 条
                print(f"微博 {doc_index+1}：{documents[doc_index]}")
            count += 1
    print(f"主题 {topic_id} 相关的微博条数：{count}")


# 对所有文档进行预处理并合并成一个字符串
all_tokens = []
for doc in documents:
    tokens = preprocess(doc, stopwords)
    all_tokens.extend(tokens)

# 将所有词语组合成一个大字符串
text = ' '.join(all_tokens)

# 生成词云图
wordcloud = WordCloud(font_path='simhei.ttf',  # 设置字体路径，支持中文
                      width=800, height=400,  # 设置图片大小
                      background_color='white',  # 背景颜色
                      max_words=100,  # 显示的最大单词数量
                      contour_width=3, contour_color='steelblue').generate(text)

# 显示词云图
plt.figure(figsize=(10, 5))
plt.imshow(wordcloud, interpolation='bilinear')
plt.axis('off')  # 不显示坐标轴
plt.show()

# 对新文档进行主题推断
#new_doc = "【公告】$ST目药 sh600671$ ST目药：杭州天目山药业股份有限公司关于收到上海证券交易所问询函的公告 点击查看 网页链接 "
#new_doc_processed = preprocess(new_doc, stopwords)
#new_doc_bow = dictionary.doc2bow(new_doc_processed)
#topic_distribution = lda_model.get_document_topics(new_doc_bow)
#print("\n新文档的主题分布：", topic_distribution)

#print("每个文档的主要主题：")
#for i, doc_bow in enumerate(corpus):
#    topic_distribution = lda_model.get_document_topics(doc_bow, minimum_probability=0.01)
#    main_topic = max(topic_distribution, key=lambda x: x[1])  # 找到概率最大的主题
#    print(f"文档 {i+1} 的主要主题是：主题 {main_topic[0]}，概率为 {main_topic[1]:.2f}")