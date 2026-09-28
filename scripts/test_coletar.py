"""Checagem mínima do coletor: python scripts/test_coletar.py"""
import json
from datetime import date, datetime, timezone
from pathlib import Path

from coletar import casa, chave, classifica, data_relativa, data_rfc, item, janelas, mesclar

TERMOS = {t["termo"]: t for t in json.loads((Path(__file__).parent.parent / "termos.json").read_text(encoding="utf-8"))}
g = lambda titulo, fonte="Agrolink": item(titulo, fonte, "https://news.google.com/x", "2026-09-24T18:41:21Z", "Google")

assert data_rfc("Thu, 24 Sep 2026 18:41:21 GMT") == "2026-09-24T18:41:21Z"
assert data_rfc("lixo") is None

# Ceasa: só Paraná, mesmo quando vem do Google
ceasa = TERMOS["Ceasa"]
assert casa(ceasa, g("Chuvarada de setembro faz preço do morango disparar na Ceasa de Londrina"), False)
assert casa(ceasa, g("Ceasa-PR completa 50 anos como orgulho da população paranaense"), False)
assert casa(ceasa, g("Ceasa avalia impacto das chuvas nos preços", "Bem Paraná"), False)
assert not casa(ceasa, g("Preço do caju registra queda de 48% na Ceasa Maracanaú", "O POVO"), False)
assert not casa(ceasa, g("CEASA Joinville terá reforma orçada em cerca R$ 4,5 milhões"), False)
assert not casa(ceasa, g("Cascavel (CE): Jovem morre após caminhão cair de ponte"), False)
assert not casa(ceasa, g("Incêndio atinge Ceasa, e empilhadeira é usada para salvar mulheres", "G1"), False)
assert not casa(ceasa, g("Curitiba sedia Panamericano de Escalada"), False)  # Ceasa só no corpo, sem prova
rss_pr = {**g("Ceasa avalia impacto das chuvas nos preços", "CGN"), "origem": "RSS", "pr": True}
assert casa(ceasa, rss_pr, True)

# RSS e Bing exigem o termo no texto; IDR só em maiúsculas e no contexto PR
idr = TERMOS["IDR"]
assert casa(idr, {**g("Dia de campo do IDR em Irati"), "origem": "RSS"}, True)
assert not casa(idr, {**g("Dia de campo do IDR em Goiânia"), "origem": "RSS"}, True)
assert not casa(idr, {**g("Taxa idr do banco em Curitiba"), "origem": "RSS"}, True)
assert casa(TERMOS["Deral"], g("Deral reduz previsão de trigo no Paraná"), True)
assert not casa(TERMOS["Deral"], g("Gatesville sports: the Reverend Deral McWhorter", "tdtnews.com"), True)
assert not casa(TERMOS["Deral"], g("Polícia Federal faz operação"), True)

n = g("Deral reduz previsão de safra de trigo", "Folha de Londrina")
acervo = {}
assert mesclar(acervo, [n], "Deral") == 1
assert mesclar(acervo, [{**n, "link": "https://folhadelondrina.com.br/a"}], "Seab") == 0
assert acervo[chave(n)]["termos"] == ["Deral", "Seab"]
assert acervo[chave(n)]["link"] == "https://folhadelondrina.com.br/a"  # troca redirect do Google pelo link direto
assert mesclar(acervo, [{**n, "fonte": "Agrolink"}], "Deral") == 1  # outro veículo conta

assert classifica(g("x", "CBN Curitiba"), {}) == "Rádio"
assert classifica(g("x", "Band News FM Curitiba"), {}) == "Rádio"
assert classifica(g("x", "RPC TV"), {}) == "TV"
assert classifica(g("x", "toledo.pr.gov.br"), {}) == "Oficial"
assert classifica(g("x", "Folha de Irati"), {}) == "Jornal"
assert classifica({**g("x", "Canal do Zé"), "origem": "YouTube"}, {}) == "Vídeo"

agora = datetime(2026, 9, 28, 12, tzinfo=timezone.utc)
assert data_relativa("há 3 horas", agora) == "2026-09-28T09:00:00Z"
assert data_relativa("Transmitido há 2 sem.", agora) == "2026-09-14T12:00:00Z"

js = list(janelas(date(2026, 9, 1), date(2026, 9, 7)))
assert js[0] == "after:2026-09-01 before:2026-09-04" and js[-1].endswith("before:2026-09-08"), js
print("ok")
