/**
 * Telefone internacional sem dependência externa.
 *
 * O backend exige E.164 (`+5511987654321`). O painel aplica o código do país e
 * a máscara local, sem exigir que a pessoa digite `+55` manualmente. A lista é
 * deliberadamente ampla, mas finita: incluir um país novo é uma alteração
 * aditiva neste arquivo, sem impacto de contrato.
 */

export interface Country {
  code: string;
  name: string;
  dialCode: string;
  minDigits: number;
  maxDigits: number;
  formats: Record<number, number[]>;
  lastSeparator?: "-";
}

const generic = (min: number, max: number): Record<number, number[]> => {
  const formats: Record<number, number[]> = {};
  for (let length = min; length <= max; length += 1) {
    const groups: number[] = [];
    let remaining = length;
    while (remaining > 0) {
      const size = remaining > 4 ? 3 : remaining;
      groups.push(size);
      remaining -= size;
    }
    formats[length] = groups;
  }
  return formats;
};

export const COUNTRIES: Country[] = [
  {
    code: "BR",
    name: "Brasil",
    dialCode: "55",
    minDigits: 10,
    maxDigits: 11,
    formats: { 10: [2, 4, 4], 11: [2, 5, 4] },
    lastSeparator: "-",
  },
  {
    code: "PT",
    name: "Portugal",
    dialCode: "351",
    minDigits: 9,
    maxDigits: 9,
    formats: { 9: [3, 3, 3] },
  },
  {
    code: "US",
    name: "Estados Unidos",
    dialCode: "1",
    minDigits: 10,
    maxDigits: 10,
    formats: { 10: [3, 3, 4] },
    lastSeparator: "-",
  },
  {
    code: "CA",
    name: "Canadá",
    dialCode: "1",
    minDigits: 10,
    maxDigits: 10,
    formats: { 10: [3, 3, 4] },
    lastSeparator: "-",
  },
  {
    code: "AR",
    name: "Argentina",
    dialCode: "54",
    minDigits: 10,
    maxDigits: 11,
    formats: generic(10, 11),
  },
  {
    code: "CL",
    name: "Chile",
    dialCode: "56",
    minDigits: 9,
    maxDigits: 9,
    formats: { 9: [1, 4, 4] },
    lastSeparator: "-",
  },
  {
    code: "CO",
    name: "Colômbia",
    dialCode: "57",
    minDigits: 10,
    maxDigits: 10,
    formats: { 10: [3, 3, 4] },
    lastSeparator: "-",
  },
  {
    code: "MX",
    name: "México",
    dialCode: "52",
    minDigits: 10,
    maxDigits: 10,
    formats: { 10: [3, 3, 4] },
    lastSeparator: "-",
  },
  {
    code: "UY",
    name: "Uruguai",
    dialCode: "598",
    minDigits: 8,
    maxDigits: 8,
    formats: { 8: [2, 3, 3] },
    lastSeparator: "-",
  },
  {
    code: "PY",
    name: "Paraguai",
    dialCode: "595",
    minDigits: 9,
    maxDigits: 9,
    formats: { 9: [3, 3, 3] },
  },
  {
    code: "BO",
    name: "Bolívia",
    dialCode: "591",
    minDigits: 8,
    maxDigits: 8,
    formats: { 8: [1, 3, 4] },
    lastSeparator: "-",
  },
  {
    code: "PE",
    name: "Peru",
    dialCode: "51",
    minDigits: 9,
    maxDigits: 9,
    formats: { 9: [3, 3, 3] },
    lastSeparator: "-",
  },
  {
    code: "EC",
    name: "Equador",
    dialCode: "593",
    minDigits: 9,
    maxDigits: 9,
    formats: { 9: [1, 4, 4] },
    lastSeparator: "-",
  },
  {
    code: "VE",
    name: "Venezuela",
    dialCode: "58",
    minDigits: 10,
    maxDigits: 10,
    formats: { 10: [3, 3, 4] },
    lastSeparator: "-",
  },
  {
    code: "ES",
    name: "Espanha",
    dialCode: "34",
    minDigits: 9,
    maxDigits: 9,
    formats: { 9: [3, 3, 3] },
  },
  {
    code: "FR",
    name: "França",
    dialCode: "33",
    minDigits: 9,
    maxDigits: 9,
    formats: { 9: [1, 2, 2, 2, 2] },
  },
  {
    code: "DE",
    name: "Alemanha",
    dialCode: "49",
    minDigits: 10,
    maxDigits: 11,
    formats: generic(10, 11),
  },
  {
    code: "IT",
    name: "Itália",
    dialCode: "39",
    minDigits: 9,
    maxDigits: 10,
    formats: generic(9, 10),
  },
  {
    code: "GB",
    name: "Reino Unido",
    dialCode: "44",
    minDigits: 10,
    maxDigits: 10,
    formats: { 10: [4, 3, 3] },
  },
  {
    code: "IE",
    name: "Irlanda",
    dialCode: "353",
    minDigits: 9,
    maxDigits: 9,
    formats: { 9: [2, 3, 4] },
  },
  {
    code: "NL",
    name: "Países Baixos",
    dialCode: "31",
    minDigits: 9,
    maxDigits: 9,
    formats: { 9: [2, 3, 4] },
  },
  {
    code: "BE",
    name: "Bélgica",
    dialCode: "32",
    minDigits: 9,
    maxDigits: 9,
    formats: { 9: [3, 2, 2, 2] },
  },
  {
    code: "CH",
    name: "Suíça",
    dialCode: "41",
    minDigits: 9,
    maxDigits: 9,
    formats: { 9: [2, 3, 2, 2] },
  },
  {
    code: "AT",
    name: "Áustria",
    dialCode: "43",
    minDigits: 10,
    maxDigits: 10,
    formats: { 10: [3, 3, 4] },
  },
  {
    code: "SE",
    name: "Suécia",
    dialCode: "46",
    minDigits: 9,
    maxDigits: 9,
    formats: { 9: [2, 3, 2, 2] },
  },
  {
    code: "NO",
    name: "Noruega",
    dialCode: "47",
    minDigits: 8,
    maxDigits: 8,
    formats: { 8: [3, 2, 3] },
  },
  {
    code: "DK",
    name: "Dinamarca",
    dialCode: "45",
    minDigits: 8,
    maxDigits: 8,
    formats: { 8: [2, 2, 2, 2] },
  },
  {
    code: "FI",
    name: "Finlândia",
    dialCode: "358",
    minDigits: 9,
    maxDigits: 9,
    formats: { 9: [2, 3, 4] },
  },
  {
    code: "PL",
    name: "Polônia",
    dialCode: "48",
    minDigits: 9,
    maxDigits: 9,
    formats: { 9: [3, 3, 3] },
  },
  {
    code: "RU",
    name: "Rússia",
    dialCode: "7",
    minDigits: 10,
    maxDigits: 10,
    formats: { 10: [3, 3, 2, 2] },
  },
  {
    code: "JP",
    name: "Japão",
    dialCode: "81",
    minDigits: 10,
    maxDigits: 10,
    formats: { 10: [2, 4, 4] },
    lastSeparator: "-",
  },
  {
    code: "AU",
    name: "Austrália",
    dialCode: "61",
    minDigits: 9,
    maxDigits: 9,
    formats: { 9: [3, 3, 3] },
  },
  {
    code: "NZ",
    name: "Nova Zelândia",
    dialCode: "64",
    minDigits: 9,
    maxDigits: 9,
    formats: { 9: [2, 3, 4] },
  },
  {
    code: "ZA",
    name: "África do Sul",
    dialCode: "27",
    minDigits: 9,
    maxDigits: 9,
    formats: { 9: [2, 3, 4] },
  },
  {
    code: "IN",
    name: "Índia",
    dialCode: "91",
    minDigits: 10,
    maxDigits: 10,
    formats: { 10: [5, 5] },
  },
  {
    code: "CN",
    name: "China",
    dialCode: "86",
    minDigits: 11,
    maxDigits: 11,
    formats: { 11: [3, 4, 4] },
  },
  {
    code: "KR",
    name: "Coreia do Sul",
    dialCode: "82",
    minDigits: 10,
    maxDigits: 10,
    formats: { 10: [2, 4, 4] },
  },
  {
    code: "SG",
    name: "Singapura",
    dialCode: "65",
    minDigits: 8,
    maxDigits: 8,
    formats: { 8: [4, 4] },
  },
  {
    code: "AE",
    name: "Emirados Árabes Unidos",
    dialCode: "971",
    minDigits: 9,
    maxDigits: 9,
    formats: { 9: [2, 3, 4] },
  },
  {
    code: "IL",
    name: "Israel",
    dialCode: "972",
    minDigits: 9,
    maxDigits: 9,
    formats: { 9: [2, 3, 4] },
  },
  {
    code: "TR",
    name: "Turquia",
    dialCode: "90",
    minDigits: 10,
    maxDigits: 10,
    formats: { 10: [3, 3, 2, 2] },
  },
  {
    code: "EG",
    name: "Egito",
    dialCode: "20",
    minDigits: 10,
    maxDigits: 10,
    formats: { 10: [2, 4, 4] },
  },
  {
    code: "NG",
    name: "Nigéria",
    dialCode: "234",
    minDigits: 10,
    maxDigits: 10,
    formats: { 10: [3, 3, 4] },
  },
  {
    code: "KE",
    name: "Quênia",
    dialCode: "254",
    minDigits: 9,
    maxDigits: 9,
    formats: { 9: [3, 3, 3] },
  },
  {
    code: "AO",
    name: "Angola",
    dialCode: "244",
    minDigits: 9,
    maxDigits: 9,
    formats: { 9: [3, 3, 3] },
  },
  {
    code: "MZ",
    name: "Moçambique",
    dialCode: "258",
    minDigits: 9,
    maxDigits: 9,
    formats: { 9: [2, 3, 4] },
  },
  {
    code: "CV",
    name: "Cabo Verde",
    dialCode: "238",
    minDigits: 7,
    maxDigits: 7,
    formats: { 7: [3, 4] },
  },
  {
    code: "GW",
    name: "Guiné-Bissau",
    dialCode: "245",
    minDigits: 9,
    maxDigits: 9,
    formats: { 9: [3, 3, 3] },
  },
  {
    code: "ST",
    name: "São Tomé e Príncipe",
    dialCode: "239",
    minDigits: 7,
    maxDigits: 7,
    formats: { 7: [3, 4] },
  },
  {
    code: "TL",
    name: "Timor-Leste",
    dialCode: "670",
    minDigits: 8,
    maxDigits: 8,
    formats: { 8: [4, 4] },
  },
];

