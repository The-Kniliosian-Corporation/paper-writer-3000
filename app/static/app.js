const notesEditor = document.getElementById("notes-editor");
const saveBtn = document.getElementById("save-btn");
const saveStatus = document.getElementById("save-status");
const modelSelect = document.getElementById("model-select");
const generateBtn = document.getElementById("generate-btn");
const compileBtn = document.getElementById("compile-btn");
const generateStatus = document.getElementById("generate-status");
const pdfFrame = document.getElementById("pdf-frame");
const texFileSelect = document.getElementById("tex-file-select");
const texEditor = document.getElementById("tex-editor");
const texSaveBtn = document.getElementById("tex-save-btn");
const texSaveStatus = document.getElementById("tex-save-status");
const chatLog = document.getElementById("chat-log");
const chatForm = document.getElementById("chat-form");
const chatInput = document.getElementById("chat-input");
const historyList = document.getElementById("history-list");
const historyRefreshBtn = document.getElementById("history-refresh-btn");
const referencesMenuBtn = document.getElementById("references-menu-btn");
const referencesModal = document.getElementById("references-modal");
const referencesCloseBtn = document.getElementById("references-close-btn");
const referencesAddBtn = document.getElementById("references-add-btn");
const referencesSaveBtn = document.getElementById("references-save-btn");
const referencesStatus = document.getElementById("references-status");
const referencesTbody = document.getElementById("references-tbody");
const figuresMenuBtn = document.getElementById("figures-menu-btn");
const figuresModal = document.getElementById("figures-modal");
const figuresCloseBtn = document.getElementById("figures-close-btn");
const figuresGrid = document.getElementById("figures-grid");
const figuresStatus = document.getElementById("figures-status");
const figuresUploadInput = document.getElementById("figures-upload-input");
const templateMenuBtn = document.getElementById("template-menu-btn");
const templateModal = document.getElementById("template-modal");
const templateCloseBtn = document.getElementById("template-close-btn");
const templateMainFile = document.getElementById("template-main-file");
const templateSectionsList = document.getElementById("template-sections-list");
const templateStatus = document.getElementById("template-status");
const templateUploadInput = document.getElementById("template-upload-input");
const projectsMenuBtn = document.getElementById("projects-menu-btn");
const projectsModal = document.getElementById("projects-modal");
const projectsCloseBtn = document.getElementById("projects-close-btn");
const projectsList = document.getElementById("projects-list");
const projectsEmptyHint = document.getElementById("projects-empty-hint");
const projectsStatus = document.getElementById("projects-status");
const newProjectForm = document.getElementById("new-project-form");
const newProjectName = document.getElementById("new-project-name");
const projectScopedEls = document.querySelectorAll(".project-scoped");

let chatHistory = [];
let texData = {};
let currentProject = new URLSearchParams(location.search).get("project");

async function api(path, options) {
  if (path.startsWith("/api/") && !path.startsWith("/api/projects")) {
    const sep = path.includes("?") ? "&" : "?";
    path = `${path}${sep}project=${encodeURIComponent(currentProject)}`;
  }
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
  texData = await api("/api/tex");
  const previouslySelected = texFileSelect.value;
  texFileSelect.innerHTML = "";
  for (const name of Object.keys(texData)) {
    const opt = document.createElement("option");
    opt.value = name;
    opt.textContent = `${name}.tex`;
    texFileSelect.appendChild(opt);
  }
  if (previouslySelected && previouslySelected in texData) {
    texFileSelect.value = previouslySelected;
  }
  texEditor.value = texData[texFileSelect.value] ?? "";
}

texFileSelect.onchange = () => {
  texEditor.value = texData[texFileSelect.value] ?? "";
  texSaveStatus.textContent = "";
};

