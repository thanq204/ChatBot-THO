const communityBase = "/api/v1";
const esc = (value) => String(value ?? "").replace(/[&<>'"]/g, (c) => ({"&":"&amp;","<":"&lt;",">":"&gt;","'":"&#39;",'"':"&quot;"}[c]));
const localDate = (value) => value ? new Date(value).toLocaleString() : "—";
const labels = { healthy:"Ổn định", disagreement:"Bất đồng", tense:"Căng thẳng", escalating:"Leo thang", critical:"Nguy cấp", resolving:"Đang hạ nhiệt", resolved:"Đã giải quyết", observe:"Theo dõi", private_nudge:"Nhắc riêng", ask_for_clarification:"Yêu cầu làm rõ", open_mediation:"Mở hoà giải", temporary_cooldown:"Tạm khóa nhiệt", public_deescalation_reply:"Phản hồi hạ nhiệt", simulated:"Mô phỏng", low:"Thấp", medium:"Trung bình", high:"Cao", safe:"An toàn", harassment:"Công kích", violence:"Bạo lực", spam:"Spam" };
const human = (value) => labels[value] ? `${labels[value]} (${value})` : String(value ?? "—");
const demoTitles = { "DEMO-HEALTHY":"Positive praise", "DEMO-DISAGREEMENT":"Fact disagreement", "DEMO-TENSE":"Tense exchange", "DEMO-ESCALATING":"Hostile escalation", "DEMO-AMBIGUOUS":"Ambiguous intent", "DEMO-RESOLVING":"Repairing conversation" };
const displayTitle = (thread, fallback) => demoTitles[thread.thread_id] ? `${thread.video_title || fallback} · ${demoTitles[thread.thread_id]}` : (thread.video_title || fallback);
const sourceLabels = { public_api: "YouTube thật · public API" };

async function communityRequest(path, options = {}) {
  const response = await fetch(`${communityBase}${path}`, {headers:{"Content-Type":"application/json", ...(options.headers || {})}, ...options});
  const body = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(body.detail || "Community API request failed.");
  return body;
}

function stageBadge(stage) { return `<span class="badge ${esc(stage)}">${esc(human(stage))}</span>`; }
function modeBadge(mode) { return `<span class="badge neutral">${esc(human(mode || "local"))} · MÔ PHỎNG</span>`; }
function scoreClass(score) { return score >= .85 ? "score-critical" : score >= .65 ? "score-high" : score >= .4 ? "score-medium" : "score-low"; }
function triggerEvidence(analysis) {
  const triggers = analysis?.triggers || [];
  if (!triggers.length) return `<span class="no-trigger">Không phát hiện cụm từ độc hại rõ ràng.</span>`;
  return triggers.map((trigger) => {
    const terms = trigger.matched_terms?.length ? trigger.matched_terms : ["Không có cụm từ cụ thể từ rule local"];
    return `<div class="trigger-evidence"><b>Cụm từ khớp: “${esc(terms.join(" · "))}”</b><span>${esc(trigger.reason || "Tín hiệu cần review")}</span><small>${esc(trigger.context_note || "Đối chiếu trực tiếp với message chứa trigger.")}</small></div>`;
  }).join("");
}
function renderEmbeddingMemory(matches) {
  if (!matches?.length) return "";
  return `<section class="review-memory"><div><span class="eyebrow">REVIEWED CASE MEMORY</span><h3>Case Admin từng đánh giá gần giống</h3><p>Similarity cao chỉ tạo đề xuất; Admin vẫn phải xác nhận.</p></div>${matches.map((match) => `<article><div><strong>${Math.round(match.score * 100)}% tương đồng</strong><span>${esc(human(match.admin_action || "reviewed"))}</span></div><p>${esc(match.source_text || "")}</p></article>`).join("")}</section>`;
}
function setLoading(button, loading, label) {
  if (!button) return;
  if (loading) {
    button.dataset.originalLabel = button.textContent;
    button.disabled = true;
    button.classList.add("is-loading");
    button.textContent = label || "Đang xử lý…";
  } else {
    button.disabled = false;
    button.classList.remove("is-loading");
    button.textContent = button.dataset.originalLabel || button.textContent;
  }
}

function renderRadar(threads) {
  const target = document.querySelector("#radar-list");
  if (!threads.length) { target.innerHTML = `<p class="empty">Chưa có thread. Vào YouTube sync hoặc Analyze một dataset.</p>`; return; }
  target.innerHTML = threads.map((thread) => {
    const a = thread.analysis || {};
    const root = thread.messages.find((message) => !message.parent_message_id) || thread.messages[0];
    const preview = root?.text || "Chưa có nội dung comment.";
    return `<article class="radar-card" data-thread="${esc(thread.thread_id)}" role="button" tabindex="0" aria-label="Mở chi tiết thread ${esc(thread.thread_id)}"><div class="radar-card-top"><span class="source-mark">${esc(thread.platform.toUpperCase())}</span>${stageBadge(a.conversation_stage || "unanalysed")}<span class="score-pill ${scoreClass(a.escalation_score || 0)}">${Math.round((a.escalation_score || 0)*100)}% · mức leo thang</span></div><h3>${esc(displayTitle(thread, a.main_topic || "Local conversation"))}</h3><p class="radar-summary">${esc(a.conflict_summary || `${thread.messages.length} messages waiting for analysis.`)}</p><p class="radar-preview"><b>Comment gốc:</b> “${esc(preview.slice(0, 180))}${preview.length > 180 ? "…" : ""}”</p><div class="radar-meta"><span>${thread.messages.length} tin nhắn</span><span>${new Set(thread.messages.map((m) => m.author_id)).size} người tham gia</span><span>${esc(human(a.category || "other"))} · risk ${esc(human(a.risk_level || "low"))}</span></div><div class="radar-card-bottom"><span class="muted">Trigger: ${esc(a.triggers?.[0]?.reason || "Không phát hiện")}</span><span class="open-hint">Mở comment + timeline →</span></div></article>`;
  }).join("");
  target.querySelectorAll("[data-thread]").forEach((card) => { card.addEventListener("click", () => loadDetail(card.dataset.thread)); card.addEventListener("keydown", (event) => { if (event.key === "Enter" || event.key === " ") { event.preventDefault(); loadDetail(card.dataset.thread); } }); });
}

async function loadDashboard() {
  const list = document.querySelector("#radar-list");
  if (!list.dataset.loaded) list.innerHTML = `<div class="loading-state"><span class="spinner"></span><div><strong>Đang dựng conversation radar</strong><small>Đang đọc dữ liệu demo và tính health metrics…</small></div></div>`;
  const filter = document.querySelector("#stage-filter").value;
  // The web UI is now production/public-only. Demo rows remain in SQLite for
  // reference, but are intentionally not rendered in the Radar.
  const sourceFilter = "public_api";
  const params = new URLSearchParams();
  if (filter) params.set("stage", filter);
  if (sourceFilter) params.set("source_mode", sourceFilter);
  const requestedVideo = new URLSearchParams(window.location.search).get("video_id");
  if (requestedVideo) params.set("video_id", requestedVideo);
  const query = params.toString() ? `?${params.toString()}` : "";
  const [health, threads, audit] = await Promise.all([communityRequest("/analytics/community-health"), communityRequest(`/conversations${query}`), communityRequest("/audit/community")]);
  document.querySelector("#metric-total").textContent = health.total_conversations;
  document.querySelector("#metric-score").textContent = `${Math.round(health.average_escalation_score * 100)}%`;
  document.querySelector("#metric-improved").textContent = health.improved_or_resolved;
  document.querySelector("#metric-agreement").textContent = `${Math.round(health.admin_agreement_rate * 100)}%`;
  const scope = document.querySelector("#source-scope");
  if (scope) scope.textContent = sourceLabels[sourceFilter] || sourceFilter;
  renderRadar(threads);
  list.dataset.loaded = "true";
  document.querySelector("#community-audit").innerHTML = audit.feedback.length ? audit.feedback.map((item) => `<article class="audit"><strong>${esc(item.admin_selected_action || "reviewed").toUpperCase()}</strong> · ${esc(item.thread_id)}<br><span class="muted">AI: ${esc(item.original_ai_stage || "—")} (${Math.round((item.original_escalation_score || 0)*100)}%) → outcome: ${esc(item.outcome_after_intervention || "unknown")} · ${localDate(item.reviewed_at)}</span></article>`).join("") : `<p class="empty">Chưa có Admin decision. Các case demo đã được phân tích nhưng chưa reviewed.</p>`;
}

function renderEvidence(messages) {
  return messages.map((message, index) => {
    const isReply = Boolean(message.parent_message_id);
    const kind = isReply ? "REPLY" : "COMMENT GỐC";
    const source = message.source_url ? `<a href="${esc(message.source_url)}" target="_blank" rel="noopener">Mở comment gốc ↗</a>` : "Nguồn local";
    return `<article class="evidence-message ${isReply ? "is-reply" : "is-root"}"><div class="evidence-top"><span class="evidence-kind">${kind}</span><span>${esc(message.author_id)}</span><span>${localDate(message.timestamp)}</span>${message.is_trigger ? `<span class="evidence-trigger">AI đánh dấu trigger</span>` : ""}</div><p>${esc(message.text)}</p><div class="evidence-bottom"><span>Message ${index + 1}${isReply ? " · phản hồi comment trước" : " · comment bắt đầu thread"}</span>${source}</div></article>`;
  }).join("");
}

const actionDescriptions = {
  observe: "Chỉ theo dõi. Không tạo draft và không tác động lên YouTube.",
  private_nudge: "Tạo gợi ý nhắc riêng trong nội bộ; YouTube public API không đăng nhắc riêng.",
  suggest_rewrite: "Gợi ý viết lại câu chữ mềm hơn; chỉ lưu nội bộ.",
  ask_for_clarification: "Tạo draft yêu cầu các bên làm rõ dữ kiện hoặc ý định.",
  public_deescalation_reply: "Tạo draft phản hồi hạ nhiệt; chưa đăng lên YouTube.",
  open_mediation: "Mở workspace hòa giải và tạo bản draft cho Admin chỉnh sửa.",
  temporary_cooldown: "Đánh dấu thread cần tạm dừng để review; chỉ mô phỏng trong MVP.",
  warn: "Lưu lựa chọn cảnh báo của Admin; chưa gửi cảnh báo thật.",
  hide: "Lưu lựa chọn ẩn comment của Admin; chưa ẩn comment thật.",
  hold_for_review: "Đưa case vào trạng thái chờ review; chưa thay đổi YouTube.",
  publish: "Lưu lựa chọn đăng của Admin; chưa đăng nội dung thật.",
  generate_reply_draft: "Tạo draft reply để Admin duyệt trước khi đăng."
};
function actionHelp(action) { return `<span class="decision-help-label">${esc(human(action))}:</span> ${esc(actionDescriptions[action] || "Lựa chọn này chỉ được lưu để Admin review.")}`; }

async function loadDetail(threadId) {
  const panel = document.querySelector("#thread-detail");
  const radarPanel = document.querySelector(".radar-panel");
  if (radarPanel) radarPanel.hidden = true;
  panel.innerHTML = `<div class="loading-state"><span class="spinner"></span><div><strong>Đang mở comment và timeline</strong><small>Đang nạp nội dung gốc để đối chiếu với AI signal…</small></div></div>`;
  panel.scrollIntoView({behavior: "smooth", block: "start"});
  try {
    const detail = await communityRequest(`/conversations/${encodeURIComponent(threadId)}`);
    const thread = detail.thread; const a = thread.analysis || {}; const rec = detail.intervention;
    const messages = thread.messages || [];
    const selectedAction = rec?.recommended_action || "observe";
    panel.innerHTML = `<div class="section-heading"><div><span class="eyebrow">THREAD DETAIL / ${esc(thread.thread_id)}</span><h2>${esc(thread.video_title || a.main_topic || "Conversation")}</h2><p class="panel-subtitle">Đây là dữ liệu AI đã dùng: ${messages.length} comment/reply · ${esc(thread.source_mode)} · ${modeBadge(thread.action_mode)}</p></div>${stageBadge(a.conversation_stage || "unanalysed")}</div><section class="evidence-panel"><div class="evidence-heading"><div><span class="eyebrow">SOURCE EVIDENCE</span><h3>Comment và reply thực tế</h3><p>Đọc phần này trước khi đánh giá AI. Comment gốc có viền xanh; reply được thụt vào.</p></div><span class="evidence-count">${messages.length} messages</span></div><div class="evidence-list">${renderEvidence(messages)}</div></section><div class="detail-grid"><div><h3>Conversation timeline</h3><div class="timeline">${messages.map((m) => `<div class="timeline-item"><span class="timeline-dot"></span><div><strong>${esc(m.author_id)}</strong><small>${localDate(m.timestamp)}</small><p>${esc(m.text)}</p></div></div>`).join("")}</div></div><div class="analysis-box"><h3>AI signal</h3><div class="score-large ${scoreClass(a.escalation_score || 0)}">${Math.round((a.escalation_score || 0)*100)}<small>/ 100</small></div><p><b>Nhóm:</b> ${esc(human(a.category || "other"))}</p><p><b>Risk:</b> ${esc(human(a.risk_level || "low"))} · <b>Urgency:</b> ${esc(human(a.urgency || "low"))}</p><p><b>Root cause:</b> ${esc((a.root_causes || []).join(" · "))}</p><div class="trigger-block"><b>Vì sao AI đánh giá:</b>${triggerEvidence(a)}</div><p><b>Recommended:</b> ${esc(human(a.recommended_intervention || "observe"))}</p><p><b>Model:</b> ${esc(a.model_used || "—")}</p></div></div><div class="decision-box"><div><h3>Admin intervention</h3><p class="muted">AI chỉ đề xuất. Bạn chọn hoặc chỉnh sửa quyết định; hệ thống sẽ lưu audit trail và feedback. Với chế độ hiện tại, không có hành động thật nào trên YouTube.</p></div><div class="decision-control"><select id="decision-action"><option value="${esc(selectedAction)}">${esc(human(selectedAction))} (AI recommendation)</option><option value="observe">Theo dõi (observe)</option><option value="private_nudge">Nhắc riêng (private_nudge)</option><option value="suggest_rewrite">Gợi ý viết lại (suggest_rewrite)</option><option value="ask_for_clarification">Yêu cầu làm rõ (ask_for_clarification)</option><option value="public_deescalation_reply">Phản hồi hạ nhiệt (public_deescalation_reply)</option><option value="open_mediation">Mở hoà giải (open_mediation)</option><option value="temporary_cooldown">Tạm khóa nhiệt (temporary_cooldown)</option><option value="warn">Cảnh báo (warn)</option><option value="hide">Ẩn (hide)</option><option value="hold_for_review">Giữ để review (hold_for_review)</option><option value="publish">Đăng (publish)</option><option value="generate_reply_draft">Tạo draft phản hồi (generate_reply_draft)</option></select><p id="decision-help" class="decision-help">${actionHelp(selectedAction)}</p></div><textarea id="decision-message" placeholder="Admin có thể sửa draft trước khi duyệt">${esc(rec?.draft_message || "")}</textarea><div class="button-row"><button id="mediation-button" class="secondary">Mở workspace hoà giải</button><button id="decision-button" class="primary-action">Lưu quyết định mô phỏng →</button></div><div id="decision-result"></div></div><div id="mediation-result"></div>`;
    const categoryOptions = ["safe", "harassment", "violence", "spam", "other"].map((value) => `<option value="${value}"${value === (a.category || "other") ? " selected" : ""}>${esc(human(value))}</option>`).join("");
    const riskOptions = ["low", "medium", "high", "critical"].map((value) => `<option value="${value}"${value === (a.risk_level || "low") ? " selected" : ""}>${esc(human(value))}</option>`).join("");
    const stageOptions = ["healthy", "disagreement", "tense", "escalating", "critical", "resolving", "resolved"].map((value) => `<option value="${value}"${value === (a.conversation_stage || "healthy") ? " selected" : ""}>${esc(human(value))}</option>`).join("");
    panel.insertAdjacentHTML("afterbegin", `<button class="back-to-radar secondary" id="back-to-radar">← Quay lại danh sách</button>`);
    panel.querySelector(".decision-box > div")?.insertAdjacentHTML("afterend", `<section class="classification-review"><div><h4>Admin review kết luận AI</h4><p class="muted">Bạn có thể xác nhận AI đúng, đánh dấu AI sai và sửa lại nhãn, hoặc để case cần review thêm. Việc này chỉ sửa dữ liệu đánh giá; không tự cấp quyền ẩn comment YouTube.</p></div><label>Đánh giá kết luận AI<select id="classification-decision"><option value="accept_ai">AI phân loại đúng</option><option value="correct_ai">AI phân loại sai — tôi chỉnh lại</option><option value="uncertain">Chưa chắc — cần review thêm</option></select></label><div class="classification-fields"><label>Category Admin<select id="admin-category">${categoryOptions}</select></label><label>Risk Admin<select id="admin-risk-level">${riskOptions}</select></label><label>Trạng thái Admin<select id="admin-conversation-stage">${stageOptions}</select></label></div></section>`);
    if (detail.embedding_matches?.length) {
      document.querySelector("#thread-detail .evidence-panel")?.insertAdjacentHTML("afterend", renderEmbeddingMemory(detail.embedding_matches));
    }
    const decisionSelect = document.querySelector("#decision-action");
    const duplicateRecommendation = [...decisionSelect.options].slice(1).find((option) => option.value === selectedAction);
    if (duplicateRecommendation) decisionSelect.options[0].remove();
    decisionSelect.value = selectedAction;
    document.querySelector("#decision-help").innerHTML = actionHelp(selectedAction);
    decisionSelect.addEventListener("change", (event) => { document.querySelector("#decision-help").innerHTML = actionHelp(event.target.value); });
    document.querySelector("#decision-button").addEventListener("click", () => saveDecision(threadId));
    document.querySelector("#mediation-button").addEventListener("click", () => loadMediation(threadId));
    document.querySelector("#back-to-radar")?.addEventListener("click", () => { if (radarPanel) radarPanel.hidden = false; panel.scrollIntoView({behavior:"smooth", block:"start"}); });
  } catch (error) { panel.innerHTML = `<p class="notice error">${esc(error.message)}</p>`; }
}

async function loadMediation(threadId) {
  const output = document.querySelector("#mediation-result"); const button = document.querySelector("#mediation-button"); output.innerHTML = `<div class="loading-state compact"><span class="spinner"></span><div><strong>Đang tạo mediation workspace</strong><small>Đang tóm tắt lập trường hai bên…</small></div></div>`; setLoading(button, true, "Đang tạo…");
  try { const item = await communityRequest(`/conversations/${encodeURIComponent(threadId)}/mediation`, {method:"POST"}); output.innerHTML = `<div class="mediation-card"><span class="eyebrow">MEDIATION WORKSPACE</span><h3>Editable resolution draft</h3><p><b>Side A:</b> ${esc(item.side_a_position)}</p><p><b>Side B:</b> ${esc(item.side_b_position)}</p><p><b>Common ground:</b> ${esc(item.common_ground.join(" · "))}</p><p><b>Core disagreement:</b> ${esc(item.core_disagreement.join(" · "))}</p><textarea>${esc(item.admin_editable_draft)}</textarea><p class="muted">Draft chỉ được gửi sau khi Admin chỉnh sửa và duyệt.</p></div>`; } catch (error) { output.innerHTML = `<p class="notice error">${esc(error.message)}</p>`; } finally { setLoading(button, false); }
}

async function saveDecision(threadId) {
  const output = document.querySelector("#decision-result"); const button = document.querySelector("#decision-button"); output.innerHTML = `<div class="loading-state compact"><span class="spinner"></span><div><strong>Đang lưu quyết định</strong><small>Đang ghi audit trail và feedback case…</small></div></div>`; setLoading(button, true, "Đang lưu…");
  try { const result = await communityRequest(`/conversations/${encodeURIComponent(threadId)}/admin-decision`, {method:"POST", body:JSON.stringify({selected_action:document.querySelector("#decision-action").value, admin_edited_message:document.querySelector("#decision-message").value, reviewer:"Admin", classification_decision:document.querySelector("#classification-decision")?.value || "accept_ai", admin_category:document.querySelector("#admin-category")?.value || null, admin_risk_level:document.querySelector("#admin-risk-level")?.value || null, admin_conversation_stage:document.querySelector("#admin-conversation-stage")?.value || null, confirm:true})}); output.innerHTML = `<p class="notice success">${esc(result.execution.message)} Feedback và phân loại Admin đã được ghi nhận.</p>`; await loadDashboard(); } catch (error) { output.innerHTML = `<p class="notice error">${esc(error.message)}</p>`; } finally { setLoading(button, false); }
}

if (document.body.dataset.page === "community-admin") {
  const navigationParams = new URLSearchParams(window.location.search);
  const requestedThread = navigationParams.get("thread_id");
  document.querySelector("#community-refresh").addEventListener("click", async (event) => { const button = event.currentTarget; document.querySelector("#radar-list").dataset.loaded = ""; setLoading(button, true, "Đang refresh…"); try { await loadDashboard(); } catch (e) { document.querySelector("#radar-list").innerHTML = `<p class="notice error">${esc(e.message)}</p>`; } finally { setLoading(button, false); } });
  document.querySelector("#stage-filter").addEventListener("change", () => { document.querySelector("#radar-list").dataset.loaded = ""; loadDashboard(); });
  loadDashboard().catch((e) => { document.querySelector("#radar-list").innerHTML = `<p class="notice error">${esc(e.message)}</p>`; });
  if (requestedThread) loadDetail(requestedThread);
}
