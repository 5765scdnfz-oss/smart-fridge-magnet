"""
MiMo API 客户端 — 复用现有配置
使用 Anthropic SDK 调用 MiMo v2.5（多模态）和 MiMo v2.5-pro（文本推理）
"""
import os
import sys
import base64
from pathlib import Path

# 加载 .env 配置
from dotenv import load_dotenv
env_path = Path(__file__).parent.parent.parent / 'claude code' / '.env'
if not env_path.exists():
    env_path = Path(__file__).parent.parent / '.env'
load_dotenv(env_path)

# MiMo 配置
MIMO_API_KEY = os.environ.get("MIMO_API_KEY")
MIMO_BASE_URL = os.environ.get("MIMO_BASE_URL", "https://token-plan-cn.xiaomimimo.com/anthropic")

MODEL_VISION = "mimo-v2.5"      # 视觉模型
MODEL_TEXT = "mimo-v2.5-pro"    # 文本模型

# 初始化客户端
client = None

def get_client():
    """获取 Anthropic 客户端"""
    global client
    if client is None:
        from anthropic import Anthropic
        client = Anthropic(api_key=MIMO_API_KEY, base_url=MIMO_BASE_URL)
    return client


def call_mimo_vision(prompt, image_path=None, image_base64=None, system_prompt=None):
    """
    调用 MiMo 多模态模型（图片识别）

    Args:
        prompt: 提示词
        image_path: 图片文件路径
        image_base64: 图片base64编码
        system_prompt: 系统提示词

    Returns:
        模型回复文本
    """
    c = get_client()

    # 处理图片
    if image_path:
        with open(image_path, 'rb') as f:
            b64_data = base64.standard_b64encode(f.read()).decode('utf-8')
        # 推断 mime type
        ext = Path(image_path).suffix.lower()
        mime_map = {'.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.png': 'image/png', '.gif': 'image/gif', '.webp': 'image/webp'}
        mime_type = mime_map.get(ext, 'image/jpeg')
    elif image_base64:
        b64_data = image_base64
        mime_type = 'image/jpeg'
    else:
        return "错误：需要提供图片"

    # 构建消息
    content = [
        {"type": "image", "source": {"type": "base64", "media_type": mime_type, "data": b64_data}},
        {"type": "text", "text": prompt}
    ]

    kwargs = {
        "model": MODEL_VISION,
        "max_tokens": 4096,
        "messages": [{"role": "user", "content": content}]
    }
    if system_prompt:
        kwargs["system"] = system_prompt

    try:
        resp = c.messages.create(**kwargs)
        return resp.content[0].text
    except Exception as e:
        return f"调用失败: {str(e)}"


def call_mimo_text(prompt, system_prompt=None, temperature=1.0):
    """
    调用 MiMo 文本模型

    Args:
        prompt: 用户输入
        system_prompt: 系统提示词
        temperature: 温度参数

    Returns:
        模型回复文本
    """
    c = get_client()

    kwargs = {
        "model": MODEL_TEXT,
        "max_tokens": 4096,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": temperature,
        "top_p": 0.95
    }
    if system_prompt:
        kwargs["system"] = system_prompt

    try:
        resp = c.messages.create(**kwargs)
        return resp.content[0].text
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
    import json

    result = call_mimo_text(prompt, system_prompt, temperature)

    # 尝试提取 JSON
    try:
        text = result.strip()
        # 去掉 markdown 代码块
        if text.startswith('```json'):
            text = text[7:]
        if text.startswith('```'):
            text = text[3:]
        if text.endswith('```'):
            text = text[:-3]
        text = text.strip()

        return json.loads(text)
    except json.JSONDecodeError:
        # 尝试找 JSON 部分
        try:
            start = result.find('[')
            if start == -1:
                start = result.find('{')
            if start != -1:
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


def health_check():
    """检查 API 连通性"""
    import time

    result = {}

    # 测试文本模型
    print(f"[Check] {MODEL_TEXT}...", end=" ", flush=True)
    start = time.time()
    try:
        resp = call_mimo_text("Reply with only: OK")
        latency = time.time() - start
        if "调用失败" in resp:
            result["text"] = {"status": "fail", "latency": round(latency, 2), "error": resp}
            print(f"FAIL: {resp[:60]}")
        else:
            result["text"] = {"status": "ok", "latency": round(latency, 2)}
            print(f"OK ({latency:.1f}s)")
    except Exception as e:
        latency = time.time() - start
        result["text"] = {"status": "fail", "latency": round(latency, 2), "error": str(e)[:80]}
        print(f"FAIL: {str(e)[:60]}")

    # 测试视觉模型（生成测试图片）
    print(f"[Check] {MODEL_VISION}...", end=" ", flush=True)
    start = time.time()
    try:
        from PIL import Image, ImageDraw
        import io

        img = Image.new('RGB', (100, 50), color='white')
        d = ImageDraw.Draw(img)
        d.text((10, 15), "TEST", fill='black')
        buf = io.BytesIO()
        img.save(buf, format='PNG')
        b64 = base64.standard_b64encode(buf.getvalue()).decode('utf-8')

        resp = call_mimo_vision("What text is shown?", image_base64=b64)
        latency = time.time() - start
        if "调用失败" in resp:
            result["vision"] = {"status": "fail", "latency": round(latency, 2), "error": resp}
            print(f"FAIL: {resp[:60]}")
        else:
            result["vision"] = {"status": "ok", "latency": round(latency, 2)}
            print(f"OK ({latency:.1f}s)")
    except Exception as e:
        latency = time.time() - start
        result["vision"] = {"status": "fail", "latency": round(latency, 2), "error": str(e)[:80]}
        print(f"FAIL: {str(e)[:60]}")

    return result


if __name__ == '__main__':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

    print("=" * 60)
    print("MiMo API Health Check")
    print("=" * 60)
    print(f"\n[Config]")
    print(f"  BASE_URL: {MIMO_BASE_URL}")
    print(f"  MODEL_VISION: {MODEL_VISION}")
    print(f"  MODEL_TEXT: {MODEL_TEXT}")
    print(f"  API_KEY: {'set' if MIMO_API_KEY else 'NOT SET'}")
    print()

    if not MIMO_API_KEY:
        print("ERROR: MIMO_API_KEY not set!")
        print(f"Please set it in {env_path}")
        sys.exit(1)

    result = health_check()

    print("\n" + "=" * 60)
    all_ok = all(v["status"] == "ok" for v in result.values())
    status = "ALL OK" if all_ok else "SOME FAILED"
    print(f"Overall: {status}")
