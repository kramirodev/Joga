import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import {
  ApiError,
  requestEmailCode,
  verifyEmailChallenge,
  webEmailLogin,
  webEmailRegistration,
} from "../lib/api";
import { AuthContext } from "../lib/auth-context";
import type { WebSessionPayload } from "../types";
import { LoginPage } from "./LoginPage";

vi.mock("../lib/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../lib/api")>();
  return {
    ...actual,
    requestEmailCode: vi.fn(),
    verifyEmailChallenge: vi.fn(),
    webEmailLogin: vi.fn(),
    webEmailRegistration: vi.fn(),
  };
});

const session: WebSessionPayload = {
  access_token: "access-1",
  access_expires_at: "2026-11-07T13:00:00Z",
  csrf_token: "csrf-1",
  user: { id: "user-1", status: "active" },
  capabilities: [],
};

function renderLogin(state?: { from?: unknown; expired?: unknown }) {
  const signIn = vi.fn();
  render(
    <MemoryRouter initialEntries={[{ pathname: "/login", state }]}>
      <AuthContext.Provider
        value={{
          user: null,
          capabilities: [],
          loading: false,
          sessionExpired: false,
          signIn,
          signOut: vi.fn(),
        }}
      >
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/" element={<div>Painel autenticado</div>} />
          <Route path="*" element={<div>Destino preservado</div>} />
        </Routes>
      </AuthContext.Provider>
    </MemoryRouter>,
  );
  return { signIn };
}

async function requestCode(
  user: ReturnType<typeof userEvent.setup>,
  email = "operador@example.com",
) {
  await user.type(screen.getByLabelText("E-mail"), email);
  await user.click(screen.getByRole("button", { name: "Receber código" }));
  await screen.findByLabelText("Código de verificação");
  await user.type(screen.getByLabelText("Código de verificação"), "123456");
}

