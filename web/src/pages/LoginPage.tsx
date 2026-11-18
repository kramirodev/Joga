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
  verifyEmailChallenge,
  webEmailLogin,
  webEmailRegistration,
  ApiError,
} from "../lib/api";
import { useAuth } from "../lib/auth-context";
import { formatError, requestIdOf } from "../lib/format";
import { safeReturnPath } from "../lib/redirect";
import { useDocumentTitle } from "../lib/useDocumentTitle";

type Mode = "login" | "register";
type Step = "email" | "code";

function nowMs(): number {
  return new Date().getTime();
}

function emailError(value: string): string | null {
  const clean = value.trim();
  if (!clean) return "Informe o e-mail da sua conta.";
  if (clean.length > 254) return "O e-mail deve ter no máximo 254 caracteres.";
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(clean)) {
    return "Informe um e-mail válido, como nome@exemplo.com.";
  }
  return null;
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
  const [step, setStep] = useState<Step>("email");
  const [email, setEmail] = useState("");
  const [emailFieldError, setEmailFieldError] = useState<string | null>(null);
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
  const purpose = mode === "login" ? "login" : "registration";
  const resendSeconds = Math.max(0, Math.ceil((resendAt - now) / 1000));

  useEffect(() => {
    if (resendSeconds <= 0) return;
    const timer = window.setInterval(() => setNow(nowMs()), 1000);
    return () => window.clearInterval(timer);
  }, [resendSeconds]);

  if (user) {
    return <Navigate to={returnTo} replace />;
  }

  function switchMode(next: Mode) {
    setMode(next);
    setStep("email");
    setChallengeId(null);
    setCode("");
    setCodeFieldError(null);
    setError(null);
    setInfo(null);
    setEmailFieldError(null);
  }

  function resetToEmail() {
    setStep("email");
    setChallengeId(null);
    setCode("");
    setCodeFieldError(null);
    setError(null);
    setInfo(null);
    window.setTimeout(() => document.getElementById("login-email")?.focus(), 0);
  }

  async function startChallenge(event?: FormEvent<HTMLFormElement>) {
    event?.preventDefault();
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
      const challenge = await requestEmailCode(cleanEmail, purpose);
      setChallengeId(challenge.challenge_id);
      setResendAt(nowMs() + challenge.resend_after_seconds * 1000);
      setNow(nowMs());
      setStep("code");
      setCode("");
      setCodeFieldError(null);
    } catch (caught) {
      setError(caught);
    } finally {
      setBusy(false);
    }
  }

  async function resendCode() {
    if (resendSeconds > 0 || resending) return;
    setResending(true);
    setError(null);
    try {
      const challenge = await requestEmailCode(cleanEmail, purpose);
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
      const session =
        mode === "login"
          ? await webEmailLogin(receipt.challenge_id, cleanEmail)
          : await webEmailRegistration(receipt.challenge_id, cleanEmail);
      signIn(session);
      navigate(returnTo, { replace: true });
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
          <p className="step-label">{step === "email" ? "Passo 1 de 2" : "Passo 2 de 2"}</p>
          <h2 id="login-title">{step === "email" ? "Acessar o painel" : "Confirmar código"}</h2>
          <p>
            {step === "code"
              ? "Digite o código de seis dígitos enviado por e-mail."
              : mode === "login"
                ? "Entre com o e-mail da sua conta JOGA."
                : "Crie a conta do responsável pelo estabelecimento."}
          </p>
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
              hint="Use o e-mail vinculado à sua conta JOGA."
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
        ) : (
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
              {busy ? "Verificando..." : mode === "login" ? "Entrar" : "Criar conta"}
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
        )}

        <p className="login-card__security">
          <ShieldIcon size={15} />
          Sessão protegida por cookie HttpOnly e código de uso único.
        </p>
      </section>
    </main>
  );
}
