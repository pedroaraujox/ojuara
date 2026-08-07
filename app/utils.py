"""Funcoes auxiliares: parsing de formularios, datas e formatacao BR."""

import calendar
import re
from datetime import date, datetime

FORMAS_PAGAMENTO = {
    "DINHEIRO": "Dinheiro",
    "PIX": "Pix",
    "CARTAO": "Cartao",
    "CREDIARIO": "Crediario/Parcelado",
}

TIPOS_MOVIMENTACAO = {
    "ENTRADA": "Entrada de estoque",
    "VENDA": "Venda",
    "BAIXA": "Baixa de estoque",
    "DEVOLUCAO_FORNECEDOR": "Devolucao ao fornecedor",
    "ESTORNO": "Estorno de venda",
    "AJUSTE": "Ajuste manual",
    "SAIDA_SACOLA": "Saida para sacola",
    "DEVOLUCAO_SACOLA": "Devolucao de sacola",
}

# Movimentacoes que retiram pecas do estoque.
TIPOS_SAIDA = ("VENDA", "BAIXA", "DEVOLUCAO_FORNECEDOR", "SAIDA_SACOLA")

# Tipos de movimentacao que sao sempre lancados atrelados a um numero de NF.
TIPOS_COM_NF = ("ENTRADA", "BAIXA", "DEVOLUCAO_FORNECEDOR")


# --- conversoes -------------------------------------------------------------

def to_decimal(valor, padrao=0.0):
    """Converte texto de formulario em float aceitando '1.234,56' e '1234.56'."""
    if valor is None:
        return padrao
    if isinstance(valor, (int, float)):
        return round(float(valor), 2)

    texto = str(valor).strip()
    if not texto:
        return padrao

    texto = re.sub(r"[^\d,.\-]", "", texto)
    if "," in texto and "." in texto:
        # 1.234,56 -> 1234.56
        texto = texto.replace(".", "").replace(",", ".")
    elif "," in texto:
        texto = texto.replace(",", ".")

    try:
        return round(float(texto), 2)
    except ValueError:
        return padrao


def to_int(valor, padrao=0):
    if valor is None:
        return padrao
    if isinstance(valor, int):
        return valor
    texto = str(valor).strip()
    if not texto:
        return padrao
    texto = re.sub(r"[^\d\-]", "", texto)
    try:
        return int(texto)
    except ValueError:
        return padrao


def normaliza_codigo(valor):
    """Codigos sao comparados sempre em maiusculas e sem espacos."""
    return re.sub(r"\s+", "", (valor or "")).upper()


def normaliza_cpf(valor):
    """Mantem apenas os digitos do CPF, descartando pontuacao."""
    return re.sub(r"\D", "", valor or "")


def formata_cpf(valor):
    """'12345678900' -> '123.456.789-00'. Retorna o valor original se invalido."""
    digitos = normaliza_cpf(valor)
    if len(digitos) != 11:
        return valor or "-"
    return "%s.%s.%s-%s" % (digitos[0:3], digitos[3:6], digitos[6:9], digitos[9:11])


def cpf_valido(valor):
    """Valida o CPF pelo algoritmo oficial dos dois digitos verificadores."""
    digitos = normaliza_cpf(valor)
    if len(digitos) != 11 or digitos == digitos[0] * 11:
        return False

    def digito_verificador(parcial):
        soma = sum(int(d) * peso for d, peso in zip(parcial, range(len(parcial) + 1, 1, -1)))
        resto = (soma * 10) % 11
        return resto if resto < 10 else 0

    primeiro = digito_verificador(digitos[:9])
    segundo = digito_verificador(digitos[:9] + str(primeiro))
    return digitos[9:] == "%d%d" % (primeiro, segundo)


def normaliza_tamanho(valor):
    """Tamanhos sao comparados sempre em maiusculas, com espacos colapsados."""
    return re.sub(r"\s+", " ", (valor or "").strip()).upper()


_ORDEM_TAMANHOS = ["PP", "P", "M", "G", "GG", "XG", "XGG", "EG", "U", "UNICO"]


