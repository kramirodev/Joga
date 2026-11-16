import type { ReactNode } from "react";

import {
  COUNTRIES,
  countryLabel,
  digitsOnly,
  findCountry,
  formatE164ForDisplay,
  formatNational,
  parseInternationalInput,
  toE164,
} from "../../lib/phone";
import { Field } from "./Field";

export function PhoneField({
  id,
  label = "Telefone",
  countryCode,
  onCountryCodeChange,
  value,
  onChange,
  error,
  hint,
  disabled,
  required = true,
  lockCountry = false,
}: {
  id: string;
  label?: string;
  countryCode: string;
  onCountryCodeChange: (code: string) => void;
  value: string;
  onChange: (nationalDigits: string) => void;
  error?: string | null;
  hint?: ReactNode;
  disabled?: boolean;
  required?: boolean;
  lockCountry?: boolean;
}) {
  const country = findCountry(countryCode);
  const describedBy = [hint ? `${id}-hint` : null, error ? `${id}-error` : null]
    .filter(Boolean)
    .join(" ");

  function handleChange(raw: string) {
    const international = parseInternationalInput(raw);
    if (international) {
      onCountryCodeChange(international.country.code);
      onChange(international.nationalDigits.slice(0, international.country.maxDigits));
      return;
    }
    onChange(digitsOnly(raw).slice(0, country.maxDigits));
  }

  const preview = value ? formatE164ForDisplay(toE164(country, value)) : `+${country.dialCode} …`;

  return (
    <Field
      id={id}
      label={label}
      hint={
        hint ?? (
          <span>
            O código do país é aplicado automaticamente. Número enviado:{" "}
            <strong className="phone-preview">{preview}</strong>. Você também pode colar o número
            completo com <code>+</code>.
          </span>
        )
      }
      error={error}
      required={required}
    >
      <div className="phone-field">
        <div className="phone-field__country">
          {lockCountry ? (
            <span className="phone-field__locked">+{country.dialCode}</span>
          ) : (
            <select
              id={`${id}-country`}
              className="select"
              aria-label="País do telefone"
              value={country.code}
              onChange={(event) => onCountryCodeChange(event.target.value)}
              disabled={disabled}
            >
              {COUNTRIES.map((item) => (
                <option key={item.code} value={item.code}>
                  {countryLabel(item)}
                </option>
              ))}
            </select>
          )}
        </div>
        <input
          id={id}
          className="input"
          type="tel"
          inputMode="tel"
          autoComplete="tel-national"
          value={formatNational(country, value)}
          onChange={(event) => handleChange(event.target.value)}
          placeholder={country.code === "BR" ? "11 98765-4321" : "Número local"}
          aria-invalid={error ? true : undefined}
          aria-describedby={describedBy || undefined}
          required={required}
          disabled={disabled}
          maxLength={country.maxDigits + 6}
        />
      </div>
    </Field>
  );
}
