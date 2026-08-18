import { useEffect, useRef, useState } from "react";
import { Navigate, useLocation } from "react-router-dom";
import { ArrowLeft, Eye, EyeSlash, SpinnerGap, WarningCircle } from "@phosphor-icons/react";
import Mascot from "../components/landing/Mascot.jsx";
import SakuraField from "../components/landing/SakuraField.jsx";
import { useAuth } from "../auth/AuthProvider.jsx";
import { auth } from "../api/client.js";
import { TransitionLink, usePageTransition } from "../transitions/PageTransition.jsx";
import "../login.css";

export default function LoginPage() {
  const location = useLocation(); const { isAuthenticated, signIn, signInWithGoogle } = useAuth(); const { transitionTo } = usePageTransition();
  const [values, setValues] = useState({ email: "", password: "" }); const [revealed, setRevealed] = useState(false); const [submitting, setSubmitting] = useState(false); const [formError, setFormError] = useState(""); const [googleClientId, setGoogleClientId] = useState(""); const [googleCredential, setGoogleCredential] = useState(""); const [googlePassword, setGooglePassword] = useState(""); const submitRef = useRef(null); const googleButtonRef = useRef(null);
  const destination = location.state?.from && location.state.from !== "/login" ? location.state.from : "/tong-quan";
  useEffect(() => { auth.googleConfig().then((config) => setGoogleClientId(config.client_id || "")).catch(() => setGoogleClientId("")); }, []);
  const submit = async (event) => {
    event.preventDefault(); setFormError(""); setSubmitting(true);
    const result = await signIn(values.email, values.password);
    if (!result.ok) { setSubmitting(false); setFormError(result.error); return; }
    const rect = submitRef.current?.getBoundingClientRect(); transitionTo(destination, rect && { x: rect.left + rect.width / 2, y: rect.top + rect.height / 2 });
  };
  const finishGoogle = async (credential, password) => {
    setSubmitting(true); const result = await signInWithGoogle(credential, password);
    if (!result.ok) {
      setSubmitting(false);
      if (result.error.includes("Hãy tạo mật khẩu")) { setGoogleCredential(credential); setFormError(""); return; }
      setFormError(result.error); return;
    }
    transitionTo(destination);
  };
  const createGooglePassword = (event) => { event.preventDefault(); if (googlePassword.length < 8) { setFormError("Mật khẩu cần ít nhất 8 ký tự."); return; } finishGoogle(googleCredential, googlePassword); };
  useEffect(() => {
    const clientId = googleClientId || import.meta.env.VITE_GOOGLE_CLIENT_ID;
    let timer;
    const render = () => {
      if (!clientId || !googleButtonRef.current) return;
      if (!window.google?.accounts?.id) { timer = window.setTimeout(render, 100); return; }
      window.google.accounts.id.initialize({ client_id: clientId, auto_select: false, callback: ({ credential }) => finishGoogle(credential) });
      window.google.accounts.id.renderButton(googleButtonRef.current, { type: "standard", theme: "outline", size: "large", text: "signin_with", shape: "pill", width: 360 });
    };
    render();
    return () => window.clearTimeout(timer);
  }, [googleClientId, signInWithGoogle, destination, transitionTo]);
  if (isAuthenticated) return <Navigate to={destination} replace />;
  return <div className="auth"><div className="auth__blobs" aria-hidden="true"><span className="auth__blob auth__blob--pink" /><span className="auth__blob auth__blob--lavender" /></div><SakuraField />
    <div className="auth__card"><TransitionLink to="/" className="auth__back"><ArrowLeft size={15} weight="bold" />Quay lại trang chủ</TransitionLink><div className="auth__head"><Mascot size={62} variant="auth" className="auth__mascot" /><span className="auth__brand">AI Community Manager</span><h1 className="auth__title">{googleCredential ? "Tạo mật khẩu" : "Chào mừng trở lại"}</h1>{googleCredential && <p className="auth__foot">Đăng nhập Google lần đầu. Hãy đặt mật khẩu để bảo vệ tài khoản.</p>}</div>
      {!googleCredential && <><form className="auth__form" onSubmit={submit}><div className="field"><label className="field__label" htmlFor="email">Email</label><input id="email" type="email" autoComplete="email" className="field__input" value={values.email} onChange={(e) => setValues({ ...values, email: e.target.value })} required /></div><div className="field"><label className="field__label" htmlFor="password">Mật khẩu</label><div className="field__wrap"><input id="password" type={revealed ? "text" : "password"} autoComplete="current-password" className="field__input" value={values.password} onChange={(e) => setValues({ ...values, password: e.target.value })} minLength="8" required /><button type="button" className="field__reveal" onClick={() => setRevealed(!revealed)} aria-label="Hiện hoặc ẩn mật khẩu">{revealed ? <EyeSlash size={17} /> : <Eye size={17} />}</button></div></div>{formError && <p className="auth__alert" role="alert"><WarningCircle size={16} weight="fill" />{formError}</p>}<button ref={submitRef} type="submit" className="auth__submit" disabled={submitting}>{submitting ? <><SpinnerGap size={17} className="spin-icon" />Đang đăng nhập</> : <>Đăng nhập</>}</button></form><div className="auth__divider"><span>hoặc</span></div><div className="auth__google" ref={googleButtonRef} aria-label="Đăng nhập với Google" /></>}
      {googleCredential && <form className="auth__form" onSubmit={createGooglePassword}><div className="field"><label className="field__label" htmlFor="google-password">Mật khẩu mới</label><input id="google-password" className="field__input" type="password" minLength="8" value={googlePassword} onChange={(event) => setGooglePassword(event.target.value)} required /></div>{formError && <p className="auth__alert" role="alert"><WarningCircle size={16} weight="fill" />{formError}</p>}<button type="submit" className="auth__submit" disabled={submitting}>{submitting ? "Đang tạo tài khoản…" : "Tạo mật khẩu và tiếp tục"}</button></form>}
    </div></div>;
}
