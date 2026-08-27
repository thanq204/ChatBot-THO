import { useState } from "react";
import { useMutation, useQueries, useQueryClient } from "@tanstack/react-query";
import {
  ArrowClockwise,
  ClipboardText,
  Scales,
  ShieldCheck,
  Storefront,
  UsersThree,
} from "@phosphor-icons/react";
import Badge from "../components/Badge.jsx";
import Card from "../components/Card.jsx";
import Pagination, { usePagination } from "../components/Pagination.jsx";
import LoadMore, { useLoadMore } from "../components/LoadMore.jsx";
import { EmptyState, ErrorState } from "../components/StatePanels.jsx";
import { SkeletonBlock } from "../components/Skeleton.jsx";
import { ops } from "../api/client.js";
import { queryKeys } from "../lib/queryClient.js";
import { formatNumber, relativeTime } from "../lib/format.js";

const SELLER_PAGE_SIZE = 15;
const TRADE_PAGE_SIZE = 15;
const ASSESSMENT_STEP = 5;

const DATA_STATUS = {
  insufficient_data: ["Chưa đủ dữ liệu", "var(--text-muted)"],
  transaction_history_available: ["Có lịch sử giao dịch", "var(--sev-low)"],
  admin_review_required: ["Cần Admin/Mod xem", "var(--sev-medium)"],
};

const TRADE_STATUS = {
  opened: ["Mới mở", "var(--text-muted)"],
  partially_confirmed: ["Chờ một bên", "var(--sev-medium)"],
  completed: ["Hai bên xác nhận", "var(--sev-low)"],
  disputed: ["Tranh chấp", "var(--sev-critical)"],
  cancelled: ["Đã hủy", "var(--text-muted)"],
};

const DECISIONS = [
  ["insufficient_data", "Chưa đủ dữ liệu"],
  ["no_confirmed_issue", "Chưa có vấn đề được xác nhận"],
  ["review_required", "Cần xem thêm bằng chứng"],
  ["restricted", "Hạn chế theo quyết định Admin/Mod"],
];

