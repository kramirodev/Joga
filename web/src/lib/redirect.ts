/** Caminho interno seguro para retorno após login. */
export function safeReturnPath(value: unknown): string {
  if (typeof value !== "string") return "/";
  if (!value.startsWith("/") || value.startsWith("//")) return "/";
  return value;
}

export function currentPath(pathname: string, search: string, hash: string): string {
  return `${pathname}${search}${hash}`;
}
