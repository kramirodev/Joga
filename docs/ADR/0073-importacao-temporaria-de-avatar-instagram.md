# ADR 0073 — Importação temporária da foto do Instagram no beta fechado

- **Status:** Aprovado em 2026-11-23 (decisão do dono), temporário.
- **Data:** 2026-11-23
- **Decisores:** responsável pelo produto e equipe técnica.
- **Relaciona:** `backend/app/modules/avatar/`; `backend/app/api/v1/avatar.py`;
  spec interna do beta fechado.

## Contexto

O perfil do app ainda não tem foto real. A integração oficial com o Instagram
(Meta Business + OAuth + App Review) depende de domínio próprio e aprovação da
Meta, o que leva semanas. Para validar o fluxo no beta fechado, o dono autorizou
uma importação temporária da foto do **próprio** perfil público informado pelo
jogador.

## Decisões

1. **Escopo:** o jogador informa a URL do próprio perfil público; o backend
   busca a página, extrai a foto, valida, reencoda para JPEG 512×512, remove
   EXIF e grava em storage privado. Não há importação em massa nem de terceiros.
2. **Flag:** `JOGA_INSTAGRAM_IMPORT_MODE=off|scrape|api`, default `off`.
   `scrape` só sobe em `local`, `teste` ou `demo`; fora disso o boot falha.
   `api` fica reservado para a integração oficial.
3. **Segurança:** allowlist de host do Instagram, somente HTTPS, um redirect,
   bloqueio de IP não público (anti-SSRF), limites de 512 KB (HTML) e 5 MB
   (imagem), sem cookies/login/proxy de ambiente. A URL assinada da CDN não é
   persistida nem logada.
4. **Privacidade:** consentimento explícito na tela; guarda-se a URL da página
   pública, nunca a URL da CDN; o jogador pode remover o avatar a qualquer
   momento; a foto é servida autenticada, com `no-store` e `nosniff`.
5. **Contrato:** `POST/DELETE /me/avatar/instagram`, `GET /me/avatar`,
   `GET /me/avatar/content` e `GET /users/{id}/avatar/content` (autenticado).
6. **Fallback:** presets/identidade atual continuam válidos; falha do Instagram
   nunca bloqueia o perfil.
7. **Remoção:** quando a integração oficial da Meta for aprovada, o caminho de
   scraping é removido e a flag passa a `api`.

## Consequências

- Migração `d9e0f1a2b3c4` cria `user_avatars` (uma linha por usuário).
- O beta fechado consegue validar foto real antes da Meta.
- Riscos aceitos e registrados: dependência do HTML público, bloqueio/rate limit
  do Instagram, perfis privados sem foto e violação dos Termos do Instagram.
  Nada disso vale para produção pública; o caminho será apagado.
