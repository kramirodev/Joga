import { useEffect, useState, type FormEvent } from "react";
import { Navigate, useLocation, useNavigate } from "react-router-dom";

import { ErrorNotice } from "../components/Feedback";
import { TextField } from "../components/ui/Field";
import {
  ArrowRightIcon,
  BuildingIcon,
  CheckIcon,
  ClockIcon,
  ShieldIcon,
  SparkIcon,
} from "../components/ui/Icons";
import {
  requestEmailCode,
  resetEmailPassword,
  verifyEmailChallenge,
  webEmailLogin,
  webEmailRegistration,
  ApiError,
  type EmailCodePurpose,
} from "../lib/api";
import { useAuth } from "../lib/auth-context";
import { formatError, requestIdOf } from "../lib/format";
import { safeReturnPath } from "../lib/redirect";
import { useDocumentTitle } from "../lib/useDocumentTitle";
import {
  emailError,
  passwordConfirmationError,
  passwordError,
  PASSWORD_MAX_LENGTH,
  PASSWORD_MIN_LENGTH,
} from "../lib/validation";

type Mode = "login" | "register" | "reset";
type Step = "credentials" | "email" | "code" | "password";

function nowMs(): number {
  return new Date().getTime();
}

function codePurpose(mode: Mode): EmailCodePurpose {
  return mode === "register" ? "registration" : "password_reset";
}

