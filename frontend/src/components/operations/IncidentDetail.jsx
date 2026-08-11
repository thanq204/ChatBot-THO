import { CursorClickIcon } from "@phosphor-icons/react";
import { Empty, Notice, Panel, SkeletonText, dateText, percent } from "../ui.jsx";

export default function IncidentDetail({ data, loading, error }) {
  return (
    <Panel title="Incident detail">
      {loading && <SkeletonText lines={5} />}
      {!loading && error && <Notice tone="error">Không mở được incident này: {error}</Notice>}
      {!loading && !error && !data && (
        <Empty icon={CursorClickIcon}>Bấm một incident để xem messages, evidence và audit trail.</Empty>
      )}
      {!loading && !error && data && <Body data={data} />}
    </Panel>
  );
}

function Body({ data }) {
  const messages = data.messages || [];
  const audit = data.audit || [];
  const root = messages.find((item) => !item.parent_message_id) || messages[0];

  return (
    <div className="detail">
      <h3>{data.incident.title}</h3>
      <p>{data.incident.summary}</p>

      {root ? (
        <div className="quote">
          <span className="quote-label">Message gốc được phân tích</span>
          <blockquote>{root.text}</blockquote>
          <div className="meta" style={{ marginTop: 8 }}>
            {root.author_id} · {dateText(root.timestamp)}
          </div>
        </div>
      ) : (
        <Empty>Chưa có message gốc trong case này.</Empty>
      )}

      <p style={{ marginTop: 12, fontSize: 13 }}>
        AI phát hiện <b>{(data.incident.categories || []).join(", ") || "chưa phân loại"}</b> · risk{" "}
        {percent(data.incident.risk_score)} · trạng thái <b>{data.incident.status}</b> · nền tảng{" "}
        <b>{data.incident.platform}</b>
      </p>

      <h4>Messages trong case</h4>
      {messages.length === 0 ? (
        <Empty>Case này chưa có message chi tiết.</Empty>
      ) : (
        messages.map((item, index) => (
          <div className="evidence" key={item.message_id || index}>
            <b>{item.parent_message_id ? "Reply" : "Message gốc"}</b> · {item.author_id} · {dateText(item.timestamp)}
            <div style={{ marginTop: 6 }}>{item.text}</div>
            <small>
              Decision: {item.decision} · Category: {item.category} · Risk: {percent(item.risk_score)}
              <br />
              Vì sao: {item.explanation || "Chưa có giải thích"}
            </small>
          </div>
        ))
      )}

      <h4>Audit trail</h4>
      {audit.length === 0 ? (
        <Empty>Chưa có audit trail.</Empty>
      ) : (
        audit.map((item, index) => (
          <div className="meta" key={index} style={{ padding: "5px 0" }}>
            {dateText(item.created_at)} · {item.event_type} · {item.actor}
          </div>
        ))
      )}
    </div>
  );
}
