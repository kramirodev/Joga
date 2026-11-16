import type {
  InputHTMLAttributes,
  ReactNode,
  SelectHTMLAttributes,
  TextareaHTMLAttributes,
} from "react";

interface FieldChrome {
  id: string;
  label: string;
  hint?: ReactNode;
  error?: string | null;
  required?: boolean;
  counter?: { current: number; max: number };
  className?: string;
}

function describedBy(id: string, hint?: ReactNode, error?: string | null): string | undefined {
  const ids = [hint ? `${id}-hint` : null, error ? `${id}-error` : null].filter(Boolean);
  return ids.length > 0 ? ids.join(" ") : undefined;
}

function FieldLabel({ id, label, required }: Pick<FieldChrome, "id" | "label" | "required">) {
  return (
    <label className="field__label" htmlFor={id}>
      {label}
      {required ? <span className="field__required" aria-hidden="true" /> : null}
    </label>
  );
}

function FieldFooter({
  id,
  hint,
  error,
  counter,
}: Pick<FieldChrome, "id" | "hint" | "error" | "counter">) {
  const ratio = counter && counter.max > 0 ? counter.current / counter.max : 0;
  return (
    <>
      {hint ? (
        <p className="field__hint" id={`${id}-hint`}>
          {hint}
        </p>
      ) : null}
      {counter ? (
        <p
          className={
            ratio >= 0.95
              ? "field__counter field__counter--limit"
              : ratio >= 0.8
                ? "field__counter field__counter--near"
                : "field__counter"
          }
          aria-hidden="true"
        >
          {counter.current}/{counter.max}
        </p>
      ) : null}
      {error ? (
        <p className="field__error" id={`${id}-error`} aria-live="polite">
          {error}
        </p>
      ) : null}
    </>
  );
}

export function Field({
  id,
  label,
  hint,
  error,
  required,
  counter,
  className,
  children,
}: FieldChrome & { children: ReactNode }) {
  return (
    <div className={className ? `field ${className}` : "field"}>
      <FieldLabel id={id} label={label} required={required} />
      {children}
      <FieldFooter id={id} hint={hint} error={error} counter={counter} />
    </div>
  );
}

type TextFieldProps = Omit<InputHTMLAttributes<HTMLInputElement>, "id" | "className"> &
  FieldChrome & { inputClassName?: string };

export function TextField({
  id,
  label,
  hint,
  error,
  required,
  counter,
  className,
  inputClassName,
  value,
  maxLength,
  ...input
}: TextFieldProps) {
  return (
    <div className={className ? `field ${className}` : "field"}>
      <FieldLabel id={id} label={label} required={required} />
      <input
        {...input}
        id={id}
        className={inputClassName ? `input ${inputClassName}` : "input"}
        value={value}
        maxLength={maxLength}
        aria-invalid={error ? true : undefined}
        aria-describedby={describedBy(id, hint, error)}
        required={required}
      />
      <FieldFooter
        id={id}
        hint={hint}
        error={error}
        counter={
          counter ??
          (maxLength ? { current: String(value ?? "").length, max: maxLength } : undefined)
        }
      />
    </div>
  );
}

type TextareaFieldProps = Omit<TextareaHTMLAttributes<HTMLTextAreaElement>, "id" | "className"> &
  FieldChrome & { inputClassName?: string };

export function TextareaField({
  id,
  label,
  hint,
  error,
  required,
  counter,
  className,
  inputClassName,
  value,
  maxLength,
  ...input
}: TextareaFieldProps) {
  return (
    <div className={className ? `field ${className}` : "field"}>
      <FieldLabel id={id} label={label} required={required} />
      <textarea
        {...input}
        id={id}
        className={inputClassName ? `textarea ${inputClassName}` : "textarea"}
        value={value}
        maxLength={maxLength}
        aria-invalid={error ? true : undefined}
        aria-describedby={describedBy(id, hint, error)}
        required={required}
      />
      <FieldFooter
        id={id}
        hint={hint}
        error={error}
        counter={
          counter ??
          (maxLength ? { current: String(value ?? "").length, max: maxLength } : undefined)
        }
      />
    </div>
  );
}

type SelectFieldProps = Omit<SelectHTMLAttributes<HTMLSelectElement>, "id" | "className"> &
  FieldChrome & { inputClassName?: string };

export function SelectField({
  id,
  label,
  hint,
  error,
  required,
  counter,
  className,
  inputClassName,
  children,
  ...input
}: SelectFieldProps) {
  return (
    <div className={className ? `field ${className}` : "field"}>
      <FieldLabel id={id} label={label} required={required} />
      <select
        {...input}
        id={id}
        className={inputClassName ? `select ${inputClassName}` : "select"}
        aria-invalid={error ? true : undefined}
        aria-describedby={describedBy(id, hint, error)}
        required={required}
      >
        {children}
      </select>
      <FieldFooter id={id} hint={hint} error={error} counter={counter} />
    </div>
  );
}

export function CheckboxField({
  id,
  label,
  hint,
  error,
  className,
  checked,
  onChange,
  disabled,
  required,
  autoFocus,
}: {
  id: string;
  label: ReactNode;
  hint?: ReactNode;
  error?: string | null;
  className?: string;
  checked: boolean;
  onChange: (checked: boolean) => void;
  disabled?: boolean;
  required?: boolean;
  autoFocus?: boolean;
}) {
  return (
    <div className={className ? `checkbox-field ${className}` : "checkbox-field"}>
      <label className="checkbox" htmlFor={id}>
        <input
          id={id}
          type="checkbox"
          checked={checked}
          onChange={(event) => onChange(event.target.checked)}
          disabled={disabled}
          required={required}
          data-autofocus={autoFocus ? true : undefined}
          aria-invalid={error ? true : undefined}
          aria-describedby={describedBy(id, hint, error)}
        />
        <span>{label}</span>
      </label>
      {hint ? (
        <p className="field__hint field__hint--indent" id={`${id}-hint`}>
          {hint}
        </p>
      ) : null}
      {error ? (
        <p className="field__error field__error--indent" id={`${id}-error`} aria-live="polite">
          {error}
        </p>
      ) : null}
    </div>
  );
}
