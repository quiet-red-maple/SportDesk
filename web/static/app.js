/**
 * [INPUT]: 依赖 /api/channels /api/news /api/script /api/bgm /api/generate
 * [OUTPUT]: 工作台交互：榜单、口播稿、垫乐默认仅打字机、出片、下载
 * [POS]: web/static 的前端编排，被 index.html 加载
 * [PROTOCOL]: 变更时更新此头部，然后检查 CLAUDE.md
 */
const $ = (id) => document.getElementById(id);

async function readJson(res) {
  const text = await res.text();
  try {
    return JSON.parse(text);
  } catch (err) {
    throw new Error(res.ok ? "返回格式不对" : "热点源暂时连不上，请稍后刷新");
  }
}

let selected = null;
let timer = null;
let bgmId = localStorage.getItem("sport-desk-bgm") || "silent";
if (bgmId === "bright") bgmId = "silent";
let bgmTracks = [];
let channelId = localStorage.getItem("sport-desk-channel") || "sports";
let boards = [];

function isCustom(id) {
  return (id || "").indexOf("q:") === 0;
}

function boardName(id) {
  if (isCustom(id)) return id.slice(2) || "自定义";
  const hit = boards.find((b) => b.id === id);
  return hit ? hit.name : "体育";
}

function paintBoards() {
  const nav = $("boards");
  nav.innerHTML = "";
  boards.forEach((ch) => {
    const el = document.createElement("button");
    el.type = "button";
    el.className = "board" + (ch.id === channelId ? " on" : "");
    el.textContent = ch.name;
    el.onclick = () => switchChannel(ch.id);
    nav.appendChild(el);
  });
  if (isCustom(channelId)) {
    const el = document.createElement("button");
    el.type = "button";
    el.className = "board on";
    el.textContent = boardName(channelId);
    nav.appendChild(el);
  }
  $("board-kicker").textContent = "今日" + boardName(channelId) + (isCustom(channelId) ? "热搜" : "热榜");
  if ($("topic")) $("topic").value = isCustom(channelId) ? boardName(channelId) : "";
}

async function loadBoards() {
  const data = await (await fetch("/api/channels")).json();
  boards = data.channels || [];
  if (!isCustom(channelId) && !boards.some((b) => b.id === channelId)) channelId = data.default || "sports";
  paintBoards();
}

async function switchChannel(id) {
  channelId = id;
  localStorage.setItem("sport-desk-channel", channelId);
  selected = null;
  paintBoards();
  await loadNews();
}

async function loadNews() {
  $("news").innerHTML = "<p class='meta'>拉取中…</p>";
  try {
    const res = await fetch("/api/news?channel=" + encodeURIComponent(channelId));
    const items = await readJson(res);
    if (!res.ok) throw new Error(items.detail || "拉取失败");
    $("news").innerHTML = "";
    if (!items.length) {
      $("news").innerHTML = "<p class='meta'>没有搜到相关热点，换个类目试试。</p>";
      return;
    }
    items.forEach((it, i) => {
      const el = document.createElement("article");
      el.className = "card" + (selected && selected.news_id === it.news_id ? " on" : "");
      el.innerHTML = `
        <img src="${it.cover}" alt="" />
        <div>
          <small>${it.published} · ${it.source}</small>
          <h3>${it.title}</h3>
        </div>`;
      el.onclick = () => pick(it, el);
      $("news").appendChild(el);
      if (i === 0 && !selected) pick(it, el);
    });
  } catch (err) {
    $("news").innerHTML = "<p class='meta'>" + (err.message || "拉取失败") + "</p>";
  }
}

async function pick(it, el) {
  selected = it;
  document.querySelectorAll(".card").forEach((c) => c.classList.remove("on"));
  if (el) el.classList.add("on");
  const script = await (await fetch("/api/script", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ news_id: it.news_id, channel: channelId }),
  })).json();
  $("title").value = script.title;
  $("hook").value = script.hook;
  $("body").value = script.body;
  fillChannels(script.title, script.hook, script.hashtags_line);
  const cur = bgmTracks.find((t) => t.track_id === bgmId);
  const bgmNote = cur ? " · 配乐 " + cur.name : " · 配乐 仅打字机";
  $("meta").textContent = `${it.title} · ${script.image_urls.length} 张配图${bgmNote}`;
}

function fillChannels(title, hook, tags) {
  const parts = [title, hook].map((s) => (s || "").trim()).filter(Boolean);
  $("ch-title").value = parts.join("｜");
  $("hashtags").value = tags || "";
}

function copyChannels() {
  const text = ($("ch-title").value + "\n\n" + $("hashtags").value).trim();
  navigator.clipboard.writeText(text).then(() => {
    $("copy-hint").textContent = "已复制，去视频号粘贴即可。";
  }).catch(() => {
    $("hashtags").select();
    $("copy-hint").textContent = "复制失败，请手动选中热词。";
  });
}

