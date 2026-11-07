import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import {
  ApiError,
  requestPhoneChallenge,
  verifyPhoneChallenge,
  webLogin,
  webRegister,
} from "../lib/api";
import { AuthContext } from "../lib/auth-context";
import type { WebSessionPayload } from "../types";
import { LoginPage } from "./LoginPage";

vi.mock("../lib/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../lib/api")>();
  return {
    ...actual,
    requestPhoneChallenge: vi.fn(),
    verifyPhoneChallenge: vi.fn(),
    webLogin: vi.fn(),
    webRegister: vi.fn(),
  };
});

const session: WebSessionPayload = {
  access_token: "access-1",
  access_expires_at: "2026-11-07T13:00:00Z",
  csrf_token: "csrf-1",
  user: { id: "user-1", status: "active" },
};

function renderLogin() {
  const signIn = vi.fn();
  render(
    <MemoryRouter initialEntries={["/login"]}>
      <AuthContext.Provider value={{ user: null, loading: false, signIn, signOut: vi.fn() }}>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/" element={<div>Painel autenticado</div>} />
        </Routes>
      </AuthContext.Provider>
    </MemoryRouter>,
  );
  return { signIn };
}

async function requestCode(user: ReturnType<typeof userEvent.setup>) {
  await user.type(screen.getByLabelText("Telefone com DDD"), "+55 11 98765-4321");
  await user.click(screen.getByRole("button", { name: "Receber código" }));
  await screen.findByText(/Enviamos um código/);
  await user.type(screen.getByLabelText("Código de verificação"), "123456");
}

describe("LoginPage", () => {
  beforeEach(() => {
    vi.mocked(requestPhoneChallenge).mockReset();
    vi.mocked(verifyPhoneChallenge).mockReset();
    vi.mocked(webLogin).mockReset();
    vi.mocked(webRegister).mockReset();
  });

  it("faz login por OTP e navega para o painel", async () => {
    vi.mocked(requestPhoneChallenge).mockResolvedValue({
      challenge_id: "challenge-1",
      expires_at: "2026-11-07T12:10:00Z",
      resend_after_seconds: 60,
    });
    vi.mocked(verifyPhoneChallenge).mockResolvedValue({
      challenge_id: "receipt-1",
      purpose: "login",
      verified_at: "2026-11-07T12:01:00Z",
      receipt_expires_at: "2026-11-07T12:11:00Z",
    });
    vi.mocked(webLogin).mockResolvedValue(session);
    const user = userEvent.setup();
    const { signIn } = renderLogin();

    await requestCode(user);
    const form = document.querySelector("form");
    expect(form).not.toBeNull();
    await user.click(within(form!).getByRole("button", { name: "Entrar" }));

    await waitFor(() => expect(webLogin).toHaveBeenCalledWith("receipt-1"));
    expect(requestPhoneChallenge).toHaveBeenCalledWith("+55 11 98765-4321", "login");
    expect(signIn).toHaveBeenCalledWith(session);
    expect(await screen.findByText("Painel autenticado")).toBeInTheDocument();
  });

  it("cria conta quando o modo é registro", async () => {
    vi.mocked(requestPhoneChallenge).mockResolvedValue({
      challenge_id: "challenge-2",
      expires_at: "2026-11-07T12:10:00Z",
      resend_after_seconds: 60,
    });
    vi.mocked(verifyPhoneChallenge).mockResolvedValue({
      challenge_id: "receipt-2",
      purpose: "registration",
      verified_at: "2026-11-07T12:01:00Z",
      receipt_expires_at: "2026-11-07T12:11:00Z",
    });
    vi.mocked(webRegister).mockResolvedValue(session);
    const user = userEvent.setup();
    const { signIn } = renderLogin();

    await user.click(screen.getByRole("tab", { name: "Criar conta" }));
    await requestCode(user);
    const form = document.querySelector("form");
    await user.click(within(form!).getByRole("button", { name: "Criar conta" }));

    await waitFor(() => expect(webRegister).toHaveBeenCalledWith("receipt-2"));
    expect(requestPhoneChallenge).toHaveBeenCalledWith("+55 11 98765-4321", "registration");
    expect(webLogin).not.toHaveBeenCalled();
    expect(signIn).toHaveBeenCalledWith(session);
  });

  it("muda para registro quando a conta não existe", async () => {
    vi.mocked(requestPhoneChallenge).mockResolvedValue({
      challenge_id: "challenge-3",
      expires_at: "2026-11-07T12:10:00Z",
      resend_after_seconds: 60,
    });
    vi.mocked(verifyPhoneChallenge).mockResolvedValue({
      challenge_id: "receipt-3",
      purpose: "login",
      verified_at: "2026-11-07T12:01:00Z",
      receipt_expires_at: "2026-11-07T12:11:00Z",
    });
    vi.mocked(webLogin).mockRejectedValue(new ApiError(404, "account_not_found"));
    const user = userEvent.setup();
    renderLogin();

    await requestCode(user);
    const form = document.querySelector("form");
    await user.click(within(form!).getByRole("button", { name: "Entrar" }));

    await waitFor(() =>
      expect(screen.getByRole("tab", { name: "Criar conta" })).toHaveAttribute(
        "aria-selected",
        "true",
      ),
    );
    expect(
      screen.getByText(
        "Não encontramos uma conta com esse telefone. Crie uma conta para continuar.",
      ),
    ).toBeInTheDocument();
    expect(screen.getByLabelText("Telefone com DDD")).toBeInTheDocument();
  });
});
