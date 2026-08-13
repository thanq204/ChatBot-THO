import { useEffect, useRef, useState } from "react";
import { Navigate, useLocation } from "react-router-dom";
import { motion, useReducedMotion } from "motion/react";
import { ArrowLeft, Eye, EyeSlash, GoogleLogo, SpinnerGap, WarningCircle } from "@phosphor-icons/react";
import Mascot from "../components/landing/Mascot.jsx";
import SakuraField from "../components/landing/SakuraField.jsx";
import { DEMO_ACCOUNTS, useAuth } from "../auth/AuthProvider.jsx";
import { TransitionLink, usePageTransition } from "../transitions/PageTransition.jsx";
import "../login.css";

const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

function validate({ email, password }) {
  const errors = {};
  if (!email.trim()) errors.email = "Vui lòng nhập email.";
  else if (!EMAIL_PATTERN.test(email.trim())) errors.email = "Email không đúng định dạng.";

  if (!password) errors.password = "Vui lòng nhập mật khẩu.";
  else if (password.length < 8) errors.password = "Mật khẩu cần ít nhất 8 ký tự.";

  return errors;
}

export default function LoginPage() {
  const reduce = useReducedMotion();
  const location = useLocation();
  const { isAuthenticated, signIn } = useAuth();
  const { transitionTo } = usePageTransition();

  const [values, setValues] = useState({ email: "", password: "" });
  const [errors, setErrors] = useState({});
  const [touched, setTouched] = useState({});
  const [revealed, setRevealed] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState("");

  const submitRef = useRef(null);
  const timerRef = useRef(null);
  // Captured once: a session created by this form must not trip the redirect
  // below before the portal has had a chance to play.
  const wasSignedInOnArrival = useRef(isAuthenticated);

  useEffect(() => () => window.clearTimeout(timerRef.current), []);

  const from = location.state?.from;
  const destination = from && from !== "/login" ? from : "/tong-quan";

  const setField = (name) => (event) => {
    const next = { ...values, [name]: event.target.value };
    setValues(next);
    if (touched[name]) setErrors(validate(next));
    if (formError) setFormError("");
  };

  const handleBlur = (name) => () => {
    setTouched((current) => ({ ...current, [name]: true }));
    setErrors(validate(values));
  };

  const fillDemo = (account) => {
    setValues({ email: account.email, password: account.password });
    setErrors({});
    setTouched({});
    setFormError("");
  };

  const handleSubmit = (event) => {
    event.preventDefault();
    const found = validate(values);
    setErrors(found);
    setTouched({ email: true, password: true });
    if (Object.keys(found).length > 0) return;

    setSubmitting(true);
    setFormError("");

    // Short delay so the pending state is visible. Swap for a real request here.
    timerRef.current = window.setTimeout(() => {
      const result = signIn(values.email, values.password);
      if (!result.ok) {
        setSubmitting(false);
        setFormError(result.error);
        return;
      }
      const rect = submitRef.current?.getBoundingClientRect();
      transitionTo(
        destination,
        rect ? { x: rect.left + rect.width / 2, y: rect.top + rect.height / 2 } : undefined,
      );
    }, 480);
  };

  const enter = (delay) => ({
    initial: reduce ? false : { opacity: 0, y: 14 },
    animate: { opacity: 1, y: 0 },
    transition: { duration: 0.5, delay, ease: [0.16, 1, 0.3, 1] },
  });

  if (wasSignedInOnArrival.current) return <Navigate to={destination} replace />;

  return (
    <div className="auth">
      <div className="auth__blobs" aria-hidden="true">
        <span className="auth__blob auth__blob--pink" />
        <span className="auth__blob auth__blob--lavender" />
      </div>
      <SakuraField />

      <motion.div className="auth__card" {...enter(0.04)}>
        <TransitionLink to="/" className="auth__back">
          <ArrowLeft size={15} weight="bold" />
          Quay lại trang chủ
        </TransitionLink>

        <motion.div className="auth__head" {...enter(0.12)}>
          <Mascot size={62} variant="auth" className="auth__mascot" />
          <span className="auth__brand">
            <span className="sk-mark" aria-hidden="true">
              ✦
            </span>
            AI Community Manager
            <span className="sk-mark" aria-hidden="true">
              ✦
            </span>
          </span>
          <h1 className="auth__title">Chào mừng trở lại</h1>
        </motion.div>

        <motion.form className="auth__form" onSubmit={handleSubmit} noValidate {...enter(0.18)}>
          <div className="field">
            <label className="field__label" htmlFor="email">
              Email
            </label>
            <input
              id="email"
              name="email"
              type="email"
              autoComplete="email"
              className={`field__input${errors.email && touched.email ? " field__input--invalid" : ""}`}
              value={values.email}
              onChange={setField("email")}
              onBlur={handleBlur("email")}
              aria-invalid={Boolean(errors.email && touched.email)}
              aria-describedby={errors.email && touched.email ? "email-error" : undefined}
            />
            {errors.email && touched.email && (
              <p className="field__error" id="email-error">
                {errors.email}
              </p>
            )}
          </div>

          <div className="field">
            <label className="field__label" htmlFor="password">
              Mật khẩu
            </label>
            <div className="field__wrap">
              <input
                id="password"
                name="password"
                type={revealed ? "text" : "password"}
                autoComplete="current-password"
                className={`field__input${errors.password && touched.password ? " field__input--invalid" : ""}`}
                value={values.password}
                onChange={setField("password")}
                onBlur={handleBlur("password")}
                aria-invalid={Boolean(errors.password && touched.password)}
                aria-describedby={errors.password && touched.password ? "password-error" : undefined}
              />
              <button
                type="button"
                className="field__reveal"
                onClick={() => setRevealed((current) => !current)}
                aria-label={revealed ? "Ẩn mật khẩu" : "Hiện mật khẩu"}
              >
                {revealed ? <EyeSlash size={17} /> : <Eye size={17} />}
              </button>
            </div>
            {errors.password && touched.password && (
              <p className="field__error" id="password-error">
                {errors.password}
              </p>
            )}
          </div>

          {formError && (
            <p className="auth__alert" role="alert">
              <WarningCircle size={16} weight="fill" />
              {formError}
            </p>
          )}

          <button ref={submitRef} type="submit" className="auth__submit" disabled={submitting}>
            {submitting ? (
              <>
                <SpinnerGap size={17} weight="bold" className="spin-icon" />
                Đang đăng nhập
              </>
            ) : (
              <>
                Đăng nhập
                <span className="sk-mark sk-mark--on-dark" aria-hidden="true">
                  ✦
                </span>
              </>
            )}
          </button>

          <a className="auth__minor" href="/quen-mat-khau" onClick={(event) => event.preventDefault()}>
            Quên mật khẩu?
          </a>
        </motion.form>

        <motion.div className="auth__demo" {...enter(0.22)}>
          <p className="auth__demo-lead">Tài khoản demo, backend chưa có xác thực thật</p>
          {DEMO_ACCOUNTS.map((account) => (
            <button
              key={account.email}
              type="button"
              className="auth__demo-row"
              onClick={() => fillDemo(account)}
            >
              <span className="auth__demo-email">{account.email}</span>
              <span className="auth__demo-role">{account.role}</span>
            </button>
          ))}
        </motion.div>

        <motion.div className="auth__divider" {...enter(0.26)}>
          <span>hoặc</span>
        </motion.div>

        <motion.div {...enter(0.32)}>
          <button
            type="button"
            className="auth__google"
            disabled
            title="Chưa khả dụng, cần cấu hình OAuth"
          >
            <GoogleLogo size={17} weight="bold" />
            Đăng nhập với Google
          </button>
          <p className="auth__foot">
            Chưa có tài khoản?{" "}
            <a href="/dang-ky" onClick={(event) => event.preventDefault()}>
              Đăng ký
            </a>
          </p>
        </motion.div>
      </motion.div>
    </div>
  );
}
