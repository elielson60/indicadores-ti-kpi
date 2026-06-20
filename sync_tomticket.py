#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
sync_tomticket.py
==================
Sincroniza os chamados do Tom Ticket (API v2.0) e gera o arquivo `tickets.json`
no mesmo formato que o Painel de Indicadores de TI já espera.

COMO USAR
---------
1. Crie um Token de Acesso em: Configurar Conta > API > "Criar Token"
2. Defina a variável de ambiente TOMTICKET_TOKEN com esse token
   (NUNCA cole o token direto no código)
3. Rode:  python3 sync_tomticket.py
4. O script gera/atualiza o arquivo tickets.json nesta mesma pasta

IMPORTANTE - CAMPOS PERSONALIZADOS
-----------------------------------
Os campos "Qual empresa deseja atendimento", "Qual Sistema ERPs",
"Qual Equipamento", "Qual Aplicativo" e "Avalie a Qualidade da Internet"
são CAMPOS PERSONALIZADOS da conta do Grupo Martins (não vêm prontos no
endpoint /ticket/list). Este script:
  1) Busca a lista de campos personalizados da conta (nome -> id)
  2) Para cada chamado, busca o detalhe (/ticket/detail) que traz os
     valores desses campos
  3) Casa pelo NOME do campo (ver dicionário CUSTOM_FIELD_NAMES abaixo)

