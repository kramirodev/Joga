import Svg, { Circle, Path, Rect } from 'react-native-svg';

import { ICONS, type IconChild, type IconName } from './icon-data';

export type { IconName };

function commonProps(child: IconChild, color: string, strokeWidth: number) {
  return {
    fill: child.attrs.fill === 'currentColor' ? color : (child.attrs.fill ?? 'none'),
    stroke: child.attrs.stroke === 'currentColor' ? color : (child.attrs.stroke ?? color),
    strokeWidth,
    strokeLinecap: 'round' as const,
    strokeLinejoin: 'round' as const,
  };
}

export function Icon({
  name,
  size = 20,
  color,
  strokeWidth = 1.9,
}: {
  name: IconName;
  size?: number;
  color: string;
  strokeWidth?: number;
}) {
  const children = ICONS[name] ?? [];
  return (
    <Svg width={size} height={size} viewBox="0 0 24 24" fill="none">
      {children.map((child, index) => {
        const common = commonProps(child, color, strokeWidth);
        if (child.tag === 'path') {
          return <Path key={index} d={child.attrs.d} {...common} />;
        }
        if (child.tag === 'rect') {
          return (
            <Rect
              key={index}
              x={Number(child.attrs.x)}
              y={Number(child.attrs.y)}
              width={Number(child.attrs.width)}
              height={Number(child.attrs.height)}
              rx={child.attrs.rx ? Number(child.attrs.rx) : undefined}
              {...common}
            />
          );
        }
        return (
          <Circle
            key={index}
            cx={Number(child.attrs.cx)}
            cy={Number(child.attrs.cy)}
            r={Number(child.attrs.r)}
            {...common}
          />
        );
      })}
    </Svg>
  );
}