texSaveBtn.onclick = async () => {
  const name = texFileSelect.value;
  if (!name) return;
  texSaveBtn.disabled = true;
  texSaveStatus.textContent = "Saving...";
  try {
    const result = await api(`/api/tex/${encodeURIComponent(name)}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ content: texEditor.value }),
    });
    texData[name] = texEditor.value;
    texSaveStatus.textContent = result.committed ? "Saved." : "No changes.";
    await loadHistory();
  } catch (err) {
    texSaveStatus.textContent = `Error: ${err.message}`;
  } finally {
    texSaveBtn.disabled = false;
  }
};

compileBtn.onclick = async () => {
  compileBtn.disabled = true;
  generateStatus.textContent = "Compiling PDF...";
  try {
    const result = await api("/api/compile", { method: "POST" });
    if (result.ok) {
      generateStatus.textContent = "PDF compiled.";
      reloadPdf();
    } else {
      generateStatus.textContent = "PDF compile failed. See console.";
      console.error(result.log);
    }
  } catch (err) {
    generateStatus.textContent = `Error: ${err.message}`;
  } finally {
    compileBtn.disabled = false;
  }
};

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
    revertBtn.textContent = "Revert draft here";
    revertBtn.onclick = () => revertTo(entry.sha);
    li.appendChild(meta);
    li.appendChild(revertBtn);
    historyList.appendChild(li);
  }
}

async function revertTo(sha) {
  if (!confirm(`Revert the rough draft and generated paper to commit ${sha.slice(0, 7)}? This creates a new commit; nothing is destroyed.`)) return;
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

function escapeHtml(str) {
  return str.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

function inlineMarkdown(text) {
  let out = escapeHtml(text);
  out = out.replace(/\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g, '<a href="$2" target="_blank" rel="noopener noreferrer">$1</a>');
  out = out.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
  out = out.replace(/(^|[^*])\*([^*]+)\*(?!\*)/g, "$1<em>$2</em>");
  out = out.replace(/`([^`]+)`/g, "<code>$1</code>");
  return out;
}

// Small, deliberately non-exhaustive markdown renderer: just enough for the
// headers/bold/links/lists that model responses (e.g. citation lists) use.
function renderMarkdown(text) {
  const lines = text.split("\n");
  let html = "";
  let inList = false;
  const closeList = () => {
    if (inList) {
      html += "</ul>";
      inList = false;
    }
  };

  for (const rawLine of lines) {
    const line = rawLine.trimEnd();
    if (/^\s*-{3,}\s*$/.test(line)) {
      closeList();
      html += "<hr>";
      continue;
    }
    const headerMatch = line.match(/^(#{1,4})\s+(.*)$/);
    if (headerMatch) {
      closeList();
      const level = Math.min(headerMatch[1].length + 2, 6);
      html += `<h${level}>${inlineMarkdown(headerMatch[2])}</h${level}>`;
      continue;
    }
    const listMatch = line.match(/^\s*[-*]\s+(.*)$/);
    if (listMatch) {
      if (!inList) {
        html += "<ul>";
        inList = true;
      }
      html += `<li>${inlineMarkdown(listMatch[1])}</li>`;
      continue;
    }
    closeList();
    if (line.trim() === "") continue;
    html += `<p>${inlineMarkdown(line)}</p>`;
  }
  closeList();
  return html;
}

function appendChatMessage(role, text) {
  const div = document.createElement("div");
  div.className = `chat-msg ${role}`;
  if (role === "assistant") {
    div.innerHTML = renderMarkdown(text);
  } else {
    div.textContent = text;
  }
  chatLog.appendChild(div);
  chatLog.scrollTop = chatLog.scrollHeight;
}

function appendProposalCard(proposal) {
  const card = document.createElement("div");
  card.className = "proposal-card";

  const header = document.createElement("div");
  header.className = "proposal-header";
  header.textContent = `Proposed edit: ${proposal.target}`;
  card.appendChild(header);

  if (proposal.summary) {
    const summary = document.createElement("div");
    summary.className = "proposal-summary";
    summary.textContent = proposal.summary;
    card.appendChild(summary);
  }

  const preview = document.createElement("textarea");
  preview.className = "proposal-preview";
  preview.readOnly = true;
  preview.value = proposal.content;
  card.appendChild(preview);

  const actions = document.createElement("div");
  actions.className = "proposal-actions";
  const applyBtn = document.createElement("button");
  applyBtn.textContent = "Apply";
  const discardBtn = document.createElement("button");
  discardBtn.textContent = "Discard";
  discardBtn.className = "discard-btn";
  actions.appendChild(applyBtn);
  actions.appendChild(discardBtn);
  card.appendChild(actions);

  discardBtn.onclick = () => card.remove();

  applyBtn.onclick = async () => {
    applyBtn.disabled = true;
    discardBtn.disabled = true;
    try {
      if (proposal.target === "paper.md") {
        await api("/api/save", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ content: proposal.content }),
        });
        notesEditor.value = proposal.content;
      } else {
        await api(`/api/tex/${encodeURIComponent(proposal.target)}`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ content: proposal.content }),
        });
        texData[proposal.target] = proposal.content;
        if (texFileSelect.value === proposal.target) {
          texEditor.value = proposal.content;
        }
      }
      await loadHistory();
      header.textContent += " -- applied";
      actions.remove();
    } catch (err) {
      applyBtn.disabled = false;
      discardBtn.disabled = false;
      header.textContent += ` -- error: ${err.message}`;
    }
  };

  chatLog.appendChild(card);
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
    for (const proposal of result.proposals || []) {
      appendProposalCard(proposal);
    }
  } catch (err) {
    appendChatMessage("assistant", `Error: ${err.message}`);
  }
};

