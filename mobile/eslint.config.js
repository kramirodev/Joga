const { defineConfig, globalIgnores } = require('eslint/config');
const expoConfig = require('eslint-config-expo/flat');

module.exports = defineConfig([
  globalIgnores(['android/*', 'ios/*', '.expo/*', 'dist/*', 'node_modules/*']),
  expoConfig,
  {
    rules: {
      // Diagnóstico permitido é `warn` (e `error`); nada de `console.log`
      // por render ou esquecido no bundle de produção.
      'no-console': ['error', { allow: ['warn', 'error'] }],
    },
  },
]);
