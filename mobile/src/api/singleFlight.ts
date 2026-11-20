/**
 * Single-flight genérico: para a mesma chave, só existe uma execução em voo.
 * Chamadas concorrentes aguardam a mesma promessa; a chave é liberada quando a
 * tarefa termina (sucesso ou erro), permitindo uma nova tentativa depois.
 *
 * Sem React e sem dependências: a lógica é testada por `node --test`.
 */
export type SingleFlight<K, T> = {
  run: (key: K, task: () => Promise<T>) => Promise<T>;
  /** Quantas chaves têm tarefa em voo. Usado em teste/diagnóstico. */
  size: () => number;
  /** Remove a chave sem cancelar a tarefa (limpeza em logout). */
  forget: (key: K) => void;
};

export function createSingleFlight<K, T>(): SingleFlight<K, T> {
  const tasks = new Map<K, Promise<T>>();
  return {
    run(key, task) {
      const current = tasks.get(key);
      if (current) {
        return current;
      }
      let promise: Promise<T>;
      try {
        promise = Promise.resolve(task());
      } catch (error) {
        return Promise.reject(error);
      }
      let tracked: Promise<T>;
      tracked = promise.finally(() => {
        if (tasks.get(key) === tracked) {
          tasks.delete(key);
        }
      });
      tasks.set(key, tracked);
      return tracked;
    },
    size() {
      return tasks.size;
    },
    forget(key) {
      tasks.delete(key);
    },
  };
}
