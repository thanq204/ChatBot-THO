import { useCallback, useDeferredValue, useMemo, useState } from "react";
import { useQueries, useQueryClient } from "@tanstack/react-query";
import {
  CheckCircle,
  ClockCounterClockwise,
  FloppyDisk,
  MagnifyingGlass,
  PencilSimple,
  Sparkle,
} from "@phosphor-icons/react";
import Card from "../components/Card.jsx";
import Modal from "../components/Modal.jsx";
import Badge from "../components/Badge.jsx";
import Pagination, { usePagination } from "../components/Pagination.jsx";
import LoadMore, { useLoadMore } from "../components/LoadMore.jsx";
import { SkeletonBlock } from "../components/Skeleton.jsx";
import { EmptyState, ErrorState } from "../components/StatePanels.jsx";
import { ops } from "../api/client.js";
import { queryKeys } from "../lib/queryClient.js";
import { formatNumber, relativeTime } from "../lib/format.js";
import { useTablist } from "../lib/useTablist.js";

const TOPIC_STEP = 5;
const FAQ_PAGE_SIZE = 10;

const EMPTY_FORM = {
  mode: "approve",
  topicId: "",
  faqId: "",
  question: "",
  answer: "",
  tags: "",
  active: true,
};

function parseTags(value) {
  return [...new Set(value.split(",").map((item) => item.trim()).filter(Boolean))].slice(0, 20);
}

