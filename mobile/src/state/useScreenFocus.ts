import { useEffect, useRef } from 'react';

import { useNav } from './context';

/**
 * Chama `onFocus` quando esta tela volta a ser o topo da pilha.
 *
 * As telas já abertas continuam montadas ao empilhar outra (`App.tsx`), então
 * o efeito de montagem não roda ao voltar de `add-friend`. O topo é observado
 * por `nav.id`. O primeiro foco é ignorado de propósito: quem acabou de montar
 * já carrega seus dados no efeito de montagem e não deve recarregar duas vezes.
 */
export function useScreenFocus(screenId: string, onFocus: () => void) {
  const nav = useNav();
  const handler = useRef(onFocus);
  const focused = useRef(nav.id === screenId);

  useEffect(() => {
    handler.current = onFocus;
  }, [onFocus]);

  useEffect(() => {
    const isTop = nav.id === screenId;
    if (!isTop) {
      focused.current = false;
      return;
    }
    if (!focused.current) {
      focused.current = true;
      handler.current();
    }
  }, [nav.id, screenId]);
}
