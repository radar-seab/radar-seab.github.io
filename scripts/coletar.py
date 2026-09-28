"""Coleta notícias para cada termo de termos.json e acumula em data/noticias.json.

Fontes: Google Notícias e Bing Notícias (busca por termo), RSS dos veículos em fontes.json
e YouTube (telejornais e vídeos), filtrados localmente pelos termos.

Uso:
  python scripts/coletar.py                     # coleta recente (rodado pelo GitHub Actions)
  python scripts/coletar.py --desde 2026-07-01  # + carga retroativa do Google em janelas de 3 dias
"""
import argparse
import email.utils
import hashlib
import html
import json
import re
import sys
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
ARQ_TERMOS = RAIZ / "termos.json"
ARQ_FONTES = RAIZ / "fontes.json"
ARQ_DADOS = RAIZ / "data" / "noticias.json"
UA = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130 Safari/537.36",
    "Accept-Language": "pt-BR,pt;q=0.9",
}
JANELA_DIAS = 3  # Google devolve no máximo ~100 itens por busca
RETENCAO_DIAS = 730
TAM_RESUMO = 240

# Contexto Paraná e marcadores de outros estados (texto já sem acento e minúsculo)
PR_RE = re.compile(
    r"\bparana\b|paranaense|\bpr\b|curitiba|londrina|maringa|cascavel|foz do iguacu|ponta grossa|guarapuava"
    r"|toledo|umuarama|francisco beltrao|pato branco|apucarana|campo mourao|ibipora|irati|paranavai|cianorte"
    r"|arapongas|colombo|sao jose dos pinhais|pr\.gov\.br"
)
OUTRO_ESTADO_RE = re.compile(
    r"\((ac|al|ap|am|ba|ce|df|es|go|ma|mt|ms|mg|pa|pb|pe|pi|rj|rn|rs|ro|rr|sc|sp|se|to)\)"
    r"|ceara|maracanau|fortaleza|joinville|santa catarina|anapolis|goias|goiania|campinas|sao paulo|ceagesp"
    r"|manaus|amazonas|recife|pernambuco|grande bh|belo horizonte|minas gerais|rio de janeiro|\brj\b|bahia"
    r"|salvador|porto alegre|rio grande do sul|brasilia|distrito federal|espirito santo|grande vitoria"
    r"|joao pessoa|teresina|belem|maceio|aracaju|cuiaba|mato grosso|campo grande|florianopolis"
)
MIDIA_RE = [
    ("Oficial", re.compile(r"pr\.gov\.br|\baen\b|agencia estadual|prefeitura|governo|camara|assembleia|\.gov\.br")),
    ("Rádio", re.compile(r"radio|\bfm\b|\bam\b|\bcbn\b|bandnews|banda b|jovem pan|educadora")),
    ("TV", re.compile(r"\btv\b|\brpc\b|\bric\b|record|\bband\b|taroba|catve|\bsbt\b|massa|globo|canal rural|telejornal")),
    ("Jornal", re.compile(r"jornal|folha|gazeta|diario|tribuna|correio|o parana\b|o presente")),
]


def sem_acento(s: str) -> str:
    return unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()


def norm(s: str) -> str:
    return sem_acento(s).lower()


def limpa(s: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", s or ""))).strip()


def baixar(url: str) -> bytes | None:
    for tentativa in range(3):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=30) as r:
                return r.read()
        except Exception as e:  # rede instável: tenta de novo, depois desiste só desta fonte
            print(f"  falha ({tentativa + 1}/3) em {url[:90]}: {e}", file=sys.stderr)
            if isinstance(e, urllib.error.HTTPError) and 400 <= e.code < 500 and e.code != 429:
                return None  # bloqueio ou página inexistente: repetir não adianta
            time.sleep(4 * (tentativa + 1))
    return None


def xml_itens(dados: bytes | None) -> list[ET.Element]:
    if not dados:
        return []
    try:
        return list(ET.fromstring(dados).iter("item"))
    except ET.ParseError as e:
        print(f"  XML inválido: {e}", file=sys.stderr)
        return []


def data_rfc(s: str | None) -> str | None:
    try:
        return email.utils.parsedate_to_datetime(s).astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    except (TypeError, ValueError):
        return None


def item(titulo, fonte, link, data, origem, resumo="") -> dict:
    return {"titulo": limpa(titulo), "fonte": limpa(fonte), "link": (link or "").strip(), "data": data,
            "origem": origem, "resumo": limpa(resumo)[:TAM_RESUMO]}


# ---------- fontes ----------

