import type { Params } from './context';

/**
 * Identidade da pilha de navegação.
 *
 * A chave React é o `uid`, nunca `id + params`: a mesma tela pode ser
 * empilhada duas vezes com os mesmos parâmetros (ex.: `queue-search`) e
 * `id + params` geraria duas chaves iguais.
 */
export type StackEntry = { uid: string; id: string; params: Params };

let sequence = 0;

export function createStackEntry(id: string, params?: Params): StackEntry {
  sequence += 1;
  return { uid: `stack-${sequence}`, id, params: params ?? {} };
}

export function sameParams(left: Params, right: Params): boolean {
  const leftKeys = Object.keys(left).sort();
  const rightKeys = Object.keys(right).sort();
  if (leftKeys.length !== rightKeys.length) {
    return false;
  }
  return leftKeys.every((key, index) => key === rightKeys[index] && left[key] === right[key]);
}

/** `false` quando a navegação só repetiria o topo atual. */
export function shouldPush(
  current: StackEntry | null | undefined,
  id: string,
  params?: Params,
): boolean {
  if (!current) {
    return true;
  }
  return !(current.id === id && sameParams(current.params, params ?? {}));
}
