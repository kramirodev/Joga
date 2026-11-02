# Prova isolada — OTP por SMS com adapter simulado

Esta pasta contém uma prova técnica da Fase 1, **não código de produto**. O objetivo é
exercitar o contrato de OTP descrito em `docs/JOGA_DOCUMENTACAO_TECNICA.md` §5.3 sem
provedor real, sem rede, sem credencial e sem custo:

- telefone normalizado em E.164;
- código de 6 dígitos, uso único, validade de 5 minutos;
- armazenamento apenas do hash HMAC do código, com segredo externo;
- até 5 tentativas por desafio;
- intervalo mínimo de 60 segundos para reenvio;
- reenvio invalida o desafio anterior;
- nenhum código ou telefone completo em `repr`/log.

O adapter `SimulatedSmsAdapter` guarda o código em memória apenas para o teste poder
lê-lo. Em produção, o adapter real entrega o código ao provedor e o código nunca é
persistido em claro.

## Por que fora de `backend/`

A Fase 2 é quem cria a estrutura `backend/` com FastAPI, migrações e testes. Colocar esta
prova em `harness/proofs/` evita antecipar a arquitetura de produto e deixa explícito que
o código aqui é uma prova descartável. Na Fase 3 (identidade e segurança), a lógica deve
ser portada para o backend, com persistência transacional e rate limiting por IP,
dispositivo, telefone e operação.

## Executar

Requer apenas Python 3.11+ (sem dependências externas):

```powershell
python -X utf8 -m unittest discover -s harness/proofs/sms-otp -v
```

## Limites conhecidos

- Normalização cobre E.164 e prefixo `00`; números locais exigem país/DDD e não são
  resolvidos aqui.
- Sem persistência, sem Redis, sem rate limit por IP/dispositivo e sem integração HTTP.
- O relógio é injetável para testar expiração sem espera real.
- Nenhum provedor de SMS foi contatado; nenhum número real foi usado.
