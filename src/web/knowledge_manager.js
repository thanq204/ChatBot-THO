(() => {
  const api = (path, options = {}) => fetch(`/api/v1${path}`, {
    headers: {"Content-Type": "application/json", ...(options.headers || {})}, ...options
  }).then(async response => {
    const body = await response.json();
    if (!response.ok) throw new Error(body.detail || "Request failed");
    return body;
  });
  const esc = value => String(value ?? "").replace(/[&<>"']/g, char => ({"&":"&amp;", "<":"&lt;", ">":"&gt;", "\"":"&quot;", "'":"&#039;"}[char]));
  let policies = [];
  let knowledge = [];
  let rendering = false;
  let editingPolicy = null;
  let editingKnowledge = null;
  let policyQuery = "";
  let knowledgeQuery = "";
  let activeBatch = null;

  const matches = (item, query, fields) => {
    const haystack = fields.map(field => item[field] ?? (Array.isArray(item[field]) ? item[field].join(" ") : "")).join(" ").toLowerCase();
    return !query || haystack.includes(query);
  };

  function render() {
    if (rendering) return;
    rendering = true;
    const scopedPolicies = activeBatch ? policies.filter(item => activeBatch.policyIds.has(item.policy_id)) : policies;
    const scopedKnowledge = activeBatch ? knowledge.filter(item => activeBatch.knowledgeIds.has(item.document_id)) : knowledge;
    const visiblePolicies = (activeBatch || policyQuery) ? scopedPolicies.filter(item => matches(item, policyQuery, ["name", "description", "category", "action", "trigger_terms"])) : [];
    const visibleKnowledge = (activeBatch || knowledgeQuery) ? scopedKnowledge.filter(item => matches(item, knowledgeQuery, ["title", "body", "dataset", "tags"])) : [];
    const policyList = document.querySelector("#policy-list");
    const knowledgeList = document.querySelector("#knowledge-list");
    if (policyList) policyList.innerHTML = visiblePolicies.map(item => `
      <div class="gate managed-record">
        <b>${esc(item.name)}</b> · ${esc(item.category)} · ${esc(item.action)}<br>
        <small>${esc(item.description)}<br>terms: ${esc(item.trigger_terms.join(", "))}<br>version ${item.version}</small>
        <div class="record-actions"><button class="record-edit" type="button" data-policy-id="${esc(item.policy_id)}">Sửa</button><button class="record-delete danger" type="button" data-policy-id="${esc(item.policy_id)}">Xóa riêng</button></div>
      </div>`).join("") || `<p class="empty">Chưa có quy định.</p>`;
    if (knowledgeList) knowledgeList.innerHTML = visibleKnowledge.map(item => `
      <div class="gate managed-record">
        <b>${esc(item.title)}</b><br><small>${esc(item.body)}<br>tags: ${esc(item.tags.join(", "))}</small>
        <div class="record-actions"><button class="record-edit" type="button" data-knowledge-id="${esc(item.document_id)}">Sửa</button><button class="record-delete danger" type="button" data-knowledge-id="${esc(item.document_id)}">Xóa riêng</button></div>
      </div>`).join("") || `<p class="empty">Chưa có tài liệu.</p>`;
    if (knowledgeList) [...knowledgeList.querySelectorAll(".managed-record")].forEach((node, index) => {
      const item = visibleKnowledge[index];
      if (!item || node.querySelector(".dataset-label")) return;
      const label = document.createElement("div"); label.className = "dataset-label"; label.textContent = `Dataset: ${item.dataset}`; node.prepend(label);
    });
    if (!activeBatch && !policyQuery && policyList) policyList.innerHTML = '<p class="empty">Nhập từ khóa để tìm policy cần sửa hoặc xóa.</p>';
    if (!activeBatch && !knowledgeQuery && knowledgeList) knowledgeList.innerHTML = '<p class="empty">Nhập từ khóa để tìm tài liệu cần sửa hoặc xóa.</p>';
    const ragDataset = document.querySelector("#rag-dataset");
    if (ragDataset) {
      const selected = ragDataset.value;
      const datasets = [...new Set(knowledge.map(item => item.dataset))].sort();
      ragDataset.innerHTML = '<option value="">Tất cả dataset phù hợp</option>' + datasets.map(item => `<option value="${esc(item)}">${esc(item)}</option>`).join("");
      ragDataset.value = datasets.includes(selected) ? selected : "";
    }
    rendering = false;
    bindRecordButtons();
  }

  async function refresh() {
    try {
      [policies, knowledge] = await Promise.all([api("/policies"), api("/knowledge")]);
      render();
    } catch (error) {
      console.error("Knowledge manager:", error);
    }
  }

  function bindRecordButtons() {
    document.querySelectorAll(".record-edit[data-policy-id]").forEach(button => button.onclick = () => {
      editingPolicy = policies.find(item => item.policy_id === button.dataset.policyId);
      if (!editingPolicy) return;
      document.querySelector("#policy-name").value = editingPolicy.name;
      document.querySelector("#policy-category").value = editingPolicy.category;
      document.querySelector("#policy-action").value = editingPolicy.action;
      document.querySelector("#policy-description").value = editingPolicy.description;
      document.querySelector("#policy-terms").value = editingPolicy.trigger_terms.join(", ");
      document.querySelector("#policy-form button").textContent = "Cập nhật policy";
      document.querySelector("#policy-form").scrollIntoView({behavior: "smooth", block: "center"});
    });
    document.querySelectorAll(".record-delete[data-policy-id]").forEach(button => button.onclick = async () => {
      if (!confirm("Xóa riêng quy định này? Các quy định khác không bị ảnh hưởng.")) return;
      try { await api(`/policies/${encodeURIComponent(button.dataset.policyId)}`, {method: "DELETE"}); await refresh(); }
      catch (error) { alert(error.message); }
    });
    document.querySelectorAll(".record-edit[data-knowledge-id]").forEach(button => button.onclick = () => {
      editingKnowledge = knowledge.find(item => item.document_id === button.dataset.knowledgeId);
      if (!editingKnowledge) return;
      document.querySelector("#knowledge-title").value = editingKnowledge.title;
      document.querySelector("#knowledge-dataset").value = editingKnowledge.dataset;
      document.querySelector("#knowledge-body").value = editingKnowledge.body;
      document.querySelector("#knowledge-tags").value = editingKnowledge.tags.join(", ");
      document.querySelector("#knowledge-form button").textContent = "Cập nhật tài liệu";
      document.querySelector("#knowledge-form").scrollIntoView({behavior: "smooth", block: "center"});
    });
    document.querySelectorAll(".record-delete[data-knowledge-id]").forEach(button => button.onclick = async () => {
      if (!confirm("Xóa riêng tài liệu này? Các tài liệu khác không bị ảnh hưởng.")) return;
      try { await api(`/knowledge/${encodeURIComponent(button.dataset.knowledgeId)}`, {method: "DELETE"}); await refresh(); }
      catch (error) { alert(error.message); }
    });
  }

  function replaceForm(id) {
    const oldForm = document.querySelector(id);
    if (!oldForm) return null;
    const form = oldForm.cloneNode(true);
    oldForm.replaceWith(form);
    if (id === "#policy-form") {
      const name = form.querySelector("#policy-name");
      if (name && !form.querySelector("#policy-category")) {
        const category = document.createElement("select"); category.id = "policy-category";
        category.innerHTML = '<option value="other">Khác</option><option value="spam">Spam</option><option value="harassment">Công kích</option><option value="violence">Đe dọa/bạo lực</option>';
        const action = document.createElement("select"); action.id = "policy-action";
        action.innerHTML = '<option value="hold_for_review">Hold for review</option><option value="allow">Allow</option><option value="warn">Warn</option><option value="hide">Hide</option>';
        name.insertAdjacentElement("afterend", action); name.insertAdjacentElement("afterend", category);
      }
    }
    if (id === "#knowledge-form") {
      const title = form.querySelector("#knowledge-title");
      if (title && !form.querySelector("#knowledge-dataset")) {
        const dataset = document.createElement("input"); dataset.id = "knowledge-dataset"; dataset.placeholder = "Dataset: league_of_legends, channel_policy, events";
        title.insertAdjacentElement("afterend", dataset);
      }
    }
    if (id === "#rag-form") {
      const question = form.querySelector("#rag-question");
      if (question && !form.querySelector("#rag-dataset")) {
        const dataset = document.createElement("select"); dataset.id = "rag-dataset";
        dataset.innerHTML = '<option value="">Tất cả dataset phù hợp</option>';
        question.insertAdjacentElement("afterend", dataset);
      }
    }
    return form;
  }

  function bindForms() {
    const policyForm = replaceForm("#policy-form");
    if (policyForm) policyForm.addEventListener("submit", async event => {
      event.preventDefault();
      const form = event.currentTarget;
      const item = editingPolicy;
      const id = item?.policy_id || `POL-CUSTOM-${Date.now()}`;
      try {
        await api(`/policies/${encodeURIComponent(id)}`, {method: "PUT", body: JSON.stringify({
          name: document.querySelector("#policy-name").value,
          description: document.querySelector("#policy-description").value,
          category: document.querySelector("#policy-category").value, action: document.querySelector("#policy-action").value,
          trigger_terms: document.querySelector("#policy-terms").value.split(",").map(value => value.trim()).filter(Boolean), active: true
        })});
        editingPolicy = null; form.reset(); form.querySelector("button").textContent = "Lưu policy"; await refresh(); return;
        editingPolicy = null; event.currentTarget.reset(); event.currentTarget.querySelector("button").textContent = "Lưu policy"; await refresh();
      } catch (error) { alert(error.message); }
    });
    const knowledgeForm = replaceForm("#knowledge-form");
    if (knowledgeForm) knowledgeForm.addEventListener("submit", async event => {
      event.preventDefault();
      const form = event.currentTarget;
      const item = editingKnowledge;
      const id = item?.document_id || `KN-CUSTOM-${Date.now()}`;
      try {
        await api(`/knowledge/${encodeURIComponent(id)}`, {method: "PUT", body: JSON.stringify({
          title: document.querySelector("#knowledge-title").value,
          body: document.querySelector("#knowledge-body").value,
          dataset: document.querySelector("#knowledge-dataset").value.trim() || "general",
          tags: document.querySelector("#knowledge-tags").value.split(",").map(value => value.trim()).filter(Boolean), active: true
        })});
        editingKnowledge = null; form.reset(); form.querySelector("button").textContent = "Lưu tài liệu"; await refresh(); return;
        editingKnowledge = null; event.currentTarget.reset(); event.currentTarget.querySelector("button").textContent = "Lưu tài liệu"; await refresh();
      } catch (error) { alert(error.message); }
    });
    const ragForm = replaceForm("#rag-form");
    if (ragForm) ragForm.addEventListener("submit", async event => {
      event.preventDefault();
      const output = document.querySelector("#rag-result"); output.textContent = "Đang tìm trong dataset...";
      try {
        const dataset = document.querySelector("#rag-dataset").value;
        const data = await api("/rag/ask", {method: "POST", body: JSON.stringify({question: document.querySelector("#rag-question").value, dataset: dataset || null})});
        output.innerHTML = `<p>${esc(data.answer).replaceAll("\n", "<br>")}</p><small>Dataset: ${esc(dataset || "all")} · Sources: ${esc(data.sources.map(source => source.title).join(", "))}</small>`;
      } catch (error) { output.textContent = error.message; }
    });
    const importForm = replaceForm("#knowledge-import-form");
    if (importForm) importForm.addEventListener("submit", async event => {
      event.preventDefault();
      const form = event.currentTarget;
      const file = document.querySelector("#knowledge-file").files[0];
      const output = document.querySelector("#knowledge-import-result");
      if (!file) return;
      output.innerHTML = '<p class="notice">Đang đọc, bóc tách và chuẩn hóa tài liệu...</p>';
      try {
        const bytes = new Uint8Array(await file.arrayBuffer()); let binary = "";
        for (let index = 0; index < bytes.length; index += 0x8000) binary += String.fromCharCode(...bytes.subarray(index, index + 0x8000));
        const response = await fetch("/api/v1/knowledge/import", {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify({filename: file.name, content_base64: btoa(binary), target: document.querySelector("#knowledge-import-target").value})});
        const data = await response.json(); if (!response.ok) throw new Error(data.detail || "Import failed");
        activeBatch = {knowledgeIds: new Set(data.knowledge_ids || []), policyIds: new Set(data.policy_ids || [])};
        policyQuery = "";
        knowledgeQuery = "";
        const warnings = data.warnings?.length ? `<br><small>${esc(data.warnings.join(" | "))}</small>` : "";
        output.innerHTML = `<p class="notice success">Đã xử lý ${data.normalized_count} bản ghi bằng ${esc(data.normalized_by)}. Bỏ qua: ${data.skipped_count}.${warnings}</p>`;
        await refresh(); form.reset(); return;
      } catch (error) { output.innerHTML = `<p class="notice error">${esc(error.message)}</p>`; }
    });
  }

  function boot() {
    bindForms();
    const policySearch = document.querySelector("#policy-search");
    const knowledgeSearch = document.querySelector("#knowledge-search");
    policySearch?.addEventListener("input", event => { policyQuery = event.target.value.trim().toLowerCase(); render(); });
    knowledgeSearch?.addEventListener("input", event => { knowledgeQuery = event.target.value.trim().toLowerCase(); render(); });
    refresh();
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", boot); else boot();
})();
