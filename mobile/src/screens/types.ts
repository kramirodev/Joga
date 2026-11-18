import type { ReactElement } from 'react';

import type { Params, TabKey } from '../state/context';

export type ScreenProps = {
  params: Params;
};

export type ScreenDef = {
  id: string;
  tab?: TabKey;
  /**
   * Tela preservada apenas como referência de estado. Não tem caminho de
   * navegação no app atual e não deve ser registrada no shell.
   */
  hidden?: true;
  render: (props: ScreenProps) => ReactElement;
};
