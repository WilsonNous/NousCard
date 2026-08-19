# NousCard Gestão — MVP Orçamentos e Ordens de Serviço

Implementação inicial para validação com a Vidraçaria Progresso.

## Incluído nesta versão

- Cadastro multiempresa de clientes.
- Cadastro de orçamentos com numeração automática por empresa.
- Itens comerciais com descrição, detalhamento, quantidade, valor e imagem.
- Informações internas por item: medidas, dados técnicos e custos estimados.
- Cálculo de subtotal, desconto, total, custo e margem estimada.
- Status: Rascunho, Enviado, Aprovado, Recusado e Cancelado.
- Visualização comercial do orçamento.
- Página A4 pronta para impressão / "Salvar como PDF" pelo navegador.
- Conversão de orçamento aprovado em Ordem de Serviço.
- Fluxo inicial da OS: Aguardando material, Material recebido, Agendado, Em execução, Concluído e Cancelado.
- Reaproveitamento da logo e dos dados já cadastrados em `Empresa`.

## Banco de dados

Antes de publicar a aplicação atualizada, executar em ambiente de homologação/backup:

`scripts/sql/20260819_mvp_clientes_orcamentos_os.sql`

O script cria apenas tabelas novas; não altera as tabelas financeiras existentes.

## Primeiro roteiro de demonstração

1. Cadastrar `Residência Serena` em Clientes.
2. Criar orçamento com descrição `Espelhos Academia`.
3. Inserir valor de R$ 3.780,00 e uma imagem comercial.
4. Informar `50% de sinal para início da produção e saldo na entrega`.
5. Definir validade de 7 dias.
6. Visualizar o documento e usar `Salvar / imprimir PDF`.
7. Alterar status para `Aprovado`.
8. Clicar em `Gerar Ordem de Serviço`.
9. Mostrar os dados técnicos herdados na OS.

## Próxima evolução após feedback do piloto

- Anexos internos (desenhos, orçamento da fábrica, fotos de medição).
- Geração de PDF no servidor, caso seja necessária experiência de download em um clique.
- Botão de compartilhamento via WhatsApp.
- Composição de custos mais flexível por fornecedor/tipo de custo.
- Integração de OS concluída com contas a receber/DRE.
