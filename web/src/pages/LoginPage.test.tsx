import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import {
  ApiError,
  requestEmailCode,
  resetEmailPassword,
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
    resetEmailPassword: vi.fn(),
  };
});

const session: WebSessionPayload = {
  access_token: "access-1",
  access_expires_at: "2026-11-19T13:00:00Z",
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

async function login(
  user: ReturnType<typeof userEvent.setup>,
  email = "operador@example.com",
  password = "senha-segura-123",
) {
  await user.type(screen.getByLabelText("E-mail"), email);
  await user.type(screen.getByLabelText("Senha"), password);
  const form = document.querySelector("form");
  await user.click(within(form!).getByRole("button", { name: "Entrar" }));
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

async function goToPasswordStep(
  user: ReturnType<typeof userEvent.setup>,
  mode: "register" | "reset",
) {
  if (mode === "register") {
    await user.click(screen.getByRole("tab", { name: "Criar conta" }));
  } else {
    await user.click(screen.getByRole("button", { name: "Esqueci minha senha" }));
  }
  await requestCode(user);
  const codeForm = document.querySelector("form");
  await user.click(within(codeForm!).getByRole("button", { name: "Continuar" }));
  const submit = await screen.findByRole("button", {
    name: mode === "register" ? "Criar conta e entrar" : "Redefinir senha",
  });
  await waitFor(() => expect(submit).toBeEnabled());
}

async function fillNewPassword(
  user: ReturnType<typeof userEvent.setup>,
  mode: "register" | "reset",
  password: string,
  confirmation = password,
) {
  await user.type(
    screen.getByLabelText(mode === "register" ? "Senha" : "Nova senha", { selector: "input" }),
    password,
  );
  await user.type(
    screen.getByLabelText(mode === "register" ? "Confirmar senha" : "Confirmar nova senha", {
      selector: "input",
    }),
    confirmation,
  );
}

describe("LoginPage", () => {
  beforeEach(() => {
    vi.mocked(requestEmailCode).mockReset();
    vi.mocked(verifyEmailChallenge).mockReset();
    vi.mocked(webEmailLogin).mockReset();
    vi.mocked(webEmailRegistration).mockReset();
    vi.mocked(resetEmailPassword).mockReset();
  });

  it("faz login direto com e-mail e senha, sem etapa de código", async () => {
    vi.mocked(webEmailLogin).mockResolvedValue(session);
    const user = userEvent.setup();
    const { signIn } = renderLogin();

    expect(screen.queryByLabelText("Código de verificação")).not.toBeInTheDocument();
    await login(user);

    await waitFor(() =>
      expect(webEmailLogin).toHaveBeenCalledWith("operador@example.com", "senha-segura-123"),
    );
    expect(requestEmailCode).not.toHaveBeenCalled();
    expect(verifyEmailChallenge).not.toHaveBeenCalled();
    expect(signIn).toHaveBeenCalledWith(session);
    expect(await screen.findByText("Painel autenticado")).toBeInTheDocument();
  });

  it("mostra erro genérico de credenciais sem revelar existência da conta", async () => {
    vi.mocked(webEmailLogin).mockRejectedValue(new ApiError(401, "invalid_credentials"));
    const user = userEvent.setup();
    renderLogin();

    await login(user);

    expect(await screen.findByText("E-mail ou senha inválidos.")).toBeInTheDocument();
    expect(screen.queryByText(/não cadastrad/i)).not.toBeInTheDocument();
  });

  it("cadastra operador com e-mail, código e senha", async () => {
    vi.mocked(requestEmailCode).mockResolvedValue({
      challenge_id: "challenge-1",
      expires_at: "2026-11-19T12:10:00Z",
      resend_after_seconds: 60,
    });
    vi.mocked(verifyEmailChallenge).mockResolvedValue({
      challenge_id: "receipt-1",
      purpose: "email_verification",
      verified_at: "2026-11-19T12:01:00Z",
      receipt_expires_at: "2026-11-19T12:11:00Z",
    });
    vi.mocked(webEmailRegistration).mockResolvedValue(session);
    const user = userEvent.setup();
    const { signIn } = renderLogin();

    await goToPasswordStep(user, "register");
    await fillNewPassword(user, "register", "senha-segura-123");
    await user.click(screen.getByRole("button", { name: "Criar conta e entrar" }));

    await waitFor(() =>
      expect(webEmailRegistration).toHaveBeenCalledWith(
        "receipt-1",
        "operador@example.com",
        "senha-segura-123",
      ),
    );
    expect(requestEmailCode).toHaveBeenCalledWith("operador@example.com", "registration");
    expect(verifyEmailChallenge).toHaveBeenCalledWith("challenge-1", "123456");
    expect(signIn).toHaveBeenCalledWith(session);
    expect(await screen.findByText("Painel autenticado")).toBeInTheDocument();
  });

  it("recupera a senha com e-mail, código e nova senha e volta ao login", async () => {
    vi.mocked(requestEmailCode).mockResolvedValue({
      challenge_id: "challenge-2",
      expires_at: "2026-11-19T12:10:00Z",
      resend_after_seconds: 60,
    });
    vi.mocked(verifyEmailChallenge).mockResolvedValue({
      challenge_id: "receipt-2",
      purpose: "password_reset",
      verified_at: "2026-11-19T12:01:00Z",
      receipt_expires_at: "2026-11-19T12:11:00Z",
    });
    vi.mocked(resetEmailPassword).mockResolvedValue(undefined);
    const user = userEvent.setup();
    renderLogin();

    await goToPasswordStep(user, "reset");
    await fillNewPassword(user, "reset", "nova-senha-123");
    await user.click(screen.getByRole("button", { name: "Redefinir senha" }));

    await waitFor(() =>
      expect(resetEmailPassword).toHaveBeenCalledWith(
        "receipt-2",
        "operador@example.com",
        "nova-senha-123",
      ),
    );
    expect(requestEmailCode).toHaveBeenCalledWith("operador@example.com", "password_reset");
    expect(webEmailLogin).not.toHaveBeenCalled();
    expect(await screen.findByText("Senha alterada. Entre com a nova senha.")).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "Entrar" })).toHaveAttribute("aria-selected", "true");
    expect(screen.getByLabelText("Senha")).toBeInTheDocument();
  });

  it("exige senha de pelo menos 10 caracteres no cadastro", async () => {
    vi.mocked(requestEmailCode).mockResolvedValue({
      challenge_id: "challenge-3",
      expires_at: "2026-11-19T12:10:00Z",
      resend_after_seconds: 60,
    });
    vi.mocked(verifyEmailChallenge).mockResolvedValue({
      challenge_id: "receipt-3",
      purpose: "email_verification",
      verified_at: "2026-11-19T12:01:00Z",
      receipt_expires_at: "2026-11-19T12:11:00Z",
    });
    const user = userEvent.setup();
    renderLogin();

    await goToPasswordStep(user, "register");
    await fillNewPassword(user, "register", "curta");
    await user.click(screen.getByRole("button", { name: "Criar conta e entrar" }));

    expect(
      await screen.findByText("A senha deve ter pelo menos 10 caracteres."),
    ).toBeInTheDocument();
    expect(webEmailRegistration).not.toHaveBeenCalled();
  });

  it("recusa confirmação de senha divergente", async () => {
    vi.mocked(requestEmailCode).mockResolvedValue({
      challenge_id: "challenge-4",
      expires_at: "2026-11-19T12:10:00Z",
      resend_after_seconds: 60,
    });
    vi.mocked(verifyEmailChallenge).mockResolvedValue({
      challenge_id: "receipt-4",
      purpose: "email_verification",
      verified_at: "2026-11-19T12:01:00Z",
      receipt_expires_at: "2026-11-19T12:11:00Z",
    });
    const user = userEvent.setup();
    renderLogin();

    await goToPasswordStep(user, "register");
    await fillNewPassword(user, "register", "senha-segura-123", "senha-segura-124");
    await user.click(screen.getByRole("button", { name: "Criar conta e entrar" }));

    expect(await screen.findByText("As senhas não coincidem.")).toBeInTheDocument();
    expect(webEmailRegistration).not.toHaveBeenCalled();
  });

  it("avisa que o 202 é enfileirado e não oferece telefone", async () => {
    vi.mocked(requestEmailCode).mockResolvedValue({
      challenge_id: "challenge-5",
      expires_at: "2026-11-19T12:10:00Z",
      resend_after_seconds: 60,
    });
    const user = userEvent.setup();
    renderLogin();

    await user.click(screen.getByRole("tab", { name: "Criar conta" }));
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

    await user.click(screen.getByRole("tab", { name: "Criar conta" }));
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
    vi.mocked(webEmailLogin).mockRejectedValue(new ApiError(503, "email_auth_disabled"));
    const user = userEvent.setup();
    renderLogin();

    await login(user);

    expect(
      await screen.findByText(
        "O acesso por e-mail está indisponível no momento. Tente novamente mais tarde.",
      ),
    ).toBeInTheDocument();
    expect(screen.queryByText(/telefone/i)).not.toBeInTheDocument();
  });

  it("reenvia o código respeitando o intervalo do servidor", async () => {
    vi.mocked(requestEmailCode).mockResolvedValue({
      challenge_id: "challenge-6",
      expires_at: "2026-11-19T12:10:00Z",
      resend_after_seconds: 0,
    });
    const user = userEvent.setup();
    renderLogin();

    await user.click(screen.getByRole("tab", { name: "Criar conta" }));
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

    await login(user, "sem-arroba", "senha-segura-123");

    expect(
      await screen.findByText("Informe um e-mail válido, como nome@exemplo.com."),
    ).toBeInTheDocument();
    expect(webEmailLogin).not.toHaveBeenCalled();
  });

  it("avisa sessão expirada e retorna ao destino original", async () => {
    vi.mocked(webEmailLogin).mockResolvedValue(session);
    const user = userEvent.setup();
    renderLogin({ from: "/organizations/org-1?tab=bookings", expired: true });

    expect(await screen.findByText(/Sua sessão expirou/)).toBeInTheDocument();

    await login(user);

    expect(await screen.findByText("Destino preservado")).toBeInTheDocument();
  });
});
