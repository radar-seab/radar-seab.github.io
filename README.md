# Radar SEAB

Clipping de notícias para a assessoria de imprensa da Secretaria da Agricultura e do Abastecimento do Paraná (SEAB) e vinculadas (IDR-Paraná, Adapar, Ceasa, Deral).

**Site:** https://radar-seab.github.io

## Como usar

- **Período:** Hoje, Ontem, Esta semana, Semana passada (seg a sex), Últimos 7 dias, Este mês, Mês passado, ou datas livres em *De / até*.
- **Termos:** ligue e desligue cada termo monitorado.
- **Mídia:** Portal, Jornal, TV, Rádio, Vídeo, Oficial.
- **Buscar:** filtra por palavra no título, resumo ou nome do veículo.
- **Copiar clipping:** copia a lista pronta para colar no WhatsApp ou e-mail.
- **Baixar planilha (CSV):** abre direto no Excel.
- O endereço da página guarda os filtros; dá para mandar o link de um recorte para alguém.

## Como funciona

Fontes, todas coletadas a cada 2 horas pelo GitHub Actions:

1. **Google Notícias**: busca por termo (principal fonte, milhares de portais, jornais, TVs e rádios com site).
2. **Bing Notícias**: busca por termo, pega o que o Google não indexa.
3. **RSS de 40 feeds de veículos do Paraná e do agro** (`fontes.json`): jornais (Gazeta do Povo, Folha de Londrina, O Diário, Tribuna…), TVs (G1/RPC, Tarobá, Massa, Canal Rural), rádios (CBN Curitiba, Banda B) e portais regionais. Em 14 deles também é feita busca por termo no acervo do próprio site.
4. **YouTube**: telejornais e vídeos do último mês que citam os termos no título ou na descrição.

Arquivos:

- `termos.json`: termos, busca usada no Google/Bing e regra de conferência no texto. Para incluir um termo, adicione uma linha.
- `fontes.json`: feeds de veículos. Para incluir um veículo, adicione `nome`, `url` do RSS, `midia` e `pr`.
- `scripts/coletar.py`: coleta, filtra e acumula em `data/noticias.json` (guarda 2 anos). `scripts/test_coletar.py` confere as regras.
- `.github/workflows/coletar.yml`: agenda da coleta. Em *Actions > Coletar notícias > Run workflow* dá para rodar na hora ou fazer carga retroativa (campo `desde`).

Regras de filtro:

- **Ceasa**: só entra com prova de Paraná no título, resumo ou veículo (Ceasa-PR, Paraná, cidades com unidade, veículo paranaense) e sem menção a outro estado. Ceasas de outros estados ficam de fora.
- **IDR, Deral e "Secretaria da Agricultura e do Abastecimento"**: buscados junto com Paraná; nos feeds e no Bing, precisam de contexto paranaense.
- Cada notícia recebe um tipo de mídia (Portal, Jornal, TV, Rádio, Vídeo, Oficial) pelo nome do veículo.

## Limites

- TV aberta, rádio ao vivo e jornal impresso só entram quando o conteúdo também sai no site do veículo ou no YouTube. Monitoramento da transmissão em si e da edição impressa exige serviço pago de clipping (decupagem).
- Os sites oficiais (Seab, IDR, Adapar, Ceasa, AEN) estão sem notícias novas por causa do período eleitoral; o que eles publicam chega pelos veículos que reproduzem.
- Redes sociais (Instagram, Facebook, X) não entram: as APIs são pagas ou fechadas.
