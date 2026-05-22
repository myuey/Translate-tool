let providers = {};
let ocrAvailable = false;

// ── Toast ──
function toast(msg) {
  const el = document.getElementById("toast");
  el.textContent = msg;
  el.classList.add("show");
  clearTimeout(el._timer);
  el._timer = setTimeout(() => el.classList.remove("show"), 2400);
}

// ── Status ──
function setStatus(text, loading) {
  const el = document.getElementById("statusLabel");
  if (loading) {
    el.innerHTML = `<span class="status-dot"></span><span class="loading-text">${text}</span>`;
  } else {
    el.innerHTML = text;
  }
}

// ── Load config ──
async function loadConfig() {
  try {
    const res = await fetch("/api/config");
    const data = await res.json();
    providers = data.providers;
    ocrAvailable = data.ocr_available;

    const sel = document.getElementById("provider");
    sel.innerHTML = "";
    for (const [key, p] of Object.entries(providers)) {
      const opt = document.createElement("option");
      opt.value = key;
      opt.textContent = p.label;
      sel.appendChild(opt);
    }
    onProviderChange();
  } catch (e) {
    toast("加载配置失败");
  }
}

// ── Provider change ──
function onProviderChange() {
  const key = document.getElementById("provider").value;
  const p = providers[key];
  if (!p) return;
  const sel = document.getElementById("model");
  sel.innerHTML = "";
  p.models.forEach((m) => {
    const opt = document.createElement("option");
    opt.value = m.id;
    opt.textContent = m.label;
    sel.appendChild(opt);
  });
}

// ── API Key toggle ──
document.getElementById("toggleKey").addEventListener("click", () => {
  const input = document.getElementById("apiKey");
  const btn = document.getElementById("toggleKey");
  if (input.type === "password") {
    input.type = "text";
    btn.textContent = "隐藏";
  } else {
    input.type = "password";
    btn.textContent = "显示";
  }
});

// ── Provider change event ──
document.getElementById("provider").addEventListener("change", onProviderChange);

// ── Translate ──
async function translate() {
  const apiKey = document.getElementById("apiKey").value.trim();
  const text = document.getElementById("inputText").value.trim();
  if (!apiKey) { toast("请先输入 API Key"); return; }
  if (!text) { toast("请先输入要翻译的文本"); return; }

  const btn = document.getElementById("translateBtn");
  btn.disabled = true;
  setStatus("翻译中...", true);

  try {
    const res = await fetch("/api/translate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        api_key: apiKey,
        text,
        provider: document.getElementById("provider").value,
        model: document.getElementById("model").value,
        direction: document.querySelector('input[name="direction"]:checked').value,
      }),
    });
    const data = await res.json();
    if (data.error) {
      toast(data.error);
      setStatus("翻译失败");
    } else {
      document.getElementById("outputText").value = data.result;
      setStatus(`翻译完成 · ${data.result.length} 字符`);
    }
  } catch (e) {
    toast("网络错误");
    setStatus("翻译失败");
  } finally {
    btn.disabled = false;
  }
}

// ── Translate button click ──
document.getElementById("translateBtn").addEventListener("click", translate);

// ── OCR via file ──
document.getElementById("ocrBtn").addEventListener("click", () => {
  if (!ocrAvailable) { toast("OCR 未安装，请运行: pip install easyocr"); return; }
  document.getElementById("fileInput").click();
});

document.getElementById("fileInput").addEventListener("change", async (e) => {
  const file = e.target.files[0];
  if (!file) return;
  await doOcr(file);
  e.target.value = "";
});

async function doOcr(file) {
  setStatus("识别中...", true);
  const btn = document.getElementById("translateBtn");
  btn.disabled = true;
  try {
    const form = new FormData();
    form.append("image", file);
    const res = await fetch("/api/ocr", { method: "POST", body: form });
    const data = await res.json();
    if (data.error) {
      toast(data.error);
      setStatus("识别失败");
    } else {
      const input = document.getElementById("inputText");
      input.value = data.text;
      setStatus(`识别完成 · ${data.chars} 字符`);
    }
  } catch (e) {
    toast("OCR 请求失败");
    setStatus("识别失败");
  } finally {
    btn.disabled = false;
  }
}