function paintBgm(tracks, fallback) {
  bgmTracks = tracks;
  if (!tracks.some((t) => t.track_id === bgmId)) bgmId = fallback || "silent";
  const sel = $("bgm-select");
  sel.innerHTML = "";
  tracks.forEach((track) => {
    const opt = document.createElement("option");
    opt.value = track.track_id;
    opt.textContent = track.name + " · " + track.mood;
    if (track.track_id === bgmId) opt.selected = true;
    sel.appendChild(opt);
  });
  $("bgm").innerHTML = "";
  tracks.forEach((track) => {
    const el = document.createElement("div");
    el.className = "bgm-item" + (track.track_id === bgmId ? " on" : "");
    el.innerHTML = "<b>" + track.name + "</b>";
    el.onclick = () => {
      bgmId = track.track_id;
      localStorage.setItem("sport-desk-bgm", bgmId);
      paintBgm(tracks, fallback);
    };
    $("bgm").appendChild(el);
  });
}

async function loadBgm() {
  const data = await (await fetch("/api/bgm")).json();
  if (!localStorage.getItem("sport-desk-bgm")) bgmId = data.default;
  paintBgm(data.tracks, data.default);
}

function previewBgm(id) {
  const player = $("bgm-player");
  player.src = "/api/bgm/preview?id=" + encodeURIComponent(id) + "&t=" + Date.now();
  player.play().catch(() => {});
}

async function uploadBgm(file) {
  const body = new FormData();
  body.append("file", file);
  const res = await fetch("/api/bgm/upload", { method: "POST", body });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "导入失败" }));
    alert(err.detail || "导入失败");
    return;
  }
  const track = await res.json();
  bgmId = track.track_id;
  localStorage.setItem("sport-desk-bgm", bgmId);
  await loadBgm();
}

function resetStage() {
  const player = $("player");
  player.pause();
  player.removeAttribute("src");
  player.load();
  const dl = $("btn-download");
  dl.classList.add("hidden");
  dl.removeAttribute("href");
  $("placeholder").classList.add("hidden");
  $("progress").classList.remove("hidden");
  $("pct").textContent = "0%";
  $("pmsg").textContent = "排队";
}

async function generate() {
  if (!selected) return;
  $("btn-gen").disabled = true;
  resetStage();
  const res = await (await fetch("/api/generate", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      news_id: selected.news_id,
      title: $("title").value,
      hook: $("hook").value,
      body: $("body").value,
      bgm_id: bgmId,
      channel: channelId,
    }),
  })).json();
  poll(res.job_id);
}

async function poll(jobId) {
  clearInterval(timer);
  timer = setInterval(async () => {
    const job = await (await fetch("/api/jobs/" + jobId)).json();
    $("pct").textContent = job.percent + "%";
    $("pmsg").textContent = job.message;
    if (job.status === "done") {
      clearInterval(timer);
      $("btn-gen").disabled = false;
      $("progress").classList.add("hidden");
      $("bgm-player").pause();
      $("placeholder").classList.add("hidden");
      $("player").src = job.url + "?t=" + Date.now();
      $("player").play().catch(() => {});
      const dl = $("btn-download");
      dl.href = "/download/" + encodeURIComponent(job.file);
      dl.download = job.file;
      dl.classList.remove("hidden");
      if (job.hashtags_line) $("hashtags").value = job.hashtags_line;
      if (job.caption) {
        const first = job.caption.split("\n")[0] || "";
        if (first) $("ch-title").value = first;
      }
      $("copy-hint").textContent = "成片已出，热词可直接复制到视频号。";
    }
    if (job.status === "error") {
      clearInterval(timer);
      $("btn-gen").disabled = false;
      $("pmsg").textContent = job.error || "失败";
    }
  }, 700);
}

$("btn-refresh").onclick = loadNews;
$("btn-gen").onclick = generate;
$("topic-form").onsubmit = (ev) => {
  ev.preventDefault();
  const q = ($("topic").value || "").trim();
  if (!q) return;
  switchChannel("q:" + q);
};
$("btn-copy").onclick = copyChannels;
$("bgm-select").onchange = (ev) => {
  bgmId = ev.target.value;
  localStorage.setItem("sport-desk-bgm", bgmId);
  paintBgm(bgmTracks, "silent");
};
$("btn-bgm-preview").onclick = () => previewBgm(bgmId);
["title", "hook", "body"].forEach((id) => {
  $(id).addEventListener("change", async () => {
    if (!selected) return;
    const script = await (await fetch("/api/script", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        news_id: selected.news_id,
        title: $("title").value,
        hook: $("hook").value,
        body: $("body").value,
        channel: channelId,
      }),
    })).json();
    fillChannels(script.title, script.hook, script.hashtags_line);
  });
});
$("bgm-file").onchange = (ev) => {
  const file = ev.target.files && ev.target.files[0];
  if (file) uploadBgm(file);
  ev.target.value = "";
};
Promise.all([loadBgm(), loadBoards()]).then(loadNews).catch((err) => {
  $("news").textContent = "加载失败：" + err;
});
