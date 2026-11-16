// Extraído de telas/jogo/prototipo-v3.html (sprite de ícones).
export type IconChild = { tag: 'path' | 'rect' | 'circle'; attrs: Record<string, string> };

export const ICONS: Record<string, IconChild[]> = {
  home: [
    {
      tag: 'path',
      attrs: {
        d: 'M3 10.5 12 3l9 7.5v9.5a1 1 0 0 1-1 1h-5v-6H9v6H4a1 1 0 0 1-1-1z',
      },
    },
  ],
  cal: [
    {
      tag: 'rect',
      attrs: {
        x: '3',
        y: '5',
        width: '18',
        height: '16',
        rx: '2',
      },
    },
    {
      tag: 'path',
      attrs: {
        d: 'M3 10h18M8 3v4M16 3v4',
      },
    },
  ],
  trophy: [
    {
      tag: 'path',
      attrs: {
        d: 'M7 4h10v4a5 5 0 0 1-10 0zM7 6H4v2a4 4 0 0 0 4 4M17 6h3v2a4 4 0 0 1-4 4M12 13v4M8 21h8M9 17h6',
      },
    },
  ],
  users: [
    {
      tag: 'circle',
      attrs: {
        cx: '9',
        cy: '8',
        r: '3.2',
      },
    },
    {
      tag: 'path',
      attrs: {
        d: 'M3 20a6 6 0 0 1 12 0M16 5.5a3 3 0 0 1 0 5.8M17 14a5 5 0 0 1 4 6',
      },
    },
  ],
  user: [
    {
      tag: 'circle',
      attrs: {
        cx: '12',
        cy: '8',
        r: '3.5',
      },
    },
    {
      tag: 'path',
      attrs: {
        d: 'M4 21a8 8 0 0 1 16 0',
      },
    },
  ],
  wallet: [
    {
      tag: 'path',
      attrs: {
        d: 'M3 7a2 2 0 0 1 2-2h13v4H5a2 2 0 0 0-2 2zM3 11h18v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z',
      },
    },
    {
      tag: 'circle',
      attrs: {
        cx: '16.5',
        cy: '15',
        r: '1.2',
      },
    },
  ],
  search: [
    {
      tag: 'circle',
      attrs: {
        cx: '11',
        cy: '11',
        r: '6.5',
      },
    },
    {
      tag: 'path',
      attrs: {
        d: 'm16 16 5 5',
      },
    },
  ],
  back: [
    {
      tag: 'path',
      attrs: {
        d: 'm15 5-7 7 7 7',
      },
    },
  ],
  next: [
    {
      tag: 'path',
      attrs: {
        d: 'm9 5 7 7-7 7',
      },
    },
  ],
  close: [
    {
      tag: 'path',
      attrs: {
        d: 'm6 6 12 12M18 6 6 18',
      },
    },
  ],
  plus: [
    {
      tag: 'path',
      attrs: {
        d: 'M12 4v16M4 12h16',
      },
    },
  ],
  check: [
    {
      tag: 'path',
      attrs: {
        d: 'm4 12 5 5L20 6',
      },
    },
  ],
  clock: [
    {
      tag: 'circle',
      attrs: {
        cx: '12',
        cy: '12',
        r: '8.5',
      },
    },
    {
      tag: 'path',
      attrs: {
        d: 'M12 7v5l3.5 2',
      },
    },
  ],
  pin: [
    {
      tag: 'path',
      attrs: {
        d: 'M12 21s7-5.6 7-11a7 7 0 1 0-14 0c0 5.4 7 11 7 11z',
      },
    },
    {
      tag: 'circle',
      attrs: {
        cx: '12',
        cy: '10',
        r: '2.4',
      },
    },
  ],
  lock: [
    {
      tag: 'rect',
      attrs: {
        x: '4.5',
        y: '10',
        width: '15',
        height: '11',
        rx: '2',
      },
    },
    {
      tag: 'path',
      attrs: {
        d: 'M8 10V7a4 4 0 0 1 8 0v3',
      },
    },
  ],
  alert: [
    {
      tag: 'path',
      attrs: {
        d: 'M12 3 2.5 20h19z',
      },
    },
    {
      tag: 'path',
      attrs: {
        d: 'M12 9v5M12 17.5v.1',
      },
    },
  ],
  chat: [
    {
      tag: 'path',
      attrs: {
        d: 'M4 5h16v11H9l-5 4z',
      },
    },
    {
      tag: 'path',
      attrs: {
        d: 'M8 9h8M8 12h5',
      },
    },
  ],
  send: [
    {
      tag: 'path',
      attrs: {
        d: 'm3 11 18-8-8 18-2-8z',
      },
    },
  ],
  filter: [
    {
      tag: 'path',
      attrs: {
        d: 'M4 6h16M7 12h10M10 18h4',
      },
    },
  ],
  gear: [
    {
      tag: 'circle',
      attrs: {
        cx: '12',
        cy: '12',
        r: '3.2',
      },
    },
    {
      tag: 'path',
      attrs: {
        d: 'M19 12a7 7 0 0 0-.1-1l2-1.5-2-3.4-2.3 1a7 7 0 0 0-1.7-1L14.6 3h-5l-.4 3.1a7 7 0 0 0-1.7 1l-2.3-1-2 3.4L5 11a7 7 0 0 0 0 2l-2 1.5 2 3.4 2.3-1a7 7 0 0 0 1.7 1l.4 3.1h5l.4-3.1a7 7 0 0 0 1.7-1l2.3 1 2-3.4L19 13a7 7 0 0 0 .1-1z',
      },
    },
  ],
  shield: [
    {
      tag: 'path',
      attrs: {
        d: 'M12 3 5 6v6c0 4.5 3 7.5 7 9 4-1.5 7-4.5 7-9V6z',
      },
    },
    {
      tag: 'path',
      attrs: {
        d: 'm9 12 2 2 4-4',
      },
    },
  ],
  share: [
    {
      tag: 'circle',
      attrs: {
        cx: '6',
        cy: '12',
        r: '2.2',
      },
    },
    {
      tag: 'circle',
      attrs: {
        cx: '18',
        cy: '6',
        r: '2.2',
      },
    },
    {
      tag: 'circle',
      attrs: {
        cx: '18',
        cy: '18',
        r: '2.2',
      },
    },
    {
      tag: 'path',
      attrs: {
        d: 'm8 11 8-4M8 13l8 4',
      },
    },
  ],
  more: [
    {
      tag: 'circle',
      attrs: {
        cx: '5',
        cy: '12',
        r: '1.4',
        fill: 'currentColor',
      },
    },
    {
      tag: 'circle',
      attrs: {
        cx: '12',
        cy: '12',
        r: '1.4',
        fill: 'currentColor',
      },
    },
    {
      tag: 'circle',
      attrs: {
        cx: '19',
        cy: '12',
        r: '1.4',
        fill: 'currentColor',
      },
    },
  ],
  arrow: [
    {
      tag: 'path',
      attrs: {
        d: 'M4 12h16M14 6l6 6-6 6',
      },
    },
  ],
  eye: [
    {
      tag: 'path',
      attrs: {
        d: 'M2.5 12S6 6 12 6s9.5 6 9.5 6-3.5 6-9.5 6-9.5-6-9.5-6z',
      },
    },
    {
      tag: 'circle',
      attrs: {
        cx: '12',
        cy: '12',
        r: '2.6',
      },
    },
  ],
  image: [
    {
      tag: 'rect',
      attrs: {
        x: '3',
        y: '4',
        width: '18',
        height: '16',
        rx: '2',
      },
    },
    {
      tag: 'path',
      attrs: {
        d: 'm3 16 5-5 4 4 3-3 6 6',
      },
    },
    {
      tag: 'circle',
      attrs: {
        cx: '8',
        cy: '9',
        r: '1.4',
      },
    },
  ],
  copy: [
    {
      tag: 'rect',
      attrs: {
        x: '8',
        y: '8',
        width: '12',
        height: '12',
        rx: '2',
      },
    },
    {
      tag: 'path',
      attrs: {
        d: 'M16 8V6a2 2 0 0 0-2-2H6a2 2 0 0 0-2 2v8a2 2 0 0 0 2 2h2',
      },
    },
  ],
  edit: [
    {
      tag: 'path',
      attrs: {
        d: 'M4 20h4l11-11-4-4L4 16z',
      },
    },
    {
      tag: 'path',
      attrs: {
        d: 'm13.5 6.5 4 4',
      },
    },
  ],
  trash: [
    {
      tag: 'path',
      attrs: {
        d: 'M4 7h16M9 7V4h6v3M6 7l1 14h10l1-14M10 11v6M14 11v6',
      },
    },
  ],
  download: [
    {
      tag: 'path',
      attrs: {
        d: 'M12 3v12M7 10l5 5 5-5M4 21h16',
      },
    },
  ],
  logout: [
    {
      tag: 'path',
      attrs: {
        d: 'M10 4H4v16h6M14 8l4 4-4 4M9 12h9',
      },
    },
  ],
  info: [
    {
      tag: 'circle',
      attrs: {
        cx: '12',
        cy: '12',
        r: '9',
      },
    },
    {
      tag: 'path',
      attrs: {
        d: 'M12 11v5M12 8v.1',
      },
    },
  ],
  bolt: [
    {
      tag: 'path',
      attrs: {
        d: 'm13 2-8 12h6l-1 8 9-13h-6z',
      },
    },
  ],
  medal: [
    {
      tag: 'circle',
      attrs: {
        cx: '12',
        cy: '14',
        r: '5',
      },
    },
    {
      tag: 'path',
      attrs: {
        d: 'm8 3 4 6 4-6M12 11v2l1.5 1',
      },
    },
  ],
  clan: [
    {
      tag: 'path',
      attrs: {
        d: 'M12 2 4 6v6c0 4.5 3.4 7.8 8 10 4.6-2.2 8-5.5 8-10V6z',
      },
    },
    {
      tag: 'path',
      attrs: {
        d: 'M8 12h8M12 8v8',
      },
    },
  ],
  globe: [
    {
      tag: 'circle',
      attrs: {
        cx: '12',
        cy: '12',
        r: '9',
      },
    },
    {
      tag: 'path',
      attrs: {
        d: 'M3 12h18M12 3c2.5 2.5 4 5.5 4 9s-1.5 6.5-4 9c-2.5-2.5-4-5.5-4-9s1.5-6.5 4-9z',
      },
    },
  ],
  'wifi-off': [
    {
      tag: 'path',
      attrs: {
        d: 'm3 3 18 18M8.5 15.5a5 5 0 0 1 7 0M5 12a10 10 0 0 1 3-2M19 12a10 10 0 0 0-3-2M12 19v.1',
      },
    },
  ],
  bell: [
    {
      tag: 'path',
      attrs: {
        d: 'M18 9a6 6 0 1 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9M10 21h4',
      },
    },
  ],
  menu: [
    {
      tag: 'path',
      attrs: {
        d: 'M4 7h16M4 12h16M4 17h16',
      },
    },
  ],
};

export type IconName = keyof typeof ICONS;
