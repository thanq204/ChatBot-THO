const ytEsc = (value) => String(value ?? "").replace(/[&<>'"]/g, (c) => ({"&":"&amp;","<":"&lt;",">":"&gt;","'":"&#39;",'"':"&quot;"}[c]));
const ytLabels = { healthy:"Ổn định", disagreement:"Bất đồng", tense:"Căng thẳng", escalating:"Leo thang", critical:"Nguy cấp", resolving:"Đang hạ nhiệt", resolved:"Đã giải quyết", observe:"Theo dõi", private_nudge:"Nhắc riêng", ask_for_clarification:"Yêu cầu làm rõ", open_mediation:"Mở hoà giải", public_deescalation_reply:"Phản hồi hạ nhiệt", low:"Thấp", medium:"Trung bình", high:"Cao", safe:"An toàn", harassment:"Công kích", violence:"Bạo lực", spam:"Spam", other:"Khác" };
const ytFilterLabels = { all:"tất cả comment", positive:"comment tích cực/an toàn", needs_review:"comment cần chú ý", negative:"comment tiêu cực/rủi ro cao" };
const ytHuman = (value) => ytLabels[value] ? `${ytLabels[value]} (${value})` : String(value ?? "—");
const youtubeSessionKey = "community-youtube-last-sync";

async function ytRequest(path, options = {}) {
  const response = await fetch(`/api/v1${path}`, {headers:{"Content-Type":"application/json"}, ...options});
  const body = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(body.detail || "YouTube request failed.");
  return body;
}

function openYtThread(card) {
  window.location.href = `/admin?thread_id=${encodeURIComponent(card.dataset.thread)}&video_id=${encodeURIComponent(card.dataset.video || "")}&source_mode=public_api`;
}

function renderYtThreads(threads) {
  const target = document.querySelector("#youtube-threads");
  target.innerHTML = threads.length ? threads.map((item, index) => {
    const a = item.analysis || {};
    return `<article class="radar-card" data-thread="${ytEsc(item.thread_id)}" data-video="${ytEsc(item.video_id || "")}" data-source="${ytEsc(item.source_mode || "public_api")}" role="button" tabindex="0" aria-label="Mở conversation thread ${index + 1}">
      <div class="radar-card-top"><span class="source-mark">YOUTUBE</span><span class="badge ${ytEsc(a.conversation_stage || "neutral")}">${ytEsc(ytHuman(a.conversation_stage || "analyzed"))}</span><span class="score-pill">${Math.round((a.escalation_score || 0) * 100)}% · mức leo thang</span></div>
      <h3>Conversation thread ${String(index + 1).padStart(2, "0")}</h3>
      <p class="radar-summary"><b>Chủ đề nhận diện:</b> ${ytEsc(a.main_topic || "Chưa xác định")}<br>${ytEsc(a.conflict_summary || "Chưa có phân tích")}</p>
      <div class="radar-meta"><span>${item.messages.length} tin nhắn</span><span>Đề xuất: ${ytEsc(ytHuman(a.recommended_intervention || "observe"))}</span><span>${ytEsc(item.action_mode || "simulated")} · mô phỏng</span></div>
      <div class="radar-card-bottom"><span class="muted">Nhóm: ${ytEsc(ytHuman(a.category || "other"))} · Rủi ro: ${ytEsc(ytHuman(a.risk_level || "low"))}</span><span class="open-hint">Bấm để xem timeline →</span></div>
    </article>`;
  }).join("") : `<p class="empty">Không có comment/reply phù hợp với bộ lọc.</p>`;
  target.querySelectorAll("[data-thread]").forEach((card) => {
    card.addEventListener("click", () => openYtThread(card));
    card.addEventListener("keydown", (event) => { if (event.key === "Enter" || event.key === " ") { event.preventDefault(); openYtThread(card); } });
  });
}

function renderYtResult(result, filterMode = result.filter_mode || "all") {
  document.querySelector("#youtube-title").textContent = result.video_title;
  document.querySelector("#youtube-action-badge").textContent = `${result.source_mode} · ${result.action_mode}`;
  document.querySelector("#youtube-stats").innerHTML = `<div class="data-point"><span>Kết quả trả về</span><strong>${result.total_threads}</strong></div><div class="data-point"><span>Bình luận gốc</span><strong>${result.new_comments}</strong></div><div class="data-point"><span>Phản hồi</span><strong>${result.new_replies}</strong></div><div class="data-point"><span>Đã quét</span><strong>${result.scanned_threads || result.total_threads}</strong></div>`;
  const notes = result.errors || [];
  document.querySelector("#youtube-filter-note").innerHTML = `<span class="filter-note-label">Bộ lọc:</span> ${ytEsc(ytFilterLabels[result.filter_mode || filterMode])} · ${result.total_threads} kết quả được hiển thị${notes.length ? `<br><span class="muted">${ytEsc(notes.join(" "))}</span>` : ""}`;
  document.querySelector("#youtube-filter").value = result.filter_mode || filterMode;
  renderYtThreads(result.threads || []);
}

function persistYtResult(result, inputValue) {
  try { sessionStorage.setItem(youtubeSessionKey, JSON.stringify({result, input: inputValue})); } catch (_) { /* storage is optional */ }
}

function restoreYtResult() {
  try {
    const saved = JSON.parse(sessionStorage.getItem(youtubeSessionKey) || "null");
    if (!saved?.result?.threads) return;
    if (!returnedVideoId && saved.input) document.querySelector("#youtube-input").value = saved.input;
    renderYtResult(saved.result);
  } catch (_) { /* ignore stale browser storage */ }
}

async function loadYtStatus() {
  const status = await ytRequest("/integrations/youtube/status");
  const modeLabel = status.data_mode === "public_api" ? "PUBLIC READ ONLY" : "AUTHORIZED MODE";
  document.querySelector("#youtube-mode").value = `${status.data_mode} / ${status.action_mode}`;
  document.querySelector("#youtube-status").innerHTML = `<b>${modeLabel}</b><br><span class="muted">${status.configured ? "YOUTUBE_API_KEY configured" : "Thiếu YOUTUBE_API_KEY — hãy thêm key để đọc video public."}</span><br><span class="muted">OAuth: ${status.connected ? "connected" : "not connected"}; thiếu: ${(status.missing_credentials || []).filter((key) => key === "YOUTUBE_API_KEY").join(", ") || "none"}</span>`;
}

const returnedVideoId = new URLSearchParams(window.location.search).get("video_id");
if (returnedVideoId) document.querySelector("#youtube-input").value = returnedVideoId;

document.querySelector("#youtube-sync").addEventListener("click", async (event) => {
  const button = event.currentTarget;
  const error = document.querySelector("#youtube-error");
  const filterMode = document.querySelector("#youtube-filter").value;
  const limit = Number(document.querySelector("#youtube-limit").value);
  error.innerHTML = "";
  button.disabled = true;
  button.classList.add("is-loading");
  button.dataset.originalLabel = button.textContent;
  button.textContent = filterMode === "all" ? "Đang sync và phân tích…" : "Đang quét và lọc comment…";
  document.querySelector("#youtube-threads").innerHTML = `<div class="loading-state"><span class="spinner"></span><div><strong>Đang lấy comment + reply</strong><small>${filterMode === "all" ? "Đang gom thread và chạy conversation analysis…" : `Đang quét batch lớn để tìm ${limit} ${ytFilterLabels[filterMode]}…`}</small></div></div>`;
  try {
    const result = await ytRequest("/youtube/sync", {method:"POST", body:JSON.stringify({video_url_or_id:document.querySelector("#youtube-input").value.trim(), max_results:limit, filter_mode:filterMode, auto_analyze:true})});
    persistYtResult(result, document.querySelector("#youtube-input").value.trim());
    renderYtResult(result, filterMode);
  } catch (e) {
    error.innerHTML = `<p class="notice error">${ytEsc(e.message)}</p>`;
    document.querySelector("#youtube-threads").innerHTML = `<p class="empty">Chưa có kết quả sync.</p>`;
  } finally {
    button.disabled = false;
    button.classList.remove("is-loading");
    button.textContent = button.dataset.originalLabel;
  }
});

document.querySelector("#youtube-oauth").addEventListener("click", async () => {
  try { const result = await ytRequest("/integrations/youtube/connect"); if (result.authorization_url) window.open(result.authorization_url, "_blank", "noopener"); else alert(result.message); } catch (e) { alert(e.message); }
});
loadYtStatus().catch((e) => { document.querySelector("#youtube-status").textContent = e.message; });
restoreYtResult();