export function LoginPage() {
  useDocumentTitle("Entrar");
  const { user, signIn } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const navigationState = location.state as { from?: unknown; expired?: unknown } | null;
  const returnTo = safeReturnPath(navigationState?.from);
  const reasonExpired = navigationState?.expired === true;
  const [mode, setMode] = useState<Mode>("login");
  const [step, setStep] = useState<Step>("credentials");
  const [email, setEmail] = useState("");
  const [emailFieldError, setEmailFieldError] = useState<string | null>(null);
  const [password, setPassword] = useState("");
  const [passwordConfirm, setPasswordConfirm] = useState("");
  const [passwordFieldError, setPasswordFieldError] = useState<string | null>(null);
  const [confirmFieldError, setConfirmFieldError] = useState<string | null>(null);
  const [code, setCode] = useState("");
  const [codeFieldError, setCodeFieldError] = useState<string | null>(null);
  const [challengeId, setChallengeId] = useState<string | null>(null);
  const [resendAt, setResendAt] = useState(0);
  const [now, setNow] = useState(0);
  const [busy, setBusy] = useState(false);
  const [resending, setResending] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [info, setInfo] = useState<string | null>(null);

  const cleanEmail = email.trim();
  const resendSeconds = Math.max(0, Math.ceil((resendAt - now) / 1000));

  useEffect(() => {
    if (resendSeconds <= 0) return;
    const timer = window.setInterval(() => setNow(nowMs()), 1000);
    return () => window.clearInterval(timer);
  }, [resendSeconds]);

  if (user) {
    return <Navigate to={returnTo} replace />;
  }

  const title =
    step === "credentials"
      ? "Acessar o painel"
      : step === "code"
        ? "Confirmar código"
        : step === "password"
          ? mode === "register"
            ? "Definir senha"
            : "Nova senha"
          : mode === "register"
            ? "Criar conta"
            : "Recuperar acesso";

  const description =
    step === "credentials"
      ? "Entre com o e-mail e a senha da sua conta JOGA."
      : step === "code"
        ? "Digite o código de seis dígitos enviado por e-mail."
        : step === "password"
          ? mode === "register"
            ? "Crie uma senha de 10 a 128 caracteres. Em seguida você entra no painel."
            : "Defina uma nova senha de 10 a 128 caracteres. Todas as sessões serão encerradas."
          : mode === "register"
            ? "Informe o e-mail que será verificado para criar a conta."
            : "Informe o e-mail da sua conta para receber um código de recuperação.";

  function switchMode(next: Mode) {
    setMode(next);
    setStep(next === "login" ? "credentials" : "email");
    setChallengeId(null);
    setCode("");
    setCodeFieldError(null);
    setPassword("");
    setPasswordConfirm("");
    setPasswordFieldError(null);
    setConfirmFieldError(null);
    setError(null);
    setInfo(null);
    setEmailFieldError(null);
  }

  function resetToEmail() {
    setStep("email");
    setChallengeId(null);
    setCode("");
    setCodeFieldError(null);
    setPassword("");
    setPasswordConfirm("");
    setPasswordFieldError(null);
    setConfirmFieldError(null);
    setError(null);
    setInfo(null);
    window.setTimeout(() => document.getElementById("login-email")?.focus(), 0);
  }

  async function startChallenge(event?: FormEvent<HTMLFormElement>) {
    event?.preventDefault();
    if (mode === "login") return;
    const validation = emailError(email);
    if (validation) {
      setEmailFieldError(validation);
      document.getElementById("login-email")?.focus();
      return;
    }
    setBusy(true);
    setError(null);
    setInfo(null);
    try {
      const challenge = await requestEmailCode(cleanEmail, codePurpose(mode));
      setChallengeId(challenge.challenge_id);
      setResendAt(nowMs() + challenge.resend_after_seconds * 1000);
      setNow(nowMs());
      setStep("code");
      setCode("");
      setCodeFieldError(null);
      setPassword("");
      setPasswordConfirm("");
      setPasswordFieldError(null);
      setConfirmFieldError(null);
    } catch (caught) {
      setError(caught);
    } finally {
      setBusy(false);
    }
  }

  async function resendCode() {
    if (mode === "login" || resendSeconds > 0 || resending) return;
    setResending(true);
    setError(null);
    try {
      const challenge = await requestEmailCode(cleanEmail, codePurpose(mode));
      setChallengeId(challenge.challenge_id);
      setResendAt(nowMs() + challenge.resend_after_seconds * 1000);
      setNow(nowMs());
      setCode("");
      setCodeFieldError(null);
      setInfo("Novo código solicitado. Use apenas o código mais recente.");
    } catch (caught) {
      if (caught instanceof ApiError && caught.retryAfterSeconds) {
        setResendAt(nowMs() + caught.retryAfterSeconds * 1000);
        setNow(nowMs());
      }
      setError(caught);
    } finally {
      setResending(false);
    }
  }

  async function confirmCode(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!challengeId) return;
    if (code.length !== 6) {
      setCodeFieldError("Digite os seis dígitos do código.");
      document.getElementById("login-code")?.focus();
      return;
    }
    setBusy(true);
    setError(null);
    setInfo(null);
    try {
      const receipt = await verifyEmailChallenge(challengeId, code);
      setChallengeId(receipt.challenge_id);
      setStep("password");
      setPassword("");
      setPasswordConfirm("");
      setPasswordFieldError(null);
      setConfirmFieldError(null);
      window.setTimeout(() => document.getElementById("login-password")?.focus(), 0);
    } catch (caught) {
      setError(caught);
    } finally {
      setBusy(false);
    }
  }

  async function submitLogin(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const validation = emailError(email);
    if (validation) {
      setEmailFieldError(validation);
      document.getElementById("login-email")?.focus();
      return;
    }
    if (!password) {
      setPasswordFieldError("Informe sua senha.");
      document.getElementById("login-password")?.focus();
      return;
    }
    setBusy(true);
    setError(null);
    setInfo(null);
    try {
      const session = await webEmailLogin(cleanEmail, password);
      setPassword("");
      signIn(session);
      navigate(returnTo, { replace: true });
    } catch (caught) {
      setError(caught);
    } finally {
      setBusy(false);
    }
  }

  async function submitPassword(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!challengeId) return;
    const validation = passwordError(password, cleanEmail);
    if (validation) {
      setPasswordFieldError(validation);
      document.getElementById("login-password")?.focus();
      return;
    }
    const confirmationError = passwordConfirmationError(password, passwordConfirm);
    if (confirmationError) {
      setConfirmFieldError(confirmationError);
      document.getElementById("login-password-confirm")?.focus();
      return;
    }
    setBusy(true);
    setError(null);
    setInfo(null);
    try {
      if (mode === "register") {
        const session = await webEmailRegistration(challengeId, cleanEmail, password);
        setPassword("");
        setPasswordConfirm("");
        signIn(session);
        navigate(returnTo, { replace: true });
        return;
      }
      await resetEmailPassword(challengeId, cleanEmail, password);
      setMode("login");
      setStep("credentials");
      setChallengeId(null);
      setCode("");
      setCodeFieldError(null);
      setPassword("");
      setPasswordConfirm("");
      setPasswordFieldError(null);
      setConfirmFieldError(null);
      setError(null);
      setInfo("Senha alterada. Entre com a nova senha.");
      window.setTimeout(() => document.getElementById("login-password")?.focus(), 0);
    } catch (caught) {
      setError(caught);
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="login-shell">
      <section className="login-hero" aria-label="JOGA y GESTÃO">
        <div className="login-hero__brand">
          <span className="brand__mark" aria-hidden="true">
            J
          </span>
          <span>
            JOGA <strong>y GESTÃO</strong>
          </span>
        </div>
        <p className="eyebrow">Painel do estabelecimento</p>
        <h1>
          A operação do JOGA
          <br />
          na sua mão.
        </h1>
        <p className="login-hero__lead">
          Gerencie quadras, agenda, reservas e repasses das operações originadas no JOGA — com
          clareza, prazos visíveis e histórico auditável.
        </p>
        <ul className="login-hero__list">
          <li>
            <BuildingIcon size={17} />
            Isolamento por organização
          </li>
          <li>
            <ShieldIcon size={17} />
            Papéis e permissões explícitos
          </li>
          <li>
            <ClockIcon size={17} />
            Prazos controlados pelo servidor
          </li>
          <li>
            <SparkIcon size={17} />
            Histórico auditável
          </li>
        </ul>
        <div className="login-hero__note">
          <CheckIcon size={16} />
          <span>Mesma conta do aplicativo JOGA. Não é necessário criar um login separado.</span>
        </div>
      </section>

      <section className="card login-card" aria-labelledby="login-title">
        <div className="login-card__heading">
          {step !== "credentials" ? (
            <p className="step-label">
              {step === "email"
                ? "Passo 1 de 3"
                : step === "code"
                  ? "Passo 2 de 3"
                  : "Passo 3 de 3"}
            </p>
          ) : null}
          <h2 id="login-title">{title}</h2>
          <p>{description}</p>
        </div>

        <div className="tabs tabs--compact" role="tablist" aria-label="Acesso">
          <button
            type="button"
            role="tab"
            aria-selected={mode === "login"}
            className={mode === "login" ? "tab tab--active" : "tab"}
            onClick={() => switchMode("login")}
            disabled={busy}
          >
            Entrar
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={mode === "register"}
            className={mode === "register" ? "tab tab--active" : "tab"}
            onClick={() => switchMode("register")}
            disabled={busy}
          >
            Criar conta
          </button>
        </div>

        {reasonExpired ? (
          <div className="notice notice--info" role="status" aria-live="polite">
            Sua sessão expirou. Entre novamente para continuar de onde parou.
          </div>
        ) : null}
        {error ? <ErrorNotice message={formatError(error)} requestId={requestIdOf(error)} /> : null}
        {info ? (
          <div className="notice notice--success" role="status" aria-live="polite">
            {info}
          </div>
        ) : null}

        {step === "credentials" ? (
          <form className="form" onSubmit={submitLogin} noValidate aria-busy={busy || undefined}>
            <TextField
              id="login-email"
              label="E-mail"
              type="email"
              inputMode="email"
              autoComplete="email"
              autoCapitalize="none"
              spellCheck={false}
              maxLength={254}
              placeholder="voce@exemplo.com"
              value={email}
              onChange={(event) => {
                setEmail(event.target.value);
                if (emailFieldError) setEmailFieldError(null);
              }}
              error={emailFieldError}
              hint="Use o e-mail vinculado à sua conta JOGA."
              disabled={busy}
              autoFocus
              required
            />
            <TextField
              id="login-password"
              label="Senha"
              type="password"
              autoComplete="current-password"
              maxLength={PASSWORD_MAX_LENGTH}
              placeholder="Sua senha"
              value={password}
              onChange={(event) => {
                setPassword(event.target.value);
                if (passwordFieldError) setPasswordFieldError(null);
              }}
              error={passwordFieldError}
              disabled={busy}
              required
            />
            <button type="submit" className="button button--primary button--block" disabled={busy}>
              {busy ? "Entrando..." : "Entrar"}
              {!busy ? <ArrowRightIcon size={17} /> : null}
            </button>
            <p className="hint hint--center">
              <button
                type="button"
                className="button button--link button--inline"
                onClick={() => switchMode("reset")}
                disabled={busy}
              >
                Esqueci minha senha
              </button>
            </p>
          </form>
        ) : null}

        {step === "email" ? (
          <form className="form" onSubmit={startChallenge} noValidate aria-busy={busy || undefined}>
            <TextField
              id="login-email"
              label="E-mail"
              type="email"
              inputMode="email"
              autoComplete="email"
              autoCapitalize="none"
              spellCheck={false}
              maxLength={254}
              placeholder="voce@exemplo.com"
              value={email}
              onChange={(event) => {
                setEmail(event.target.value);
                if (emailFieldError) setEmailFieldError(null);
              }}
              error={emailFieldError}
              hint={
                mode === "register"
                  ? "O código confirma que o endereço é seu antes de criar a conta."
                  : "Enviaremos um código para confirmar a recuperação."
              }
              disabled={busy}
              autoFocus
              required
            />
            <button type="submit" className="button button--primary button--block" disabled={busy}>
              {busy ? "Enviando código..." : "Receber código"}
              {!busy ? <ArrowRightIcon size={17} /> : null}
            </button>
            <p className="hint hint--center">
              Enviamos um código de seis dígitos. A entrega é feita em lotes a cada 5 minutos e pode
              levar alguns minutos.
            </p>
          </form>
        ) : null}

        {step === "code" ? (
          <form className="form" onSubmit={confirmCode} noValidate aria-busy={busy || undefined}>
            <div className="otp-target">
              <span>Enviamos um código de seis dígitos para</span>
              <strong>{cleanEmail}</strong>
              <button
                type="button"
                className="button button--link button--inline"
                onClick={resetToEmail}
                disabled={busy}
              >
                Trocar e-mail
              </button>
            </div>
            <p className="hint">
              A entrega é feita em lotes a cada 5 minutos; o código pode levar alguns minutos para
              chegar.
            </p>
            <TextField
              id="login-code"
              label="Código de verificação"
              type="text"
              inputMode="numeric"
              autoComplete="one-time-code"
              pattern="[0-9]{6}"
              maxLength={6}
              placeholder="000000"
              value={code}
              onChange={(event) => {
                setCode(event.target.value.replace(/\D/g, "").slice(0, 6));
                if (codeFieldError) setCodeFieldError(null);
              }}
              error={codeFieldError}
              hint="Seis dígitos, sem espaços."
              inputClassName="otp-input"
              autoFocus
              required
            />
            <button
              type="submit"
              className="button button--primary button--block"
              disabled={busy || code.length !== 6}
            >
              {busy ? "Verificando..." : "Continuar"}
              {!busy ? <ArrowRightIcon size={17} /> : null}
            </button>
            <button
              type="button"
              className="button button--ghost button--block"
              onClick={resendCode}
              disabled={resendSeconds > 0 || resending || busy}
            >
              {resending
                ? "Reenviando..."
                : resendSeconds > 0
                  ? `Reenviar código em ${resendSeconds}s`
                  : "Reenviar código"}
            </button>
          </form>
        ) : null}

        {step === "password" ? (
          <form className="form" onSubmit={submitPassword} noValidate aria-busy={busy || undefined}>
            <div className="otp-target">
              <span>{mode === "register" ? "Definindo a senha de" : "Redefinindo a senha de"}</span>
              <strong>{cleanEmail}</strong>
              <button
                type="button"
                className="button button--link button--inline"
                onClick={resetToEmail}
                disabled={busy}
              >
                Recomeçar
              </button>
            </div>
            <TextField
              id="login-password"
              label={mode === "register" ? "Senha" : "Nova senha"}
              type="password"
              autoComplete="new-password"
              minLength={PASSWORD_MIN_LENGTH}
              maxLength={PASSWORD_MAX_LENGTH}
              placeholder={`${PASSWORD_MIN_LENGTH} a ${PASSWORD_MAX_LENGTH} caracteres`}
              value={password}
              onChange={(event) => {
                setPassword(event.target.value);
                if (passwordFieldError) setPasswordFieldError(null);
              }}
              error={passwordFieldError}
              hint="Evite senhas comuns e não use o próprio e-mail."
              disabled={busy}
              autoFocus
              required
            />
            <TextField
              id="login-password-confirm"
              label={mode === "register" ? "Confirmar senha" : "Confirmar nova senha"}
              type="password"
              autoComplete="new-password"
              maxLength={PASSWORD_MAX_LENGTH}
              placeholder="Repita a senha"
              value={passwordConfirm}
              onChange={(event) => {
                setPasswordConfirm(event.target.value);
                if (confirmFieldError) setConfirmFieldError(null);
              }}
              error={confirmFieldError}
              disabled={busy}
              required
            />
            <button type="submit" className="button button--primary button--block" disabled={busy}>
              {busy
                ? "Salvando..."
                : mode === "register"
                  ? "Criar conta e entrar"
                  : "Redefinir senha"}
              {!busy ? <ArrowRightIcon size={17} /> : null}
            </button>
          </form>
        ) : null}

        <p className="login-card__security">
          <ShieldIcon size={15} />
          Sessão protegida por cookie HttpOnly e CSRF. A senha não é armazenada no navegador.
        </p>
      </section>
    </main>
  );
}
