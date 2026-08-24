import { useEffect, useState } from "react";
import { Eye, EyeSlash } from "@phosphor-icons/react";
import Modal from "./Modal.jsx";
import { useAuth } from "../auth/AuthProvider.jsx";

const roleLabel = (role) => (role === "admin" ? "Quản trị viên" : "Kiểm duyệt viên");

function PasswordField({ label, value, onChange, autoComplete, minLength, placeholder }) {
  const [revealed, setRevealed] = useState(false);
  return (
    <label className="field">
      {label}
      <div className="password-input">
        <input
          type={revealed ? "text" : "password"}
          autoComplete={autoComplete}
          minLength={minLength}
          value={value}
          onChange={onChange}
          placeholder={placeholder}
        />
        <button
          type="button"
          className="password-input__toggle"
          onClick={() => setRevealed((prev) => !prev)}
          aria-label={revealed ? "Ẩn mật khẩu" : "Hiện mật khẩu"}
          tabIndex={-1}
        >
          {revealed ? <EyeSlash size={16} /> : <Eye size={16} />}
        </button>
      </div>
    </label>
  );
}

export default function ProfileModal({ open, onClose }) {
  const { user, updateProfile } = useAuth();
  const [displayName, setDisplayName] = useState(user?.display_name ?? "");
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  // The modal stays mounted while closed, so re-sync the form to the latest
  // account each time it opens instead of only at first mount.
  useEffect(() => {
    if (!open) return;
    setDisplayName(user?.display_name ?? "");
    setCurrentPassword(""); setNewPassword(""); setConfirmPassword("");
    setError(""); setSuccess("");
  }, [open, user]);

  const resetPasswordFields = () => { setCurrentPassword(""); setNewPassword(""); setConfirmPassword(""); };

  const submit = async (event) => {
    event.preventDefault();
    setError(""); setSuccess("");
    const wantsPasswordChange = Boolean(newPassword || confirmPassword || currentPassword);
    if (wantsPasswordChange) {
      if (newPassword.length < 8) return setError("Mật khẩu mới phải có ít nhất 8 ký tự.");
      if (newPassword !== confirmPassword) return setError("Xác nhận mật khẩu mới không khớp.");
      if (!currentPassword) return setError("Nhập mật khẩu hiện tại để đổi mật khẩu.");
    }
    const payload = {};
    if (displayName.trim() && displayName.trim() !== user?.display_name) payload.display_name = displayName.trim();
    if (wantsPasswordChange) { payload.current_password = currentPassword; payload.new_password = newPassword; }
    if (Object.keys(payload).length === 0) return setError("Chưa có thay đổi nào để lưu.");
    setSaving(true);
    const result = await updateProfile(payload);
    setSaving(false);
    if (!result.ok) return setError(result.error);
    resetPasswordFields();
    setSuccess("Đã lưu thay đổi.");
  };

  return (
    <Modal open={open} title="Hồ sơ tài khoản" onClose={onClose}>
      <div className="profile-summary">
        <span className="profile-summary__name">{user?.display_name}</span>
        <span className="muted small">{user?.email}</span>
        <span className="muted small">{roleLabel(user?.role)}{user?.is_root_admin ? " · Admin gốc" : ""}</span>
      </div>

      <form className="stack-form" onSubmit={submit}>
        <label className="field">
          Tên hiển thị
          <input value={displayName} onChange={(event) => setDisplayName(event.target.value)} maxLength={120} />
        </label>

        <div className="field-row">
          <PasswordField
            label="Mật khẩu hiện tại"
            autoComplete="current-password"
            value={currentPassword}
            onChange={(event) => setCurrentPassword(event.target.value)}
            placeholder="Chỉ cần khi đổi mật khẩu"
          />
          <PasswordField
            label="Mật khẩu mới"
            autoComplete="new-password"
            minLength={8}
            value={newPassword}
            onChange={(event) => setNewPassword(event.target.value)}
            placeholder="Ít nhất 8 ký tự"
          />
          <PasswordField
            label="Xác nhận mật khẩu mới"
            autoComplete="new-password"
            minLength={8}
            value={confirmPassword}
            onChange={(event) => setConfirmPassword(event.target.value)}
          />
        </div>

        {error && <p className="small" style={{ color: "var(--sev-critical)" }}>{error}</p>}
        {success && <p className="small" style={{ color: "var(--status-resolved, var(--sev-low))" }}>{success}</p>}

        <div className="form-actions">
          <button type="submit" className="btn btn--primary" disabled={saving}>{saving ? "Đang lưu…" : "Lưu thay đổi"}</button>
        </div>
      </form>
    </Modal>
  );
}