historyRefreshBtn.onclick = loadHistory;

function addReferenceRow(url = "", note = "") {
  const tr = document.createElement("tr");

  const urlTd = document.createElement("td");
  const urlInput = document.createElement("input");
  urlInput.type = "text";
  urlInput.className = "ref-url";
  urlInput.placeholder = "https://...";
  urlInput.value = url;
  urlTd.appendChild(urlInput);

  const noteTd = document.createElement("td");
  const noteInput = document.createElement("input");
  noteInput.type = "text";
  noteInput.className = "ref-note";
  noteInput.placeholder = "what to use it for";
  noteInput.value = note;
  noteTd.appendChild(noteInput);

  const delTd = document.createElement("td");
  const delBtn = document.createElement("button");
  delBtn.textContent = "Delete";
  delBtn.onclick = () => tr.remove();
  delTd.appendChild(delBtn);

  tr.appendChild(urlTd);
  tr.appendChild(noteTd);
  tr.appendChild(delTd);
  referencesTbody.appendChild(tr);
}

async function loadReferences() {
  referencesStatus.textContent = "";
  const entries = await api("/api/references");
  referencesTbody.innerHTML = "";
  for (const entry of entries) {
    addReferenceRow(entry.url, entry.note);
  }
}

referencesMenuBtn.onclick = async () => {
  referencesModal.classList.remove("hidden");
  try {
    await loadReferences();
  } catch (err) {
    referencesStatus.textContent = `Error: ${err.message}`;
  }
};

function closeReferencesModal() {
  referencesModal.classList.add("hidden");
}

referencesCloseBtn.onclick = closeReferencesModal;

referencesModal.addEventListener("mousedown", (e) => {
  if (e.target === referencesModal) closeReferencesModal();
});

referencesAddBtn.onclick = () => addReferenceRow();

async function loadFigures() {
  figuresStatus.textContent = "";
  const filenames = await api("/api/figures");
  figuresGrid.innerHTML = "";
  for (const filename of filenames) {
    const fig = document.createElement("figure");
    fig.className = "figure-thumb";
    fig.draggable = true;

    const img = document.createElement("img");
    img.src = `/api/figures/${encodeURIComponent(filename)}`;
    img.alt = filename;
    img.draggable = false;

    const caption = document.createElement("figcaption");
    caption.textContent = filename;

    fig.appendChild(img);
    fig.appendChild(caption);

    fig.addEventListener("dragstart", (e) => {
      e.dataTransfer.setData("text/plain", `[figure: ${filename}]`);
      e.dataTransfer.effectAllowed = "copy";
    });

    figuresGrid.appendChild(fig);
  }
}

figuresMenuBtn.onclick = async () => {
  figuresModal.classList.remove("hidden");
  try {
    await loadFigures();
  } catch (err) {
    figuresStatus.textContent = `Error: ${err.message}`;
  }
};

function closeFiguresModal() {
  figuresModal.classList.add("hidden");
}

figuresCloseBtn.onclick = closeFiguresModal;

document.addEventListener("mousedown", (e) => {
  if (!figuresModal.classList.contains("hidden") && !figuresModal.contains(e.target) && e.target !== figuresMenuBtn) {
    closeFiguresModal();
  }
});

document.addEventListener("keydown", (e) => {
  if (e.key !== "Escape") return;
  if (!figuresModal.classList.contains("hidden")) closeFiguresModal();
  if (!referencesModal.classList.contains("hidden")) closeReferencesModal();
  if (!templateModal.classList.contains("hidden")) closeTemplateModal();
  if (!projectsModal.classList.contains("hidden")) closeProjectsModal();
});

figuresUploadInput.onchange = async () => {
  const file = figuresUploadInput.files[0];
  if (!file) return;
  figuresStatus.textContent = "Uploading...";
  try {
    const formData = new FormData();
    formData.append("file", file);
    await api("/api/figures", { method: "POST", body: formData });
    figuresStatus.textContent = "Uploaded.";
    await loadFigures();
  } catch (err) {
    figuresStatus.textContent = `Error: ${err.message}`;
  } finally {
    figuresUploadInput.value = "";
  }
};

async function loadTemplate() {
  templateStatus.textContent = "";
  const data = await api("/api/template");
  templateMainFile.textContent = `${data.main_file}.tex`;
  templateSectionsList.innerHTML = "";
  for (const name of data.sections) {
    const li = document.createElement("li");
    li.textContent = `${name}.tex`;
    templateSectionsList.appendChild(li);
  }
}

