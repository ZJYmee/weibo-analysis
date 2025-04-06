## 微博用户画像分析系统

### 环境要求：

```
Python 3.11+
Neo4j 4.0+
pip install -r requirements.txt
```


### 1. 启动Neo4j容器

使用Docker运行Neo4j数据库：

```bash
docker run \
    --name neo4j \
    -p 7474:7474 -p 7687:7687 \
    -d \
    neo4j
```

容器启动后，可以通过以下方式访问：

- Neo4j Browser界面：http://localhost:7474
- Bolt连接地址：bolt://localhost:7687

确保Neo4j容器正常运行后，再继续后续步骤。

### 2. 配置文件

添加.env文件，配置以下信息：

```bash
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=your username
NEO4J_PASSWORD=your password
```

添加cookies.json文件，填入你的微博的cookies：

```json
{
  "SINAGLOBAL": "",
  "UOR": "",
  "SCF": "",
  "XSRF-TOKEN": "",
  "SUB": "",
  "SUBP": "",
  "ALF": "",
  "_s_tentry": "",
  "Apache": "",
  "ULV": "",
  "WBPSESS": ""
}
```

请将从浏览器中获取的微博cookies填入对应字段。

### 3. 社交圈分析程序运行
使用以下命令运行社交圈GUI程序：

```bash
python net_gui.py
```

### 4. 用户画像分析平台运行
1. 在`./tampermonkey/app.py`中设置API_KEY
```
def generate_model_output(target_str):
    client = OpenAI(
        api_key="",
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
    )
```

2. 将`./tampermonkey/plugin.js`置入你的油猴chrome插件中，并开启该插件

3. 运行后端服务器程序
```bash
cd ./tampermonkey
python ./app.py
```

4. 向前端chatbox中发送微博用户的id，等待处理，你可以在后端的终端看到处理过程。

5. 你可以查看部署文档，有具体的图示。
## 参考资料
https://github.com/Driftcell/weibo-social-network-crawler

https://github.com/Artificialimbecile/WeiboSpider

停用词表：https://github.com/CharyHong/Stopwords

## 许可证

本项目采用MIT许可证。详见LICENSE文件。