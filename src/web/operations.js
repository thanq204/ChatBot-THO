const api = (path, options = {}) => fetch(`/api/v1${path}`, {headers: {"Content-Type": "application/json", ...(options.headers || {})}, ...options}).then(async response => { const body = await response.json(); if (!response.ok) throw new Error(body.detail || "Request failed"); return body; });
const esc = value => String(value ?? "").replace(/[&<>"']/g, char => ({"&":"&amp;", "<":"&lt;", ">":"&gt;", "\"":"&quot;", "'":"&#039;"}[char]));
const dateText = value => value ? new Date(value).toLocaleString("vi-VN") : "-";
let liveDefaultApplied = false;

async function load() {
  const filter = document.querySelector("#platform-filter").value;
  const [summary, incidents, platforms] = await Promise.all([
    api("/analytics"),
    api(`/incidents${filter ? `?platform=${encodeURIComponent(filter)}` : ""}`),
    api("/platforms"),
  ]);
  document.querySelector("#kpi-messages").textContent = summary.messages_analyzed;
  document.querySelector("#kpi-open").textContent = summary.open_incidents;
  document.querySelector("#kpi-critical").textContent = summary.critical_incidents;
  document.querySelector("#kpi-platforms").textContent = platforms.filter(item => item.configured).length;
  document.querySelector("#platform-statuses").innerHTML = platforms.map(item => `<span class="pill ${item.mode === "live-read" ? "pill-low" : ""}">${esc(item.platform)}: ${esc(item.mode)}</span>`).join(" ");
  const live = platforms.filter(item => item.mode === "live-read");
  if (!liveDefaultApplied && !filter && live.length) { document.querySelector("#platform-filter").value = live[0].platform; liveDefaultApplied = true; return load(); }
  document.querySelector("#incidents").innerHTML = incidents.length ? incidents.map(item => `<article class="incident-row" data-id="${esc(item.incident_id)}"><span class="pill pill-${esc(item.severity)}">${esc(item.severity)}</span> <span class="pill">${esc(item.platform)}</span><strong>${esc(item.title)}</strong><div class="incident-meta">${esc(item.incident_id)} · ${item.message_count} message · risk ${Math.round(item.risk_score * 100)}% · ${esc(item.status)} · ${dateText(item.updated_at)}</div><p>${esc(item.summary)}</p><button class="incident-open" type="button" data-incident-id="${esc(item.incident_id)}">Mở message gốc →</button></article>`).join("") : `<p class="empty">Chưa có incident cho bộ lọc này. Hãy Scan connector thật.</p>`;
  document.querySelectorAll(".incident-row").forEach(row => {
    row.addEventListener("click", () => loadDetail(row.dataset.id));
    row.querySelector(".incident-open").addEventListener("click", event => { event.stopPropagation(); loadDetail(event.currentTarget.dataset.incidentId); });
  });
}

async function loadDetail(id) {
  const detail = document.querySelector("#incident-detail");
  detail.innerHTML = `<div class="incident-loading"><span class="loading-spinner"></span>Đang mở message gốc và audit trail…</div>`;
  detail.scrollIntoView({behavior: "smooth", block: "start"});
  try {
    const data = await api(`/incidents/${encodeURIComponent(id)}`);
    const messages = data.messages || [];
    const rootMessage = messages.find(item => !item.parent_message_id) || messages[0];
    const sourceMarkup = rootMessage ? `<div class="source-message"><div class="source-message-label">Message gốc được phân tích</div><blockquote>${esc(rootMessage.text)}</blockquote><small>${esc(rootMessage.author_id)} · ${dateText(rootMessage.timestamp)}</small></div>` : `<p class="empty">Chưa có message gốc trong case này.</p>`;
    const messageMarkup = messages.length ? messages.map(item => `<div class="gate"><b>${item.parent_message_id ? "Reply" : "Message gốc"}</b> · ${esc(item.author_id)} · ${dateText(item.timestamp)}<br>${esc(item.text)}<br><small>Decision: ${esc(item.decision)} · Category: ${esc(item.category)} · Risk: ${Math.round((item.risk_score || 0) * 100)}%<br>Vì sao: ${esc(item.explanation || "Chưa có giải thích")}</small></div>`).join("") : `<p class="empty">Case này chưa có message chi tiết.</p>`;
    detail.innerHTML = `<h3>${esc(data.incident.title)}</h3><p>${esc(data.incident.summary)}</p>${sourceMarkup}<div class="incident-guide"><div><strong>AI phát hiện</strong><span>${esc(data.incident.categories.join(", "))} · risk ${Math.round((data.incident.risk_score || 0) * 100)}%</span></div><div><strong>Admin cần làm gì?</strong><span>Đọc message và evidence bên dưới, sau đó quyết định có giữ, cảnh báo hay chuyển review.</span></div></div><p><b>Trạng thái:</b> ${esc(data.incident.status)} · <b>Nền tảng:</b> ${esc(data.incident.platform)}</p><h4>Messages trong case</h4>${messageMarkup}<h4>Audit trail</h4>${data.audit.length ? data.audit.map(item => `<div class="incident-meta">${dateText(item.created_at)} · ${esc(item.event_type)} · ${esc(item.actor)}</div>`).join("") : `<p class="empty">Chưa có audit trail.</p>`}`;
  } catch (error) {
    detail.innerHTML = `<div class="notice error">Không mở được Incident này: ${esc(error.message)}</div>`;
  }
}

