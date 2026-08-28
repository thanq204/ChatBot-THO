import { useCallback, useMemo, useRef, useState } from "react";
import { useQueries, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  MagnifyingGlass,
  PencilSimple,
  Trash,
  FloppyDisk,
  Plus,
  UploadSimple,
  PaperPlaneRight,
  CaretRight,
  CaretDown,
  BookOpen,
  Scales,
  Robot,
  FileArrowUp,
  Sparkle,
  ShieldWarning,
  ShieldCheck,
  Tag,
  Check,
  X,
  FileText,
  ArrowsClockwise,
  CheckCircle,
} from "@phosphor-icons/react";
import Card from "../components/Card.jsx";
import Modal from "../components/Modal.jsx";
import Badge from "../components/Badge.jsx";
import Pagination, { usePagination } from "../components/Pagination.jsx";
import LoadMore, { useLoadMore } from "../components/LoadMore.jsx";
import { SkeletonBlock, SkeletonLine } from "../components/Skeleton.jsx";
import { ErrorState, EmptyState } from "../components/StatePanels.jsx";
import { ops, fileToBase64 } from "../api/client.js";
import { queryKeys } from "../lib/queryClient.js";
import { relativeTime } from "../lib/format.js";
import { categoryLabel, CATEGORY_COLORS, decisionLabel, DECISION_COLORS } from "../lib/taxonomy.js";

const BLANK_DOC = { title: "", dataset: "general", body: "", tags: "" };
const BLANK_POLICY = {
  name: "",
  description: "",
  category: "spam",
  action: "warn",
  trigger_terms: "",
  active: true,
};

const DOC_PAGE_SIZE_OPTIONS = [10, 20, 50];
const IMPORT_STEP = 6;

const QUICK_PROMPTS = [
  "Quy định về an toàn giao dịch mua bán?",
  "Khi nào thành viên bị cấm phát ngôn?",
  "Lịch trình sự kiện Anime sắp tới là khi nào?",
  "Làm sao để liên hệ trực tiếp với Ban Quản Trị?",
  "Chính sách xử lý tài khoản spam liên kết?",
];

const POLICY_CATEGORIES = [
  { value: "", label: "Tất cả danh mục" },
  { value: "spam", label: "Spam / Quảng cáo" },
  { value: "toxic", label: "Công kích / Xúc phạm" },
  { value: "scam", label: "Lừa đảo / Phishing" },
  { value: "harassment", label: "Quấy rối" },
  { value: "violence", label: "Bạo lực / Đe doạ" },
  { value: "other", label: "Khác" },
];

const POLICY_ACTIONS = [
  { value: "allow", label: "Cho phép (Allow)" },
  { value: "warn", label: "Cảnh báo (Warn)" },
  { value: "hide", label: "Ẩn tin nhắn (Hide)" },
  { value: "hold_for_review", label: "Giữ lại chờ duyệt (Hold)" },
];

function matches(item, query) {
  return [item.title, item.body, item.dataset, (item.tags || []).join(" ")]
    .join(" ")
    .toLowerCase()
    .includes(query);
}

