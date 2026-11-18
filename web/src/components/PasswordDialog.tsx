import { useId, useState, type FormEvent } from "react";

import { ErrorNotice } from "./Feedback";
import { TextField } from "./ui/Field";
import { Modal } from "./ui/Modal";
import { useToast } from "./ui/toast-context";
import { ApiError, changePassword } from "../lib/api";
import { formatError, requestIdOf } from "../lib/format";
import {
  passwordConfirmationError,
  passwordError,
  PASSWORD_MAX_LENGTH,
  PASSWORD_MIN_LENGTH,
} from "../lib/validation";

export function PasswordDialog({ open, onClose }: { open: boolean; onClose: () => void }) {
  const toast = useToast();
  const formId = useId();
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmation, setConfirmation] = useState("");
  const [currentError, setCurrentError] = useState<string | null>(null);
  const [newError, setNewError] = useState<string | null>(null);
  const [confirmationError, setConfirmationError] = useState<string | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);

  function reset() {
    setCurrentPassword("");
    setNewPassword("");
    setConfirmation("");
    setCurrentError(null);
    setNewError(null);
    setConfirmationError(null);
    setError(null);
  }

  function close() {
    if (busy) return;
    reset();
    onClose();
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const currentValidation = currentPassword ? null : "Informe a senha atual.";
    const newValidation = passwordError(newPassword);
    const confirmationValidation = passwordConfirmationError(newPassword, confirmation);
    setCurrentError(currentValidation);
    setNewError(newValidation);
    setConfirmationError(confirmationValidation);
    if (currentValidation || newValidation || confirmationValidation) {
      const firstId = currentValidation
        ? "current-password"
        : newValidation
          ? "new-password"
          : "confirm-password";
      document.getElementById(firstId)?.focus();
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await changePassword(currentPassword, newPassword);
      reset();
      toast.push({
        title: "Senha alterada",
        description: "As outras sessões foram encerradas.",
        tone: "success",
      });
      onClose();
    } catch (caught) {
      if (caught instanceof ApiError && caught.code === "invalid_credentials") {
        setCurrentError("A senha atual está incorreta.");
        document.getElementById("current-password")?.focus();
        return;
      }
      setError(caught);
    } finally {
      setBusy(false);
    }
  }

  return (
    <Modal
      open={open}
      title="Alterar senha"
      description="A troca encerra as outras sessões; esta continua válida."
      onClose={close}
      closeOnOverlay={!busy}
      size="sm"
      footer={
        <>
          <button type="button" className="button button--ghost" onClick={close} disabled={busy}>
            Cancelar
          </button>
          <button
            type="submit"
            form={formId}
            className="button button--primary"
            disabled={busy}
            aria-busy={busy || undefined}
          >
            {busy ? "Salvando..." : "Salvar nova senha"}
          </button>
        </>
      }
    >
      <form id={formId} className="form" onSubmit={submit} noValidate>
        {error ? <ErrorNotice message={formatError(error)} requestId={requestIdOf(error)} /> : null}
        <TextField
          id="current-password"
          label="Senha atual"
          type="password"
          autoComplete="current-password"
          maxLength={PASSWORD_MAX_LENGTH}
          value={currentPassword}
          onChange={(event) => {
            setCurrentPassword(event.target.value);
            if (currentError) setCurrentError(null);
          }}
          error={currentError}
          disabled={busy}
          data-autofocus
          required
        />
        <TextField
          id="new-password"
          label="Nova senha"
          type="password"
          autoComplete="new-password"
          minLength={PASSWORD_MIN_LENGTH}
          maxLength={PASSWORD_MAX_LENGTH}
          value={newPassword}
          onChange={(event) => {
            setNewPassword(event.target.value);
            if (newError) setNewError(null);
          }}
          error={newError}
          hint="Use de 10 a 128 caracteres. Evite senhas comuns."
          disabled={busy}
          required
        />
        <TextField
          id="confirm-password"
          label="Confirmar nova senha"
          type="password"
          autoComplete="new-password"
          maxLength={PASSWORD_MAX_LENGTH}
          value={confirmation}
          onChange={(event) => {
            setConfirmation(event.target.value);
            if (confirmationError) setConfirmationError(null);
          }}
          error={confirmationError}
          disabled={busy}
          required
        />
      </form>
    </Modal>
  );
}