export default function SellerTrustPage() {
  const queryClient = useQueryClient();
  const [sellersQuery, tradesQuery, assessmentsQuery] = useQueries({
    queries: [
      { queryKey: queryKeys.sellers, queryFn: ops.sellers },
      { queryKey: queryKeys.trades(), queryFn: () => ops.trades() },
      { queryKey: queryKeys.sellerAssessments(), queryFn: () => ops.sellerAssessments() },
    ],
  });
  const sellers = sellersQuery.data ?? [];
  const trades = tradesQuery.data ?? [];
  const assessments = assessmentsQuery.data ?? [];
  const loading = sellersQuery.isPending || tradesQuery.isPending || assessmentsQuery.isPending;
  const error = (sellersQuery.error || tradesQuery.error || assessmentsQuery.error)?.message ?? "";

  const refresh = () => {
    queryClient.invalidateQueries({ queryKey: queryKeys.sellers });
    queryClient.invalidateQueries({ queryKey: ["trades"] });
    queryClient.invalidateQueries({ queryKey: ["seller-assessments"] });
  };
  const completed = trades.filter((trade) => trade.status === "completed").length;
  const disputes = trades.filter((trade) => trade.status === "disputed").length;
  const openAssessments = assessments.filter((item) => item.status === "open");

  const sellerPage = usePagination(sellers, SELLER_PAGE_SIZE);
  // The trade table used to render trades.slice(0, 30) with nothing saying so:
  // past 30 rows the data simply vanished, which is worse than a long list
  // because an Admin reads the truncated table as the whole picture.
  const tradePage = usePagination(trades, TRADE_PAGE_SIZE);
  const assessmentFeed = useLoadMore(openAssessments, ASSESSMENT_STEP);

  return (
    <div className="page-grid seller-trust-page">
      <div className="page-grid__row">
        <Card title="Độ tin cậy người bán" className="span-12 reputation-hero" action={(
          <button type="button" className="btn btn--ghost" onClick={refresh} disabled={loading}>
            <ArrowClockwise size={15} /> Làm mới
          </button>
        )}>
          <p className="muted small">
            Hệ thống chỉ tổng hợp giao dịch được buyer và seller xác nhận. AI hỗ trợ tóm tắt dữ kiện, không tự tuyên bố người bán an toàn, lừa đảo hoặc có trách nhiệm pháp lý.
          </p>
          <div className="reputation-stats">
            <SummaryStat icon={Storefront} label="Người bán có dữ liệu" value={sellers.length} />
            <SummaryStat icon={ShieldCheck} label="Giao dịch xác nhận" value={completed} tone="positive" />
            <SummaryStat icon={Scales} label="Tranh chấp" value={disputes} tone="danger" />
            <SummaryStat icon={ClipboardText} label="Chờ Admin/Mod" value={openAssessments.length} tone="warning" />
          </div>
        </Card>
      </div>

      {error && <ErrorState message={`Không tải được hồ sơ người bán: ${error}`} onRetry={refresh} />}
      {!error && (
        <div className="page-grid__row">
          <Card title="Hồ sơ giao dịch người bán" className="span-12">
            <p className="muted small">
              Số sao luôn đi kèm số giao dịch, số người mua khác nhau và trạng thái dữ liệu. “Chưa có vấn đề được xác nhận” không đồng nghĩa với bảo đảm an toàn.
            </p>
            {loading && <SkeletonBlock height={260} />}
            {!loading && sellers.length === 0 && <EmptyState message="Chưa có giao dịch nào được ghi nhận từ kênh giao dịch Discord." />}
            {!loading && sellers.length > 0 && (
              <div className="reputation-table-wrap">
                <table className="reputation-table seller-table">
                  <thead><tr><th>Người bán</th><th>Hoàn tất</th><th>Đánh giá xác thực</th><th>Người mua khác nhau</th><th>Điểm TB</th><th>Tín hiệu cần xem</th><th>Trạng thái dữ liệu</th></tr></thead>
                  <tbody>
                    {sellerPage.slice.map((seller) => {
                      const [label, tone] = DATA_STATUS[seller.data_status] || DATA_STATUS.insufficient_data;
                      return (
                        <tr key={`${seller.community_id}:${seller.seller_id}`}>
                          <td><strong>{seller.seller_name || "Chưa có tên"}</strong><small>User ID: {seller.seller_id}</small></td>
                          <td>{formatNumber(seller.completed_trades)}</td>
                          <td>{formatNumber(seller.verified_reviews)}</td>
                          <td>{formatNumber(seller.unique_buyers)}</td>
                          <td>{seller.average_rating == null ? "Chưa có" : `${seller.average_rating}/5`}</td>
                          <td className={seller.open_disputes || seller.confirmed_spam_incidents || seller.anomaly_flags.length ? "score-negative" : ""}>
                            {seller.open_disputes} tranh chấp · {seller.confirmed_spam_incidents} spam đã duyệt · {seller.anomaly_flags.length} bất thường
                          </td>
                          <td><Badge tone={tone}>{label}</Badge></td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}
            {!loading && sellers.length > 0 && (
              <Pagination
                page={sellerPage.page}
                pageCount={sellerPage.pageCount}
                onPageChange={sellerPage.setPage}
                from={sellerPage.from}
                to={sellerPage.to}
                total={sellerPage.total}
                unit="người bán"
              />
            )}
          </Card>
        </div>
      )}

      {!error && (
        <div className="page-grid__row">
          <Card title="Yêu cầu Admin/Mod kiểm tra" className="span-12">
            <p className="muted small">
              Thành viên dùng <code>/seller_check</code>. Admin/Mod phải đọc tin nhắn gốc, bằng chứng giao dịch và tranh chấp trước khi ghi kết luận có phạm vi.
            </p>
            {loading && <SkeletonBlock height={220} />}
            {!loading && openAssessments.length === 0 && <EmptyState message="Không có yêu cầu kiểm tra đang chờ." />}
            {!loading && assessmentFeed.visible.map((assessment) => (
              <AssessmentCard assessment={assessment} key={assessment.assessment_id} onSaved={refresh} />
            ))}
            {!loading && (
              <LoadMore
                remaining={assessmentFeed.remaining}
                step={ASSESSMENT_STEP}
                unit="yêu cầu"
                onMore={assessmentFeed.showMore}
                canCollapse={assessmentFeed.canCollapse}
                onCollapse={assessmentFeed.collapse}
              />
            )}
          </Card>
        </div>
      )}

      {!error && (
        <div className="page-grid__row">
          <Card title="Giao dịch gần đây" className="span-12">
            <p className="muted small">
              Luồng Discord/Telegram: <code>/trade_open</code> → buyer và seller dùng <code>/trade_confirm</code> → buyer dùng <code>/trade_review</code>.
            </p>
            {loading && <SkeletonBlock height={220} />}
            {!loading && trades.length === 0 && <EmptyState message="Chưa có giao dịch." />}
            {!loading && trades.length > 0 && (
              <div className="reputation-table-wrap">
                <table className="reputation-table seller-table">
                  <thead><tr><th>Mã</th><th>Người mua</th><th>Người bán</th><th>Nội dung</th><th>Xác nhận</th><th>Trạng thái</th><th>Cập nhật</th></tr></thead>
                  <tbody>
                    {tradePage.slice.map((trade) => {
                      const [label, tone] = TRADE_STATUS[trade.status] || TRADE_STATUS.opened;
                      return (
                        <tr key={trade.trade_id}>
                          <td><code>{trade.trade_id}</code></td>
                          <td>{trade.buyer_name || trade.buyer_id}</td>
                          <td>{trade.seller_name || trade.seller_id}</td>
                          <td>{trade.item_summary}</td>
                          <td>{trade.buyer_confirmed ? "Người mua ✓" : "Người mua …"} · {trade.seller_confirmed ? "Người bán ✓" : "Người bán …"}</td>
                          <td><Badge tone={tone}>{label}</Badge></td>
                          <td>{relativeTime(trade.updated_at)}</td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}
            {!loading && trades.length > 0 && (
              <Pagination
                page={tradePage.page}
                pageCount={tradePage.pageCount}
                onPageChange={tradePage.setPage}
                from={tradePage.from}
                to={tradePage.to}
                total={tradePage.total}
                unit="giao dịch"
              />
            )}
          </Card>
        </div>
      )}

      <div className="page-grid__row">
        <Card title="Tiêu chí có ích và giới hạn" className="span-12">
          <div className="seller-criteria-grid">
            <Criteria title="Dữ kiện được dùng" items={["Giao dịch hai bên xác nhận", "Đánh giá từ đúng người mua", "Độ chính xác mô tả", "Giao tiếp và hoàn tất", "Số người mua khác nhau", "Tranh chấp đã có bằng chứng"]} />
            <Criteria title="Chống thao túng" items={["Một đánh giá cho mỗi mã giao dịch", "Không tự đánh giá bản thân", "Phát hiện đánh giá dồn trong 24 giờ", "Cảnh báo người mua tập trung", "Cảnh báo giao dịch đối ứng lặp", "Admin/Mod quyết định trường hợp nhạy cảm"]} />
            <Criteria title="Không được suy diễn" items={["Không bảo đảm giao dịch an toàn", "Không kết tội từ một đánh giá", "Không dùng lời khen trong chat làm điểm", "Không lưu OTP/thẻ/mật khẩu", "Không đưa tư vấn pháp lý", "Không ẩn đánh giá chỉ vì tiêu cực"]} />
          </div>
        </Card>
      </div>
    </div>
  );
}

function AssessmentCard({ assessment, onSaved }) {
  const queryClient = useQueryClient();
  const [decision, setDecision] = useState("insufficient_data");
  const [note, setNote] = useState("");
  const mutation = useMutation({
    mutationFn: () => ops.decideSellerAssessment(assessment.assessment_id, { decision, admin_note: note }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["seller-assessments"] });
      onSaved();
    },
  });
  return (
    <article className="seller-assessment-card">
      <div className="seller-assessment-card__head">
        <div><strong>{assessment.assessment_id}</strong><small>Người bán: {assessment.seller_id} · Người hỏi: {assessment.requester_id}</small></div>
        <Badge tone="var(--sev-medium)">Chờ duyệt</Badge>
      </div>
      <p><strong>Lý do:</strong> {assessment.reason}</p>
      <p className="muted small"><strong>Tóm tắt hỗ trợ ({assessment.model_used}):</strong> {assessment.ai_summary}</p>
      <div className="seller-assessment-card__form">
        <select value={decision} onChange={(event) => setDecision(event.target.value)} aria-label="Kết luận Admin/Mod">
          {DECISIONS.map(([value, label]) => <option value={value} key={value}>{label}</option>)}
        </select>
        <input value={note} onChange={(event) => setNote(event.target.value)} placeholder="Ghi rõ bằng chứng và phạm vi kết luận..." />
        <button type="button" className="btn btn--primary" disabled={note.trim().length < 3 || mutation.isPending} onClick={() => mutation.mutate()}>
          {mutation.isPending ? "Đang lưu..." : "Lưu quyết định"}
        </button>
      </div>
      {mutation.error && <p className="form-error">{mutation.error.message}</p>}
    </article>
  );
}

function SummaryStat({ icon: Icon, label, value, tone = "" }) {
  return (
    <div className={`reputation-stat ${tone ? `reputation-stat--${tone}` : ""}`}>
      <Icon size={20} weight="duotone" /><span>{label}</span><strong>{formatNumber(value)}</strong>
    </div>
  );
}

function Criteria({ title, items }) {
  return <article className="reputation-rule"><div className="reputation-rule__head"><strong>{title}</strong><UsersThree size={20} /></div><ul>{items.map((item) => <li key={item}>{item}</li>)}</ul></article>;
}