export const DEFAULT_COUNTRY = COUNTRIES[0];

export function findCountry(code: string): Country {
  return COUNTRIES.find((country) => country.code === code) ?? DEFAULT_COUNTRY;
}

export function digitsOnly(value: string): string {
  return value.replace(/\D/g, "");
}

export function countryLabel(country: Country): string {
  return `${country.name} (+${country.dialCode})`;
}

/**
 * Aceita um número colado em formato internacional (`+55 ...` ou `0055 ...`).
 * Devolve `null` quando o texto não tem prefixo internacional reconhecível.
 */
export function parseInternationalInput(
  value: string,
): { country: Country; nationalDigits: string } | null {
  const trimmed = value.trim();
  const hasPlus = trimmed.startsWith("+");
  const hasZeroZero = trimmed.startsWith("00");
  if (!hasPlus && !hasZeroZero) return null;

  const digits = digitsOnly(trimmed);
  const international = hasPlus ? digits : digits.slice(2);
  const candidates = [...COUNTRIES].sort((a, b) => b.dialCode.length - a.dialCode.length);
  for (const country of candidates) {
    if (!international.startsWith(country.dialCode)) continue;
    const nationalDigits = international.slice(country.dialCode.length);
    if (nationalDigits.length >= 4) return { country, nationalDigits };
  }
  return null;
}

