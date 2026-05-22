import os
import sys
import tempfile
import threading
import webbrowser

from flask import Flask, render_template, request, jsonify


def resource_path(relative_path):
    """Get absolute path to resource — works for dev and PyInstaller frozen builds."""
    try:
        base_path = sys._MEIPASS
    except AttributeError:
        base_path = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_path, relative_path)

PROVIDERS = {
    "deepseek": {
        "label": "DeepSeek",
        "base_url": "https://api.deepseek.com/v1/chat/completions",
        "models": [
            {"id": "deepseek-chat", "label": "deepseek-chat"},
            {"id": "deepseek-reasoner", "label": "deepseek-reasoner"},
        ],
        "multimodal": False,
    },
    "doubao": {
        "label": "豆包",
        "base_url": "https://ark.cn-beijing.volces.com/api/v3/chat/completions",
        "models": [
            {"id": "doubao-pro-32k", "label": "doubao-pro-32k"},
            {"id": "doubao-pro-128k", "label": "doubao-pro-128k"},
            {"id": "doubao-lite-32k", "label": "doubao-lite-32k"},
            {"id": "doubao-lite-128k", "label": "doubao-lite-128k"},
        ],
        "multimodal": False,
    },
    "kimi": {
        "label": "Kimi",
        "base_url": "https://api.moonshot.cn/v1/chat/completions",
        "models": [
            {"id": "moonshot-v1-8k", "label": "moonshot-v1-8k"},
            {"id": "moonshot-v1-32k", "label": "moonshot-v1-32k"},
            {"id": "moonshot-v1-128k", "label": "moonshot-v1-128k"},
        ],
        "multimodal": True,
    },
}

DIRECTIONS = {
    "zh2en": {
        "sys_prompt": "You are a professional translator. Translate the following Chinese text to English. Output only the translation, nothing else.",
    },
    "en2zh": {
        "sys_prompt": "You are a professional translator. Translate the following English text to Chinese. Output only the translation, nothing else.",
    },
}

OCR_AVAILABLE = False
_ocr_reader = None

try:
    import easyocr

    OCR_AVAILABLE = True
except ImportError:
    pass


def get_ocr_reader():
    global _ocr_reader
    if _ocr_reader is None and OCR_AVAILABLE:
        _ocr_reader = easyocr.Reader(["ch_sim", "en"], gpu=False)
    return _ocr_reader


app = Flask(__name__,
    template_folder=resource_path("templates"),
    static_folder=resource_path("static"))


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/config")
def api_config():
    return jsonify({
        "providers": {
            k: {"label": v["label"], "models": v["models"], "multimodal": v.get("multimodal", False)}
            for k, v in PROVIDERS.items()
        },
        "directions": {k: {"label": v.get("label", k)} for k, v in DIRECTIONS.items()},
        "ocr_available": OCR_AVAILABLE,
    })


@app.route("/api/translate", methods=["POST"])
def api_translate():
    data = request.json
    api_key = (data.get("api_key") or "").strip()
    text = (data.get("text") or "").strip()
    provider_key = data.get("provider", "deepseek")
    model_id = data.get("model", "deepseek-chat")
    direction = data.get("direction", "zh2en")

    if not api_key:
        return jsonify({"error": "请输入 API Key"}), 400
    if not text:
        return jsonify({"error": "请输入要翻译的文本"}), 400

    provider = PROVIDERS.get(provider_key)
    if not provider:
        return jsonify({"error": "未知的服务商"}), 400

    sys_prompt = DIRECTIONS.get(direction, {}).get("sys_prompt", "")
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model_id,
        "messages": [
            {"role": "system", "content": sys_prompt},
            {"role": "user", "content": text},
        ],
        "stream": False,
    }

    try:
        import requests

        resp = requests.post(provider["base_url"], headers=headers, json=payload, timeout=60)
        data = resp.json()
        if resp.status_code == 200:
            result = data["choices"][0]["message"]["content"].strip()
            return jsonify({"result": result})
        else:
            error_msg = data.get("error", {}).get("message", str(resp.status_code))
            return jsonify({"error": f"API 错误 ({resp.status_code}): {error_msg}"}), 502
    except requests.exceptions.Timeout:
        return jsonify({"error": "请求超时，请检查网络连接"}), 504
    except Exception as e:
        return jsonify({"error": f"请求失败: {e}"}), 500


@app.route("/api/ocr", methods=["POST"])
def api_ocr():
    if not OCR_AVAILABLE:
        return jsonify({"error": "OCR 未安装，请运行: pip install easyocr"}), 400

    image_data = None
    if "image" in request.files:
        image_data = request.files["image"].read()
    elif request.json and request.json.get("image"):
        import base64
        image_data = base64.b64decode(request.json["image"])

    if not image_data:
        return jsonify({"error": "未提供图片"}), 400

    tmp_path = None
    try:
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".png")
        tmp_path = tmp.name
        tmp.close()
        with open(tmp_path, "wb") as f:
            f.write(image_data)

        reader = get_ocr_reader()
        if reader is None:
            return jsonify({"error": "OCR 模型加载失败"}), 500

        result = reader.readtext(tmp_path)
        lines = [item[1] for item in result]
        text = "\n".join(lines) if lines else ""
        return jsonify({"text": text, "chars": len(text)})
    except Exception as e:
        return jsonify({"error": f"识别失败: {e}"}), 500
    finally:
        if tmp_path:
            try:
                os.unlink(tmp_path)
            except Exception:
                pass