def google(consulta: str) -> list[dict]:
    url = "https://news.google.com/rss/search?" + urllib.parse.urlencode(
        {"q": consulta, "hl": "pt-BR", "gl": "BR", "ceid": "BR:pt-419"})
    out = []
    for i in xml_itens(baixar(url)):
        fonte = (i.findtext("source") or "").strip()
        titulo = (i.findtext("title") or "").strip()
        if fonte and titulo.endswith(f" - {fonte}"):
            titulo = titulo[: -len(fonte) - 3]
        out.append(item(titulo, fonte, i.findtext("link"), data_rfc(i.findtext("pubDate")), "Google"))
    return out


def bing(consulta: str, intervalo: str) -> list[dict]:
    url = "https://www.bing.com/news/search?" + urllib.parse.urlencode(
        {"q": consulta, "format": "rss", "qft": f'interval="{intervalo}"', "setlang": "pt-br", "cc": "br"})
    out = []
    for i in xml_itens(baixar(url)):
        link = i.findtext("link") or ""
        real = urllib.parse.parse_qs(urllib.parse.urlparse(link).query).get("url")
        fonte = next((c.text for c in i if c.tag.endswith("Source")), "") or urllib.parse.urlparse(real[0] if real else link).netloc
        out.append(item(i.findtext("title"), fonte, real[0] if real else link, data_rfc(i.findtext("pubDate")),
                        "Bing", i.findtext("description")))
    return out


def rss(feed: dict) -> list[dict]:
    return [{**item(i.findtext("title"), feed["nome"], i.findtext("link"), data_rfc(i.findtext("pubDate")), "RSS",
                    i.findtext("description")), "pr": feed["pr"]}
            for i in xml_itens(baixar(feed["url"]))]


UNIDADES = {"minuto": 60, "hora": 3600, "dia": 86400, "sem": 604800, "mes": 2592000, "ano": 31536000}


def data_relativa(txt: str, agora: datetime) -> str | None:
    """'há 3 horas', 'Transmitido há 2 sem.' -> ISO aproximado."""
    m = re.search(r"(\d+)\s*(minuto|hora|dia|sem|mes|ano)", norm(txt or ""))
    if not m:
        return None
    return (agora - timedelta(seconds=int(m[1]) * UNIDADES[m[2]])).strftime("%Y-%m-%dT%H:%M:%SZ")


def youtube(consulta: str) -> list[dict]:
    url = "https://www.youtube.com/results?" + urllib.parse.urlencode(
        {"search_query": consulta, "sp": "EgQIBBAB"})  # vídeos publicados no último mês
    dados = baixar(url)
    m = re.search(rb"var ytInitialData = (\{.*?\});</script>", dados or b"")
    if not m:
        return []
    videos, pilha = [], [json.loads(m[1])]
    while pilha:  # busca todos os videoRenderer na árvore
        o = pilha.pop()
        if isinstance(o, dict):
            if "videoRenderer" in o:
                videos.append(o["videoRenderer"])
            pilha.extend(o.values())
        elif isinstance(o, list):
            pilha.extend(o)
    agora = datetime.now(timezone.utc)
    out = []
    for v in videos:
        txt = lambda k: "".join(r.get("text", "") for r in v.get(k, {}).get("runs", []))
        snip = " ".join("".join(r.get("text", "") for r in s.get("snippetText", {}).get("runs", []))
                        for s in v.get("detailedMetadataSnippets", []))
        data = data_relativa(v.get("publishedTimeText", {}).get("simpleText", ""), agora)
        if data:
            out.append(item(txt("title"), txt("ownerText"), f"https://www.youtube.com/watch?v={v['videoId']}",
                            data, "YouTube", snip))
    return out


# ---------- filtro e acervo ----------

def casa(termo: dict, n: dict, exige_texto: bool) -> bool:
    """O item menciona o termo, no contexto certo?"""
    texto = f"{n['titulo']} {n['resumo']}"
    alvo = sem_acento(texto) if termo.get("maiusculas") else norm(texto)
    if exige_texto and not re.search(termo["regex"], alvo):
        return False
    ctx = termo.get("contexto")
    no_pr = n.get("pr", False) or bool(PR_RE.search(norm(f"{texto} {n['fonte']}")))
    if ctx == "pr" and exige_texto:
        return no_pr
    if ctx == "estrito":  # Ceasa: só Paraná, sempre, mesmo vindo do Google
        return bool(re.search(termo["regex"], norm(n["titulo"] + " " + n["resumo"]))) and no_pr \
            and not OUTRO_ESTADO_RE.search(norm(n["titulo"] + " " + n["resumo"]))
    return True


def classifica(n: dict, midia_fontes: dict[str, str]) -> str:
    if n["fonte"] in midia_fontes:
        return midia_fontes[n["fonte"]]
    f = norm(n["fonte"])
    for midia, rx in MIDIA_RE:
        if rx.search(f):
            return midia
    return "Vídeo" if n["origem"] == "YouTube" else "Portal"


