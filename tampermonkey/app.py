from flask import Flask, request, jsonify
from flask_cors import CORS
import time

app = Flask(__name__)
# 配置CORS，允许所有来源的请求
CORS(app, resources={r"/*": {"origins": "*", "methods": ["GET", "POST", "OPTIONS"]}})

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
        response = f"服务器收到消息: {message}"
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
