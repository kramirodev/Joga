import Constants from 'expo-constants';
import { Platform } from 'react-native';

const expoConfig = Constants.expoConfig;

/** Versão do binário/app.json; 0.0.0 falha fechado se não houver configuração. */
export const APP_VERSION = expoConfig?.version?.trim() || '0.0.0';

const nativeBuild =
  Platform.OS === 'android' ? expoConfig?.android?.versionCode : expoConfig?.ios?.buildNumber;

export const APP_BUILD = nativeBuild ? String(nativeBuild) : APP_VERSION;
export const CLIENT_NAME = 'mobile';
export const CLIENT_PLATFORM = Platform.OS;
