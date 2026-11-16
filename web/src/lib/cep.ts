export function normalizeCep(value: string): string {
  return value.replace(/\D/g, "").slice(0, 8);
}

export function formatCep(value: string): string {
  const digits = normalizeCep(value);
  if (digits.length <= 5) return digits;
  return `${digits.slice(0, 5)}-${digits.slice(5)}`;
}

export function cepError(value: string): string | null {
  const digits = normalizeCep(value);
  if (!digits) return "Informe o CEP do estabelecimento.";
  if (digits.length !== 8) return "O CEP precisa ter oito dígitos.";
  if (/^0{8}$/.test(digits)) return "Informe um CEP válido.";
  return null;
}
