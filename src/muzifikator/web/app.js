"use strict";

const POLL_INTERVAL_MS = 1000;
const STAGE_WIDTH = { tts: "33%", music: "66%", mix: "100%" };
const STAGE_LABEL = { tts: "Озвучка", music: "Музыка", mix: "Микс" };

const state = {
  busy: false,
  timer: null,
  currentId: null,
  lastParams: null,
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

function normalizeFolder(value) {
  return value
    .trim()
    .replace(/\\/g, "/")
    .replace(/^\/+/, "")
    .replace(/\/+$/, "");
}

function setBusy(busy) {
  state.busy = busy;
  el("submit").disabled = busy || !el("text").value.trim();
  el("regenerate").disabled = busy || state.lastParams === null;
  el("submit").textContent = busy ? "Генерация…" : "Сгенерировать";
}

function showStatus(text, stage) {
  const section = el("status");
  section.hidden = false;
  el("status-text").textContent = text;
  el("status-bar").style.width = STAGE_WIDTH[stage] || "5%";
}

function hideStatus() {
  el("status").hidden = true;
  el("status-bar").style.width = "0";
}

function renderFiles(files) {
  const list = el("result-files");
  list.replaceChildren();
  for (const [format, path] of Object.entries(files)) {
    const item = document.createElement("li");
    item.textContent = format + ": " + path;
    list.append(item);
  }
  el("result").hidden = Object.keys(files).length === 0;
}

function renderListing(listing) {
  const list = el("files-list");
  list.replaceChildren();
  for (const entry of listing.entries) {
    const item = document.createElement("li");
    item.textContent = entry.kind === "dir" ? entry.name + "/" : entry.name;
    list.append(item);
  }
  const shown = listing.path ? "/" + listing.path : "/";
  el("files-path").textContent = listing.root + shown;

  const datalist = el("folders");
  datalist.replaceChildren();
  for (const entry of listing.entries) {
    if (entry.kind !== "dir") {
      continue;
    }
    const option = document.createElement("option");
    option.value = entry.path;
    datalist.append(option);
  }
}

async function refreshFiles() {
  const folder = normalizeFolder(el("folder").value);
  try {
    const listing = await api("/api/files?path=" + encodeURIComponent(folder));
    renderListing(listing);
  } catch (error) {
    el("files-list").replaceChildren();
    if (error.status === 404) {
      el("files-path").textContent = folder ? "папки пока нет: /" + folder : "";
      return;
    }
    el("files-path").textContent = "";
    showMessage(error.message, "error");
  }
}

async function loadSettings() {
  const settings = await api("/api/settings");
  el("tags").value = settings.music_tags || "";
  return settings;
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

function collectParams() {
  return {
    text: el("text").value,
    voice: el("voice").value,
    music_tags: el("tags").value.trim() || null,
    folder: normalizeFolder(el("folder").value) || null,
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
      renderFiles(body.files);
      setBusy(false);
      state.currentId = null;
      await refreshFiles();
      return;
    }
    if (body.status === "failed") {
      hideStatus();
      renderFiles({});
      showMessage(body.error || "генерация не удалась", "error");
      setBusy(false);
      state.currentId = null;
      await refreshFiles();
      return;
    }
    const stage = body.stage || "";
    showStatus(STAGE_LABEL[stage] || "В работе", stage);
    await new Promise((resolve) => setTimeout(resolve, POLL_INTERVAL_MS));
  }
}

async function submitGeneration(params, { regenerate }) {
  if (state.busy) {
    return;
  }
  if (!params.text.trim()) {
    showMessage("Введите текст", "error");
    return;
  }
  setBusy(true);
  showMessage("");
  renderFiles({});
  showStatus("Отправка", "");
  try {
    const payload = {
      text: params.text,
      voice: params.voice,
      music_tags: params.music_tags,
      folder: params.folder,
    };
    const created = await api("/api/generations", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(payload),
    });
    state.lastParams = params;
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
    submitGeneration(collectParams(), { regenerate: null });
  });
  el("regenerate").addEventListener("click", () => {
    if (state.lastParams) {
      submitGeneration(state.lastParams, { regenerate: state.lastParams });
    }
  });
  el("save-settings").addEventListener("click", saveSettings);
  el("folder").addEventListener("change", refreshFiles);

  try {
    const settings = await loadSettings();
    await loadVoices(settings);
  } catch (error) {
    showMessage("Не удалось загрузить настройки: " + error.message, "error");
  }
  setBusy(false);
  await refreshFiles();
}

init();