function groupsFor(country: Country, length: number): number[] {
  const explicit = country.formats[length];
  if (explicit) return explicit;
  const fallback = generic(length, length)[length] ?? [];
  return fallback;
}

export function formatNational(country: Country, nationalDigits: string): string {
  const digits = digitsOnly(nationalDigits);
  if (!digits) return "";
  const groups = groupsFor(country, digits.length);
  if (groups.length === 0) return digits;

  const parts: string[] = [];
  let offset = 0;
  for (const size of groups) {
    if (offset >= digits.length) break;
    parts.push(digits.slice(offset, offset + size));
    offset += size;
  }
  if (offset < digits.length) parts.push(digits.slice(offset));

  return parts
    .map((part, index) =>
      index === parts.length - 1
        ? part
        : `${part}${country.lastSeparator === "-" && index === parts.length - 2 ? "-" : " "}`,
    )
    .join("");
}

export function toE164(country: Country, nationalDigits: string): string {
  return `+${country.dialCode}${digitsOnly(nationalDigits)}`;
}

export function e164Digits(country: Country, nationalDigits: string): number {
  return country.dialCode.length + digitsOnly(nationalDigits).length;
}

export function phoneError(country: Country, nationalDigits: string): string | null {
  const digits = digitsOnly(nationalDigits);
  if (!digits) return "Informe o telefone.";

  if (digits.length < country.minDigits) {
    return country.code === "BR"
      ? "Informe DDD e número. Ex.: 11 98765-4321."
      : `Número incompleto para ${country.name}.`;
  }
  if (digits.length > country.maxDigits) {
    return country.code === "BR"
      ? "O telefone brasileiro deve ter 10 ou 11 dígitos, sem o +55."
      : `Número longo demais para ${country.name}.`;
  }
  if (e164Digits(country, digits) > 15) {
    return "O número ultrapassa o limite internacional de 15 dígitos.";
  }
  if (country.code === "BR") {
    const ddd = Number(digits.slice(0, 2));
    if (ddd < 11 || ddd > 99) return "DDD inválido. Use um DDD entre 11 e 99.";
    const subscriber = digits.slice(2);
    if (subscriber.length === 9 && subscriber[0] !== "9") {
      return "Celular brasileiro deve ter 9 como primeiro dígito após o DDD.";
    }
    if (subscriber.length === 8 && subscriber[0] === "9") {
      return "Faltou um dígito no celular. Confira o número completo.";
    }
  }
  return null;
}

export function formatE164ForDisplay(e164: string): string {
  const parsed = parseInternationalInput(e164);
  if (!parsed) return e164;
  return `+${parsed.country.dialCode} ${formatNational(parsed.country, parsed.nationalDigits)}`;
}
