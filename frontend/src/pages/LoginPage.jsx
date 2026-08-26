import { useRef, useState } from "react";
import { Navigate, useLocation } from "react-router-dom";
import { ArrowLeft, EnvelopeSimple, Eye, EyeSlash, IdentificationBadge, Info, LockSimple, SpinnerGap, WarningCircle } from "@phosphor-icons/react";
import SakuraField from "../components/landing/SakuraField.jsx";
import { useAuth } from "../auth/AuthProvider.jsx";
import { TransitionLink, usePageTransition } from "../transitions/PageTransition.jsx";
import "../login.css";
import { BRAND } from "../lib/brand.js";
import ThoMascot from "../components/ThoMascot.jsx";
import { useTablist } from "../lib/useTablist.js";

const REGISTER_BLANK = { email: "", display_name: "", password: "" };
const DEMO_PASSWORD = "12345678";
const DEMO_ACCOUNTS = [
  { email: "admin@gmail.com", password: DEMO_PASSWORD, role: "Admin" },
  { email: "thaitudev04@gmail.com", password: DEMO_PASSWORD, role: "Mod" },
];

export default function LoginPage() {
  const location = useLocation(); const { isAuthenticated, signIn, register } = useAuth(); const { transitionTo } = usePageTransition();
  const [tab, setTab] = useState("login"); const [values, setValues] = useState({ email: "", password: "" }); const [registerValues, setRegisterValues] = useState(REGISTER_BLANK); const [revealed, setRevealed] = useState(false); const [submitting, setSubmitting] = useState(false); const [formError, setFormError] = useState(""); const submitRef = useRef(null);
  const authTabs = useTablist();
  const switchTab = (next) => { setTab(next); setFormError(""); };
  const fillDemo = (account) => { setValues({ email: account.email, password: account.password }); setFormError(""); };
  const destination = location.state?.from && location.state.from !== "/login" ? location.state.from : "/tong-quan";
  const submit = async (event) => {
    event.preventDefault(); setFormError(""); setSubmitting(true);
    const result = await signIn(values.email, values.password);
    if (!result.ok) { setSubmitting(false); setFormError(result.error); return; }
    const rect = submitRef.current?.getBoundingClientRect(); transitionTo(destination, rect && { x: rect.left + rect.width / 2, y: rect.top + rect.height / 2 });
  };
  const submitRegister = async (event) => {
    event.preventDefault(); setFormError(""); setSubmitting(true);
    const result = await register(registerValues);
    if (!result.ok) { setSubmitting(false); setFormError(result.error); return; }
    const rect = submitRef.current?.getBoundingClientRect(); transitionTo(destination, rect && { x: rect.left + rect.width / 2, y: rect.top + rect.height / 2 });
  };
  if (isAuthenticated) return <Navigate to={destination} replace />;
  return <div className="auth"><div className="auth__blobs" aria-hidden="true"><span className="auth__blob auth__blob--pink" /><span className="auth__blob auth__blob--lavender" /></div><SakuraField />
    <div className="auth__card"><TransitionLink to="/" className="auth__back"><ArrowLeft size={15} weight="bold" />Quay lại trang chủ</TransitionLink>
      <div className="auth__head">
        <ThoMascot height={74} className="auth__mascot" />
        <span className="auth__brand">{BRAND.name} · {BRAND.tagline}</span>
        <h1 className="auth__title">{tab === "register" ? "Tạo tài khoản" : "Chào mừng trở lại"}</h1>
        <p className="auth__subtitle">{tab === "register" ? "Tạo tài khoản Admin để bắt đầu quản lý cộng đồng." : "Đăng nhập để tiếp tục quản lý cộng đồng."}</p>
      </div>

      <div className="auth__tabs" role="tablist" aria-label="Đăng nhập hoặc đăng ký" ref={authTabs.ref} onKeyDown={authTabs.onKeyDown}>
        <button type="button" role="tab" aria-selected={tab === "login"} className={`auth__tab ${tab === "login" ? "is-active" : ""}`.trim()} onClick={() => switchTab("login")}>Đăng nhập</button>
        <button type="button" role="tab" aria-selected={tab === "register"} className={`auth__tab ${tab === "register" ? "is-active" : ""}`.trim()} onClick={() => switchTab("register")}>Đăng ký</button>
      </div>

      {tab === "login" && <form className="auth__form" onSubmit={submit}>
        <div className="field">
          <label className="field__label" htmlFor="email">Email</label>
          <div className="field__wrap"><EnvelopeSimple size={17} className="field__icon" /><input id="email" type="email" autoComplete="email" className="field__input" value={values.email} onChange={(e) => setValues({ ...values, email: e.target.value })} required /></div>
        </div>
        <div className="field">
          <label className="field__label" htmlFor="password">Mật khẩu</label>
          <div className="field__wrap field__wrap--password"><LockSimple size={17} className="field__icon" /><input id="password" type={revealed ? "text" : "password"} autoComplete="current-password" className="field__input" value={values.password} onChange={(e) => setValues({ ...values, password: e.target.value })} minLength="8" required /><button type="button" className="field__reveal" onClick={() => setRevealed(!revealed)} aria-label="Hiện hoặc ẩn mật khẩu">{revealed ? <EyeSlash size={17} /> : <Eye size={17} />}</button></div>
        </div>
        {formError && <p className="auth__alert" role="alert"><WarningCircle size={16} weight="fill" />{formError}</p>}
        <button ref={submitRef} type="submit" className="auth__submit" disabled={submitting}>{submitting ? <><SpinnerGap size={17} className="spin-icon" />Đang đăng nhập</> : <>Đăng nhập</>}</button>
      </form>}

      {tab === "login" && <div className="auth__demo">
        <p className="auth__demo-lead">Tài khoản demo — bấm để điền nhanh (mật khẩu: {DEMO_PASSWORD})</p>
        {DEMO_ACCOUNTS.map((account) => (
          <button key={account.email} type="button" className="auth__demo-row" onClick={() => fillDemo(account)}>
            <span className="auth__demo-email">{account.email}</span>
            <span className="auth__demo-role">{account.role}</span>
          </button>
        ))}
      </div>}

      {tab === "register" && <>
        <p className="auth__notice"><Info size={16} weight="fill" /><span>Tài khoản tạo ở đây có quyền <strong>Admin</strong>. Nếu bạn được mời làm Mod, hãy dùng link mời Admin đã gửi cho bạn thay vì đăng ký ở đây.</span></p>
        <form className="auth__form" onSubmit={submitRegister}>
          <div className="field">
            <label className="field__label" htmlFor="register-email">Email</label>
            <div className="field__wrap"><EnvelopeSimple size={17} className="field__icon" /><input id="register-email" type="email" autoComplete="email" className="field__input" value={registerValues.email} onChange={(e) => setRegisterValues({ ...registerValues, email: e.target.value })} required /></div>
          </div>
          <div className="field">
            <label className="field__label" htmlFor="register-name">Tên hiển thị</label>
            <div className="field__wrap"><IdentificationBadge size={17} className="field__icon" /><input id="register-name" className="field__input" value={registerValues.display_name} onChange={(e) => setRegisterValues({ ...registerValues, display_name: e.target.value })} required /></div>
          </div>
          <div className="field">
            <label className="field__label" htmlFor="register-password">Mật khẩu</label>
            <div className="field__wrap field__wrap--password"><LockSimple size={17} className="field__icon" /><input id="register-password" type={revealed ? "text" : "password"} autoComplete="new-password" className="field__input" value={registerValues.password} onChange={(e) => setRegisterValues({ ...registerValues, password: e.target.value })} minLength="8" required /><button type="button" className="field__reveal" onClick={() => setRevealed(!revealed)} aria-label="Hiện hoặc ẩn mật khẩu">{revealed ? <EyeSlash size={17} /> : <Eye size={17} />}</button></div>
          </div>
          {formError && <p className="auth__alert" role="alert"><WarningCircle size={16} weight="fill" />{formError}</p>}
          <button ref={submitRef} type="submit" className="auth__submit" disabled={submitting}>{submitting ? <><SpinnerGap size={17} className="spin-icon" />Đang tạo tài khoản</> : <>Đăng ký</>}</button>
        </form>
      </>}
    </div></div>;
}
