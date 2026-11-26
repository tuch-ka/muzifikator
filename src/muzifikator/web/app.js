"use strict";

const POLL_INTERVAL_MS = 1000;
const PAGE_SIZE = 50;
const STAGE_WIDTH = { tts: "33%", music: "66%", mix: "100%" };
const STAGE_LABEL = { tts: "Озвучка", music: "Музыка", mix: "Микс" };
const STAGE_LABEL_SONG = { tts: "Вокал", music: "Подложка", mix: "Сведение" };
const AUDIO_EXTENSIONS = [".mp3", ".m4a", ".wav", ".aac"];

const state = {
  busy: false,
  currentId: null,
  lastParams: null,
  storagePath: "",
  browserPath: "",
  browserParent: null,
  currentMode: "song",
  filesOffset: 0,
};

const el = (id) => document.getElementById(id);

async function api(path, options) {
  const response = await fetch(path, options);
  let body = null;
  try {
    body = await response.json();
  } catch (error) {
    body = null;
  }
  if (!response.ok) {
    const detail = body ? body.detail : null;
    let message = "ошибка " + response.status;
    if (typeof detail === "string") {
      message = detail;
    } else if (detail && typeof detail.message === "string") {
      message = detail.message;
    }
    const failure = new Error(message);
    failure.status = response.status;
    failure.body = body;
    throw failure;
  }
  return body;
}

function showMessage(text, kind) {
  const node = el("message");
  node.textContent = text || "";
  if (kind) {
    node.dataset.kind = kind;
  } else {
    delete node.dataset.kind;
  }
}

function setBusy(busy) {
  state.busy = busy;
  el("submit").disabled = busy || !el("text").value.trim();
  el("regenerate").disabled = busy || state.lastParams === null;
  el("submit").textContent = busy ? "Генерация…" : "Сгенерировать";
}

function showStatus(text, stage) {
  el("status").hidden = false;
  el("status-text").textContent = text;
  el("status-bar").style.width = STAGE_WIDTH[stage] || "5%";
}

function hideStatus() {
  el("status").hidden = true;
  el("status-bar").style.width = "0";
}

function renderResultFiles(files) {
  const list = el("result-files");
  list.replaceChildren();
  for (const [format, path] of Object.entries(files)) {
    const item = document.createElement("li");
    item.textContent = format + ": " + path;
    list.append(item);
  }
  el("result").hidden = Object.keys(files).length === 0;
}

function isAudio(name) {
  const lower = name.toLowerCase();
  return AUDIO_EXTENSIONS.some((extension) => lower.endsWith(extension));
}

function actionButton(label, handler, disabled) {
  const button = document.createElement("button");
  button.type = "button";
  button.className = "small secondary";
  button.textContent = label;
  button.disabled = Boolean(disabled);
  button.addEventListener("click", handler);
  return button;
}

function fileItem(entry) {
  const item = document.createElement("li");
  if (!entry.exists) {
    item.classList.add("missing");
  }
  const line = document.createElement("div");
  line.className = "line";

  const title = document.createElement("span");
  title.className = "title";
  title.textContent = entry.name + (entry.exists ? "" : " (нет на диске)");
  line.append(title);

  if (isAudio(entry.name)) {
    line.append(
      actionButton("Проиграть", () => playFile(entry), !entry.exists)
    );
  }
  line.append(
    actionButton("Показать", () => revealFile(entry), !entry.exists)
  );
  line.append(actionButton("Удалить", () => deleteGeneration(entry)));

  const meta = document.createElement("div");
  meta.className = "meta";
  const created = new Date(entry.created_at);
  const duration = entry.duration_seconds
    ? " · " + entry.duration_seconds.toFixed(1) + " с"
    : "";
  meta.textContent =
    entry.format +
    " · " +
    created.toLocaleString("ru-RU") +
    duration +
    (entry.size ? " · " + Math.round(entry.size / 1024) + " КБ" : "");
  item.append(line, meta);
  return item;
}

