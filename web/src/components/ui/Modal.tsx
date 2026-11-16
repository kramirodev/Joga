import { useEffect, useId, useRef, type FormEvent, type ReactNode } from "react";
import { createPortal } from "react-dom";

import { CloseIcon } from "./Icons";
import { TextareaField } from "./Field";

const FOCUSABLE =
  'a[href], button:not([disabled]), textarea:not([disabled]), input:not([disabled]), select:not([disabled]), [tabindex]:not([tabindex="-1"])';

interface ModalProps {
  open: boolean;
  title: string;
  description?: ReactNode;
  children?: ReactNode;
  footer?: ReactNode;
  onClose: () => void;
  size?: "sm" | "md" | "lg";
  closeOnOverlay?: boolean;
}

export function Modal({
  open,
  title,
  description,
  children,
  footer,
  onClose,
  size = "md",
  closeOnOverlay = true,
}: ModalProps) {
  const titleId = useId();
  const descriptionId = useId();
  const dialogRef = useRef<HTMLDivElement>(null);
  const previouslyFocused = useRef<HTMLElement | null>(null);
  const onCloseRef = useRef(onClose);

  useEffect(() => {
    onCloseRef.current = onClose;
  }, [onClose]);

  useEffect(() => {
    if (!open) return;
    previouslyFocused.current = document.activeElement as HTMLElement | null;
    document.body.classList.add("modal-open");

    const dialog = dialogRef.current;
    const first =
      dialog?.querySelector<HTMLElement>("[data-autofocus]") ??
      dialog?.querySelector<HTMLElement>(FOCUSABLE) ??
      dialog;
    first?.focus();

    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        event.preventDefault();
        onCloseRef.current();
        return;
      }
      if (event.key !== "Tab" || !dialog) return;
      const focusable = Array.from(dialog.querySelectorAll<HTMLElement>(FOCUSABLE)).filter(
        (element) => element.offsetParent !== null || element === document.activeElement,
      );
      if (focusable.length === 0) {
        event.preventDefault();
        return;
      }
      const firstItem = focusable[0];
      const lastItem = focusable[focusable.length - 1];
      if (event.shiftKey && document.activeElement === firstItem) {
        event.preventDefault();
        lastItem?.focus();
      } else if (!event.shiftKey && document.activeElement === lastItem) {
        event.preventDefault();
        firstItem?.focus();
      }
    }

    document.addEventListener("keydown", handleKeyDown);
    return () => {
      document.removeEventListener("keydown", handleKeyDown);
      document.body.classList.remove("modal-open");
      previouslyFocused.current?.focus();
    };
  }, [open]);

  if (!open) return null;

  return createPortal(
    <div
      className="modal-overlay"
      onMouseDown={(event) => {
        if (closeOnOverlay && event.target === event.currentTarget) onClose();
      }}
    >
      <div
        ref={dialogRef}
        className={`modal modal--${size}`}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        aria-describedby={description ? descriptionId : undefined}
        tabIndex={-1}
      >
        <div className="modal__header">
          <div>
            <h2 id={titleId} className="modal__title">
              {title}
            </h2>
            {description ? (
              <div id={descriptionId} className="modal__description">
                {description}
              </div>
            ) : null}
          </div>
          <button type="button" className="icon-button" aria-label="Fechar" onClick={onClose}>
            <CloseIcon size={18} />
          </button>
        </div>
        {children ? <div className="modal__body">{children}</div> : null}
        {footer ? <div className="modal__footer">{footer}</div> : null}
      </div>
    </div>,
    document.body,
  );
}

interface ConfirmDialogProps {
  open: boolean;
  title: string;
  description?: ReactNode;
  children?: ReactNode;
  confirmLabel?: string;
  cancelLabel?: string;
  tone?: "default" | "danger";
  busy?: boolean;
  confirmDisabled?: boolean;
  onConfirm: () => void;
  onClose: () => void;
}

export function ConfirmDialog({
  open,
  title,
  description,
  children,
  confirmLabel = "Confirmar",
  cancelLabel = "Cancelar",
  tone = "default",
  busy = false,
  confirmDisabled = false,
  onConfirm,
  onClose,
}: ConfirmDialogProps) {
  return (
    <Modal
      open={open}
      title={title}
      description={description}
      onClose={busy ? () => undefined : onClose}
      closeOnOverlay={!busy}
      size="sm"
      footer={
        <>
          <button type="button" className="button button--ghost" onClick={onClose} disabled={busy}>
            {cancelLabel}
          </button>
          <button
            type="button"
            className={
              tone === "danger"
                ? "button button--danger button--solid-danger"
                : "button button--primary"
            }
            onClick={onConfirm}
            disabled={busy || confirmDisabled}
            aria-busy={busy || undefined}
          >
            {busy ? "Processando..." : confirmLabel}
          </button>
        </>
      }
    >
      {children}
    </Modal>
  );
}

interface ReasonDialogProps {
  open: boolean;
  title: string;
  description?: ReactNode;
  label: string;
  value: string;
  onChange: (value: string) => void;
  error?: string | null;
  placeholder?: string;
  maxLength?: number;
  minLength?: number;
  confirmLabel?: string;
  tone?: "default" | "danger";
  busy?: boolean;
  children?: ReactNode;
  onConfirm: () => void;
  onClose: () => void;
}

export function ReasonDialog({
  open,
  title,
  description,
  label,
  value,
  onChange,
  error,
  placeholder,
  maxLength = 200,
  minLength = 1,
  confirmLabel = "Confirmar",
  tone = "default",
  busy = false,
  children,
  onConfirm,
  onClose,
}: ReasonDialogProps) {
  const id = useId();

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (busy) return;
    onConfirm();
  }

  return (
    <Modal
      open={open}
      title={title}
      description={description}
      onClose={busy ? () => undefined : onClose}
      closeOnOverlay={!busy}
      size="md"
      footer={
        <>
          <button type="button" className="button button--ghost" onClick={onClose} disabled={busy}>
            Cancelar
          </button>
          <button
            type="submit"
            form={id}
            className={
              tone === "danger"
                ? "button button--danger button--solid-danger"
                : "button button--primary"
            }
            disabled={busy || value.trim().length < minLength}
            aria-busy={busy || undefined}
          >
            {busy ? "Processando..." : confirmLabel}
          </button>
        </>
      }
    >
      <form id={id} className="form" onSubmit={submit}>
        {children}
        <TextareaField
          id={`${id}-reason`}
          label={label}
          value={value}
          onChange={(event) => onChange(event.target.value)}
          error={error}
          placeholder={placeholder}
          maxLength={maxLength}
          minLength={minLength}
          required
          rows={4}
          data-autofocus
        />
      </form>
    </Modal>
  );
}
