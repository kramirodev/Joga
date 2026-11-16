import type { ReactNode } from "react";

import { normalizeMoneyInput } from "../../lib/validation";
import { Field } from "./Field";

export function MoneyField({
  id,
  label,
  value,
  onChange,
  error,
  hint,
  disabled,
  required = true,
  placeholder = "0,00",
  autoFocus = false,
}: {
  id: string;
  label: string;
  value: string;
  onChange: (value: string) => void;
  error?: string | null;
  hint?: ReactNode;
  disabled?: boolean;
  required?: boolean;
  placeholder?: string;
  autoFocus?: boolean;
}) {
  const describedBy = [hint ? `${id}-hint` : null, error ? `${id}-error` : null]
    .filter(Boolean)
    .join(" ");

  return (
    <Field id={id} label={label} hint={hint} error={error} required={required}>
      <div className="money-field">
        <span className="money-field__prefix" aria-hidden="true">
          R$
        </span>
        <input
          id={id}
          className="input money-field__input"
          type="text"
          inputMode="decimal"
          autoComplete="off"
          value={value}
          onChange={(event) => onChange(event.target.value.replace(/[^\d.,]/g, ""))}
          onBlur={() => {
            if (value.trim()) onChange(normalizeMoneyInput(value));
          }}
          placeholder={placeholder}
          aria-invalid={error ? true : undefined}
          aria-describedby={describedBy || undefined}
          required={required}
          disabled={disabled}
          data-autofocus={autoFocus ? true : undefined}
        />
      </div>
    </Field>
  );
}