export default function SettingsPage() {
  const queryClient = useQueryClient();
  const [activeTab, setActiveTab] = useState("documents"); // "documents" | "policies" | "rag_test" | "import"
  const [actionError, setActionError] = useState(null);

  // Queries
  const knowledgeQuery = useQuery({ queryKey: queryKeys.knowledge, queryFn: () => ops.knowledge() });
  const policiesQuery = useQuery({ queryKey: queryKeys.policies, queryFn: ops.policies });
  const importsQuery = useQuery({
    queryKey: queryKeys.knowledgeImports,
    queryFn: ops.knowledgeImports,
    retry: false,
  });

  const knowledge = knowledgeQuery.data ?? [];
  const policies = policiesQuery.data ?? [];
  const imports = importsQuery.data ?? [];
  const loading = knowledgeQuery.isPending || policiesQuery.isPending;

  // ----------------------------------------------------
  // Tab 1: Documents State & Handlers
  // ----------------------------------------------------
  const [docQuery, setDocQuery] = useState("");
  const [datasetFilter, setDatasetFilter] = useState("");
  const [docModalOpen, setDocModalOpen] = useState(false);
  const [editingDocId, setEditingDocId] = useState(null);
  const [docForm, setDocForm] = useState(BLANK_DOC);
  const [docSaving, setDocSaving] = useState(false);
  const [docFormError, setDocFormError] = useState("");
  const [selectedDocIds, setSelectedDocIds] = useState(() => new Set());
  const [expandedDocIds, setExpandedDocIds] = useState(() => new Set());
  const [pageSize, setPageSize] = useState(10);
  const [bulkDeleting, setBulkDeleting] = useState(false);

  // Extract unique dataset names
  const availableDatasets = useMemo(() => {
    const set = new Set(["general"]);
    knowledge.forEach((d) => {
      if (d.dataset) set.add(d.dataset);
    });
    return Array.from(set);
  }, [knowledge]);

  const visibleDocs = useMemo(() => {
    let list = knowledge;
    if (datasetFilter) {
      list = list.filter((item) => (item.dataset || "general") === datasetFilter);
    }
    if (docQuery.trim()) {
      const q = docQuery.toLowerCase().trim();
      list = list.filter((item) => matches(item, q));
    }
    return list;
  }, [knowledge, datasetFilter, docQuery]);

  const paged = usePagination(visibleDocs, pageSize, `${docQuery}-${datasetFilter}`);
  const pageRows = paged.slice;
  const allPageSelected = pageRows.length > 0 && pageRows.every((item) => selectedDocIds.has(item.document_id));

  const toggleSelectDoc = (id) => {
    setSelectedDocIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const toggleSelectAllDocs = () => {
    setSelectedDocIds((prev) => {
      const next = new Set(prev);
      for (const item of pageRows) {
        if (allPageSelected) next.delete(item.document_id);
        else next.add(item.document_id);
      }
      return next;
    });
  };

  const toggleExpandDoc = (id) => {
    setExpandedDocIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const startCreateDoc = () => {
    setEditingDocId(null);
    setDocForm(BLANK_DOC);
    setDocFormError("");
    setDocModalOpen(true);
  };

  const startEditDoc = (item) => {
    setEditingDocId(item.document_id);
    setDocForm({
      title: item.title,
      dataset: item.dataset || "general",
      body: item.body || "",
      tags: (item.tags || []).join(", "),
    });
    setDocFormError("");
    setDocModalOpen(true);
  };

  const handleSaveDoc = async (e) => {
    e.preventDefault();
    setDocFormError("");
    setDocSaving(true);
    try {
      await ops.saveKnowledge(editingDocId || `KN-${Date.now()}`, {
        title: docForm.title,
        body: docForm.body,
        dataset: docForm.dataset.trim() || "general",
        tags: docForm.tags.split(",").map((v) => v.trim()).filter(Boolean),
        active: true,
      });
      setDocModalOpen(false);
      queryClient.invalidateQueries({ queryKey: queryKeys.knowledge });
    } catch (err) {
      setDocFormError(err.message);
    } finally {
      setDocSaving(false);
    }
  };

  const handleDeleteDoc = async (item) => {
    if (!window.confirm(`Bạn có chắc muốn xóa tài liệu "${item.title}"?`)) return;
    try {
      await ops.deleteKnowledge(item.document_id);
      queryClient.invalidateQueries({ queryKey: queryKeys.knowledge });
    } catch (err) {
      setActionError(err.message);
    }
  };

  const handleBulkDeleteDocs = async () => {
    const ids = Array.from(selectedDocIds);
    if (!ids.length) return;
    if (!window.confirm(`Xóa ${ids.length} tài liệu đã chọn?`)) return;
    setBulkDeleting(true);
    try {
      await Promise.all(ids.map((id) => ops.deleteKnowledge(id)));
      setSelectedDocIds(new Set());
      queryClient.invalidateQueries({ queryKey: queryKeys.knowledge });
    } catch (err) {
      setActionError(err.message);
    } finally {
      setBulkDeleting(false);
    }
  };

  // ----------------------------------------------------
  // Tab 2: Policies State & Handlers
  // ----------------------------------------------------
  const [policyQuery, setPolicyQuery] = useState("");
  const [policyCatFilter, setPolicyCatFilter] = useState("");
  const [policyModalOpen, setPolicyModalOpen] = useState(false);
  const [editingPolicyId, setEditingPolicyId] = useState(null);
  const [policyForm, setPolicyForm] = useState(BLANK_POLICY);
  const [policySaving, setPolicySaving] = useState(false);
  const [policyFormError, setPolicyFormError] = useState("");

  const visiblePolicies = useMemo(() => {
    let list = policies;
    if (policyCatFilter) {
      list = list.filter((p) => p.category === policyCatFilter);
    }
    if (policyQuery.trim()) {
      const q = policyQuery.toLowerCase().trim();
      list = list.filter(
        (p) =>
          p.name.toLowerCase().includes(q) ||
          p.description.toLowerCase().includes(q) ||
          (p.trigger_terms || []).some((t) => t.toLowerCase().includes(q)),
      );
    }
    return list;
  }, [policies, policyCatFilter, policyQuery]);

  const startCreatePolicy = () => {
    setEditingPolicyId(null);
    setPolicyForm(BLANK_POLICY);
    setPolicyFormError("");
    setPolicyModalOpen(true);
  };

  const startEditPolicy = (p) => {
    setEditingPolicyId(p.policy_id);
    setPolicyForm({
      name: p.name,
      description: p.description,
      category: p.category || "spam",
      action: p.action || "warn",
      trigger_terms: (p.trigger_terms || []).join(", "),
      active: p.active ?? true,
    });
    setPolicyFormError("");
    setPolicyModalOpen(true);
  };

  const handleSavePolicy = async (e) => {
    e.preventDefault();
    setPolicyFormError("");
    setPolicySaving(true);
    try {
      await ops.savePolicy(editingPolicyId || `POL-${Date.now()}`, {
        name: policyForm.name,
        description: policyForm.description,
        category: policyForm.category,
        action: policyForm.action,
        trigger_terms: policyForm.trigger_terms
          .split(",")
          .map((v) => v.trim())
          .filter(Boolean),
        active: policyForm.active,
      });
      setPolicyModalOpen(false);
      queryClient.invalidateQueries({ queryKey: queryKeys.policies });
    } catch (err) {
      setPolicyFormError(err.message);
    } finally {
      setPolicySaving(false);
    }
  };

  const handleTogglePolicyActive = async (p) => {
    try {
      await ops.savePolicy(p.policy_id, {
        name: p.name,
        description: p.description,
        category: p.category,
        action: p.action,
        trigger_terms: p.trigger_terms || [],
        active: !p.active,
      });
      queryClient.invalidateQueries({ queryKey: queryKeys.policies });
    } catch (err) {
      setActionError(err.message);
    }
  };

  const handleDeletePolicy = async (p) => {
    if (!window.confirm(`Bạn có chắc muốn xóa chính sách "${p.name}"?`)) return;
    try {
      await ops.deletePolicy(p.policy_id);
      queryClient.invalidateQueries({ queryKey: queryKeys.policies });
    } catch (err) {
      setActionError(err.message);
    }
  };

  // ----------------------------------------------------
  // Tab 3: RAG Interactive Playground State & Handlers
  // ----------------------------------------------------
  const [ragQuestion, setRagQuestion] = useState("");
  const [ragDataset, setRagDataset] = useState("");
  const [ragState, setRagState] = useState({ status: "idle", data: null, error: "" });

  const handleAskRAG = async (e) => {
    e?.preventDefault();
    if (!ragQuestion.trim()) return;
    setRagState({ status: "loading", data: null, error: "" });
    try {
      const res = await ops.ask(ragQuestion.trim(), ragDataset || undefined);
      setRagState({ status: "done", data: res, error: "" });
    } catch (err) {
      setRagState({ status: "error", data: null, error: err.message });
    }
  };

  // ----------------------------------------------------
  // Tab 4: Drag & Drop File Import State & Handlers
  // ----------------------------------------------------
  const fileInputRef = useRef(null);
  const [importTarget, setImportTarget] = useState("auto");
  const [importState, setImportState] = useState(null);
  const [importing, setImporting] = useState(false);
  const [isDragging, setIsDragging] = useState(false);
  const importHistoryFeed = useLoadMore(imports, IMPORT_STEP);

  const handleFileUpload = async (file) => {
    if (!file) return;
    setImporting(true);
    setImportState({ tone: "", text: `Đang đọc và chuẩn hóa canonical file ${file.name}...` });
    try {
      const data = await ops.importKnowledge({
        filename: file.name,
        content_base64: await fileToBase64(file),
        target: importTarget,
      });
      setImportState({
        tone: "success",
        text: `Nhập thành công! Đã chuẩn hóa ${data.normalized_count} bản ghi (${data.normalized_by}). Bỏ qua: ${data.skipped_count}.${
          data.warnings?.length ? ` Cảnh báo: ${data.warnings.join(" | ")}` : ""
        }`,
      });
      if (fileInputRef.current) fileInputRef.current.value = "";
      queryClient.invalidateQueries({ queryKey: queryKeys.knowledge });
      queryClient.invalidateQueries({ queryKey: queryKeys.policies });
      queryClient.invalidateQueries({ queryKey: queryKeys.knowledgeImports });
    } catch (err) {
      setImportState({ tone: "error", text: err.message });
    } finally {
      setImporting(false);
    }
  };

  return (
    <div className="page-grid">
      {/* 1. Header: Command Center & Stats Banner */}
      <div className="span-12">
        <div className="overview-header" style={{ borderBottom: "none", paddingBottom: 6 }}>
          <div className="overview-header__main">
            <div className="overview-header__title-row">
              <h1 className="overview-header__title">Kho Tri thức & Chính sách AI</h1>
              <span className="overview-header__live-tag">
                <span className="live-pulse" />
                RAG Engine & Semantic Gate
              </span>
            </div>
            <p className="overview-header__desc">
              Quản lý tài liệu huấn luyện RAG, định nghĩa quy tắc kiểm duyệt nội dung và kiểm thử độ chính xác của AI.
            </p>
          </div>

          <div className="overview-header__controls">
            <button
              type="button"
              className="btn btn--ghost"
              onClick={() => {
                queryClient.invalidateQueries();
              }}
              title="Làm mới dữ liệu"
            >
              <ArrowsClockwise size={14} className={loading ? "spin-icon" : undefined} />
              Làm mới
            </button>
          </div>
        </div>

        {/* 4 Mini Stat Cards */}
        <div className="knowledge-stats-summary">
          <div className="queue-stat-card">
            <div className="queue-stat-card__icon queue-stat-card__icon--resolved">
              <BookOpen size={20} weight="fill" />
            </div>
            <div className="queue-stat-card__body">
              <span className="queue-stat-card__value">{knowledge.length}</span>
              <span className="queue-stat-card__label">Tài liệu tri thức RAG</span>
            </div>
          </div>

          <div className="queue-stat-card">
            <div className="queue-stat-card__icon queue-stat-card__icon--monitoring">
              <Tag size={20} weight="fill" />
            </div>
            <div className="queue-stat-card__body">
              <span className="queue-stat-card__value">{availableDatasets.length}</span>
              <span className="queue-stat-card__label">Bộ Dataset phân loại</span>
            </div>
          </div>

          <div className="queue-stat-card">
            <div className="queue-stat-card__icon queue-stat-card__icon--critical">
              <Scales size={20} weight="fill" />
            </div>
            <div className="queue-stat-card__body">
              <span className="queue-stat-card__value">{policies.filter((p) => p.active).length} / {policies.length}</span>
              <span className="queue-stat-card__label">Chính sách AI đang bật</span>
            </div>
          </div>

          <div className="queue-stat-card">
            <div className="queue-stat-card__icon queue-stat-card__icon--reports">
              <FileArrowUp size={20} weight="fill" />
            </div>
            <div className="queue-stat-card__body">
              <span className="queue-stat-card__value">{imports.length}</span>
              <span className="queue-stat-card__label">Lần nhập file hàng loạt</span>
            </div>
          </div>
        </div>

        {/* Navigation Tabs Bar */}
        <div className="knowledge-nav-tabs" role="tablist">
          <button
            type="button"
            className={`knowledge-nav-tab${activeTab === "documents" ? " is-active" : ""}`}
            onClick={() => setActiveTab("documents")}
          >
            <BookOpen size={16} weight={activeTab === "documents" ? "fill" : "regular"} />
            Tài liệu Tri thức RAG
            <span className="knowledge-nav-tab__count">{knowledge.length}</span>
          </button>

          <button
            type="button"
            className={`knowledge-nav-tab${activeTab === "policies" ? " is-active" : ""}`}
            onClick={() => setActiveTab("policies")}
          >
            <Scales size={16} weight={activeTab === "policies" ? "fill" : "regular"} />
            Quy tắc & Chính sách AI
            <span className="knowledge-nav-tab__count">{policies.length}</span>
          </button>

          <button
            type="button"
            className={`knowledge-nav-tab${activeTab === "rag_test" ? " is-active" : ""}`}
            onClick={() => setActiveTab("rag_test")}
          >
            <Robot size={16} weight={activeTab === "rag_test" ? "fill" : "regular"} />
            Thử nghiệm Hỏi RAG
          </button>

          <button
            type="button"
            className={`knowledge-nav-tab${activeTab === "import" ? " is-active" : ""}`}
            onClick={() => setActiveTab("import")}
          >
            <FileArrowUp size={16} weight={activeTab === "import" ? "fill" : "regular"} />
            Tải file & Lịch sử
            <span className="knowledge-nav-tab__count">{imports.length}</span>
          </button>
        </div>
      </div>

      {actionError && (
        <div className="span-12">
          <ErrorState message={actionError} onRetry={() => setActionError(null)} />
        </div>
      )}

      {/* =========================================================================
          TAB 1: TÀI LIỆU TRI THỨC RAG
          ========================================================================= */}
      {activeTab === "documents" && (
        <div className="span-12" style={{ display: "flex", flexDirection: "column", gap: 14 }}>
          {/* Toolbar */}
          <div className="community-toolbar">
            <div className="community-toolbar__top">
              <div className="community-search-box">
                <MagnifyingGlass size={16} className="community-search-box__icon" />
                <input
                  type="text"
                  className="community-search-box__input"
                  placeholder="Tìm tài liệu theo tiêu đề, nội dung, dataset, thẻ tag..."
                  value={docQuery}
                  onChange={(e) => setDocQuery(e.target.value)}
                />
                {docQuery && (
                  <button
                    type="button"
                    className="community-search-box__clear"
                    onClick={() => setDocQuery("")}
                  >
                    <X size={14} />
                  </button>
                )}
              </div>

              <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                {selectedDocIds.size > 0 && (
                  <button
                    type="button"
                    className="btn btn--danger"
                    onClick={handleBulkDeleteDocs}
                    disabled={bulkDeleting}
                  >
                    <Trash size={14} />
                    {bulkDeleting ? "Đang xoá..." : `Xoá đã chọn (${selectedDocIds.size})`}
                  </button>
                )}
                <button type="button" className="btn btn--primary" onClick={startCreateDoc}>
                  <Plus size={14} weight="bold" /> Thêm tài liệu
                </button>
              </div>
            </div>

            <div className="community-toolbar__filters">
              <div className="community-filter-group">
                <span className="muted small" style={{ marginRight: 2 }}>Dataset:</span>
                <button
                  type="button"
                  className={`community-pill-btn${datasetFilter === "" ? " is-active" : ""}`}
                  onClick={() => setDatasetFilter("")}
                >
                  Tất cả ({knowledge.length})
                </button>
                {availableDatasets.map((ds) => (
                  <button
                    key={ds}
                    type="button"
                    className={`community-pill-btn${datasetFilter === ds ? " is-active" : ""}`}
                    onClick={() => setDatasetFilter(ds)}
                  >
                    #{ds} ({knowledge.filter((d) => (d.dataset || "general") === ds).length})
                  </button>
                ))}
              </div>

              {pageRows.length > 0 && (
                <label className="select-all" style={{ fontSize: 12 }}>
                  <input
                    type="checkbox"
                    checked={allPageSelected}
                    onChange={toggleSelectAllDocs}
                  />
                  Chọn cả trang ({pageRows.length})
                </label>
              )}
            </div>
          </div>

          {/* Document Cards */}
          {knowledgeQuery.isPending && (
            <div className="stack">
              <SkeletonBlock height={140} />
              <SkeletonBlock height={140} />
            </div>
          )}

          {!knowledgeQuery.isPending && visibleDocs.length === 0 && (
            <Card>
              <EmptyState
                message={
                  docQuery
                    ? `Không tìm thấy tài liệu nào khớp "${docQuery}".`
                    : "Chưa có tài liệu tri thức nào trong kho."
                }
                action={
                  <button type="button" className="btn btn--primary" onClick={startCreateDoc}>
                    <Plus size={14} weight="bold" /> Thêm tài liệu đầu tiên
                  </button>
                }
              />
            </Card>
          )}

          {!knowledgeQuery.isPending && visibleDocs.length > 0 && (
            <>
              <div className="knowledge-card-grid">
                {pageRows.map((item) => {
                  const expanded = expandedDocIds.has(item.document_id);
                  const ds = item.dataset || "general";
                  const isSelected = selectedDocIds.has(item.document_id);

                  return (
                    <div
                      key={item.document_id}
                      className={`knowledge-card${isSelected ? " is-selected" : ""}`}
                      style={{
                        borderColor: isSelected ? "var(--accent-solid)" : undefined,
                      }}
                    >
                      <div className="knowledge-card__head">
                        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                          <input
                            type="checkbox"
                            checked={isSelected}
                            onChange={() => toggleSelectDoc(item.document_id)}
                            aria-label={`Chọn tài liệu ${item.title}`}
                          />
                          <span
                            className={`dataset-badge dataset-badge--${
                              ds.includes("event")
                                ? "events"
                                : ds.includes("rule")
                                ? "rules"
                                : ds.includes("qa") || ds.includes("faq")
                                ? "qa"
                                : "general"
                            }`}
                          >
                            #{ds}
                          </span>
                        </div>
                        <span className="muted small">{relativeTime(item.updated_at)}</span>
                      </div>

                      <div>
                        <h3 className="knowledge-card__title">{item.title}</h3>
                        <div
                          className="knowledge-card__body"
                          style={{
                            maxHeight: expanded ? "none" : 100,
                            marginTop: 8,
                          }}
                        >
                          {item.body}
                        </div>
                      </div>

                      {item.tags && item.tags.length > 0 && (
                        <div className="knowledge-card__tags">
                          {item.tags.map((tag) => (
                            <span key={tag} className="chip" style={{ fontSize: 11 }}>
                              #{tag}
                            </span>
                          ))}
                        </div>
                      )}

                      <div className="knowledge-card__foot">
                        <button
                          type="button"
                          className="btn btn--ghost"
                          style={{ padding: "3px 8px", fontSize: 11.5 }}
                          onClick={() => toggleExpandDoc(item.document_id)}
                        >
                          {expanded ? <CaretDown size={12} /> : <CaretRight size={12} />}
                          {expanded ? "Thu gọn" : "Xem toàn bộ"} ({(item.body || "").length} ký tự)
                        </button>

                        <div style={{ display: "flex", gap: 6 }}>
                          <button
                            type="button"
                            className="btn btn--ghost"
                            style={{ padding: "4px 8px", fontSize: 12 }}
                            onClick={() => startEditDoc(item)}
                            title="Chỉnh sửa tài liệu"
                          >
                            <PencilSimple size={13} /> Sửa
                          </button>
                          <button
                            type="button"
                            className="btn btn--ghost"
                            style={{ padding: "4px 8px", fontSize: 12, color: "var(--sev-critical)" }}
                            onClick={() => handleDeleteDoc(item)}
                            title="Xóa tài liệu"
                          >
                            <Trash size={13} />
                          </button>
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>

              <Pagination
                page={paged.page}
                pageCount={paged.pageCount}
                onPageChange={paged.setPage}
                from={paged.from}
                to={paged.to}
                total={paged.total}
                unit="tài liệu"
                pageSize={pageSize}
                pageSizeOptions={DOC_PAGE_SIZE_OPTIONS}
                onPageSizeChange={setPageSize}
              />
            </>
          )}
        </div>
      )}

      {/* =========================================================================
          TAB 2: QUY TẮC & CHÍNH SÁCH AI (POLICIES)
          ========================================================================= */}
      {activeTab === "policies" && (
        <div className="span-12" style={{ display: "flex", flexDirection: "column", gap: 14 }}>
          {/* Toolbar */}
          <div className="community-toolbar">
            <div className="community-toolbar__top">
              <div className="community-search-box">
                <MagnifyingGlass size={16} className="community-search-box__icon" />
                <input
                  type="text"
                  className="community-search-box__input"
                  placeholder="Tìm chính sách theo tên, mô tả, từ khóa kích hoạt..."
                  value={policyQuery}
                  onChange={(e) => setPolicyQuery(e.target.value)}
                />
                {policyQuery && (
                  <button
                    type="button"
                    className="community-search-box__clear"
                    onClick={() => setPolicyQuery("")}
                  >
                    <X size={14} />
                  </button>
                )}
              </div>

              <button type="button" className="btn btn--primary" onClick={startCreatePolicy}>
                <Plus size={14} weight="bold" /> Thêm quy tắc mới
              </button>
            </div>

            <div className="community-toolbar__filters">
              <div className="community-filter-group">
                <span className="muted small" style={{ marginRight: 2 }}>Phân loại:</span>
                {POLICY_CATEGORIES.map((cat) => (
                  <button
                    key={cat.value}
                    type="button"
                    className={`community-pill-btn${policyCatFilter === cat.value ? " is-active" : ""}`}
                    onClick={() => setPolicyCatFilter(cat.value)}
                  >
                    {cat.label}
                  </button>
                ))}
              </div>
            </div>
          </div>

          {/* Policy Cards Grid */}
          {policiesQuery.isPending && (
            <div className="stack">
              <SkeletonBlock height={160} />
              <SkeletonBlock height={160} />
            </div>
          )}

          {!policiesQuery.isPending && visiblePolicies.length === 0 && (
            <Card>
              <EmptyState
                message={
                  policyQuery
                    ? `Không tìm thấy chính sách nào khớp "${policyQuery}".`
                    : "Chưa có quy tắc chính sách kiểm duyệt nào."
                }
                action={
                  <button type="button" className="btn btn--primary" onClick={startCreatePolicy}>
                    <Plus size={14} weight="bold" /> Tạo quy tắc đầu tiên
                  </button>
                }
              />
            </Card>
          )}

          {!policiesQuery.isPending && visiblePolicies.length > 0 && (
            <div className="policy-card-grid">
              {visiblePolicies.map((p) => {
                const actionColor = DECISION_COLORS[p.action] || "var(--accent-solid)";
                const catColor = CATEGORY_COLORS[p.category] || "var(--sev-medium)";

                return (
                  <div
                    key={p.policy_id}
                    className={`policy-card${!p.active ? " is-inactive" : ""}`}
                  >
                    <div className="policy-card__top">
                      <Badge tone={catColor}>{categoryLabel(p.category)}</Badge>
                      <Badge tone={actionColor}>
                        Hành động: {decisionLabel(p.action)}
                      </Badge>
                    </div>

                    <div className="policy-card__title-row">
                      <h3 className="policy-card__name">{p.name}</h3>
                      <span className="muted small">v{p.version || 1}</span>
                    </div>

                    <p className="policy-card__desc">{p.description}</p>

                    {p.trigger_terms && p.trigger_terms.length > 0 && (
                      <div className="policy-card__terms">
                        <span className="policy-card__terms-label">Từ khóa kích hoạt:</span>
                        <div className="policy-card__terms-cloud">
                          {p.trigger_terms.map((term) => (
                            <span key={term} className="policy-term-pill">
                              {term}
                            </span>
                          ))}
                        </div>
                      </div>
                    )}

                    <div className="policy-card__foot">
                      <label className="switch-toggle" title="Bật/Tắt chính sách">
                        <input
                          type="checkbox"
                          checked={p.active}
                          onChange={() => handleTogglePolicyActive(p)}
                        />
                        <span className="switch-slider" />
                        <span>{p.active ? "Đang bật" : "Đã tắt"}</span>
                      </label>

                      <div style={{ display: "flex", gap: 6 }}>
                        <button
                          type="button"
                          className="btn btn--ghost"
                          style={{ padding: "4px 8px", fontSize: 12 }}
                          onClick={() => startEditPolicy(p)}
                        >
                          <PencilSimple size={13} /> Sửa
                        </button>
                        <button
                          type="button"
                          className="btn btn--ghost"
                          style={{ padding: "4px 8px", fontSize: 12, color: "var(--sev-critical)" }}
                          onClick={() => handleDeletePolicy(p)}
                        >
                          <Trash size={13} />
                        </button>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}

      {/* =========================================================================
          TAB 3: THỬ NGHIỆM HỎI ĐÁP RAG AI (RAG PLAYGROUND)
          ========================================================================= */}
      {activeTab === "rag_test" && (
        <div className="span-12 rag-playground-grid">
          {/* Left Column: Question Form */}
          <Card title="Thử nghiệm Hỏi RAG Engine">
            <form className="stack" onSubmit={handleAskRAG}>
              <label className="field">
                Câu hỏi thử nghiệm
                <textarea
                  value={ragQuestion}
                  onChange={(e) => setRagQuestion(e.target.value)}
                  rows={4}
                  maxLength={2000}
                  placeholder="Nhập câu hỏi để kiểm tra khả năng trích xuất tri thức từ kho tài liệu..."
                  required
                />
              </label>

              <label className="field">
                Lọc Dataset cụ thể (tùy chọn)
                <select value={ragDataset} onChange={(e) => setRagDataset(e.target.value)}>
                  <option value="">Tất cả datasets (Toàn bộ kho tri thức)</option>
                  {availableDatasets.map((ds) => (
                    <option key={ds} value={ds}>
                      #{ds}
                    </option>
                  ))}
                </select>
              </label>

              <div>
                <span className="muted small" style={{ fontWeight: 600 }}>Gợi ý câu hỏi nhanh:</span>
                <div className="quick-prompt-chips">
                  {QUICK_PROMPTS.map((prompt) => (
                    <button
                      key={prompt}
                      type="button"
                      className="quick-prompt-chip"
                      onClick={() => setRagQuestion(prompt)}
                    >
                      {prompt}
                    </button>
                  ))}
                </div>
              </div>

              <div className="form-actions" style={{ marginTop: 8 }}>
                <button
                  type="submit"
                  className="btn btn--primary"
                  disabled={ragState.status === "loading" || !ragQuestion.trim()}
                >
                  <PaperPlaneRight size={14} weight="fill" />
                  {ragState.status === "loading" ? "Đang trích xuất & suy luận..." : "Hỏi AI Knowledge Hub"}
                </button>
              </div>
            </form>
          </Card>

          {/* Right Column: AI Output & Source Citations */}
          <Card title="Kết quả Trích xuất & Câu trả lời AI">
            {ragState.status === "idle" && (
              <EmptyState message="Nhập câu hỏi ở bên trái và bấm 'Hỏi AI Knowledge Hub' để xem kết quả trích xuất RAG." />
            )}

            {ragState.status === "loading" && (
              <div className="stack">
                <SkeletonLine width="60%" />
                <SkeletonBlock height={140} />
                <SkeletonLine width="40%" />
              </div>
            )}

            {ragState.status === "error" && (
              <ErrorState message={ragState.error} onRetry={handleAskRAG} />
            )}

            {ragState.status === "done" && ragState.data && (
              <div className="stack">
                <div className="chat-bubble chat-bubble--discord" style={{ width: "100%" }}>
                  <div className="chat-bubble__avatar">AI</div>
                  <div className="chat-bubble__body">
                    <div className="chat-bubble__meta">
                      <span className="chat-bubble__author">AI Assistant (RAG Pipeline)</span>
                      <span className="chat-bubble__platform-tag">
                        {ragState.data.model_used || "rag-retrieval"}
                      </span>
                    </div>
                    <p className="chat-bubble__text" style={{ whiteSpace: "pre-wrap" }}>
                      {ragState.data.answer}
                    </p>
                  </div>
                </div>

                {/* Sources list */}
                {ragState.data.sources && ragState.data.sources.length > 0 && (
                  <div style={{ marginTop: 10 }}>
                    <span className="section-heading" style={{ fontSize: 13, marginBottom: 8, display: "block" }}>
                      📑 Tài liệu nguồn trích xuất ({ragState.data.sources.length} tài liệu)
                    </span>
                    <div className="rag-sources-list">
                      {ragState.data.sources.map((src) => (
                        <div key={src.document_id} className="rag-source-item">
                          <div className="rag-source-item__head">
                            <span className="rag-source-item__title">{src.title}</span>
                            <span className="dataset-badge" style={{ fontSize: 10 }}>
                              #{src.dataset || "general"}
                            </span>
                          </div>
                          <p className="muted small" style={{ lineClamp: 3, WebkitLineClamp: 3, display: "-webkit-box", WebkitBoxOrient: "vertical", overflow: "hidden" }}>
                            {src.body}
                          </p>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            )}
          </Card>
        </div>
      )}

      {/* =========================================================================
          TAB 4: NHẬP FILE HÀNG LOẠT & LỊCH SỬ IMPORT
          ========================================================================= */}
      {activeTab === "import" && (
        <div className="span-12 page-grid__row">
          {/* Left: Drag and Drop Upload */}
          <Card title="Nhập File Tài liệu Hàng loạt" className="span-6">
            <p className="muted small">
              Hệ thống tự động chuẩn hóa canonical, bóc tách cấu trúc và lưu vào kho tri thức RAG hoặc chính sách AI.
            </p>

            <div
              className={`drag-drop-zone${isDragging ? " is-dragging" : ""}`}
              onDragOver={(e) => {
                e.preventDefault();
                setIsDragging(true);
              }}
              onDragLeave={() => setIsDragging(false)}
              onDrop={(e) => {
                e.preventDefault();
                setIsDragging(false);
                const file = e.dataTransfer?.files?.[0];
                if (file) handleFileUpload(file);
              }}
              onClick={() => fileInputRef.current?.click()}
            >
              <UploadSimple size={36} color="var(--accent-solid)" />
              <div>
                <strong style={{ fontSize: 14, color: "var(--text-primary)" }}>
                  Kéo thả file vào đây hoặc bấm để duyệt
                </strong>
                <p className="muted small" style={{ marginTop: 2 }}>
                  Dung lượng tối đa 5 MB mỗi file.
                </p>
              </div>

              <div className="drag-drop-zone__formats">
                <span className="file-format-pill">PDF</span>
                <span className="file-format-pill">DOCX</span>
                <span className="file-format-pill">XLSX</span>
                <span className="file-format-pill">CSV / TSV</span>
                <span className="file-format-pill">JSON / JSONL</span>
                <span className="file-format-pill">YAML</span>
                <span className="file-format-pill">MARKDOWN</span>
                <span className="file-format-pill">TXT</span>
              </div>

              <input
                ref={fileInputRef}
                type="file"
                style={{ display: "none" }}
                accept=".json,.jsonl,.csv,.tsv,.xlsx,.yaml,.yml,.html,.htm,.md,.markdown,.txt,.docx,.pdf"
                onChange={(e) => {
                  const file = e.target.files?.[0];
                  if (file) handleFileUpload(file);
                }}
              />
            </div>

            <div style={{ marginTop: 14 }}>
              <label className="field">
                Đích đến sau khi chuẩn hóa:
                <select value={importTarget} onChange={(e) => setImportTarget(e.target.value)}>
                  <option value="auto">Tự động nhận diện (Tài liệu hoặc Quy tắc)</option>
                  <option value="knowledge">Kho tài liệu tri thức RAG</option>
                  <option value="policy">Bộ quy tắc chính sách kiểm duyệt</option>
                </select>
              </label>
            </div>

            {importState && (
              <div
                style={{
                  marginTop: 10,
                  padding: "10px 12px",
                  borderRadius: "var(--radius-control)",
                  fontSize: 12.5,
                  background:
                    importState.tone === "error"
                      ? "color-mix(in srgb, var(--sev-critical) 10%, var(--surface-alt))"
                      : importState.tone === "success"
                      ? "color-mix(in srgb, var(--sev-low) 10%, var(--surface-alt))"
                      : "var(--surface-alt)",
                  color:
                    importState.tone === "error"
                      ? "var(--sev-critical)"
                      : importState.tone === "success"
                      ? "var(--sev-low)"
                      : "var(--text-primary)",
                  border: "1px solid currentColor",
                }}
              >
                {importState.text}
              </div>
            )}
          </Card>

          {/* Right: Import History */}
          <Card title="Lịch sử các lần Nhập dữ liệu" className="span-6">
            {importsQuery.isPending && <SkeletonLine width="80%" />}
            {!importsQuery.isPending && (!imports || imports.length === 0) && (
              <EmptyState message="Chưa có lịch sử nhập dữ liệu lần nào." />
            )}
            {!importsQuery.isPending && imports && imports.length > 0 && (
              <>
                <div className="list">
                  {importHistoryFeed.visible.map((item) => (
                    <div className="list-row" key={item.import_id}>
                      <div className="list-row__head">
                        <span className="list-row__title" style={{ display: "flex", alignItems: "center", gap: 6 }}>
                          <FileText size={16} />
                          {item.filename}
                        </span>
                        <span className="list-row__meta">{relativeTime(item.created_at)}</span>
                      </div>
                      <div style={{ display: "flex", alignItems: "center", gap: 8, marginTop: 4 }}>
                        <span className="dataset-badge" style={{ fontSize: 11 }}>
                          {item.format} → {item.target}
                        </span>
                        <span className="muted small">
                          <strong>{item.normalized_count}</strong> bản ghi chuẩn hóa · {item.skipped_count} bỏ qua
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
                <LoadMore
                  remaining={importHistoryFeed.remaining}
                  step={IMPORT_STEP}
                  unit="lần nhập"
                  onMore={importHistoryFeed.showMore}
                  canCollapse={importHistoryFeed.canCollapse}
                  onCollapse={importHistoryFeed.collapse}
                />
              </>
            )}
          </Card>
        </div>
      )}

      {/* =========================================================================
          MODALS: THÊM / SỬA TÀI LIỆU
          ========================================================================= */}
      <Modal
        open={docModalOpen}
        title={editingDocId ? "Chỉnh sửa Tài liệu Tri thức" : "Thêm Tài liệu Tri thức Mới"}
        onClose={() => setDocModalOpen(false)}
      >
        <form className="stack" onSubmit={handleSaveDoc}>
          <label className="field">
            Tiêu đề tài liệu
            <input
              value={docForm.title}
              onChange={(e) => setDocForm((p) => ({ ...p, title: e.target.value }))}
              placeholder="Ví dụ: Quy định xử lý khiếu nại giao dịch"
              required
              maxLength={200}
            />
          </label>

          <div className="field-row">
            <label className="field">
              Dataset phân loại
              <input
                value={docForm.dataset}
                onChange={(e) => setDocForm((p) => ({ ...p, dataset: e.target.value }))}
                placeholder="general, rules, events, faq..."
                required
              />
            </label>
            <label className="field">
              Thẻ Tags (cách nhau dấu phẩy)
              <input
                value={docForm.tags}
                onChange={(e) => setDocForm((p) => ({ ...p, tags: e.target.value }))}
                placeholder="trade, quy định, bot"
              />
            </label>
          </div>

          <label className="field">
            Nội dung tri thức
            <textarea
              value={docForm.body}
              onChange={(e) => setDocForm((p) => ({ ...p, body: e.target.value }))}
              rows={6}
              maxLength={10000}
              placeholder="Nhập toàn bộ nội dung chi tiết để AI làm căn cứ trích xuất câu trả lời..."
              required
            />
            <span className="muted small" style={{ textAlign: "right" }}>
              {docForm.body.length} / 10.000 ký tự
            </span>
          </label>

          {docFormError && (
            <p style={{ color: "var(--sev-critical)", fontSize: 12.5 }}>{docFormError}</p>
          )}

          <div className="form-actions">
            <button type="submit" className="btn btn--primary" disabled={docSaving}>
              <FloppyDisk size={14} weight="bold" />
              {docSaving ? "Đang lưu..." : editingDocId ? "Cập nhật" : "Lưu tài liệu"}
            </button>
            <button type="button" className="btn btn--ghost" onClick={() => setDocModalOpen(false)}>
              Hủy
            </button>
          </div>
        </form>
      </Modal>

      {/* =========================================================================
          MODALS: THÊM / SỬA CHÍNH SÁCH (POLICY)
          ========================================================================= */}
      <Modal
        open={policyModalOpen}
        title={editingPolicyId ? "Chỉnh sửa Chính sách AI" : "Tạo Chính sách Kiểm duyệt Mới"}
        onClose={() => setPolicyModalOpen(false)}
      >
        <form className="stack" onSubmit={handleSavePolicy}>
          <label className="field">
            Tên chính sách
            <input
              value={policyForm.name}
              onChange={(e) => setPolicyForm((p) => ({ ...p, name: e.target.value }))}
              placeholder="Ví dụ: Chặn liên kết lừa đảo Steam Nitro"
              required
              maxLength={200}
            />
          </label>

          <label className="field">
            Mô tả mục đích
            <textarea
              value={policyForm.description}
              onChange={(e) => setPolicyForm((p) => ({ ...p, description: e.target.value }))}
              rows={2}
              maxLength={1000}
              placeholder="Giải thích vì sao chính sách này được áp dụng..."
              required
            />
          </label>

          <div className="field-row">
            <label className="field">
              Danh mục vi phạm
              <select
                value={policyForm.category}
                onChange={(e) => setPolicyForm((p) => ({ ...p, category: e.target.value }))}
              >
                {POLICY_CATEGORIES.filter((c) => c.value).map((c) => (
                  <option key={c.value} value={c.value}>
                    {c.label}
                  </option>
                ))}
              </select>
            </label>

            <label className="field">
              Hành động thực thi
              <select
                value={policyForm.action}
                onChange={(e) => setPolicyForm((p) => ({ ...p, action: e.target.value }))}
              >
                {POLICY_ACTIONS.map((a) => (
                  <option key={a.value} value={a.value}>
                    {a.label}
                  </option>
                ))}
              </select>
            </label>
          </div>

          <label className="field">
            Từ khóa kích hoạt (cách nhau dấu phẩy)
            <input
              value={policyForm.trigger_terms}
              onChange={(e) => setPolicyForm((p) => ({ ...p, trigger_terms: e.target.value }))}
              placeholder="free nitro, hack pass, cút đi, đồ ngu..."
            />
          </label>

          <label style={{ display: "flex", alignItems: "center", gap: 8, cursor: "pointer", fontSize: 13 }}>
            <input
              type="checkbox"
              checked={policyForm.active}
              onChange={(e) => setPolicyForm((p) => ({ ...p, active: e.target.checked }))}
            />
            Kích hoạt chính sách này ngay lập tức
          </label>

          {policyFormError && (
            <p style={{ color: "var(--sev-critical)", fontSize: 12.5 }}>{policyFormError}</p>
          )}

          <div className="form-actions">
            <button type="submit" className="btn btn--primary" disabled={policySaving}>
              <FloppyDisk size={14} weight="bold" />
              {policySaving ? "Đang lưu..." : editingPolicyId ? "Cập nhật" : "Tạo chính sách"}
            </button>
            <button type="button" className="btn btn--ghost" onClick={() => setPolicyModalOpen(false)}>
              Hủy
            </button>
          </div>
        </form>
      </Modal>
    </div>
  );
}