templateMenuBtn.onclick = async () => {
  templateModal.classList.remove("hidden");
  try {
    await loadTemplate();
  } catch (err) {
    templateStatus.textContent = `Error: ${err.message}`;
  }
};

function closeTemplateModal() {
  templateModal.classList.add("hidden");
}

templateCloseBtn.onclick = closeTemplateModal;

templateModal.addEventListener("mousedown", (e) => {
  if (e.target === templateModal) closeTemplateModal();
});

templateUploadInput.onchange = async () => {
  const file = templateUploadInput.files[0];
  if (!file) return;
  if (
    !confirm(
      `Install "${file.name}" as the new manuscript template? This replaces the current template, ` +
        "including any generated content and figures. Nothing is destroyed -- it's committed to history first."
    )
  ) {
    templateUploadInput.value = "";
    return;
  }

  templateStatus.textContent = "Uploading...";
  try {
    const formData = new FormData();
    formData.append("file", file);
    const result = await api("/api/template", { method: "POST", body: formData });
    templateStatus.textContent = `Installed: ${result.main_file}.tex, ${result.sections.length} section(s).`;
    await Promise.all([loadTemplate(), loadNotes(), loadTex(), loadHistory()]);
  } catch (err) {
    templateStatus.textContent = `Error: ${err.message}`;
  } finally {
    templateUploadInput.value = "";
  }
};

notesEditor.addEventListener("dragover", (e) => {
  e.preventDefault();
  e.dataTransfer.dropEffect = "copy";
});

notesEditor.addEventListener("drop", (e) => {
  e.preventDefault();
  const marker = e.dataTransfer.getData("text/plain");
  if (!marker) return;
  const { selectionStart, selectionEnd, value } = notesEditor;
  notesEditor.value = value.slice(0, selectionStart) + marker + value.slice(selectionEnd);
  const caret = selectionStart + marker.length;
  notesEditor.focus();
  notesEditor.setSelectionRange(caret, caret);
});

referencesSaveBtn.onclick = async () => {
  const entries = [...referencesTbody.querySelectorAll("tr")]
    .map((tr) => ({
      url: tr.querySelector(".ref-url").value.trim(),
      note: tr.querySelector(".ref-note").value.trim(),
    }))
    .filter((entry) => entry.url || entry.note);

  referencesSaveBtn.disabled = true;
  referencesStatus.textContent = "Saving...";
  try {
    const result = await api("/api/references", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ entries }),
    });
    referencesStatus.textContent = result.committed ? "Saved." : "No changes.";
    await loadHistory();
  } catch (err) {
    referencesStatus.textContent = `Error: ${err.message}`;
  } finally {
    referencesSaveBtn.disabled = false;
  }
};

function makeColResizer(gutter, leftPanel, rightPanel) {
  const minWidth = 150;
  gutter.addEventListener("mousedown", (e) => {
    e.preventDefault();
    const startX = e.clientX;
    const startLeft = leftPanel.getBoundingClientRect().width;
    const startRight = rightPanel.getBoundingClientRect().width;
    gutter.classList.add("dragging");
    document.body.classList.add("resizing");
    document.body.style.cursor = "col-resize";

    function onMove(ev) {
      const dx = ev.clientX - startX;
      const newLeft = startLeft + dx;
      const newRight = startRight - dx;
      if (newLeft < minWidth || newRight < minWidth) return;
      leftPanel.style.flex = `0 0 ${newLeft}px`;
      rightPanel.style.flex = `0 0 ${newRight}px`;
    }
    function onUp() {
      gutter.classList.remove("dragging");
      document.body.classList.remove("resizing");
      document.body.style.cursor = "";
      document.removeEventListener("mousemove", onMove);
      document.removeEventListener("mouseup", onUp);
    }
    document.addEventListener("mousemove", onMove);
    document.addEventListener("mouseup", onUp);
  });
}

function makeRowResizer(gutter, panelBelow) {
  const minHeight = 60;
  gutter.addEventListener("mousedown", (e) => {
    e.preventDefault();
    const startY = e.clientY;
    const startHeight = panelBelow.getBoundingClientRect().height;
    gutter.classList.add("dragging");
    document.body.classList.add("resizing");
    document.body.style.cursor = "row-resize";

    function onMove(ev) {
      const dy = ev.clientY - startY;
      const newHeight = startHeight - dy;
      if (newHeight < minHeight) return;
      panelBelow.style.flex = `0 0 ${newHeight}px`;
    }
    function onUp() {
      gutter.classList.remove("dragging");
      document.body.classList.remove("resizing");
      document.body.style.cursor = "";
      document.removeEventListener("mousemove", onMove);
      document.removeEventListener("mouseup", onUp);
    }
    document.addEventListener("mousemove", onMove);
    document.addEventListener("mouseup", onUp);
  });
}

