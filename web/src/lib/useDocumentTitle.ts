import { useEffect } from "react";

const SUFFIX = "JOGA y GESTÃO";

export function useDocumentTitle(title?: string | null) {
  useEffect(() => {
    document.title = title ? `${title} · ${SUFFIX}` : SUFFIX;
  }, [title]);
}
