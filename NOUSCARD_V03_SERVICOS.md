# NousCard v0.3 — Serviços & Automotivo

## Entregue nesta fase
- Veículos vinculados a clientes (opcional por orçamento).
- Orçamento com veículo.
- Link público por token aleatório.
- Compartilhamento por WhatsApp sem API paga.
- Aprovar / solicitar alteração / recusar orçamento pelo cliente.
- Auditoria básica da resposta: data/hora, IP, user-agent, nome e mensagem.
- Conversão do orçamento aprovado em OS preservada.
- Workflow ampliado para funilaria/oficina sem retirar os estados já usados por outros segmentos.
- Custos reais por OS (peça, material, mão de obra, terceiro, outro).
- Forma de pagamento, valor recebido e taxa de pagamento.
- Resultado e margem por OS.

## Banco
Execute `migrations_sql/20260921_servicos_automotivo.sql` no MySQL após backup.

## Próxima fase recomendada
- Importação/identificação automática de vendas de adquirente por OS.
- Match automático de PIX/extrato bancário com contas a receber/OS.
- Contas a receber parceladas e agenda de cartão.
- Status configuráveis por empresa em tabela própria.
- Fotos de entrada/saída do veículo e checklist de avarias.
- Assinatura/aceite com política jurídica definida.

## Segurança
O link público usa token aleatório forte. Não exponha IDs internos como mecanismo de autorização.
