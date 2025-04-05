from flask import Flask, request, jsonify
from flask_cors import CORS
import time
import csv
from utils import Weibo, get_str_with_id
import os
import openai
from openai import OpenAI
app = Flask(__name__)
# 配置CORS，允许所有来源的请求
CORS(app, resources={r"/*": {"origins": "*", "methods": ["GET", "POST", "OPTIONS"]}})

def generate_model_output(target_str):
    client = OpenAI(
        api_key="Your API Key",
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
    )
    completion = client.chat.completions.create(
        model="qwen-long",
        messages=[
            {'role': 'system', 'content': 'You are a helpful assistant.'},
            {'role': 'user', 'content': '这是一个微博账号的主页里提取到的微博内容，请总结这个账号的行为特点，做情感分析，结果用普通文本格式而非markdown格式。' + target_str}
        ],
        stream=True,
        stream_options={"include_usage": True}
    )

    full_content = ""
    for chunk in completion:
        if chunk.choices and chunk.choices[0].delta.content:
            full_content += chunk.choices[0].delta.content
    
    return full_content

def find_specific_csv(target_filename, search_dir="./weibo"):
    """
    在指定目录及其子目录中查找特定名称的CSV文件
    
    :param target_filename: 目标文件名（如 "101.csv"）
    :param search_dir: 搜索的根目录，默认为 "./weibo"
    :return: 匹配文件的完整路径列表
    """
    matched_files = []
    
    for root, _, files in os.walk(search_dir):
        for file in files:
            if file == target_filename:
                matched_files.append(os.path.join(root, file))
    
    return matched_files

def concatenate_text_from_csv(csv_file_path, output_file_path=None):
    """
    读取CSV文件，拼接所有"正文"列的文字，用"//"分割
    
    :param csv_file_path: 输入的CSV文件路径
    :param output_file_path: 可选，输出结果保存路径
    :return: 拼接后的字符串
    """
    texts = []
    
    with open(csv_file_path, mode='r', encoding='utf-8') as csvfile:
        reader = csv.DictReader(csvfile)
        
        for row in reader:
            if '正文' in row and row['正文'].strip():  # 检查"正文"列是否存在且非空
                texts.append(row['正文'].strip())
    
    # 用"//"拼接所有正文
    result = ' // '.join(texts)
    
    # 如果需要保存到文件
    if output_file_path:
        with open(output_file_path, 'w', encoding='utf-8') as f:
            f.write(result)
    
    return result

def get_response(message):
    try:
        id = int(message)
    except ValueError:
        return "无效的微博ID，请输入数字。"
    try:
        get_str_with_id(id)
        csv_file_path = find_specific_csv(f"{id}.csv")
        if not csv_file_path:
            return "未找到相关微博数据，请检查微博ID。"
        string_to_concatenate = concatenate_text_from_csv(csv_file_path[0])
        if not string_to_concatenate:
            return "微博数据为空，请检查微博ID。"
        final_ans = generate_model_output(string_to_concatenate)
        return final_ans
        
    except Exception as e:
        return f"获取微博内容失败: {str(e)}"


# 添加日志记录，帮助调试
@app.before_request
def log_request_info():
    print('Headers:', dict(request.headers))
    print('Body:', request.get_data().decode())

@app.route('/message', methods=['POST', 'OPTIONS'])
def handle_message():
    if request.method == 'OPTIONS':
        # 处理预检请求
        response = jsonify({'status': 'ok'})
        response.headers.add('Access-Control-Allow-Headers', 'Content-Type')
        return response

    try:
        print("收到请求:", request.json)  # 调试日志
        data = request.json
        message = data.get('message', '')
        
        # 生成回复
        # response = f"服务器收到消息: {message}"
        response = get_response(message)
        print("发送回复:", response)  # 调试日志
        
        return jsonify({
            "status": "success",
            "response": response,
            "timestamp": time.strftime('%Y-%m-%d %H:%M:%S')
        })
        
    except Exception as e:
        print("错误:", str(e))  # 调试日志
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500

if __name__ == '__main__':
    # 确保监听所有网络接口
    app.run(debug=True, host='0.0.0.0', port=5000)
