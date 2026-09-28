"""Coleta notícias do Google News RSS para cada termo de termos.json e acumula em data/noticias.json.

Uso:
  python scripts/coletar.py                     # últimos 2 dias (rodado pelo GitHub Actions)
  python scripts/coletar.py --desde 2026-07-01  # carga retroativa em janelas de 3 dias
"""
import argparse
import email.utils
import hashlib
import json
import re
import sys
import time
import unicodedata
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import date, timedelta
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
ARQ_TERMOS = RAIZ / "termos.json"
ARQ_DADOS = RAIZ / "data" / "noticias.json"
UA = {"User-Agent": "Mozilla/5.0 (RadarSEAB clipping)"}
JANELA_DIAS = 3  # Google devolve no máximo ~100 itens por busca
RETENCAO_DIAS = 730


def buscar(consulta: str) -> list[dict]:
    url = "https://news.google.com/rss/search?" + urllib.parse.urlencode(
        {"q": consulta, "hl": "pt-BR", "gl": "BR", "ceid": "BR:pt-419"}
    )
    for tentativa in range(3):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=30) as r:
                raiz = ET.fromstring(r.read())
            return [parse_item(i) for i in raiz.iter("item")]
        except Exception as e:  # rede instável: tenta de novo, depois desiste só desta busca
            print(f"  falha ({tentativa + 1}/3) em {consulta!r}: {e}", file=sys.stderr)
            time.sleep(5 * (tentativa + 1))
    return []


def parse_item(item: ET.Element) -> dict:
    fonte = (item.findtext("source") or "").strip()
    titulo = (item.findtext("title") or "").strip()
    sufixo = f" - {fonte}"
    if fonte and titulo.endswith(sufixo):
        titulo = titulo[: -len(sufixo)]
    publicado = email.utils.parsedate_to_datetime(item.findtext("pubDate"))
    return {
        "titulo": titulo,
        "fonte": fonte,
        "link": (item.findtext("link") or "").strip(),
        "data": publicado.strftime("%Y-%m-%dT%H:%M:%SZ"),
    }


def chave(n: dict) -> str:
    # mesma matéria republicada por veículos diferentes = entradas diferentes no clipping
    base = unicodedata.normalize("NFKD", f"{n['titulo']}|{n['fonte']}").encode("ascii", "ignore").decode()
    return hashlib.sha1(re.sub(r"\W+", "", base.lower()).encode()).hexdigest()[:16]


def mesclar(acervo: dict, itens: list[dict], termo: str) -> int:
    novos = 0
    for n in itens:
        if not n["titulo"] or not n["link"]:
            continue
        k = chave(n)
        if k not in acervo:
            acervo[k] = {**n, "id": k, "termos": []}
            novos += 1
        if termo not in acervo[k]["termos"]:
            acervo[k]["termos"] = [*acervo[k]["termos"], termo]
    return novos


def janelas(desde: date, ate: date):
    ini = desde
    while ini <= ate:
        fim = min(ini + timedelta(days=JANELA_DIAS), ate + timedelta(days=1))
        yield f"after:{ini.isoformat()} before:{fim.isoformat()}"
        ini = fim


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--desde", type=date.fromisoformat)
    args = ap.parse_args()

    termos = json.loads(ARQ_TERMOS.read_text(encoding="utf-8"))
    acervo = {}
    if ARQ_DADOS.exists():
        acervo = {n["id"]: n for n in json.loads(ARQ_DADOS.read_text(encoding="utf-8"))["noticias"]}

    filtros = list(janelas(args.desde, date.today())) if args.desde else ["when:2d"]
    total = 0
    for t in termos:
        for f in filtros:
            itens = buscar(f"{t['busca']} {f}")
            novos = mesclar(acervo, itens, t["termo"])
            total += novos
            print(f"{t['termo']:<55} {f:<40} {len(itens):>3} itens, {novos:>3} novos")
            time.sleep(1)

    limite = (date.today() - timedelta(days=RETENCAO_DIAS)).isoformat()
    noticias = sorted((n for n in acervo.values() if n["data"] >= limite), key=lambda n: n["data"], reverse=True)
    ARQ_DADOS.parent.mkdir(exist_ok=True)
    ARQ_DADOS.write_text(
        json.dumps(
            {"atualizado": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
             "termos": [t["termo"] for t in termos], "noticias": noticias},
            ensure_ascii=False, separators=(",", ":"),
        ),
        encoding="utf-8",
    )
    print(f"{total} novas; acervo com {len(noticias)} notícias")


if __name__ == "__main__":
    main()