def chave(n: dict) -> str:
    # mesma matéria republicada por veículos diferentes = entradas diferentes no clipping
    base = norm(f"{n['titulo']}|{n['fonte']}")
    return hashlib.sha1(re.sub(r"\W+", "", base).encode()).hexdigest()[:16]


def mesclar(acervo: dict, itens: list[dict], termo: str) -> int:
    novos = 0
    for n in itens:
        if not n["titulo"] or not n["link"] or not n["data"]:
            continue
        k = chave(n)
        if k not in acervo:
            acervo[k] = {**n, "id": k, "termos": []}
            novos += 1
        atual = acervo[k]
        if "news.google.com" in atual["link"] and "news.google.com" not in n["link"]:
            atual = {**atual, "link": n["link"]}  # prefere o link direto do veículo
        if n["resumo"] and not atual.get("resumo"):
            atual = {**atual, "resumo": n["resumo"]}
        if termo not in atual["termos"]:
            atual = {**atual, "termos": [*atual["termos"], termo]}
        acervo[k] = atual
    return novos


def revalidar(n: dict, termos: list[dict], midia_fontes: dict) -> dict | None:
    """Reaplica as regras estritas a todo o acervo (vale para itens antigos quando uma regra muda)."""
    n = {"resumo": "", "origem": "Google", **n}
    por_nome = {t["termo"]: t for t in termos}
    ok = [t for t in n["termos"] if t in por_nome
          and (por_nome[t].get("contexto") != "estrito" or casa(por_nome[t], n, True))]
    return {**n, "termos": ok, "midia": classifica(n, midia_fontes)} if ok else None


def janelas(desde: date, ate: date):
    ini = desde
    while ini <= ate:
        fim = min(ini + timedelta(days=JANELA_DIAS), ate + timedelta(days=1))
        yield f"after:{ini.isoformat()} before:{fim.isoformat()}"
        ini = fim


def coletar_termo(t: dict, filtros_google: list[str], intervalo_bing: str) -> list[dict]:
    itens = []
    for f in filtros_google:
        itens += google(f"{t['busca']} {f}")
        time.sleep(1)
    itens += bing(t["busca"], intervalo_bing)
    itens += youtube(t.get("youtube", t["termo"]))
    return itens


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--desde", type=date.fromisoformat)
    args = ap.parse_args()

    termos = json.loads(ARQ_TERMOS.read_text(encoding="utf-8"))
    fontes = json.loads(ARQ_FONTES.read_text(encoding="utf-8"))
    midia_fontes = {f["nome"]: f["midia"] for f in fontes}
    acervo = {}
    if ARQ_DADOS.exists():
        acervo = {n["id"]: n for n in json.loads(ARQ_DADOS.read_text(encoding="utf-8"))["noticias"]}

    filtros = list(janelas(args.desde, date.today())) if args.desde else ["when:2d"]
    intervalo_bing = "9" if args.desde else "8"  # 9 = último mês, 8 = última semana

    with ThreadPoolExecutor(8) as ex:
        rss_itens = [n for lote in ex.map(rss, fontes) for n in lote]
    print(f"RSS: {len(rss_itens)} itens de {len(fontes)} feeds")

    # veículos WordPress que aceitam busca por termo em RSS (?s=termo&feed=rss2)
    bases_wp = {urllib.parse.urlsplit(f["url"])._replace(path="/", query="").geturl(): f
                for f in fontes if f.get("busca_wp")}

    total = 0
    for t in termos:
        buscas_wp = [{**f, "url": f"{base}?{urllib.parse.urlencode({'s': t['termo'], 'feed': 'rss2'})}"}
                     for base, f in bases_wp.items()]
        with ThreadPoolExecutor(8) as ex:
            wp_itens = [n for lote in ex.map(rss, buscas_wp) for n in lote]
        buscados = [n for n in coletar_termo(t, filtros, intervalo_bing)
                    if casa(t, n, exige_texto=n["origem"] != "Google")]
        locais = [n for n in rss_itens + wp_itens if casa(t, n, exige_texto=True)]
        novos = mesclar(acervo, buscados + locais, t["termo"])
        total += novos
        print(f"{t['termo']:<55} {len(buscados):>4} busca, {len(locais):>3} RSS, {novos:>3} novos")

    limite = (date.today() - timedelta(days=RETENCAO_DIAS)).isoformat()
    validas = (revalidar(n, termos, midia_fontes) for n in acervo.values() if n["data"] >= limite)
    noticias = sorted((n for n in validas if n), key=lambda n: n["data"], reverse=True)
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