describe("LoginPage", () => {
  beforeEach(() => {
    vi.mocked(requestEmailCode).mockReset();
    vi.mocked(verifyEmailChallenge).mockReset();
    vi.mocked(webEmailLogin).mockReset();
    vi.mocked(webEmailRegistration).mockReset();
  });

  it("faz login por código de e-mail e navega para o painel", async () => {
    vi.mocked(requestEmailCode).mockResolvedValue({
      challenge_id: "challenge-1",
      expires_at: "2026-11-07T12:10:00Z",
      resend_after_seconds: 60,
    });
    vi.mocked(verifyEmailChallenge).mockResolvedValue({
      challenge_id: "receipt-1",
      purpose: "email_login",
      verified_at: "2026-11-07T12:01:00Z",
      receipt_expires_at: "2026-11-07T12:11:00Z",
    });
    vi.mocked(webEmailLogin).mockResolvedValue(session);
    const user = userEvent.setup();
    const { signIn } = renderLogin();

    await requestCode(user);
    const form = document.querySelector("form");
    expect(form).not.toBeNull();
    await user.click(within(form!).getByRole("button", { name: "Entrar" }));

    await waitFor(() =>
      expect(webEmailLogin).toHaveBeenCalledWith("receipt-1", "operador@example.com"),
    );
    expect(requestEmailCode).toHaveBeenCalledWith("operador@example.com", "login");
    expect(verifyEmailChallenge).toHaveBeenCalledWith("challenge-1", "123456");
    expect(signIn).toHaveBeenCalledWith(session);
    expect(await screen.findByText("Painel autenticado")).toBeInTheDocument();
  });

  it("cria conta de operador por e-mail quando o modo é registro", async () => {
    vi.mocked(requestEmailCode).mockResolvedValue({
      challenge_id: "challenge-2",
      expires_at: "2026-11-07T12:10:00Z",
      resend_after_seconds: 60,
    });
    vi.mocked(verifyEmailChallenge).mockResolvedValue({
      challenge_id: "receipt-2",
      purpose: "email_verification",
      verified_at: "2026-11-07T12:01:00Z",
      receipt_expires_at: "2026-11-07T12:11:00Z",
    });
    vi.mocked(webEmailRegistration).mockResolvedValue(session);
    const user = userEvent.setup();
    const { signIn } = renderLogin();

    await user.click(screen.getByRole("tab", { name: "Criar conta" }));
    await requestCode(user);
    const form = document.querySelector("form");
    await user.click(within(form!).getByRole("button", { name: "Criar conta" }));

    await waitFor(() =>
      expect(webEmailRegistration).toHaveBeenCalledWith("receipt-2", "operador@example.com"),
    );
    expect(requestEmailCode).toHaveBeenCalledWith("operador@example.com", "registration");
    expect(webEmailLogin).not.toHaveBeenCalled();
    expect(signIn).toHaveBeenCalledWith(session);
  });

  it("avisa que o 202 é enfileirado e pode levar alguns minutos", async () => {
    vi.mocked(requestEmailCode).mockResolvedValue({
      challenge_id: "challenge-3",
      expires_at: "2026-11-07T12:10:00Z",
      resend_after_seconds: 60,
    });
    const user = userEvent.setup();
    renderLogin();

    await user.type(screen.getByLabelText("E-mail"), "operador@example.com");
    await user.click(screen.getByRole("button", { name: "Receber código" }));

    expect(await screen.findByText(/Enviamos um código de seis dígitos para/)).toBeInTheDocument();
    expect(screen.getByText(/pode levar alguns minutos/)).toBeInTheDocument();
    expect(screen.queryByLabelText("Telefone")).not.toBeInTheDocument();
    expect(screen.queryByText(/SMS/)).not.toBeInTheDocument();
  });

  it("mostra o Retry-After de 429 e mantém o usuário no passo de e-mail", async () => {
    vi.mocked(requestEmailCode).mockRejectedValue(
      new ApiError(429, "rate_limited", undefined, null, [], 45),
    );
    const user = userEvent.setup();
    renderLogin();

    await user.type(screen.getByLabelText("E-mail"), "operador@example.com");
    await user.click(screen.getByRole("button", { name: "Receber código" }));

    expect(
      await screen.findByText("Muitas tentativas. Tente novamente em 45 segundos."),
    ).toBeInTheDocument();
    expect(screen.getByLabelText("E-mail")).toBeInTheDocument();
  });

  it("explica cadastro fechado no registro", async () => {
    vi.mocked(requestEmailCode).mockRejectedValue(new ApiError(403, "signup_closed"));
    const user = userEvent.setup();
    renderLogin();

    await user.click(screen.getByRole("tab", { name: "Criar conta" }));
    await user.type(screen.getByLabelText("E-mail"), "operador@example.com");
    await user.click(screen.getByRole("button", { name: "Receber código" }));

    expect(
      await screen.findByText("O cadastro está fechado no momento. Entre com uma conta existente."),
    ).toBeInTheDocument();
  });

  it("trata 503 de e-mail desabilitado sem falar em telefone", async () => {
    vi.mocked(requestEmailCode).mockRejectedValue(new ApiError(503, "email_auth_disabled"));
    const user = userEvent.setup();
    renderLogin();

    await user.type(screen.getByLabelText("E-mail"), "operador@example.com");
    await user.click(screen.getByRole("button", { name: "Receber código" }));

    expect(
      await screen.findByText(
        "O acesso por e-mail está indisponível no momento. Tente novamente mais tarde.",
      ),
    ).toBeInTheDocument();
    expect(screen.queryByText(/telefone/i)).not.toBeInTheDocument();
  });

  it("informa credencial inválida no login sem dizer que o e-mail não está cadastrado", async () => {
    vi.mocked(requestEmailCode).mockResolvedValue({
      challenge_id: "challenge-7",
      expires_at: "2026-11-07T12:10:00Z",
      resend_after_seconds: 60,
    });
    vi.mocked(verifyEmailChallenge).mockResolvedValue({
      challenge_id: "receipt-7",
      purpose: "email_login",
      verified_at: "2026-11-07T12:01:00Z",
      receipt_expires_at: "2026-11-07T12:11:00Z",
    });
    vi.mocked(webEmailLogin).mockRejectedValue(new ApiError(401, "invalid_email_login"));
    const user = userEvent.setup();
    renderLogin();

    await requestCode(user);
    const form = document.querySelector("form");
    await user.click(within(form!).getByRole("button", { name: "Entrar" }));

    expect(
      await screen.findByText(
        "Este e-mail não consegue entrar. Confira o endereço ou crie uma conta.",
      ),
    ).toBeInTheDocument();
    expect(screen.queryByText(/não cadastrad/i)).not.toBeInTheDocument();
  });

  it("reenvia o código respeitando o intervalo do servidor", async () => {
    vi.mocked(requestEmailCode).mockResolvedValue({
      challenge_id: "challenge-8",
      expires_at: "2026-11-07T12:10:00Z",
      resend_after_seconds: 0,
    });
    const user = userEvent.setup();
    renderLogin();

    await requestCode(user);
    await user.click(screen.getByRole("button", { name: "Reenviar código" }));

    await waitFor(() => expect(requestEmailCode).toHaveBeenCalledTimes(2));
    expect(
      await screen.findByText("Novo código solicitado. Use apenas o código mais recente."),
    ).toBeInTheDocument();
  });

  it("valida o formato do e-mail antes de chamar o servidor", async () => {
    const user = userEvent.setup();
    renderLogin();

    await user.type(screen.getByLabelText("E-mail"), "sem-arroba");
    await user.click(screen.getByRole("button", { name: "Receber código" }));

    expect(
      await screen.findByText("Informe um e-mail válido, como nome@exemplo.com."),
    ).toBeInTheDocument();
    expect(requestEmailCode).not.toHaveBeenCalled();
  });

  it("avisa sessão expirada e retorna ao destino original", async () => {
    vi.mocked(requestEmailCode).mockResolvedValue({
      challenge_id: "challenge-9",
      expires_at: "2026-11-07T12:10:00Z",
      resend_after_seconds: 60,
    });
    vi.mocked(verifyEmailChallenge).mockResolvedValue({
      challenge_id: "receipt-9",
      purpose: "email_login",
      verified_at: "2026-11-07T12:01:00Z",
      receipt_expires_at: "2026-11-07T12:11:00Z",
    });
    vi.mocked(webEmailLogin).mockResolvedValue(session);
    const user = userEvent.setup();
    renderLogin({ from: "/organizations/org-1?tab=bookings", expired: true });

    expect(await screen.findByText(/Sua sessão expirou/)).toBeInTheDocument();

    await requestCode(user);
    const form = document.querySelector("form");
    await user.click(within(form!).getByRole("button", { name: "Entrar" }));

    expect(await screen.findByText("Destino preservado")).toBeInTheDocument();
  });
});
