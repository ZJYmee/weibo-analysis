// ==UserScript==
// @name         Chat Box Plugin
// @namespace    http://tampermonkey.net/
// @version      0.2
// @description  Weibo search with image and text response
// @author       Anonymous
// @match        *://*/*
// @grant        GM_addStyle
// ==/UserScript==

(function() {
    'use strict';

    // 添加样式
    GM_addStyle(`
        .chat-container {
            position: fixed;
            bottom: 20px;
            right: 20px;
            width: 300px;
            background: white;
            border-radius: 10px;
            box-shadow: 0 0 10px rgba(0,0,0,0.1);
            display: flex;
            flex-direction: column;
            z-index: 9999;
            transition: all 0.3s ease;
            color: #000000;
        }

        .chat-container.collapsed {
            width: 50px;
            height: 50px !important;
            border-radius: 25px;
            overflow: hidden;
        }

        .chat-header {
            padding: 10px;
            background: #4CAF50;
            color: white;
            border-radius: 10px 10px 0 0;
            cursor: move;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }

        .chat-container.collapsed .chat-header {
            border-radius: 25px;
            padding: 0;
            height: 50px;
            width: 50px;
            justify-content: center;
        }

        .toggle-button {
            cursor: pointer;
            padding: 5px;
            user-select: none;
        }

        .chat-icon {
            display: none;
            font-size: 24px;
            color: white;
        }

        .chat-container.collapsed .chat-icon {
            display: block;
        }

        .chat-container.collapsed .header-text,
        .chat-container.collapsed .toggle-button {
            display: none;
        }

        .chat-container.collapsed .chat-messages,
        .chat-container.collapsed .chat-input {
            display: none;
        }

        .chat-messages {
            flex: 1;
            overflow-y: auto;
            padding: 10px;
            color: #000000;
        }

        .message {
            margin: 5px;
            padding: 8px;
            border-radius: 5px;
            color: #000000;
            word-break: break-all;
        }

        .sent {
            background: #E3F2FD;
            margin-left: 20px;
        }

        .received {
            background: #F5F5F5;
            margin-right: 20px;
        }

        .chat-input {
            display: flex;
            padding: 10px;
            border-top: 1px solid #eee;
        }

        .chat-input input {
            flex: 1;
            padding: 8px;
            border: 1px solid #ddd;
            border-radius: 4px;
            margin-right: 5px;
            color: #000000;
        }

        .chat-input button {
            padding: 8px 15px;
            background: #4CAF50;
            color: white;
            border: none;
            border-radius: 4px;
            cursor: pointer;
        }

        .chat-input button:hover {
            background: #45a049;
        }

        /* 针对图片的样式 */
        .message img {
            max-width: 100%;
            border-radius: 5px;
            margin: 5px;
        }
    `);

    // 创建聊天框HTML
    const chatHTML = `
        <div class="chat-container">
            <div class="chat-header">
                <span class="header-text">DeepWeibo</span>
                <span class="chat-icon">💬</span>
                <span class="toggle-button">➖</span>
            </div>
            <div class="chat-messages"></div>
            <div class="chat-input">
                <input type="text" placeholder="输入用户名">
                <button>发送</button>
            </div>
        </div>
    `;

    // 添加聊天框到页面
    document.body.insertAdjacentHTML('beforeend', chatHTML);

    // 获取DOM元素
    const chatContainer = document.querySelector('.chat-container');
    const messagesContainer = document.querySelector('.chat-messages');
    const input = document.querySelector('.chat-input input');
    const sendButton = document.querySelector('.chat-input button');
    const header = document.querySelector('.chat-header');
    const toggleButton = document.querySelector('.toggle-button');
    const chatIcon = document.querySelector('.chat-icon');

    // 设置初始高度
    chatContainer.style.height = '400px';

    // 切换展开/收起状态
    function toggleChat() {
        chatContainer.classList.toggle('collapsed');
        toggleButton.textContent = chatContainer.classList.contains('collapsed') ? '➖' : '➖';
    }

    toggleButton.addEventListener('click', toggleChat);
    chatIcon.addEventListener('click', toggleChat);

    // 实现拖拽功能
    let isDragging = false;
    let currentX;
    let currentY;
    let initialX;
    let initialY;
    let xOffset = 0;
    let yOffset = 0;

    header.addEventListener('mousedown', dragStart);
    document.addEventListener('mousemove', drag);
    document.addEventListener('mouseup', dragEnd);

    function dragStart(e) {
        initialX = e.clientX - xOffset;
        initialY = e.clientY - yOffset;
        if (e.target === header || e.target === chatIcon) {
            isDragging = true;
        }
    }

    function drag(e) {
        if (isDragging) {
            e.preventDefault();
            currentX = e.clientX - initialX;
            currentY = e.clientY - initialY;
            xOffset = currentX;
            yOffset = currentY;
            chatContainer.style.transform = `translate(${currentX}px, ${currentY}px)`;
        }
    }

    function dragEnd() {
        isDragging = false;
    }

    // 添加文字消息到聊天框
    function addMessage(message, type) {
        const messageDiv = document.createElement('div');
        messageDiv.classList.add('message', type);
        messageDiv.textContent = message;
        messagesContainer.appendChild(messageDiv);
        messagesContainer.scrollTop = messagesContainer.scrollHeight;
    }

    // 添加图片消息到聊天框
    function addImage(imageBase64, type) {
        const img = document.createElement('img');
        img.src = 'data:image/png;base64,' + imageBase64;
        img.classList.add('message', type);
        messagesContainer.appendChild(img);
        messagesContainer.scrollTop = messagesContainer.scrollHeight;
    }

    // 发送消息
    function sendMessage() {
        const message = input.value.trim();
        if (message) {
            addMessage(message, 'sent');

            // 添加调试日志
            console.log('Sending message:', message);

            // 发起请求到后端
            fetch('http://localhost:5000/message', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Accept': 'application/json',
                },
                mode: 'cors', // 明确指定跨域模式
                credentials: 'omit', // 不发送cookies
                body: JSON.stringify({ message: message })
            })
            .then(response => {
                console.log('Response status:', response.status); // 调试日志
                return response.json();
            })
            .then(data => {
                console.log('Received data:', data); // 调试日志
                if(data.response.text) {
                    addMessage(data.response.text, 'received');
                }
                if(data.response.image) {
                    addImage(data.response.image, 'received');
                }
            })
            .catch(error => {
                console.error('Error:', error);
                addMessage('发送失败，请检查服务器连接', 'received');
            });

            input.value = '';
        }
    }

    // 绑定发送事件
    sendButton.addEventListener('click', sendMessage);
    input.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') {
            sendMessage();
        }
    });
})();