⚠️ Como eu (Claude) não tenho acesso à internet para testar contra a conta
real do Tom Ticket, a estrutura exata do retorno de /ticket/detail para
campos personalizados foi montada com base na documentação oficial, mas
pode precisar de um pequeno ajuste. Rode primeiro com DEBUG_FIRST_TICKET=1
(veja abaixo) para conferir o formato real e ajustar se necessário.
"""

import os
import sys
import json
import time
import urllib.request
import urllib.parse
import urllib.error
from datetime import datetime

# ============================================================
# CONFIGURAÇÃO
# ============================================================

TOKEN = os.environ.get("TOMTICKET_TOKEN", "").strip()
BASE_URL = "https://api.tomticket.com/v2.0"
OUTPUT_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tickets.json")

# Nome do departamento de TI no Tom Ticket (como aparece em Configurar Conta).
# O script busca o ID automaticamente pelo nome — ajuste aqui se o nome
# exato do departamento for diferente de "Informática".
DEPARTMENT_NAME = os.environ.get("TOMTICKET_DEPARTMENT", "Informática")

# Buscar só chamados criados a partir desta data (deixe None para buscar tudo)
# Formato: "YYYY-MM-DD HH:MM:SS-0300"
CREATION_DATE_GE = None  # ex: "2025-01-01 00:00:00-0300"

# Ative para imprimir o JSON bruto do primeiro chamado e conferir os campos
DEBUG_FIRST_TICKET = os.environ.get("DEBUG_FIRST_TICKET", "0") == "1"

# Nomes EXATOS dos campos personalizados, como aparecem no Tom Ticket.
# Ajuste aqui se o nome real divergir um pouco (ex: acentuação, espaços).
CUSTOM_FIELD_NAMES = {
    "emp":     "Qual empresa deseja atendimento? (Chamado Externo)",
    "erp":     "Qual Sistema ERPs (Chamado Externo)",
    "equip":   "Qual Equipamento Deseja Atendimento? (Chamado Externo)",
    "app":     "Qual Aplicativo Deseja Atendimento (Chamado Externo)",
    "net":     "Avalie a Qualidade da sua Internet (Chamado Externo)",
    "problema":"Informe o Problema (Chamado Externo)",
}

# Mapeamento da nota de avaliação (built-in evaluation.grade) para os
# rótulos que o painel já usa. Ajuste se a conta usar um campo de
# "Opinião" customizado em vez da avaliação padrão do Tom Ticket.
GRADE_TO_OPINIAO = {
    5: "Muito Satisfeito",
    4: "Satisfeito",
    3: "Regular",
    2: "Insatisfeito",
    1: "Muito Insatisfeito",
}

PRIORITY_MAP = {1: "Baixa", 2: "Normal", 3: "Alta", 4: "Urgente"}

RATE_LIMIT_SLEEP = 0.4  # ~2.5 req/s, dentro do limite de 3 req/s da API


# ============================================================
# HTTP HELPERS (sem dependências externas, só biblioteca padrão)
# ============================================================

def api_get(path, params=None):
    if not TOKEN:
        print("ERRO: variável de ambiente TOMTICKET_TOKEN não definida.", file=sys.stderr)
        sys.exit(1)

    url = f"{BASE_URL}{path}"
    if params:
        clean = {k: v for k, v in params.items() if v is not None}
        url += "?" + urllib.parse.urlencode(clean)

    req = urllib.request.Request(url, method="GET")
    req.add_header("Authorization", f"Bearer {TOKEN}")

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        print(f"ERRO HTTP {e.code} em {path}: {body}", file=sys.stderr)
        raise
    time.sleep(RATE_LIMIT_SLEEP)
    return data


# ============================================================
# 1) CAMPOS PERSONALIZADOS — descobre o ID de cada campo pelo nome
# ============================================================

def list_categories(department_id):
    """Retorna lista de {id, name} das categorias de um departamento."""
    result = api_get("/department/category/list", {"department_id": department_id})
    if result.get("error"):
        print("  aviso: não foi possível listar categorias:", result.get("message"))
        return []
    return result.get("data") or []


def load_custom_field_ids(department_id):
    """Retorna um dict {nome_do_campo: id_do_campo} para os campos de
    'Chamado Externo' (ticket) vinculados ao departamento informado.
    Os campos podem estar atrelados ao departamento (sem categoria) e/ou
    a cada categoria especificamente, então consultamos todas as
    combinações e juntamos os resultados."""
    if not department_id:
        print("  aviso: sem department_id, não é possível carregar campos personalizados.")
        return {}

    name_to_id = {}

    def merge_fields(result):
        data = result.get("data") or {}
        items = data.get("ticket") or []
        for item in items:
            label = item.get("label") or item.get("name")
            field_id = item.get("id")
            if label and field_id:
                name_to_id[label] = field_id

    # 1) Campos vinculados ao departamento sem categoria definida
    result = api_get("/custom_field/department/list", {"department_id": department_id})
    if result.get("error"):
        print("  aviso (sem categoria):", result.get("message"))
    else:
        merge_fields(result)

    # 2) Campos vinculados a cada categoria do departamento
    categories = list_categories(department_id)
    print(f"  {len(categories)} categorias encontradas no departamento.")
    for cat in categories:
        cat_id = cat.get("id")
        result = api_get("/custom_field/department/list",
                          {"department_id": department_id, "category_id": cat_id})
        if not result.get("error"):
            merge_fields(result)

    if not name_to_id:
        print("  aviso: nenhum campo encontrado em nenhuma categoria.")

    return name_to_id


def _normalize(s):
    import unicodedata
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode("ascii")
    return s.lower().strip()


def find_department_id(name_filter):
    """Busca o ID do departamento cujo nome contém `name_filter` (ex: 'Informática').
    Tenta também variações sem acento e palavras-chave alternativas comuns
    (TI, Tecnologia, Suporte) caso o nome exato não seja encontrado."""
    result = api_get("/department/list")
    if result.get("error"):
        print("Aviso: não foi possível listar departamentos:", result.get("message"))
        return None

    items = result.get("data") or []
    candidates = [name_filter, "tecnologia", "informatica", "ti", "suporte"]

    for candidate in candidates:
        norm_candidate = _normalize(candidate)
        for item in items:
            name = item.get("name") or ""
            norm_name = _normalize(name)
            if len(norm_candidate) <= 2:
                # candidato curto (ex: "ti") -> exige palavra inteira, não substring
                words = norm_name.replace("-", " ").split()
                match = norm_candidate in words
            else:
                match = norm_candidate in norm_name
            if match:
                print(f"  departamento encontrado: '{name}' (id={item.get('id')})")
                return item.get("id")

    print(f"  aviso: nenhum departamento parecido com '{name_filter}' foi encontrado.")
    print("  departamentos disponíveis:", [item.get("name") for item in items])
    return None


def extract_custom_value(ticket_detail, field_name, name_to_id):
    """
    Procura o valor de um campo personalizado dentro do detalhe de um chamado.
    Tenta casar por nome diretamente, e por id como plano B.
    """
    custom_values = (
        ticket_detail.get("custom_fields")
        or ticket_detail.get("custom_field")
        or []
    )
    target_id = name_to_id.get(field_name)

    for cf in custom_values:
        cf_name = cf.get("name") or cf.get("title") or cf.get("label")
        cf_id = cf.get("id") or cf.get("custom_field_id")
        cf_value = cf.get("value")
        if cf_value in (None, "", []):
            continue
        if cf_name == field_name or (target_id and cf_id == target_id):
            if isinstance(cf_value, list):
                return cf_value[0] if cf_value else None
            return cf_value
    return None


# ============================================================
# 2) LISTAGEM DE CHAMADOS (paginado)
# ============================================================

def fetch_all_tickets(department_id=None):
    all_tickets = []
    page = 1
    while True:
        params = {"page": page, "column": "protocol", "order": "ASC"}
        if CREATION_DATE_GE:
            params["creation_date_ge"] = CREATION_DATE_GE
        if department_id:
            params["department_id"] = department_id

        result = api_get("/ticket/list", params)
        if result.get("error"):
            print("ERRO ao listar chamados:", result.get("message"), file=sys.stderr)
            sys.exit(1)

        batch = result.get("data", [])
        all_tickets.extend(batch)
        print(f"  página {page}/{result.get('pages', '?')} — {len(batch)} chamados "
              f"(total acumulado: {len(all_tickets)})")

        next_page = result.get("next_page")
        if not next_page:
            break
        page = next_page

    return all_tickets


def fetch_ticket_detail(ticket_id):
    result = api_get("/ticket/detail", {"ticket_id": ticket_id})
    if result.get("error"):
        print(f"  aviso: erro ao buscar detalhe do chamado {ticket_id}: {result.get('message')}")
        return None
    return result.get("data", result)


# ============================================================
# 3) TRANSFORMAÇÃO PARA O FORMATO DO PAINEL
# ============================================================

def cat_short(name):
    if not name:
        return "Não informado"
    if ". " in name:
        return name.split(". ", 1)[-1]
    if " - " in name:
        return name.split(" - ", 1)[-1]
    return name


def norm_internet(v):
    if not v:
        return None
    v = str(v).strip()
    low = v.lower()
    if low in ("ótima", "otima"):
        return "Ótima"
    if low == "boa":
        return "Boa"
    if low == "bom":
        return "Bom"
    if low == "ruim":
        return "Ruim"
    return v


def to_record(ticket, detail, name_to_id):
    sla = ticket.get("sla", {}) or {}
    sla_deadline = sla.get("deadline", {}) or {}
    sla_startup = sla.get("startup", {}) or {}

    creation_date = ticket.get("creation_date")  # "YYYY-MM-DD HH:MM:SS"
    end_date = ticket.get("end_date")
    deadline_date = sla_deadline.get("date")

    finalizado = bool(end_date)

    elapsed = ticket.get("elapsed_time")
    res_h = round(elapsed / 3600, 2) if (finalizado and elapsed) else None

    atrasado = False
    if not finalizado and deadline_date:
        try:
            dl = datetime.strptime(deadline_date[:19], "%Y-%m-%d %H:%M:%S")
            atrasado = dl < datetime.now()
        except ValueError:
            pass

    priority_code = ticket.get("priority")
    pri = PRIORITY_MAP.get(priority_code, "Não informado")

    customer = ticket.get("customer", {}) or {}
    category = ticket.get("category", {}) or {}
    situation = ticket.get("situation", {}) or {}
    evaluation = ticket.get("evaluation", {}) or {}

    mes = creation_date[:7] if creation_date else None  # "YYYY-MM"

    erp = equip = app = net = problema = emp = None
    if detail:
        emp = extract_custom_value(detail, CUSTOM_FIELD_NAMES["emp"], name_to_id)
        erp = extract_custom_value(detail, CUSTOM_FIELD_NAMES["erp"], name_to_id)
        equip = extract_custom_value(detail, CUSTOM_FIELD_NAMES["equip"], name_to_id)
        app = extract_custom_value(detail, CUSTOM_FIELD_NAMES["app"], name_to_id)
        net = norm_internet(extract_custom_value(detail, CUSTOM_FIELD_NAMES["net"], name_to_id))
        problema = extract_custom_value(detail, CUSTOM_FIELD_NAMES["problema"], name_to_id)

    if erp and erp.strip().lower() == "easycarros":
        erp = "EasyCarros"

    grade = evaluation.get("grade")
    op = GRADE_TO_OPINIAO.get(grade) if grade else None

    return {
        "id": str(ticket.get("protocol") or ticket.get("id")),
        "assunto": ticket.get("subject"),
        "emp": emp or "Não informado",
        "cat": cat_short(category.get("name")),
        "pri": pri,
        "mes": mes,
        "fin": finalizado,
        "atr": atrasado,
        "slaD": "Sim" if sla_deadline.get("accomplished") else ("Não" if sla_deadline else "Não possui"),
        "slaI": "Sim" if sla_startup.get("accomplished") else ("Não" if sla_startup else "Não possui"),
        "res_h": res_h,
        "op": op,
        "erp": erp,
        "equip": equip,
        "app": app,
        "net": net,
        "cliente": customer.get("name") or "Não informado",
        "situacao": situation.get("description"),
        "problema": problema,
        "criado": creation_date.replace(" ", "T") if creation_date else None,
        "finalizadoEm": end_date.replace(" ", "T") if end_date else None,
        "deadline": deadline_date.replace(" ", "T") if deadline_date else None,
    }


# ============================================================
# MAIN
# ============================================================

def main():
    print("Tom Ticket -> Painel de TI - sincronizacao")
    print("=" * 50)

    print(f"\n[1/5] Localizando departamento '{DEPARTMENT_NAME}'...")
    department_id = find_department_id(DEPARTMENT_NAME)
    if not department_id:
        print("  ATENÇÃO: seguindo sem filtro de departamento (vai trazer TODOS os chamados da conta).")

    print("\n[2/5] Carregando campos personalizados do departamento...")
    name_to_id = load_custom_field_ids(department_id)
    print(f"  {len(name_to_id)} campos personalizados encontrados.")

    print("\n[3/5] Listando chamados (paginado, 50 por pagina)...")
    tickets = fetch_all_tickets(department_id)
    print(f"  Total de chamados: {len(tickets)}")

    print("\n[4/5] Buscando detalhe de cada chamado (campos personalizados)...")
    records = []
    for i, ticket in enumerate(tickets, 1):
        detail = fetch_ticket_detail(ticket.get("id"))
        if DEBUG_FIRST_TICKET and i == 1:
            print("\n----- DEBUG: retorno bruto do primeiro chamado -----")
            print(json.dumps(detail, ensure_ascii=False, indent=2)[:3000])
            print("----- FIM DEBUG -----\n")
        records.append(to_record(ticket, detail, name_to_id))
        if i % 50 == 0 or i == len(tickets):
            print(f"  {i}/{len(tickets)} processados")

    print(f"\n[5/5] Salvando {OUTPUT_FILE}...")
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False)

    print("\nConcluido com sucesso!")
    print(f"  Total de registros: {len(records)}")


if __name__ == "__main__":
    main()
