import { useEffect, useRef, useState } from "react";
import { Navigate, useSearchParams } from "react-router-dom";
import { ArrowLeft, EnvelopeSimple, Eye, EyeSlash, IdentificationBadge, LockSimple, SpinnerGap, WarningCircle } from "@phosphor-icons/react";
import SakuraField from "../components/landing/SakuraField.jsx";
import { useAuth } from "../auth/AuthProvider.jsx";
import { auth } from "../api/client.js";
import { TransitionLink, usePageTransition } from "../transitions/PageTransition.jsx";
import "../login.css";
import { BRAND } from "../lib/brand.js";
import ThoMascot from "../components/ThoMascot.jsx";

export default function AcceptInvitePage() {
  const [searchParams] = useSearchParams();
  const token = searchParams.get("token") || "";
  const { isAuthenticated, acceptInvite } = useAuth();
  const { transitionTo } = usePageTransition();
  const [status, setStatus] = useState("checking"); // checking | valid | invalid | declined
  const [email, setEmail] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [password, setPassword] = useState("");
  const [revealed, setRevealed] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [declining, setDeclining] = useState(false);
  const [formError, setFormError] = useState("");
  const submitRef = useRef(null);

  useEffect(() => {
    if (!token) { setStatus("invalid"); return; }
    auth.previewInvite(token).then((preview) => { setEmail(preview.email); setStatus("valid"); }).catch(() => setStatus("invalid"));
  }, [token]);

  const submit = async (event) => {
    event.preventDefault(); setFormError(""); setSubmitting(true);
    const result = await acceptInvite(token, { display_name: displayName, password });
    if (!result.ok) { setSubmitting(false); setFormError(result.error); return; }
    const rect = submitRef.current?.getBoundingClientRect(); transitionTo("/tong-quan", rect && { x: rect.left + rect.width / 2, y: rect.top + rect.height / 2 });
  };

  const decline = async () => {
    if (!window.confirm("Từ chối lời mời làm Mod? Link này sẽ không dùng được nữa.")) return;
    setDeclining(true);
    try { await auth.declineInvite(token); setStatus("declined"); }
    catch (err) { setFormError(err.message); }
    finally { setDeclining(false); }
  };

  if (isAuthenticated) return <Navigate to="/tong-quan" replace />;

  return <div className="auth"><div className="auth__blobs" aria-hidden="true"><span className="auth__blob auth__blob--pink" /><span className="auth__blob auth__blob--lavender" /></div><SakuraField />
    <div className="auth__card"><TransitionLink to="/" className="auth__back"><ArrowLeft size={15} weight="bold" />Quay lại trang chủ</TransitionLink>
      <div className="auth__head">
        <ThoMascot height={74} className="auth__mascot" />
        <span className="auth__brand">{BRAND.name} · {BRAND.tagline}</span>
        <h1 className="auth__title">Nhận lời mời làm Mod</h1>
        <p className="auth__subtitle">Hoàn tất đăng ký để tham gia đội kiểm duyệt.</p>
      </div>

      {status === "checking" && <p className="auth__foot auth__foot--lead" style={{ textAlign: "center" }}>Đang kiểm tra lời mời…</p>}

      {status === "invalid" && <>
        <p className="auth__alert" role="alert"><WarningCircle size={16} weight="fill" />Link mời không hợp lệ hoặc đã được sử dụng. Liên hệ Admin để được mời lại.</p>
        <TransitionLink to="/login" className="auth__minor" style={{ marginTop: 18, display: "block", textAlign: "center" }}>Về trang đăng nhập</TransitionLink>
      </>}

      {status === "declined" && <>
        <p className="auth__notice"><EnvelopeSimple size={16} weight="fill" /><span>Bạn đã từ chối lời mời này. Link không còn dùng được nữa.</span></p>
        <TransitionLink to="/" className="auth__minor" style={{ marginTop: 18, display: "block", textAlign: "center" }}>Về trang chủ</TransitionLink>
      </>}

      {status === "valid" && <>
        <p className="auth__notice"><EnvelopeSimple size={16} weight="fill" /><span>Tạo tài khoản Mod cho <strong>{email}</strong>, email này đã được Admin mời.</span></p>
        <form className="auth__form" onSubmit={submit}>
          <div className="field">
            <label className="field__label" htmlFor="invite-name">Tên hiển thị</label>
            <div className="field__wrap"><IdentificationBadge size={17} className="field__icon" /><input id="invite-name" className="field__input" value={displayName} onChange={(e) => setDisplayName(e.target.value)} required /></div>
          </div>
          <div className="field">
            <label className="field__label" htmlFor="invite-password">Mật khẩu</label>
            <div className="field__wrap field__wrap--password"><LockSimple size={17} className="field__icon" /><input id="invite-password" type={revealed ? "text" : "password"} autoComplete="new-password" className="field__input" value={password} onChange={(e) => setPassword(e.target.value)} minLength="8" required /><button type="button" className="field__reveal" onClick={() => setRevealed(!revealed)} aria-label="Hiện hoặc ẩn mật khẩu">{revealed ? <EyeSlash size={17} /> : <Eye size={17} />}</button></div>
          </div>
          {formError && <p className="auth__alert" role="alert"><WarningCircle size={16} weight="fill" />{formError}</p>}
          <button ref={submitRef} type="submit" className="auth__submit" disabled={submitting || declining}>{submitting ? <><SpinnerGap size={17} className="spin-icon" />Đang tạo tài khoản</> : <>Chấp nhận, tạo tài khoản</>}</button>
          <button type="button" className="auth__minor auth__decline" onClick={decline} disabled={submitting || declining}>{declining ? "Đang xử lý…" : "Từ chối lời mời"}</button>
        </form>
      </>}
    </div></div>;
}