async function syncPlatform(platform, button) {
  const output = document.querySelector("#sync-result"); button.disabled = true;
  output.innerHTML = `<p class="notice">Đang đọc dữ liệu thật từ ${esc(platform)}...</p>`;
  try { const limit = platform === "discord" ? document.querySelector("#sync-limit").value : "50"; const result = await api(`/platforms/${platform}/pull?limit=${limit}`, {method: "POST"}); output.innerHTML = `<p class="notice success">Đã nhận ${result.received} message và phân tích ${result.analyzed} message từ ${esc(platform)}.</p>`; await load(); }
  catch (error) { output.innerHTML = `<p class="notice error">${esc(error.message)}</p>`; }
  finally { button.disabled = false; }
}

document.querySelector("#refresh-button").addEventListener("click", async event => {
  const button = event.currentTarget; const original = button.textContent;
  button.disabled = true; button.textContent = "Đang tải dữ liệu...";
  try { await load(); }
  catch (error) { const output = document.querySelector("#sync-result"); if (output) output.innerHTML = `<p class="notice error">Không thể refresh dữ liệu: ${esc(error.message)}</p>`; }
  finally { button.disabled = false; button.textContent = original; }
});
document.querySelector("#platform-filter").addEventListener("change", () => load().catch(error => alert(error.message)));
document.querySelector("#sync-discord").addEventListener("click", event => syncPlatform("discord", event.currentTarget));
document.querySelector("#sync-telegram").addEventListener("click", event => syncPlatform("telegram", event.currentTarget));
document.querySelector("#analyze-form").addEventListener("submit", async event => { event.preventDefault(); const output = document.querySelector("#analysis-result"); output.textContent = "Đang chạy Gate 1 -> Gate 2 -> Gate 3..."; try { const data = await api("/messages/analyze", {method: "POST", body: JSON.stringify({message: {message_id: `web-${Date.now()}`, platform: document.querySelector("#message-platform").value, channel_id: document.querySelector("#message-channel").value, thread_key: document.querySelector("#message-thread").value, author_id: "admin-demo", text: document.querySelector("#message-text").value, timestamp: new Date().toISOString()}})}); const result = data.result; output.innerHTML = `<h3>${esc(result.decision.toUpperCase())} · ${esc(result.category)}</h3><p>Risk ${Math.round(result.risk_score * 100)}% · ${esc(result.severity)} · ${esc(result.explanation)}</p>${result.gates.map(gate => `<div class="gate"><b>${esc(gate.gate)}</b> · ${esc(gate.label)} · ${Math.round(gate.risk_score * 100)}%<br>${esc(gate.explanation)}<br><small>Evidence: ${esc(gate.evidence.join(", ") || "none")}</small></div>`).join("")}`; await load(); } catch (error) { output.textContent = error.message; } });
document.querySelector("#rag-form").addEventListener("submit", async event => { event.preventDefault(); const output = document.querySelector("#rag-result"); output.textContent = "Đang tìm knowledge..."; try { const data = await api("/rag/ask", {method: "POST", body: JSON.stringify({question: document.querySelector("#rag-question").value})}); output.innerHTML = `<p>${esc(data.answer).replaceAll("\n", "<br>")}</p><small>Sources: ${esc(data.sources.map(source => source.title).join(", "))} · ${esc(data.model_used)}</small>`; } catch (error) { output.textContent = error.message; } });
document.querySelector("#policy-form").addEventListener("submit", async event => { event.preventDefault(); try { await api("/policies/POL-CUSTOM-001", {method: "PUT", body: JSON.stringify({name: document.querySelector("#policy-name").value, description: document.querySelector("#policy-description").value, category: "other", action: "hold_for_review", trigger_terms: document.querySelector("#policy-terms").value.split(",").map(item => item.trim()).filter(Boolean), active: true})}); await load(); event.currentTarget.reset(); } catch (error) { alert(error.message); } });
document.querySelector("#knowledge-form").addEventListener("submit", async event => { event.preventDefault(); try { await api("/knowledge/KN-CUSTOM-001", {method: "PUT", body: JSON.stringify({title: document.querySelector("#knowledge-title").value, body: document.querySelector("#knowledge-body").value, tags: document.querySelector("#knowledge-tags").value.split(",").map(item => item.trim()).filter(Boolean), active: true})}); await load(); event.currentTarget.reset(); } catch (error) { alert(error.message); } });
load().catch(error => { document.querySelector("#incidents").innerHTML = `<p class="notice error">${esc(error.message)}</p>`; });
document.querySelector("#knowledge-import-form").addEventListener("submit", async event => { event.preventDefault(); const file = document.querySelector("#knowledge-file").files[0]; const output = document.querySelector("#knowledge-import-result"); if (!file) return; output.innerHTML = `<p class="notice">Đang đọc và chuẩn hóa ${esc(file.name)}...</p>`; try { const bytes = new Uint8Array(await file.arrayBuffer()); let binary = ""; for (let index = 0; index < bytes.length; index += 0x8000) binary += String.fromCharCode(...bytes.subarray(index, index + 0x8000)); const response = await fetch("/api/v1/knowledge/import", {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify({filename: file.name, content_base64: btoa(binary), target: document.querySelector("#knowledge-import-target").value})}); const data = await response.json(); if (!response.ok) throw new Error(data.detail || "Import failed"); output.innerHTML = `<p class="notice success">Đã chuẩn hóa ${data.normalized_count} bản ghi từ ${esc(data.filename)}. Bỏ qua: ${data.skipped_count}.</p>`; await load(); event.currentTarget.reset(); } catch (error) { output.innerHTML = `<p class="notice error">${esc(error.message)}</p>`; } });
