import tkinter as tk
from tkinter import ttk, messagebox
import requests
import json
import threading


DEEPSEEK_API_URL = "https://api.deepseek.com/v1/chat/completions"

DIRECTIONS = {
    "zh2en": {"label": "中 → 英", "input_hint": "输入中文：", "output_hint": "英文结果：",
              "input_warn": "请先输入要翻译的中文", "sys_prompt": "You are a professional translator. Translate the following Chinese text to English. Output only the translation, nothing else."},
    "en2zh": {"label": "英 → 中", "input_hint": "输入英文：", "output_hint": "中文结果：",
              "input_warn": "请先输入要翻译的英文", "sys_prompt": "You are a professional translator. Translate the following English text to Chinese. Output only the translation, nothing else."},
}


def translate_with_deepseek(api_key, text, direction, callback):
    """Call DeepSeek API in a separate thread."""

    def task():
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": "deepseek-chat",
            "messages": [
                {"role": "system", "content": DIRECTIONS[direction]["sys_prompt"]},
                {"role": "user", "content": text},
            ],
            "stream": False,
        }
        try:
            resp = requests.post(DEEPSEEK_API_URL, headers=headers, json=payload, timeout=60)
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


def on_direction_change(*args):
    d = direction_var.get()
    info = DIRECTIONS[d]
    input_label.config(text=info["input_hint"])
    output_label.config(text=info["output_hint"])
    root.title(f"DeepSeek 翻译 - {info['label']}")


def translate_text():
    api_key = api_key_var.get().strip()
    if not api_key:
        messagebox.showwarning("提示", "请先输入 DeepSeek API Key")
        return
    input_text = input_box.get("1.0", tk.END).strip()
    if not input_text:
        messagebox.showwarning("提示", DIRECTIONS[direction_var.get()]["input_warn"])
        return

    translate_btn.config(state=tk.DISABLED)
    status_label.config(text="翻译中...")
    translate_with_deepseek(api_key, input_text, direction_var.get(), on_translate_complete)


def clear_text():
    input_box.delete("1.0", tk.END)
    output_box.delete("1.0", tk.END)


def toggle_api_key_visibility():
    if api_key_entry.cget("show") == "":
        api_key_entry.config(show="*")
        toggle_btn.config(text="显示")
    else:
        api_key_entry.config(show="")
        toggle_btn.config(text="隐藏")


# Build GUI
root = tk.Tk()
root.title("DeepSeek 翻译 - 中 → 英")
root.geometry("620x540")
root.resizable(True, True)

frame = ttk.Frame(root, padding="16")
frame.pack(fill=tk.BOTH, expand=True)

# API Key row
ttk.Label(frame, text="DeepSeek API Key：", font=("微软雅黑", 10)).pack(anchor=tk.W)
api_key_frame = ttk.Frame(frame)
api_key_frame.pack(fill=tk.X, pady=(4, 4))

api_key_var = tk.StringVar()
api_key_entry = ttk.Entry(api_key_frame, textvariable=api_key_var, show="*", font=("微软雅黑", 10))
api_key_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)

toggle_btn = ttk.Button(api_key_frame, text="显示", width=5, command=toggle_api_key_visibility)
toggle_btn.pack(side=tk.RIGHT, padx=(6, 0))

# Separator
ttk.Separator(frame, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=(10, 10))

# Direction selector
dir_frame = ttk.Frame(frame)
dir_frame.pack(fill=tk.X, pady=(0, 8))

direction_var = tk.StringVar(value="zh2en")
direction_var.trace_add("write", on_direction_change)

ttk.Label(dir_frame, text="翻译方向：", font=("微软雅黑", 10)).pack(side=tk.LEFT)
ttk.Radiobutton(dir_frame, text="中 → 英", variable=direction_var, value="zh2en").pack(side=tk.LEFT, padx=(8, 4))
ttk.Radiobutton(dir_frame, text="英 → 中", variable=direction_var, value="en2zh").pack(side=tk.LEFT, padx=4)

# Input area
input_label = ttk.Label(frame, text="输入中文：", font=("微软雅黑", 11))
input_label.pack(anchor=tk.W)
input_box = tk.Text(frame, height=8, font=("微软雅黑", 11), padx=6, pady=6)
input_box.pack(fill=tk.X, pady=(4, 8))

# Button row
btn_frame = ttk.Frame(frame)
btn_frame.pack(fill=tk.X, pady=4)

translate_btn = ttk.Button(btn_frame, text="翻译 →", command=translate_text)
translate_btn.pack(side=tk.LEFT, padx=(0, 8))

clear_btn = ttk.Button(btn_frame, text="清空", command=clear_text)
clear_btn.pack(side=tk.LEFT)

status_label = ttk.Label(btn_frame, text="就绪", font=("微软雅黑", 9), foreground="gray")
status_label.pack(side=tk.RIGHT)

# Output area
output_label = ttk.Label(frame, text="英文结果：", font=("微软雅黑", 11))
output_label.pack(anchor=tk.W, pady=(12, 0))
output_box = tk.Text(frame, height=8, font=("微软雅黑", 11), padx=6, pady=6, fg="#2c3e50")
output_box.pack(fill=tk.BOTH, expand=True, pady=(4, 8))

# Hotkey hint
ttk.Label(frame, text="快捷键: Ctrl+Enter 翻译 | Ctrl+Shift+C 清空",
          font=("微软雅黑", 9), foreground="gray").pack(anchor=tk.E)

# Keyboard shortcuts
root.bind("<Control-Return>", lambda e: translate_text())
root.bind("<Control-Shift-KeyPress-C>", lambda e: clear_text())

root.mainloop()
