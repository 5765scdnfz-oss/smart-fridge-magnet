"""
MiMo API 客户端 — 调用 MiMo v2.5（多模态）和 MiMo v2.5-pro（文本推理）
"""
import requests
import json
import base64
import os

# MiMo API 配置
MIMO_API_KEY = os.environ.get('MIMO_API_KEY', '')
MIMO_BASE_URL = os.environ.get('MIMO_BASE_URL', 'https://api.mimo.com/v1')

# 模型配置
MODEL_VISION = 'mimo-v2.5'  # 多模态，用于图片识别
MODEL_TEXT = 'mimo-v2.5-pro'  # 文本推理，用于对话和菜谱生成


def call_mimo_text(prompt, system_prompt=None, temperature=0.7):
    """
    调用 MiMo 文本模型

    Args:
        prompt: 用户输入
        system_prompt: 系统提示词
        temperature: 温度参数

    Returns:
        模型回复文本
    """
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    headers = {
        'Authorization': f'Bearer {MIMO_API_KEY}',
        'Content-Type': 'application/json'
    }

    payload = {
        'model': MODEL_TEXT,
        'messages': messages,
        'temperature': temperature,
        'max_tokens': 4096
    }

    try:
        resp = requests.post(
            f'{MIMO_BASE_URL}/chat/completions',
            headers=headers,
            json=payload,
            timeout=60
        )
        resp.raise_for_status()
        data = resp.json()
        return data['choices'][0]['message']['content']
    except Exception as e:
        return f"调用失败: {str(e)}"


def call_mimo_vision(prompt, image_path=None, image_base64=None, system_prompt=None):
    """
    调用 MiMo 多模态模型（图片识别）

    Args:
        prompt: 提示词
        image_path: 图片文件路径
        image_base64: 图片base64编码（与image_path二选一）
        system_prompt: 系统提示词

    Returns:
        模型回复文本
    """
    # 处理图片
    if image_path:
        with open(image_path, 'rb') as f:
            image_data = base64.b64encode(f.read()).decode('utf-8')
    elif image_base64:
        image_data = image_base64
    else:
        return "错误：需要提供图片"

    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})

    # 构建包含图片的消息
    messages.append({
        "role": "user",
        "content": [
            {
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/jpeg;base64,{image_data}"
                }
            },
            {
                "type": "text",
                "text": prompt
            }
        ]
    })

    headers = {
        'Authorization': f'Bearer {MIMO_API_KEY}',
        'Content-Type': 'application/json'
    }

    payload = {
        'model': MODEL_VISION,
        'messages': messages,
        'temperature': 0.3,  # 识别任务用较低温度
        'max_tokens': 4096
    }

    try:
        resp = requests.post(
            f'{MIMO_BASE_URL}/chat/completions',
            headers=headers,
            json=payload,
            timeout=120
        )
        resp.raise_for_status()
        data = resp.json()
        return data['choices'][0]['message']['content']
    except Exception as e:
        return f"调用失败: {str(e)}"


def call_mimo_text_with_json(prompt, system_prompt=None, temperature=0.3):
    """
    调用 MiMo 文本模型并强制返回 JSON

    Args:
        prompt: 用户输入
        system_prompt: 系统提示词
        temperature: 温度参数

    Returns:
        解析后的 JSON 对象
    """
    # 在 prompt 末尾强调返回 JSON
    if "返回" not in prompt.lower() and "json" not in prompt.lower():
        prompt += "\n\n请返回纯JSON格式，不要包含其他文字。"

    result = call_mimo_text(prompt, system_prompt, temperature)

    # 尝试提取 JSON
    try:
        # 去掉可能的 markdown 代码块标记
        text = result.strip()
        if text.startswith('```json'):
            text = text[7:]
        if text.startswith('```'):
            text = text[3:]
        if text.endswith('```'):
            text = text[:-3]
        text = text.strip()

        return json.loads(text)
    except json.JSONDecodeError:
        # 如果直接解析失败，尝试找 JSON 部分
        try:
            start = result.find('[')
            if start == -1:
                start = result.find('{')
            if start != -1:
                # 找到对应的结束符
                bracket_count = 0
                for i in range(start, len(result)):
                    if result[i] in '[{':
                        bracket_count += 1
                    elif result[i] in ']}':
                        bracket_count -= 1
                    if bracket_count == 0:
                        return json.loads(result[start:i+1])
        except:
            pass

        return {"error": "无法解析JSON", "raw": result}


if __name__ == '__main__':
    # 测试配置
    print(f"API Base URL: {MIMO_BASE_URL}")
    print(f"API Key: {'*' * 10 if MIMO_API_KEY else '未设置'}")
    print(f"Vision Model: {MODEL_VISION}")
    print(f"Text Model: {MODEL_TEXT}")
    print("\n请设置环境变量 MIMO_API_KEY 和 MIMO_BASE_URL 后运行测试")