makeColResizer(
  document.querySelector('[data-resize="col-0"]'),
  document.getElementById("panel-notes"),
  document.getElementById("panel-output")
);
makeColResizer(
  document.querySelector('[data-resize="col-1"]'),
  document.getElementById("panel-output"),
  document.getElementById("panel-chat")
);
makeRowResizer(document.querySelector('[data-resize="row-0"]'), document.getElementById("panel-history"));

function setProjectScopedVisible(visible) {
  projectScopedEls.forEach((el) => el.classList.toggle("hidden", !visible));
}

function openProject(slug) {
  location.href = `${location.pathname}?project=${encodeURIComponent(slug)}`;
}

function renderProjectRow(project) {
  const li = document.createElement("li");

  const left = document.createElement("span");
  const nameSpan = document.createElement("span");
  nameSpan.className = "project-name";
  nameSpan.textContent = project.name;
  const metaSpan = document.createElement("span");
  metaSpan.className = "project-meta";
  metaSpan.textContent = project.created ? new Date(project.created).toLocaleString() : "";
  left.appendChild(nameSpan);
  left.appendChild(metaSpan);

  const actions = document.createElement("span");
  actions.className = "project-actions";

  const openBtn = document.createElement("button");
  openBtn.textContent = "Open";
  openBtn.onclick = () => openProject(project.slug);

  const renameBtn = document.createElement("button");
  renameBtn.textContent = "Rename";
  renameBtn.onclick = async () => {
    const newName = prompt("Rename project:", project.name);
    if (!newName || !newName.trim() || newName.trim() === project.name) return;
    try {
      await api(`/api/projects/${encodeURIComponent(project.slug)}/rename`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: newName.trim() }),
      });
      await loadProjectsList();
    } catch (err) {
      projectsStatus.textContent = `Error: ${err.message}`;
    }
  };

  const archiveBtn = document.createElement("button");
  archiveBtn.textContent = "Archive";
  archiveBtn.className = "archive-btn";
  archiveBtn.onclick = async () => {
    if (!confirm(`Archive "${project.name}"? This hides it from the list -- nothing on disk is deleted.`)) return;
    try {
      await api(`/api/projects/${encodeURIComponent(project.slug)}/archive`, { method: "POST" });
      await loadProjectsList();
    } catch (err) {
      projectsStatus.textContent = `Error: ${err.message}`;
    }
  };

  actions.appendChild(openBtn);
  actions.appendChild(renameBtn);
  actions.appendChild(archiveBtn);
  li.appendChild(left);
  li.appendChild(actions);
  return li;
}

async function loadProjectsList() {
  const list = await api("/api/projects");
  projectsList.innerHTML = "";
  projectsEmptyHint.classList.toggle("hidden", list.length > 0);
  for (const project of list) {
    projectsList.appendChild(renderProjectRow(project));
  }
  return list;
}

function openProjectsModal(dismissable) {
  projectsModal.classList.remove("hidden");
  projectsCloseBtn.classList.toggle("hidden", !dismissable);
  projectsStatus.textContent = "";
  loadProjectsList().catch((err) => {
    projectsStatus.textContent = `Error: ${err.message}`;
  });
}

function closeProjectsModal() {
  if (!currentProject) return; // landing mode -- nothing to fall back to until one is picked
  projectsModal.classList.add("hidden");
}

projectsMenuBtn.onclick = () => openProjectsModal(!!currentProject);
projectsCloseBtn.onclick = closeProjectsModal;

projectsModal.addEventListener("mousedown", (e) => {
  if (e.target === projectsModal) closeProjectsModal();
});

newProjectForm.onsubmit = async (e) => {
  e.preventDefault();
  const name = newProjectName.value.trim();
  if (!name) return;
  projectsStatus.textContent = "Creating...";
  try {
    const result = await api("/api/projects", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name }),
    });
    newProjectName.value = "";
    openProject(result.slug);
  } catch (err) {
    projectsStatus.textContent = `Error: ${err.message}`;
  }
};

(async function init() {
  if (!currentProject) {
    openProjectsModal(false);
    return;
  }
  try {
    await Promise.all([loadNotes(), loadModels(), loadTex(), loadHistory()]);
    setProjectScopedVisible(true);
    reloadPdf();
  } catch (err) {
    currentProject = null;
    openProjectsModal(false);
  }
})();