function appendFiles(entries) {
  const list = el("files-list");
  for (const entry of entries) {
    list.append(fileItem(entry));
  }
}

async function loadFiles({ reset }) {
  if (reset) {
    state.filesOffset = 0;
    el("files-list").replaceChildren();
  }
  const page = await api(
    "/api/files?limit=" + PAGE_SIZE + "&offset=" + state.filesOffset
  );
  appendFiles(page.files);
  state.filesOffset += page.files.length;
  el("files-more").hidden = !page.has_more;
}

function playFile(entry) {
  const player = el("player");
  player.src =
    "/api/generations/" +
    encodeURIComponent(entry.generation_id) +
    "/files/" +
    encodeURIComponent(entry.format) +
    "/media";
  player.hidden = false;
  player.play().catch(() => {
    showMessage("Браузер не смог воспроизвести файл", "error");
  });
}

async function revealFile(entry) {
  try {
    await api(
      "/api/generations/" +
        encodeURIComponent(entry.generation_id) +
        "/files/" +
        encodeURIComponent(entry.format) +
        "/reveal",
      { method: "POST" }
    );
  } catch (error) {
    showMessage("Не удалось открыть файл: " + error.message, "error");
  }
}

async function deleteGeneration(entry) {
  const approved = window.confirm(
    "Удалить «" + entry.name + "» и всю генерацию? Действие необратимо."
  );
  if (!approved) {
    return;
  }
  try {
    await api("/api/generations/" + encodeURIComponent(entry.generation_id), {
      method: "DELETE",
    });
    showMessage("Генерация удалена", "ok");
    el("player").hidden = true;
    el("player").removeAttribute("src");
    renderResultFiles({});
    await loadFiles({ reset: true });
  } catch (error) {
    showMessage("Не удалось удалить: " + error.message, "error");
  }
}

async function loadSettings() {
  const settings = await api("/api/settings");
  el("tags").value = settings.music_tags || "";
  state.storagePath = settings.output_dir || "";
  renderStorage();
  return settings;
}

function renderStorage() {
  el("storage-path").textContent = state.storagePath || "не задан";
}

async function loadVoices(settings) {
  const voices = await api("/api/voices");
  const select = el("voice");
  select.replaceChildren();
  for (const voice of voices) {
    const option = document.createElement("option");
    option.value = voice.name;
    option.textContent = voice.name + " (" + voice.locale + ")";
    select.append(option);
  }
  if (settings && settings.tts_voice) {
    select.value = settings.tts_voice;
  }
}

async function loadBrowse(path) {
  const query = path ? "?path=" + encodeURIComponent(path) : "";
  const listing = await api("/api/storage/browse" + query);
  state.browserPath = listing.path;
  el("browser-path").textContent = listing.path;
  el("browser-up").disabled = !listing.parent;
  const list = el("browser-list");
  list.replaceChildren();
  for (const entry of listing.entries) {
    const item = document.createElement("li");
    item.textContent = entry.name + "/";
    item.addEventListener("click", () => {
      loadBrowse(entry.path).catch((error) =>
        showMessage(error.message, "error")
      );
    });
    list.append(item);
  }
  state.browserParent = listing.parent;
}

async function saveStorage(path) {
  const patched = await api("/api/settings", {
    method: "PATCH",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ output_dir: path }),
  });
  state.storagePath = patched.output_dir;
  renderStorage();
  el("storage-browser").hidden = true;
  showMessage("Каталог хранения сохранён", "ok");
}

function syncMode() {
  el("voice").disabled = el("mode").value === "song";
}

function collectParams() {
  return {
    text: el("text").value,
    mode: el("mode").value,
    voice: el("voice").value,
    music_tags: el("tags").value.trim() || null,
  };
}

