# NousCard — Repaginação UX 2026

## Escopo
Esta entrega altera somente a apresentação do sistema.

- menu principal vertical em desktop;
- barra contextual horizontal de usuário/empresa;
- navegação agrupada em Gestão e Financeiro;
- dashboard com hierarquia executiva;
- KPIs principais priorizados;
- camada gerencial secundária mais discreta;
- cards e espaçamentos padronizados;
- comportamento responsivo para tablet/celular.

## Arquivos alterados
- `templates/base.html`: inclusão do stylesheet da nova camada visual.
- `templates/dashboard.html`: classes semânticas nos blocos financeiros para hierarquia visual.
- `static/css/nouscard-ux.css`: nova camada visual completa.

## Não alterado
Rotas, APIs, models, banco, migrations, serviços, JavaScript de carregamento e regras financeiras não foram modificados.

## Rollback
Remover a referência a `nouscard-ux.css` em `templates/base.html` e, opcionalmente, apagar o arquivo. As três classes extras do dashboard são inofensivas sem o CSS.