export default function FaqManagementPage() {
  const faqTabs = useTablist();
  const queryClient = useQueryClient();
  const [activeTab, setActiveTab] = useState("top");
  const [query, setQuery] = useState("");
  const deferredQuery = useDeferredValue(query);
  const [form, setForm] = useState(EMPTY_FORM);
  const [modalOpen, setModalOpen] = useState(false);
  const [saving, setSaving] = useState(false);
  const [actionError, setActionError] = useState("");
  const [notice, setNotice] = useState(null);

  const [topicsQuery, faqsQuery] = useQueries({
    queries: [
      { queryKey: queryKeys.faqTopTopics(10), queryFn: () => ops.faqTopTopics(10) },
      { queryKey: queryKeys.faqs(false), queryFn: () => ops.faqs(false) },
    ],
  });

  const topics = topicsQuery.data ?? null;
  const faqs = faqsQuery.data ?? null;
  const loading = topicsQuery.isPending || faqsQuery.isPending;
  const error = actionError || (topicsQuery.error || faqsQuery.error)?.message || "";

  const load = useCallback(() => {
    setActionError("");
    queryClient.invalidateQueries({ queryKey: ["faqs"] });
    queryClient.invalidateQueries({ queryKey: ["faq-top-topics"] });
  }, [queryClient]);

  const visibleFaqs = useMemo(() => {
    const needle = deferredQuery.trim().toLowerCase();
    if (!needle) return faqs || [];
    return (faqs || []).filter((faq) =>
      [faq.faq_id, faq.question, faq.answer, ...(faq.tags || [])].join(" ").toLowerCase().includes(needle),
    );
  }, [deferredQuery, faqs]);

  const activeFaqCount = (faqs || []).filter((faq) => faq.active).length;
  const pausedFaqCount = (faqs || []).length - activeFaqCount;

  function startApproval(topic) {
    setForm({
      ...EMPTY_FORM,
      mode: "approve",
      topicId: topic.cluster_id,
      question: topic.representative_question,
    });
    setNotice(null);
    setModalOpen(true);
  }

  function startEdit(faq) {
    setForm({
      ...EMPTY_FORM,
      mode: "edit",
      faqId: faq.faq_id,
      question: faq.question,
      answer: faq.answer,
      tags: (faq.tags || []).join(", "),
      active: faq.active,
    });
    setNotice(null);
    setModalOpen(true);
  }

  function closeModal() {
    if (saving) return;
    setModalOpen(false);
    setForm(EMPTY_FORM);
  }

  function update(key) {
    return (event) => {
      const value = event.target.type === "checkbox" ? event.target.checked : event.target.value;
      setForm((current) => ({ ...current, [key]: value }));
    };
  }

  async function submit(event) {
    event.preventDefault();
    setSaving(true);
    setNotice(null);
    try {
      const payload = {
        question: form.question.trim(),
        answer: form.answer.trim(),
        tags: parseTags(form.tags),
      };
      const result = form.mode === "approve"
        ? await ops.approveFaqTopic(form.topicId, payload)
        : await ops.saveFaq(form.faqId, { ...payload, active: form.active });

      setNotice({
        tone: result.duplicate_warning ? "warning" : "success",
        text: result.duplicate_warning || (form.mode === "approve"
          ? "Đã duyệt câu trả lời. Topic đã rời Top 10 và được chuyển vào lịch sử FAQ."
          : "Đã cập nhật FAQ và embedding câu hỏi."),
      });
      setModalOpen(false);
      setForm(EMPTY_FORM);
      setActiveTab("history");
      await load();
    } catch (err) {
      setNotice({ tone: "error", text: err.message });
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="page-grid faq-page">
      <div className="page-grid__row">
        <Card title="Luồng FAQ được Admin duyệt" className="span-12 faq-overview">
          <p className="muted small">
            Hệ thống gom các câu hỏi tương đương từ member. Admin trả lời một lần, FAQ được embedding và chatbot ưu tiên
            dùng lại trước khi gọi RAG hoặc LLM.
          </p>
          <div className="faq-stats">
            <div className="faq-stat">
              <Sparkle size={18} weight="duotone" />
              <span>Đang chờ trong Top 10</span>
              <strong>{formatNumber((topics || []).length)}</strong>
            </div>
            <div className="faq-stat">
              <CheckCircle size={18} weight="duotone" />
              <span>FAQ đang hoạt động</span>
              <strong>{formatNumber(activeFaqCount)}</strong>
            </div>
            <div className="faq-stat">
              <ClockCounterClockwise size={18} weight="duotone" />
              <span>FAQ tạm ngưng</span>
              <strong>{formatNumber(pausedFaqCount)}</strong>
            </div>
          </div>
        </Card>
      </div>

      {notice && (
        <div className={`faq-notice faq-notice--${notice.tone}`} role="status">
          {notice.text}
        </div>
      )}

      {error && <ErrorState message={`Không tải được dữ liệu FAQ: ${error}`} onRetry={load} />}

      {!error && (
        <div className="page-grid__row">
          <Card className="span-12">
            <div className="faq-toolbar">
              <div className="tab-bar" role="tablist" aria-label="Quản lý FAQ" ref={faqTabs.ref} onKeyDown={faqTabs.onKeyDown}>
                <button
                  type="button"
                  role="tab"
                  aria-selected={activeTab === "top"}
                  className={activeTab === "top" ? "is-active" : ""}
                  onClick={() => setActiveTab("top")}
                >
                  Top 10 câu hỏi ({(topics || []).length})
                </button>
                <button
                  type="button"
                  role="tab"
                  aria-selected={activeTab === "history"}
                  className={activeTab === "history" ? "is-active" : ""}
                  onClick={() => setActiveTab("history")}
                >
                  Lịch sử FAQ ({(faqs || []).length})
                </button>
              </div>
              <button type="button" className="btn btn--ghost" onClick={load} disabled={loading}>
                Làm mới
              </button>
            </div>

            {loading && <SkeletonBlock height={300} />}

            {!loading && activeTab === "top" && <TopTopics topics={topics || []} onAnswer={startApproval} />}

            {!loading && activeTab === "history" && (
              <FaqHistory
                faqs={visibleFaqs}
                total={faqs?.length || 0}
                query={query}
                onQueryChange={setQuery}
                onEdit={startEdit}
              />
            )}
          </Card>
        </div>
      )}

      <Modal
        open={modalOpen}
        title={form.mode === "approve" ? "Tạo câu trả lời FAQ" : "Sửa FAQ đã duyệt"}
        onClose={closeModal}
      >
        <form className="stack" onSubmit={submit}>
          <label className="field">
            Câu hỏi chuẩn
            <textarea value={form.question} onChange={update("question")} rows={3} minLength={3} maxLength={500} required />
            <span className="field__hint">Có thể viết gọn lại câu đại diện trước khi xuất bản.</span>
          </label>
          <label className="field">
            Câu trả lời đã duyệt
            <textarea
              value={form.answer}
              onChange={update("answer")}
              rows={6}
              maxLength={5000}
              placeholder="Nhập đáp án chatbot sẽ dùng cho các câu hỏi tương đương..."
              required
            />
          </label>
          <label className="field">
            Tags
            <input value={form.tags} onChange={update("tags")} placeholder="lịch học, đăng ký môn, hỗ trợ" />
            <span className="field__hint">Phân tách bằng dấu phẩy, tối đa 20 thẻ.</span>
          </label>
          {form.mode === "edit" && (
            <label className="faq-active-toggle">
              <input type="checkbox" checked={form.active} onChange={update("active")} />
              <span>
                <strong>Cho phép chatbot sử dụng FAQ này</strong>
                <small>Bỏ chọn để tạm ngưng nhưng vẫn giữ trong lịch sử.</small>
              </span>
            </label>
          )}
          {notice?.tone === "error" && <p className="faq-form-error">{notice.text}</p>}
          <div className="form-actions">
            <button className="btn btn--primary" type="submit" disabled={saving || !form.question.trim() || !form.answer.trim()}>
              <FloppyDisk size={14} weight="bold" /> {saving ? "Đang lưu..." : form.mode === "approve" ? "Duyệt và đưa vào FAQ" : "Lưu thay đổi"}
            </button>
            <button className="btn btn--ghost" type="button" onClick={closeModal} disabled={saving}>
              Hủy
            </button>
          </div>
        </form>
      </Modal>
    </div>
  );
}

function TopTopics({ topics, onAnswer }) {
  const feed = useLoadMore(topics, TOPIC_STEP);

  if (topics.length === 0) {
    return <EmptyState message="Chưa có chủ đề nào đang chờ. Các câu hỏi mới đủ điều kiện sẽ tự xuất hiện tại đây." />;
  }

  return (
    <div className="faq-topic-list">
      {feed.visible.map((topic, index) => (
        <article className="faq-topic" key={topic.cluster_id}>
          <div className="faq-rank" aria-label={`Hạng ${index + 1}`}>{index + 1}</div>
          <div className="faq-topic__content">
            <div className="faq-topic__head">
              <div>
                <h3>{topic.topic_label || topic.representative_question}</h3>
                <p>{topic.representative_question}</p>
              </div>
              <Badge tone="var(--accent-solid)">{formatNumber(topic.question_count)} lượt hỏi</Badge>
            </div>
            {topic.sample_questions?.length > 0 && (
              <details className="faq-samples">
                <summary>Xem {topic.sample_questions.length} câu hỏi mẫu</summary>
                <ul>
                  {topic.sample_questions.map((question, sampleIndex) => (
                    <li key={`${topic.cluster_id}-${sampleIndex}`}>{question}</li>
                  ))}
                </ul>
              </details>
            )}
            <div className="list-row__actions">
              <button type="button" className="btn btn--primary" onClick={() => onAnswer(topic)}>
                <Sparkle size={13} /> Thêm câu trả lời
              </button>
              <span className="list-row__meta">Cập nhật {relativeTime(topic.updated_at)}</span>
            </div>
          </div>
        </article>
      ))}
      <LoadMore
        remaining={feed.remaining}
        step={TOPIC_STEP}
        unit="chủ đề"
        onMore={feed.showMore}
        canCollapse={feed.canCollapse}
        onCollapse={feed.collapse}
      />
    </div>
  );
}

function FaqHistory({ faqs, total, query, onQueryChange, onEdit }) {
  const page = usePagination(faqs, FAQ_PAGE_SIZE, query);

  return (
    <>
      <div className="search-box">
        <MagnifyingGlass size={15} />
        <input
          type="search"
          value={query}
          onChange={(event) => onQueryChange(event.target.value)}
          placeholder="Tìm theo câu hỏi, câu trả lời, ID hoặc thẻ..."
          aria-label="Tìm trong lịch sử FAQ"
        />
      </div>
      {faqs.length === 0 && (
        <EmptyState message={total === 0 ? "Chưa có FAQ nào được duyệt." : `Không có FAQ nào khớp “${query}”.`} />
      )}
      {faqs.length > 0 && (
        <div className="list faq-history-list">
          {page.slice.map((faq) => (
            <article className="list-row" key={faq.faq_id}>
              <div className="list-row__head">
                <div>
                  <span className="list-row__title">{faq.question}</span>
                  <span className="list-row__meta faq-id">{faq.faq_id}</span>
                </div>
                <Badge tone={faq.active ? "var(--sev-low)" : "var(--text-muted)"}>
                  {faq.active ? "Đang dùng" : "Tạm ngưng"}
                </Badge>
              </div>
              <p className="list-row__body faq-answer">{faq.answer}</p>
              <div className="faq-history__footer">
                <div className="chip-row">
                  {(faq.tags || []).map((tag) => <span className="chip" key={`${faq.faq_id}-${tag}`}>{tag}</span>)}
                  {(!faq.tags || faq.tags.length === 0) && <span className="list-row__meta">Chưa có thẻ</span>}
                </div>
                <span className="list-row__meta">Sửa {relativeTime(faq.updated_at)}</span>
              </div>
              <div className="list-row__actions">
                <button type="button" className="btn btn--ghost" onClick={() => onEdit(faq)}>
                  <PencilSimple size={13} /> Sửa câu hỏi và đáp án
                </button>
              </div>
            </article>
          ))}
        </div>
      )}
      {faqs.length > 0 && (
        <Pagination
          page={page.page}
          pageCount={page.pageCount}
          onPageChange={page.setPage}
          from={page.from}
          to={page.to}
          total={page.total}
          unit="FAQ"
        />
      )}
    </>
  );
}