// ── Translate image (multimodal: vision API; non-multimodal: OCR + translate) ──
async function doTranslateImage(file) {
  const apiKey = document.getElementById("apiKey").value.trim();
  if (!apiKey) { toast("请先输入 API Key"); return; }

  setStatus("识别+翻译中...", true);
  const btn = document.getElementById("translateBtn");
  btn.disabled = true;

  try {
    const form = new FormData();
    form.append("image", file);
    form.append("api_key", apiKey);
    form.append("provider", document.getElementById("provider").value);
    form.append("model", document.getElementById("model").value);
    form.append("direction", document.querySelector('input[name="direction"]:checked').value);

    const res = await fetch("/api/translate-image", { method: "POST", body: form });
    const data = await res.json();

    if (data.error) {
      toast(data.error);
      setStatus("处理失败");
    } else {
      document.getElementById("outputText").value = data.result;
      if (data.multimodal) {
        setStatus(`多模态翻译完成 · ${data.result.length} 字符`);
      } else {
        setStatus(`OCR+翻译完成 · ${data.result.length} 字符`);
      }
    }
  } catch (e) {
    toast("请求失败");
    setStatus("处理失败");
  } finally {
    btn.disabled = false;
  }
}

// ── OCR via clipboard paste ──
document.addEventListener("paste", async (e) => {
  if (e.target && e.target.id === "apiKey") return;

  const items = e.clipboardData?.items;
  if (!items) return;

  let imageItem = null;
  for (const item of items) {
    if (item.type.startsWith("image/")) { imageItem = item; break; }
  }
  if (!imageItem) return;

  e.preventDefault();
  const file = imageItem.getAsFile();
  if (!file) return;

  // 判断当前选中的模型是否多模态
  const providerKey = document.getElementById("provider").value;
  const modelId = document.getElementById("model").value;
  const provider = providers[providerKey];
  const model = provider && provider.models.find(m => m.id === modelId);
  if (model && model.multimodal) {
    // 多模态模型 → 直接调用大模型识别+翻译
    await doTranslateImage(file);
  } else {
    // 非多模态模型 → 需要 easyocr 回退
    if (!ocrAvailable) {
      toast("当前模型不支持图片识别，请切换至 Kimi 或安装 easyocr");
      return;
    }
    await doOcr(file);
  }
});

// ── Copy ──
document.getElementById("copyBtn").addEventListener("click", async () => {
  const text = document.getElementById("outputText").value;
  if (!text) { toast("没有可复制的内容"); return; }
  try {
    await navigator.clipboard.writeText(text);
    toast("已复制到剪贴板");
  } catch {
    toast("复制失败");
  }
});

// ── Clear ──
document.getElementById("clearBtn").addEventListener("click", () => {
  document.getElementById("inputText").value = "";
  document.getElementById("outputText").value = "";
  setStatus("已清空");
  setTimeout(() => setStatus("就绪"), 1200);
});

// ── Keyboard shortcuts ──
document.addEventListener("keydown", (e) => {
  if (e.ctrlKey && e.key === "Enter") {
    e.preventDefault();
    translate();
  }
});

// ── Card mouse tracking for glow ──
document.querySelectorAll('.card').forEach(card => {
  card.addEventListener('mousemove', e => {
    const rect = card.getBoundingClientRect();
    const x = ((e.clientX - rect.left) / rect.width) * 100;
    const y = ((e.clientY - rect.top) / rect.height) * 100;
    card.style.setProperty('--mx', x + '%');
    card.style.setProperty('--my', y + '%');
  });
});

// ── Init ──
loadConfig();
