"""Checagem mínima do coletor: python scripts/test_coletar.py"""
import xml.etree.ElementTree as ET

from coletar import chave, janelas, mesclar, parse_item
from datetime import date

item = ET.fromstring(
    "<item><title>Deral reduz previsão de safra de trigo - Folha de Londrina</title>"
    "<link>https://news.google.com/x</link><pubDate>Thu, 24 Sep 2026 18:41:21 GMT</pubDate>"
    "<source url='https://folhadelondrina.com.br'>Folha de Londrina</source></item>"
)
n = parse_item(item)
assert n["titulo"] == "Deral reduz previsão de safra de trigo", n
assert n["fonte"] == "Folha de Londrina" and n["data"] == "2026-09-24T18:41:21Z"

acervo = {}
assert mesclar(acervo, [n], "Deral") == 1
assert mesclar(acervo, [n], "Seab") == 0  # mesma matéria, outro termo: não duplica
assert acervo[chave(n)]["termos"] == ["Deral", "Seab"]
assert mesclar(acervo, [{**n, "fonte": "Agrolink"}], "Deral") == 1  # outro veículo conta
assert chave(n) == chave({**n, "titulo": "DERAL reduz previsao de safra de trigo"})  # acento/caixa

js = list(janelas(date(2026, 9, 1), date(2026, 9, 7)))
assert js[0] == "after:2026-09-01 before:2026-09-04" and js[-1].endswith("before:2026-09-08"), js
print("ok")
