import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import requests
import json
import threading

try:
    import easyocr
    OCR_AVAILABLE = True
except ImportError:
    OCR_AVAILABLE = False


PROVIDERS = {
    "deepseek": {
        "label": "DeepSeek",
        "base_url": "https://api.deepseek.com/v1/chat/completions",
        "models": [
            {"id": "deepseek-chat", "label": "deepseek-chat"},
            {"id": "deepseek-reasoner", "label": "deepseek-reasoner"},
        ],
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
    },
    "kimi": {
        "label": "Kimi",
        "base_url": "https://api.moonshot.cn/v1/chat/completions",
        "models": [
            {"id": "moonshot-v1-8k", "label": "moonshot-v1-8k"},
            {"id": "moonshot-v1-32k", "label": "moonshot-v1-32k"},
            {"id": "moonshot-v1-128k", "label": "moonshot-v1-128k"},
        ],
    },
}

DIRECTIONS = {
    "zh2en": {"label": "中 → 英", "input_hint": "输入中文：", "output_hint": "英文结果：",
              "input_warn": "请先输入要翻译的中文",
              "sys_prompt": "You are a professional translator. Translate the following Chinese text to English. Output only the translation, nothing else."},
    "en2zh": {"label": "英 → 中", "input_hint": "输入英文：", "output_hint": "中文结果：",
              "input_warn": "请先输入要翻译的英文",
              "sys_prompt": "You are a professional translator. Translate the following English text to Chinese. Output only the translation, nothing else."},
}


def translate(api_key, text, direction, callback):
    provider = PROVIDERS[get_provider_key()]
    model_id = model_var.get()
    sys_prompt = DIRECTIONS[direction]["sys_prompt"]

    def task():
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
            resp = requests.post(provider["base_url"], headers=headers, json=payload, timeout=60)
            data = resp.json()
            if resp.status_code == 200:
                result = data["choices"][0]["message"]["content"].strip()
                callback(result, None)
            else:
                error_msg = data.get("error", {}).get("message", str(resp.status_code))
                callback(None, f"API 错误 ({resp.status_code}): {error_msg}")
        except requests.exceptions.Timeout:
            callback(None, "请求超时，请检查网络连接")
        except Exception as e:
            callback(None, f"请求失败: {e}")

    threading.Thread(target=task, daemon=True).start()


def on_translate_complete(result, error):
    status_label.config(text="就绪")
    translate_btn.config(state=tk.NORMAL)
    if error:
        messagebox.showerror("翻译失败", error)
    else:
        output_box.delete("1.0", tk.END)
        output_box.insert("1.0", result)


def get_provider_key():
    label = provider_var.get()
    for key, p in PROVIDERS.items():
        if p["label"] == label:
            return key
    return "deepseek"

def on_provider_change(*args):
    provider = PROVIDERS[get_provider_key()]
    models = provider["models"]
    model_menu["values"] = [m["label"] for m in models]
    model_var.set(models[0]["id"])


def on_direction_change(*args):
    d = direction_var.get()
    info = DIRECTIONS[d]
    input_label.config(text=info["input_hint"])
    output_label.config(text=info["output_hint"])


def translate_text():
    api_key = api_key_var.get().strip()
    if not api_key:
        messagebox.showwarning("提示", "请先输入 API Key")
        return
    input_text = input_box.get("1.0", tk.END).strip()
    if not input_text:
        messagebox.showwarning("提示", DIRECTIONS[direction_var.get()]["input_warn"])
        return

    translate_btn.config(state=tk.DISABLED)
    status_label.config(text="翻译中...")
    translate(api_key, input_text, direction_var.get(), on_translate_complete)


def clear_text():
    input_box.delete("1.0", tk.END)
    output_box.delete("1.0", tk.END)


def copy_result():
    text = output_box.get("1.0", tk.END).strip()
    if not text:
        return
    root.clipboard_clear()
    root.clipboard_append(text)
    status_label.config(text="已复制")
    root.after(2000, lambda: status_label.config(text="就绪"))


_ocr_reader = None
def get_ocr_reader():
    global _ocr_reader
    if _ocr_reader is None:
        _ocr_reader = easyocr.Reader(["ch_sim", "en"], gpu=False)
    return _ocr_reader


def select_image():
    if not OCR_AVAILABLE:
        messagebox.showwarning("提示", "OCR 未安装，请运行: pip install easyocr")
        return
    file_path = filedialog.askopenfilename(
        title="选择图片",
        filetypes=[("图片文件", "*.png *.jpg *.jpeg *.bmp *.tiff")],
    )
    if not file_path:
        return

    translate_btn.config(state=tk.DISABLED)
    status_label.config(text="识别中...")

    def task():
        try:
            reader = get_ocr_reader()
            result = reader.readtext(file_path)
            lines = [item[1] for item in result]
            text = "\n".join(lines) if lines else ""
            root.after(0, lambda: _on_ocr_done(text))
        except Exception as e:
            root.after(0, lambda: _on_ocr_error(str(e)))

    threading.Thread(target=task, daemon=True).start()


def _on_ocr_done(text):
    translate_btn.config(state=tk.NORMAL)
    if text.strip():
        input_box.delete("1.0", tk.END)
        input_box.insert("1.0", text)
        status_label.config(text=f"识别完成，{len(text)} 字符")
    else:
        status_label.config(text="未识别到文字")


