import type { ReactElement } from 'react';

import type { Params, TabKey } from '../state/context';

export type ScreenProps = {
  params: Params;
};

export type ScreenDef = {
  id: string;
  tab?: TabKey;
  render: (props: ScreenProps) => ReactElement;
};
