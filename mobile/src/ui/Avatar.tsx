import { View } from 'react-native';
import Svg, { Circle, Path, Rect } from 'react-native-svg';

import type { Palette } from './theme';

export type AvatarProps = {
  size?: number;
  skin?: string;
  hair?: string;
  shirt?: string;
  bg?: string;
  style?: 1 | 2 | 3;
  glasses?: boolean;
  palette: Palette;
};

export function Avatar({
  size = 48,
  skin = '#A6ABB1',
  hair = '#383D43',
  shirt = '#62686E',
  bg = '#E7EAE7',
  style = 1,
  glasses = false,
  palette,
}: AvatarProps) {
  return (
    <View
      style={{
        width: size,
        height: size,
        borderRadius: size / 2,
        overflow: 'hidden',
        borderWidth: 1.5,
        borderColor: palette.line,
        backgroundColor: bg,
      }}
    >
      <Svg width={size} height={size} viewBox="0 0 64 64">
        <Rect width="64" height="64" fill={bg} />
        <Path d="M10 64c1-13 9-20 22-20s21 7 22 20z" fill={shirt} />
        <Rect x="28" y="34" width="8" height="10" rx="3" fill={skin} />
        <Circle cx="32" cy="26" r="14" fill={skin} />
        {style === 1 ? (
          <Path
            d="M17 25c0-9 6-15 15-15s15 6 15 15c0 2-1 4-2 5l-3-7c-6 2-14 2-20 0l-3 7c-1-1-2-3-2-5z"
            fill={hair}
          />
        ) : null}
        {style === 2 ? (
          <>
            <Path d="M16 26c0-10 7-16 16-16s16 6 16 16l-4 1-1-8c-7 3-15 3-22 0l-1 8z" fill={hair} />
            <Path d="M18 22c3-6 9-9 14-9 6 0 11 3 14 9" fill="none" stroke={hair} strokeWidth={4} />
          </>
        ) : null}
        {style === 3 ? (
          <Path d="M17 27c-1-11 6-17 15-17s16 6 15 17l-4-2-2-7c-5 3-13 3-18 0l-2 7z" fill={hair} />
        ) : null}
        <Circle cx="26.5" cy="26" r="1.7" fill="#17191B" />
        <Circle cx="37.5" cy="26" r="1.7" fill="#17191B" />
        <Path
          d="M28 32c2.5 2 5.5 2 8 0"
          fill="none"
          stroke="#17191B"
          strokeWidth={1.7}
          strokeLinecap="round"
        />
        {glasses ? (
          <>
            <Rect
              x="21"
              y="22.5"
              width="9"
              height="7"
              rx="2"
              fill="none"
              stroke="#17191B"
              strokeWidth={1.5}
            />
            <Rect
              x="34"
              y="22.5"
              width="9"
              height="7"
              rx="2"
              fill="none"
              stroke="#17191B"
              strokeWidth={1.5}
            />
            <Path d="M30 26h4" stroke="#17191B" strokeWidth={1.5} />
          </>
        ) : null}
      </Svg>
    </View>
  );
}
