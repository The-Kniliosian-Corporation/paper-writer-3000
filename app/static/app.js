const notesEditor = document.getElementById("notes-editor");
const saveBtn = document.getElementById("save-btn");
const saveStatus = document.getElementById("save-status");
const modelSelect = document.getElementById("model-select");
const generateBtn = document.getElementById("generate-btn");
const generateStatus = document.getElementById("generate-status");
const pdfFrame = document.getElementById("pdf-frame");
const texView = document.getElementById("tex-view");
const chatLog = document.getElementById("chat-log");
const chatForm = document.getElementById("chat-form");
const chatInput = document.getElementById("chat-input");
const historyList = document.getElementById("history-list");
const historyRefreshBtn = document.getElementById("history-refresh-btn");

let chatHistory = [];

async function api(path, options) {
  const res = await fetch(path, options);
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || `${res.status} ${res.statusText}`);
  }
  return res.json();
}

async function loadNotes() {
  const data = await api("/api/notes");
  notesEditor.value = data.content;
}

async function loadModels() {
  const data = await api("/api/models");
  modelSelect.innerHTML = "";
  for (const m of data.models) {
    const opt = document.createElement("option");
    opt.value = m;
    opt.textContent = m;
    if (m === data.default) opt.selected = true;
    modelSelect.appendChild(opt);
  }
}

async function loadTex() {
  const data = await api("/api/tex");
  texView.textContent = Object.entries(data)
    .map(([name, content]) => `% ===== ${name}.tex =====\n${content}`)
    .join("\n\n");
}

function reloadPdf() {
  pdfFrame.src = `/api/pdf?t=${Date.now()}`;
}

async function loadHistory() {
  const entries = await api("/api/history");
  historyList.innerHTML = "";
  for (const entry of entries) {
    const li = document.createElement("li");
    const meta = document.createElement("span");
    meta.className = "meta";
    meta.textContent = `${entry.sha.slice(0, 7)} · ${entry.message} · ${new Date(entry.date).toLocaleString()}`;
    const revertBtn = document.createElement("button");
    revertBtn.textContent = "Revert notes here";
    revertBtn.onclick = () => revertTo(entry.sha);
    li.appendChild(meta);
    li.appendChild(revertBtn);
    historyList.appendChild(li);
  }
}

async function revertTo(sha) {
  if (!confirm(`Revert paper.md to commit ${sha.slice(0, 7)}? This creates a new commit; nothing is destroyed.`)) return;
  await api("/api/revert", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ sha }),
  });
  await loadNotes();
  await loadHistory();
}

saveBtn.onclick = async () => {
  saveBtn.disabled = true;
  saveStatus.textContent = "Saving...";
  try {
    const result = await api("/api/save", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ content: notesEditor.value }),
    });
    saveStatus.textContent = result.committed ? "Saved." : "No changes.";
    await loadHistory();
  } catch (err) {
    saveStatus.textContent = `Error: ${err.message}`;
  } finally {
    saveBtn.disabled = false;
  }
};

generateBtn.onclick = async () => {
  generateBtn.disabled = true;
  generateStatus.textContent = "Generating (this can take a minute)...";
  try {
    const result = await api("/api/generate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ model: modelSelect.value }),
    });
    if (result.compiled) {
      generateStatus.textContent = `Done (${result.model}).`;
      reloadPdf();
    } else {
      generateStatus.textContent = `LaTeX written, but PDF compile failed. See console.`;
      console.error(result.compile_log);
    }
    await loadTex();
    await loadHistory();
  } catch (err) {
    generateStatus.textContent = `Error: ${err.message}`;
  } finally {
    generateBtn.disabled = false;
  }
};

document.querySelectorAll(".tab-btn").forEach((btn) => {
  btn.onclick = () => {
    document.querySelectorAll(".tab-btn").forEach((b) => b.classList.remove("active"));
    document.querySelectorAll(".tab-content").forEach((c) => c.classList.remove("active"));
    btn.classList.add("active");
    document.getElementById(`tab-${btn.dataset.tab}`).classList.add("active");
  };
});

function appendChatMessage(role, text) {
  const div = document.createElement("div");
  div.className = `chat-msg ${role}`;
  div.textContent = text;
  chatLog.appendChild(div);
  chatLog.scrollTop = chatLog.scrollHeight;
}

chatForm.onsubmit = async (e) => {
  e.preventDefault();
  const message = chatInput.value.trim();
  if (!message) return;
  chatInput.value = "";
  appendChatMessage("user", message);
  try {
    const result = await api("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message, history: chatHistory }),
    });
    chatHistory.push({ role: "user", content: message });
    chatHistory.push({ role: "assistant", content: result.reply });
    appendChatMessage("assistant", result.reply);
  } catch (err) {
    appendChatMessage("assistant", `Error: ${err.message}`);
  }
};

historyRefreshBtn.onclick = loadHistory;

(async function init() {
  await Promise.all([loadNotes(), loadModels(), loadTex(), loadHistory()]);
  reloadPdf();
})();