async function poll(generationId) {
  state.currentId = generationId;
  while (state.currentId === generationId) {
    let body;
    try {
      body = await api("/api/generations/" + encodeURIComponent(generationId));
    } catch (error) {
      showMessage(error.message, "error");
      setBusy(false);
      state.currentId = null;
      return;
    }
    if (body.status === "done") {
      showStatus("Готово", "mix");
      renderResultFiles(body.files);
      setBusy(false);
      state.currentId = null;
      await loadFiles({ reset: true });
      return;
    }
    if (body.status === "failed") {
      hideStatus();
      renderResultFiles({});
      showMessage(body.error || "генерация не удалась", "error");
      setBusy(false);
      state.currentId = null;
      await loadFiles({ reset: true });
      return;
    }
    const stage = body.stage || "";
    const labels = state.currentMode === "song" ? STAGE_LABEL_SONG : STAGE_LABEL;
    showStatus(labels[stage] || "В работе", stage);
    await new Promise((resolve) => setTimeout(resolve, POLL_INTERVAL_MS));
  }
}

async function submitGeneration(params) {
  if (state.busy) {
    return;
  }
  if (!params.text.trim()) {
    showMessage("Введите текст", "error");
    return;
  }
  setBusy(true);
  showMessage("");
  renderResultFiles({});
  showStatus("Отправка", "");
  try {
    const created = await api("/api/generations", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({
        text: params.text,
        mode: params.mode || "song",
        voice: params.voice,
        music_tags: params.music_tags,
      }),
    });
    state.lastParams = params;
    state.currentMode = params.mode || "song";
    showStatus("В работе", "");
    await poll(created.id);
  } catch (error) {
    if (error.status === 409) {
      const detail = error.body ? error.body.detail : null;
      const current = detail && detail.generation_id;
      showMessage("Уже идёт другая генерация, ждём её завершения", "error");
      if (current) {
        await poll(current);
        return;
      }
    }
    hideStatus();
    showMessage(error.message, "error");
    setBusy(false);
  }
}

async function saveSettings() {
  try {
    await api("/api/settings", {
      method: "PATCH",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({
        tts_voice: el("voice").value,
        music_tags: el("tags").value.trim(),
      }),
    });
    showMessage("Настройки сохранены", "ok");
  } catch (error) {
    showMessage("Не удалось сохранить настройки: " + error.message, "error");
  }
}

async function init() {
  el("text").addEventListener("input", () => setBusy(state.busy));
  el("generation-form").addEventListener("submit", (event) => {
    event.preventDefault();
    submitGeneration(collectParams());
  });
  el("regenerate").addEventListener("click", () => {
    if (state.lastParams) {
      submitGeneration(state.lastParams);
    }
  });
  el("save-settings").addEventListener("click", saveSettings);
  el("mode").addEventListener("change", syncMode);
  syncMode();

  el("storage-edit").addEventListener("click", () => {
    el("storage-browser").hidden = false;
    loadBrowse(state.storagePath || "").catch((error) =>
      showMessage(error.message, "error")
    );
  });
  el("browser-close").addEventListener("click", () => {
    el("storage-browser").hidden = true;
  });
  el("browser-up").addEventListener("click", () => {
    if (state.browserParent) {
      loadBrowse(state.browserParent).catch((error) =>
        showMessage(error.message, "error")
      );
    }
  });
  el("browser-use").addEventListener("click", () => {
    saveStorage(state.browserPath).catch((error) =>
      showMessage("Не удалось сохранить каталог: " + error.message, "error")
    );
  });
  el("browser-manual-use").addEventListener("click", () => {
    const typed = el("browser-manual").value.trim();
    saveStorage(typed).catch((error) =>
      showMessage("Не удалось сохранить каталог: " + error.message, "error")
    );
  });
  el("files-more").addEventListener("click", () => {
    loadFiles({ reset: false }).catch((error) =>
      showMessage(error.message, "error")
    );
  });

  try {
    const settings = await loadSettings();
    await loadVoices(settings);
  } catch (error) {
    showMessage("Не удалось загрузить настройки: " + error.message, "error");
  }
  setBusy(false);
  try {
    await loadFiles({ reset: true });
  } catch (error) {
    showMessage(error.message, "error");
  }
}

init();
