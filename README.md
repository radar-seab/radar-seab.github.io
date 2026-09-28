# Radar SEAB

Clipping de notícias para a assessoria de imprensa da Secretaria da Agricultura e do Abastecimento do Paraná (SEAB) e vinculadas (IDR-Paraná, Adapar, Ceasa, Deral).

**Site:** https://radar-seab.github.io

## Como usar

- **Período:** Hoje, Ontem, Esta semana, Semana passada (seg a sex), Últimos 7 dias, Este mês, Mês passado, ou datas livres em *De / até*.
- **Termos:** ligue e desligue cada termo monitorado.
- **Buscar:** filtra por palavra no título ou no nome do veículo.
- **Copiar clipping:** copia a lista pronta para colar no WhatsApp ou e-mail.
- **Baixar planilha (CSV):** abre direto no Excel.
- O endereço da página guarda os filtros; dá para mandar o link de um recorte para alguém.

## Como funciona

- `termos.json`: lista de termos e a busca feita para cada um. Para incluir um termo, adicione uma linha e faça commit.
- `scripts/coletar.py`: consulta o Google Notícias (RSS) para cada termo e acumula em `data/noticias.json` (guarda 2 anos).
- `.github/workflows/coletar.yml`: roda a coleta a cada 2 horas. Em *Actions > Coletar notícias > Run workflow* dá para rodar na hora ou fazer carga retroativa (campo `desde`).

Termos genéricos (IDR, Ceasa, "Secretaria da Agricultura e do Abastecimento") são buscados junto com "Paraná" ou cidades com unidade da Ceasa-PR, para não trazer notícias de outros estados.

## Limites

- A fonte é o Google Notícias: cobre portais e jornais online, não TV, rádio nem impresso.
- O Google devolve no máximo cerca de 100 resultados por busca; a coleta a cada 2 horas fica bem abaixo disso.