def _on_ocr_error(msg):
    translate_btn.config(state=tk.NORMAL)
    status_label.config(text="识别失败")
    messagebox.showerror("识别失败", msg)


def toggle_api_key_visibility():
    if api_key_entry.cget("show") == "":
        api_key_entry.config(show="*")
        toggle_btn.config(text="显示")
    else:
        api_key_entry.config(show="")
        toggle_btn.config(text="隐藏")


# ========== GUI ==========
root = tk.Tk()
root.title("AI 翻译工具")
root.geometry("640x600")
root.resizable(True, True)

frame = ttk.Frame(root, padding="16")
frame.pack(fill=tk.BOTH, expand=True)

# ── Provider & API Key & Model ──
cfg_frame = ttk.LabelFrame(frame, text="模型配置", padding=(8, 6))
cfg_frame.pack(fill=tk.X, pady=(10, 0))

# Row 1: provider
p_row = ttk.Frame(cfg_frame)
p_row.pack(fill=tk.X, pady=(0, 6))
ttk.Label(p_row, text="服务商：", font=("微软雅黑", 10)).pack(side=tk.LEFT)

provider_var = tk.StringVar(value="deepseek")
provider_var.trace_add("write", on_provider_change)
provider_menu = ttk.Combobox(
    p_row, textvariable=provider_var, state="readonly", width=14, font=("微软雅黑", 10)
)
provider_menu["values"] = [p["label"] for p in PROVIDERS.values()]
provider_menu.pack(side=tk.LEFT, padx=(4, 0))

# Row 2: API Key
api_row = ttk.Frame(cfg_frame)
api_row.pack(fill=tk.X, pady=(0, 6))
ttk.Label(api_row, text="API Key：", font=("微软雅黑", 10)).pack(side=tk.LEFT)

api_key_var = tk.StringVar()
api_key_entry = ttk.Entry(api_row, textvariable=api_key_var, show="*", font=("微软雅黑", 10))
api_key_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(4, 4))

toggle_btn = ttk.Button(api_row, text="显示", width=5, command=toggle_api_key_visibility)
toggle_btn.pack(side=tk.RIGHT)

# Row 3: model version
m_row = ttk.Frame(cfg_frame)
m_row.pack(fill=tk.X, pady=(0, 4))
ttk.Label(m_row, text="模　型：", font=("微软雅黑", 10)).pack(side=tk.LEFT)

model_var = tk.StringVar(value="deepseek-chat")
model_menu = ttk.Combobox(
    m_row, textvariable=model_var, state="readonly", width=30, font=("微软雅黑", 10)
)
model_menu.pack(side=tk.LEFT, padx=(4, 0))


# ── Direction ──
dir_frame = ttk.LabelFrame(frame, text="翻译方向", padding=(8, 6))
dir_frame.pack(fill=tk.X, pady=(8, 0))

direction_var = tk.StringVar(value="zh2en")
direction_var.trace_add("write", on_direction_change)
ttk.Radiobutton(dir_frame, text="中 → 英", variable=direction_var, value="zh2en").pack(side=tk.LEFT, padx=(4, 12))
ttk.Radiobutton(dir_frame, text="英 → 中", variable=direction_var, value="en2zh").pack(side=tk.LEFT, padx=4)

# ── Separator ──
ttk.Separator(frame, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=(12, 10))

# ── Input ──
input_label = ttk.Label(frame, text="输入中文：", font=("微软雅黑", 11))
input_label.pack(anchor=tk.W)
input_box = tk.Text(frame, height=6, font=("微软雅黑", 11), padx=6, pady=6)
input_box.pack(fill=tk.X, pady=(4, 8))

# ── Buttons ──
btn_frame = ttk.Frame(frame)
btn_frame.pack(fill=tk.X, pady=4)

translate_btn = ttk.Button(btn_frame, text="翻译 →", command=translate_text)
translate_btn.pack(side=tk.LEFT, padx=(0, 6))

ocr_btn = ttk.Button(btn_frame, text="识别图片", command=select_image)
ocr_btn.pack(side=tk.LEFT, padx=(0, 6))

ttk.Separator(btn_frame, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=(0, 6))

clear_btn = ttk.Button(btn_frame, text="清空", command=clear_text)
clear_btn.pack(side=tk.LEFT, padx=(0, 6))

copy_btn = ttk.Button(btn_frame, text="复制", command=copy_result)
copy_btn.pack(side=tk.LEFT)

status_label = ttk.Label(btn_frame, text="就绪", font=("微软雅黑", 9), foreground="gray")
status_label.pack(side=tk.RIGHT)

# ── Output ──
output_label = ttk.Label(frame, text="英文结果：", font=("微软雅黑", 11))
output_label.pack(anchor=tk.W, pady=(12, 0))
output_box = tk.Text(frame, height=6, font=("微软雅黑", 11), padx=6, pady=6, fg="#2c3e50")
output_box.pack(fill=tk.BOTH, expand=True, pady=(4, 8))

# ── Hotkey hint ──
ttk.Label(frame, text="快捷键: Ctrl+Enter 翻译 | Ctrl+Shift+C 清空",
          font=("微软雅黑", 9), foreground="gray").pack(anchor=tk.E)

root.bind("<Control-Return>", lambda e: translate_text())
root.bind("<Control-Shift-KeyPress-C>", lambda e: clear_text())

# Init
on_provider_change()

root.mainloop()