MULTIMODAL_PROMPTS = {
    "zh2en": "请识别这张图片中的文字，然后将其翻译成英文。直接输出翻译结果，不要额外说明。",
    "en2zh": "请识别这张图片中的文字，然后将其翻译成中文。直接输出翻译结果，不要额外说明。",
}


@app.route("/api/translate-image", methods=["POST"])
def api_translate_image():
    api_key = (request.form.get("api_key") or "").strip()
    provider_key = request.form.get("provider", "deepseek")
    model_id = request.form.get("model", "deepseek-chat")
    direction = request.form.get("direction", "zh2en")

    if not api_key:
        return jsonify({"error": "请输入 API Key"}), 400

    provider = PROVIDERS.get(provider_key)
    if not provider:
        return jsonify({"error": "未知的服务商"}), 400

    # Read image
    image_data = None
    if "image" in request.files:
        image_data = request.files["image"].read()
    elif request.form.get("image"):
        import base64
        image_data = base64.b64decode(request.form["image"])

    if not image_data:
        return jsonify({"error": "未提供图片"}), 400

    is_multimodal = provider.get("multimodal", False)

    if is_multimodal:
        # ── Vision API: 大模型直接识别+翻译 ──
        import base64
        img_b64 = base64.b64encode(image_data).decode("utf-8")
        mime = "image/png"

        user_text = MULTIMODAL_PROMPTS.get(direction, MULTIMODAL_PROMPTS["zh2en"])

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": model_id,
            "messages": [
                {"role": "system", "content": "You are a professional translator and OCR assistant."},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": user_text},
                        {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{img_b64}"}},
                    ],
                },
            ],
            "stream": False,
        }

        try:
            import requests
            resp = requests.post(provider["base_url"], headers=headers, json=payload, timeout=120)
            data = resp.json()
            if resp.status_code == 200:
                result = data["choices"][0]["message"]["content"].strip()
                return jsonify({"result": result, "multimodal": True})
            else:
                error_msg = data.get("error", {}).get("message", str(resp.status_code))
                return jsonify({"error": f"API 错误 ({resp.status_code}): {error_msg}"}), 502
        except requests.exceptions.Timeout:
            return jsonify({"error": "请求超时，请检查网络连接"}), 504
        except Exception as e:
            return jsonify({"error": f"请求失败: {e}"}), 500

    else:
        # ── 非多模态: easyocr 识别 + 翻译 ──
        if not OCR_AVAILABLE:
            return jsonify({"error": "当前模型不支持图片识别，且未安装 OCR 组件（easyocr）"}), 400

        tmp_path = None
        try:
            tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".png")
            tmp_path = tmp.name
            tmp.close()
            with open(tmp_path, "wb") as f:
                f.write(image_data)

            reader = get_ocr_reader()
            if reader is None:
                return jsonify({"error": "OCR 模型加载失败"}), 500

            result = reader.readtext(tmp_path)
            lines = [item[1] for item in result]
            text = "\n".join(lines) if lines else ""

            if not text.strip():
                return jsonify({"error": "图片中未识别到文字"}), 400

            # Translate the OCR result
            sys_prompt = DIRECTIONS.get(direction, {}).get("sys_prompt", "")
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            }
            payload = {
                "model": model_id,
                "messages": [
                    {"role": "system", "content": sys_prompt},
                    {"role": "user", "content": text},
                ],
                "stream": False,
            }

            import requests
            resp = requests.post(provider["base_url"], headers=headers, json=payload, timeout=60)
            data = resp.json()
            if resp.status_code == 200:
                translated = data["choices"][0]["message"]["content"].strip()
                return jsonify({"result": translated, "ocr_text": text, "multimodal": False})
            else:
                error_msg = data.get("error", {}).get("message", str(resp.status_code))
                return jsonify({"error": f"翻译失败 ({resp.status_code}): {error_msg}"}), 502

        except requests.exceptions.Timeout:
            return jsonify({"error": "翻译请求超时"}), 504
        except Exception as e:
            return jsonify({"error": f"处理失败: {e}"}), 500
        finally:
            if tmp_path:
                try:
                    os.unlink(tmp_path)
                except Exception:
                    pass


if __name__ == "__main__":
    threading.Timer(2.5, lambda: webbrowser.open("http://127.0.0.1:5000")).start()
    app.run(host="127.0.0.1", port=5000, debug=False, threaded=True)
