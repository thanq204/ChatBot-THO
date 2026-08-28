import Modal from "./Modal.jsx";
import IncidentDetailPanel from "./IncidentDetailPanel.jsx";

/**
 * Case detail as a dialog, shared by the community list and the overview feed.
 * `onClose` must be a stable reference — Modal keys its Escape/scroll-lock effect on it.
 */
export default function IncidentDetailModal({ incidentId, headline, onClose, onUpdated }) {
  return (
    <Modal open={Boolean(incidentId)} title={headline || "Chi tiết trường hợp"} onClose={onClose}>
      <IncidentDetailPanel incidentId={incidentId} onUpdated={onUpdated} isModal={true} />
    </Modal>
  );
}
