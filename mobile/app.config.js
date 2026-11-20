// Guarda de build: o release do app precisa apontar para o demo, nunca para a
// máquina local. Falha o bundle (Gradle `bundleRelease`/`export:embed`) antes de
// gerar um APK inútil. Em desenvolvimento, `127.0.0.1` continua permitido.
const isRelease = process.env.JOGA_RELEASE_BUILD === '1' || process.env.NODE_ENV === 'production';

const LOCAL_HOST = /(^|\/\/)(127\.0\.0\.1|localhost)(:\d+)?(\/|$)/i;

module.exports = ({ config }) => {
  const apiUrl = (process.env.EXPO_PUBLIC_API_URL ?? '').trim();

  if (isRelease) {
    if (!apiUrl) {
      throw new Error(
        'EXPO_PUBLIC_API_URL ausente: o build de release exige a URL do ambiente de demo.',
      );
    }
    if (LOCAL_HOST.test(apiUrl)) {
      throw new Error(
        'EXPO_PUBLIC_API_URL aponta para 127.0.0.1/localhost: proibido no build de release.',
      );
    }
    if (!/^https:\/\//i.test(apiUrl)) {
      throw new Error('EXPO_PUBLIC_API_URL precisa ser HTTPS no build de release.');
    }
  }

  return config;
};
