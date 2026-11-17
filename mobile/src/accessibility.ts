import * as SecureStore from 'expo-secure-store';

export type AccessibilityPreferences = {
  fontScale: 'A' | 'AA' | 'AAA';
  reducedMotion: boolean;
  largeTargets: boolean;
};

export const defaultAccessibility: AccessibilityPreferences = {
  fontScale: 'AA',
  reducedMotion: false,
  largeTargets: true,
};

export function fontScaleFactor(scale: AccessibilityPreferences['fontScale']): number {
  if (scale === 'A') {
    return 0.92;
  }
  if (scale === 'AAA') {
    return 1.18;
  }
  return 1;
}

const ACCESSIBILITY_KEY = 'joga.accessibility';

export async function loadAccessibility(): Promise<AccessibilityPreferences> {
  try {
    const raw = await SecureStore.getItemAsync(ACCESSIBILITY_KEY);
    if (!raw) {
      return defaultAccessibility;
    }
    const parsed = JSON.parse(raw) as Partial<AccessibilityPreferences>;
    return {
      fontScale:
        parsed.fontScale === 'A' || parsed.fontScale === 'AAA' || parsed.fontScale === 'AA'
          ? parsed.fontScale
          : defaultAccessibility.fontScale,
      reducedMotion:
        typeof parsed.reducedMotion === 'boolean'
          ? parsed.reducedMotion
          : defaultAccessibility.reducedMotion,
      largeTargets:
        typeof parsed.largeTargets === 'boolean'
          ? parsed.largeTargets
          : defaultAccessibility.largeTargets,
    };
  } catch {
    return defaultAccessibility;
  }
}

export async function saveAccessibility(preferences: AccessibilityPreferences): Promise<void> {
  await SecureStore.setItemAsync(ACCESSIBILITY_KEY, JSON.stringify(preferences));
}
