import { useState, type FormEvent } from "react";
import { Navigate, useNavigate } from "react-router-dom";

import { ErrorNotice } from "../components/Feedback";
import {
  ApiError,
  requestPhoneChallenge,
  verifyPhoneChallenge,
  webLogin,
  webRegister,
} from "../lib/api";
import { useAuth } from "../lib/auth-context";
import { formatError, requestIdOf } from "../lib/format";

type Mode = "login" | "register";
type Step = "phone" | "code";

export function LoginPage() {
  const { user, signIn } = useAuth();
  const navigate = useNavigate();
  const [mode, setMode] = useState<Mode>("login");
  const [step, setStep] = useState<Step>("phone");
  const [phone, setPhone] = useState("");
  const [code, setCode] = useState("");
  const [challengeId, setChallengeId] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);

  if (user) {
    return <Navigate to="/" replace />;
  }

  function switchMode(next: Mode) {
    setMode(next);
    setStep("phone");
    setChallengeId(null);
    setCode("");
    setError(null);
  }

  async function startChallenge(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const challenge = await requestPhoneChallenge(
        phone,
        mode === "login" ? "login" : "registration",
      );
      setChallengeId(challenge.challenge_id);
      setStep("code");
    } catch (caught) {
      setError(caught);
    } finally {
      setBusy(false);
    }
  }

  async function confirmCode(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!challengeId) return;
    setBusy(true);
    setError(null);
    try {
      const receipt = await verifyPhoneChallenge(challengeId, code);
      const session =
        mode === "login"
          ? await webLogin(receipt.challenge_id)
          : await webRegister(receipt.challenge_id);
      signIn(session);
      navigate("/", { replace: true });
    } catch (caught) {
      if (caught instanceof ApiError && caught.code === "account_not_found") {
        switchMode("register");
      } else if (caught instanceof ApiError && caught.code === "phone_already_registered") {
        switchMode("login");
      }
      setError(caught);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="login-shell">
      <section className="login-hero" aria-label="JOGA y GESTÃO">
        <p className="eyebrow">Painel do estabelecimento</p>
        <h1>
          A operação do JOGA
          <br />
          na sua mão.
        </h1>
        <p>
          Gerencie organizações, membros, estabelecimentos e a trilha de auditoria das operações
          originadas no JOGA.
        </p>
        <ul className="login-hero__list">
          <li>Isolamento por organização</li>
          <li>Papéis e permissões explícitos</li>
          <li>Histórico auditável</li>
        </ul>
      </section>

      <section className="card login-card">
        <div className="tabs tabs--compact" role="tablist" aria-label="Acesso">
          <button
            type="button"
            role="tab"
            aria-selected={mode === "login"}
            className={mode === "login" ? "tab tab--active" : "tab"}
            onClick={() => switchMode("login")}
          >
            Entrar
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={mode === "register"}
            className={mode === "register" ? "tab tab--active" : "tab"}
            onClick={() => switchMode("register")}
          >
            Criar conta
          </button>
        </div>

        <p className="muted">
          {mode === "login"
            ? "Use o mesmo telefone da sua conta JOGA. Não é necessário criar uma conta separada."
            : "Crie a conta do responsável pelo estabelecimento. Ela também serve para o aplicativo JOGA."}
        </p>

        {error ? <ErrorNotice message={formatError(error)} requestId={requestIdOf(error)} /> : null}

        {step === "phone" ? (
          <form className="form" onSubmit={startChallenge}>
            <label className="field">
              <span>Telefone com DDD</span>
              <input
                type="tel"
                inputMode="tel"
                autoComplete="tel"
                placeholder="+55 11 98765-4321"
                value={phone}
                onChange={(event) => setPhone(event.target.value)}
                required
                minLength={7}
                maxLength={20}
              />
            </label>
            <button type="submit" className="button button--primary" disabled={busy}>
              {busy ? "Enviando..." : "Receber código"}
            </button>
            <p className="hint">
              Em ambiente local, o OTP pode estar fixado por <code>JOGA_DEV_FIXED_OTP</code>.
            </p>
          </form>
        ) : (
          <form className="form" onSubmit={confirmCode}>
            <p className="muted">
              Enviamos um código de seis dígitos para <strong>{phone}</strong>.
            </p>
            <label className="field">
              <span>Código de verificação</span>
              <input
                type="text"
                inputMode="numeric"
                autoComplete="one-time-code"
                pattern="[0-9]{6}"
                maxLength={6}
                placeholder="000000"
                value={code}
                onChange={(event) => setCode(event.target.value.replace(/\D/g, ""))}
                required
              />
            </label>
            <button
              type="submit"
              className="button button--primary"
              disabled={busy || code.length !== 6}
            >
              {busy ? "Verificando..." : mode === "login" ? "Entrar" : "Criar conta"}
            </button>
            <button
              type="button"
              className="button button--link"
              onClick={() => {
                setStep("phone");
                setChallengeId(null);
                setCode("");
                setError(null);
              }}
            >
              Trocar telefone
            </button>
          </form>
        )}
      </section>
    </div>
  );
}
