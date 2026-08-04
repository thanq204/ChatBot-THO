const apiBase = "/api/v1/moderation";
const historyStorageKey = "community-channel-conversation-history";

const escapeHtml = (value) => String(value ?? "").replace(/[&<>'"]/g, (char) => ({ "&":"&amp;", "<":"&lt;", ">":"&gt;", "'":"&#39;", '"':"&quot;" }[char]));

async function request(path, options = {}) {
  const response = await fetch(`${apiBase}${path}`, {
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  });
  const body = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(body.detail || "Request failed. Please try again.");
  return body;
}

function badge(action) { return `<span class="badge ${escapeHtml(action)}">${escapeHtml(action)}</span>`; }
function dateText(value) { return value ? new Date(value).toLocaleString() : "—"; }
function renderModeBadge(mode, fallbackUsed, elementId = "") {
  const label = fallbackUsed ? "MOCK FALLBACK" : `${mode} MODE`.toUpperCase();
  return `<span${elementId ? ` id="${escapeHtml(elementId)}"` : ""} class="badge neutral">${escapeHtml(label)}</span>`;
}

function readConversationHistory() {
  try {
    const saved = JSON.parse(localStorage.getItem(historyStorageKey) || "[]");
    return Array.isArray(saved) ? saved.slice(-30) : [];
  } catch (_) { return []; }
}

function renderConversationHistory(history) {
  const container = document.querySelector("#conversation-history");
  if (!history.length) {
    container.innerHTML = `<div class="history-empty"><span>✦</span><p>Your conversation history will appear here after you submit.</p></div>`;
    return;
  }
  container.innerHTML = history.map((item, index) => `<div class="history-item"><span class="history-index">${String(index + 1).padStart(2, "0")}</span><div class="history-message"><p>${escapeHtml(item.text)}</p><small>${dateText(item.created_at)}${item.action ? ` · ${escapeHtml(item.action.toUpperCase())}` : ""}</small></div></div>`).join("");
  container.scrollTop = container.scrollHeight;
}

async function setupMember() {
  const form = document.querySelector("#submission-form");
  const text = document.querySelector("#content");
  const count = document.querySelector("#content-count");
  const error = document.querySelector("#form-error");
  const resultPanel = document.querySelector("#result-panel");
  const modeBadgeElement = document.querySelector("#mode-badge");
  const history = readConversationHistory();
  text.addEventListener("input", () => { count.textContent = `${text.value.length} / 5000`; });

  const [status, cases] = await Promise.all([request("/status"), request("/demo-cases")]);
  modeBadgeElement.outerHTML = status.configured
    ? renderModeBadge(status.mode, false, "mode-badge")
    : `<span id="mode-badge" class="badge neutral">GEMINI API NOT CONFIGURED</span>`;
  renderConversationHistory(history);
  document.querySelector("#clear-history").addEventListener("click", () => {
    history.length = 0;
    localStorage.removeItem(historyStorageKey);
    renderConversationHistory(history);
  });
  document.querySelector("#sample-list").innerHTML = cases.map((item, index) => `<button class="sample" data-sample="${index}">Case ${index + 1}<small>${escapeHtml(item.text)}</small></button>`).join("");
  document.querySelectorAll("[data-sample]").forEach((button) => button.addEventListener("click", () => {
    const item = cases[Number(button.dataset.sample)];
    document.querySelector("#user-id").value = item.user_id;
    document.querySelector("#channel").value = item.channel;
    text.value = item.text;
    document.querySelector("#recent-context").value = item.recent_context.join("\n");
    count.textContent = `${text.value.length} / 5000`;
    text.focus();
  }));

  form.addEventListener("submit", async (event) => {
    event.preventDefault(); error.hidden = true;
    const payload = {
      user_id: document.querySelector("#user-id").value.trim(), role: "member", text: text.value.trim(),
      channel: document.querySelector("#channel").value.trim(),
      recent_context: [...history.slice(-5).map((item) => item.text), ...document.querySelector("#recent-context").value.split("\n").map((line) => line.trim()).filter(Boolean)].slice(-10),
    };
    if (!payload.text) { error.textContent = "Vui lòng nhập nội dung trước khi submit."; error.hidden = false; return; }
    try {
      const result = await request("/submit", { method: "POST", body: JSON.stringify(payload) });
      const moderation = result.moderation;
      history.push({ text: payload.text, created_at: new Date().toISOString(), action: moderation.action });
      while (history.length > 30) history.shift();
      localStorage.setItem(historyStorageKey, JSON.stringify(history));
      renderConversationHistory(history);
      const currentModeBadge = document.querySelector("#mode-badge");
      if (currentModeBadge) {
        currentModeBadge.outerHTML = renderModeBadge(moderation.mode, moderation.fallback_used, "mode-badge");
      }
      resultPanel.hidden = false;
      resultPanel.innerHTML = `<div class="section-heading"><div><span class="eyebrow">MODERATION RESULT</span><h2>${result.review ? "Sent to Admin Review Queue" : "Automatic decision complete"}</h2></div>${badge(moderation.action)}</div><div class="result-grid"><div class="data-point"><span>Category</span><strong>${escapeHtml(moderation.category)}</strong></div><div class="data-point"><span>Risk level</span><strong>${escapeHtml(moderation.risk_level)}</strong></div><div class="data-point"><span>Confidence</span><strong>${Math.round(moderation.confidence * 100)}%</strong></div><div class="data-point"><span>Model</span><strong>${escapeHtml(moderation.model_used)}</strong></div></div><p><strong>Reason:</strong> ${escapeHtml(moderation.reason)}</p><p><strong>Evidence:</strong> ${escapeHtml((moderation.evidence || []).join(" · ") || "—")}</p><p class="${result.review ? "notice" : "muted"}">${escapeHtml(result.message)}</p>${moderation.fallback_reason ? `<p class="muted">${escapeHtml(moderation.fallback_reason)}</p>` : ""}`;
      const trace = (moderation.agent_trace || []).map((agent) => escapeHtml(agent)).join(" → ");
      if (trace) {
        const traceElement = document.createElement("div");
        traceElement.className = "agent-trace";
        traceElement.innerHTML = `<span>Agent pipeline</span><strong>${trace}</strong>`;
        resultPanel.appendChild(traceElement);
      }
    } catch (requestError) { error.textContent = requestError.message; error.hidden = false; }
  });
}

function caseCard(item) {
  const context = item.recent_context.length ? `<div class="context-box"><strong>Recent context</strong><br>${escapeHtml(item.recent_context.join("\n"))}</div>` : "";
  return `<article class="case" data-review="${escapeHtml(item.review_id)}"><div class="case-header"><strong>${escapeHtml(item.review_id)}</strong>${badge(item.model_action)} ${renderModeBadge(item.fallback_used ? "mock-fallback" : "gemini", item.fallback_used)}</div><p class="case-content">${escapeHtml(item.content)}</p><p class="metadata">User: ${escapeHtml(item.user_id)} · #${escapeHtml(item.channel)} · Submitted: ${dateText(item.created_at)}</p>${context}<p><strong>${escapeHtml(item.model_category)}</strong> · ${escapeHtml(item.model_risk_level)} risk · ${Math.round(item.model_confidence * 100)}% confidence · model: ${escapeHtml(item.model_used)}</p><p class="muted">${escapeHtml(item.model_reason)}</p><p class="muted"><strong>Evidence:</strong> ${escapeHtml((item.evidence || []).join(" · ") || "—")}</p><div class="decision-inputs"><input class="reviewer" value="Admin" maxlength="100" aria-label="Reviewer name"><input class="admin-note" placeholder="Admin note (optional)" maxlength="1000" aria-label="Admin note"></div><div class="case-actions"><button class="allow" data-decision="allow">Allow</button><button class="warn" data-decision="warn">Warn</button><button class="hide" data-decision="hide">Hide</button></div></article>`;
}

async function setupAdmin() {
  const queue = document.querySelector("#queue"); const audit = document.querySelector("#audit-log");
  async function load() {
    const [pending, entries] = await Promise.all([request("/review-queue"), request("/audit-logs")]);
    document.querySelector("#pending-count").textContent = pending.length;
    queue.innerHTML = pending.length ? pending.map(caseCard).join("") : `<p class="empty">No content is waiting for review.</p>`;
    audit.innerHTML = entries.length ? entries.map((item) => `<article class="audit"><strong>${escapeHtml(item.admin_action.toUpperCase())}</strong> · ${escapeHtml(item.review_id)} · ${escapeHtml(item.user_id)}<br><span class="muted">${escapeHtml(item.model_category)} (${Math.round(item.model_confidence * 100)}%) → ${escapeHtml(item.reviewer)} at ${dateText(item.reviewed_at)}${item.admin_note ? ` · ${escapeHtml(item.admin_note)}` : ""}</span></article>`).join("") : `<p class="empty">No audit decisions yet.</p>`;
    queue.querySelectorAll("[data-decision]").forEach((button) => button.addEventListener("click", async () => {
      const card = button.closest("[data-review]");
      try {
        await request(`/review-queue/${encodeURIComponent(card.dataset.review)}/decision`, { method: "POST", body: JSON.stringify({ action: button.dataset.decision, reviewer: card.querySelector(".reviewer").value.trim() || "Admin", admin_note: card.querySelector(".admin-note").value.trim() }) });
        await load();
      } catch (requestError) { window.alert(requestError.message); }
    }));
  }
  document.querySelector("#refresh-button").addEventListener("click", load); await load();
}

if (document.body.dataset.page === "member") setupMember().catch((error) => { document.querySelector("#form-error").textContent = error.message; document.querySelector("#form-error").hidden = false; });
if (document.body.dataset.page === "admin") setupAdmin().catch((error) => { document.querySelector("#queue").innerHTML = `<p class="notice error">${escapeHtml(error.message)}</p>`; });