def chave_ordem_tamanho(tamanho):
    """Ordena grades como PP/P/M/G/GG antes de numeros, e numeros antes do resto."""
    tamanho = (tamanho or "").strip().upper()
    if tamanho in _ORDEM_TAMANHOS:
        return (0, _ORDEM_TAMANHOS.index(tamanho), tamanho)
    if tamanho.isdigit():
        return (1, int(tamanho), tamanho)
    return (2, 0, tamanho)


def ordenar_por_tamanho(linhas, chave="tamanho"):
    return sorted(linhas, key=lambda linha: chave_ordem_tamanho(linha[chave]))


# --- datas ------------------------------------------------------------------

def hoje_iso():
    return date.today().isoformat()


def agora_iso():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


_FORMATOS_DATA = ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y")


def parse_data(texto, padrao=None):
    """Aceita YYYY-MM-DD (input date) ou DD/MM/AAAA. Retorna date."""
    if isinstance(texto, date):
        return texto
    texto = (texto or "").strip()
    for formato in _FORMATOS_DATA:
        try:
            return datetime.strptime(texto, formato).date()
        except ValueError:
            continue
    return padrao if padrao is not None else date.today()


def parse_data_ou_none(texto):
    """Como parse_data, mas retorna None em vez de cair no dia de hoje.

    Usado para validar campos de data obrigatorios (nascimento, por exemplo)
    onde um valor ausente ou invalido precisa virar erro, nao um valor default.
    """
    if isinstance(texto, date):
        return texto
    texto = (texto or "").strip()
    for formato in _FORMATOS_DATA:
        try:
            return datetime.strptime(texto, formato).date()
        except ValueError:
            continue
    return None


def soma_meses(data_base, meses):
    """Avanca N meses preservando o dia quando possivel (31/01 + 1 -> 28/02)."""
    total = data_base.month - 1 + meses
    ano = data_base.year + total // 12
    mes = total % 12 + 1
    dia = min(data_base.day, calendar.monthrange(ano, mes)[1])
    return date(ano, mes, dia)


def intervalo_mes(competencia):
    """'2026-07' -> ('2026-07-01', '2026-07-31'). Invalido cai no mes atual."""
    try:
        ano, mes = competencia.split("-")
        ano, mes = int(ano), int(mes)
        date(ano, mes, 1)
    except (ValueError, AttributeError):
        hoje = date.today()
        ano, mes = hoje.year, hoje.month
    ultimo = calendar.monthrange(ano, mes)[1]
    return date(ano, mes, 1).isoformat(), date(ano, mes, ultimo).isoformat()


def competencia_atual():
    return date.today().strftime("%Y-%m")


NOMES_MESES = [
    "janeiro", "fevereiro", "marco", "abril", "maio", "junho",
    "julho", "agosto", "setembro", "outubro", "novembro", "dezembro",
]


def rotulo_competencia(competencia):
    try:
        ano, mes = competencia.split("-")
        return "%s/%s" % (NOMES_MESES[int(mes) - 1].capitalize(), ano)
    except (ValueError, IndexError, AttributeError):
        return competencia


# --- filtros Jinja ----------------------------------------------------------

def brl(valor):
    """1234.5 -> 'R$ 1.234,50'"""
    try:
        numero = float(valor or 0)
    except (TypeError, ValueError):
        numero = 0.0
    inteiro = "{:,.2f}".format(abs(numero))
    inteiro = inteiro.replace(",", "#").replace(".", ",").replace("#", ".")
    sinal = "-" if numero < 0 else ""
    return "%sR$ %s" % (sinal, inteiro)


def data_br(valor):
    """'2026-07-24' ou '2026-07-24 10:30:00' -> '24/07/2026'."""
    if not valor:
        return "-"
    texto = str(valor)[:10]
    try:
        return datetime.strptime(texto, "%Y-%m-%d").strftime("%d/%m/%Y")
    except ValueError:
        return texto


def data_hora_br(valor):
    if not valor:
        return "-"
    try:
        return datetime.strptime(str(valor), "%Y-%m-%d %H:%M:%S").strftime(
            "%d/%m/%Y %H:%M"
        )
    except ValueError:
        return data_br(valor)


def registra_filtros(app):
    app.jinja_env.filters["brl"] = brl
    app.jinja_env.filters["data_br"] = data_br
    app.jinja_env.filters["data_hora_br"] = data_hora_br
    app.jinja_env.filters["cpf"] = formata_cpf
