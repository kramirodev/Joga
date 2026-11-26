import { useCallback, useEffect, useRef, useState } from "react";

import { api } from "./api";
import { normalizeCep } from "./cep";
import type { PostalCodeLookup } from "../types";

const DEFAULT_DELAY_MS = 500;

interface LookupState {
  key: string | null;
  data: PostalCodeLookup | null;
  error: unknown;
  pending: boolean;
}

const emptyState: LookupState = { key: null, data: null, error: null, pending: false };

export interface CepLookupCallbacks {
  onResolved: (result: PostalCodeLookup, postalCode: string) => void;
  onFailed?: (error: unknown) => void;
}

interface UseCepLookupOptions extends CepLookupCallbacks {
  cep: string;
  number?: string;
  enabled?: boolean;
  delayMs?: number;
}

export interface CepLookupController {
  data: PostalCodeLookup | null;
  error: unknown;
  pending: boolean;
  searched: boolean;
  run: () => void;
  reset: () => void;
}

/**
 * Consulta o CEP automaticamente quando os oito dígitos estão completos,
 * com debounce, sem repetir a mesma busca e descartando respostas atrasadas.
 */
export function useCepLookup({
  cep,
  number,
  enabled = true,
  delayMs = DEFAULT_DELAY_MS,
  onResolved,
  onFailed,
}: UseCepLookupOptions): CepLookupController {
  const digits = normalizeCep(cep);
  const key = digits.length === 8 ? digits : null;
  const [state, setState] = useState<LookupState>(emptyState);
  const [searchedKey, setSearchedKey] = useState<string | null>(null);
  const requestSeq = useRef(0);
  const timer = useRef<number | null>(null);
  const callbacks = useRef<CepLookupCallbacks>({ onResolved, onFailed });
  const numberRef = useRef(number ?? "");
  const digitsRef = useRef(digits);

  useEffect(() => {
    callbacks.current = { onResolved, onFailed };
    numberRef.current = number ?? "";
    digitsRef.current = digits;
  });

  const runFor = useCallback(async (target: string) => {
    if (timer.current !== null) {
      window.clearTimeout(timer.current);
      timer.current = null;
    }
    const seq = ++requestSeq.current;
    setSearchedKey(target);
    setState({ key: target, data: null, error: null, pending: true });
    const isStale = () => {
      if (requestSeq.current !== seq) return "superseded" as const;
      if (digitsRef.current !== target) return "cep-changed" as const;
      return null;
    };
    const drop = (reason: ReturnType<typeof isStale>) => {
      if (reason === "cep-changed") {
        setState((current) =>
          current.key === target && current.pending ? { ...current, pending: false } : current,
        );
      }
    };
    try {
      const result = await api.lookupPostalCode(target, numberRef.current || null);
      const reason = isStale();
      if (reason) {
        drop(reason);
        return;
      }
      setState({ key: target, data: result, error: null, pending: false });
      callbacks.current.onResolved(result, target);
    } catch (error) {
      const reason = isStale();
      if (reason) {
        drop(reason);
        return;
      }
      setState({ key: target, data: null, error, pending: false });
      callbacks.current.onFailed?.(error);
    }
  }, []);

  useEffect(() => {
    if (!enabled || key === null) return;
    const handled =
      state.key === key && (state.pending || state.data !== null || state.error !== null);
    if (handled) return;
    const handle = window.setTimeout(() => {
      timer.current = null;
      void runFor(key);
    }, delayMs);
    timer.current = handle;
    return () => {
      window.clearTimeout(handle);
      if (timer.current === handle) timer.current = null;
    };
  }, [delayMs, enabled, key, runFor, state.data, state.error, state.key, state.pending]);

  const run = useCallback(() => {
    if (key !== null) void runFor(key);
  }, [key, runFor]);

  const reset = useCallback(() => {
    requestSeq.current += 1;
    setSearchedKey(null);
    setState(emptyState);
  }, []);

  const active = state.key === key ? state : null;
  return {
    data: active?.data ?? null,
    error: active?.error ?? null,
    pending: active?.pending ?? false,
    searched: key !== null && searchedKey === key,
    run,
    reset,
  };
}
