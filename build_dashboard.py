#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build_dashboard.py
===================
Reconstrói o arquivo Painel_TI_Grupo_Martins.html a partir de:
  - tickets.json       (gerado por sync_tomticket.py)
  - wifi_survey.json   (pesquisa de WiFi do hotel, atualizada manualmente
                         se vocês quiserem trazer essa aba também pela API)
  - dashboard_template.html (modelo do painel, com os placeholders
                              __DATA__, __WIFIDATA__ e __CHARTJS__)

Este script é chamado automaticamente pelo GitHub Actions
(.github/workflows/sync-dashboard.yml) toda vez que o sync_tomticket.py
roda e atualiza o tickets.json.
"""

import json
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

with open(os.path.join(BASE_DIR, "tickets.json"), encoding="utf-8") as f:
    tickets_raw = f.read()

wifi_path = os.path.join(BASE_DIR, "wifi_survey.json")
if os.path.exists(wifi_path):
    with open(wifi_path, encoding="utf-8") as f:
        wifi_raw = f.read()
else:
    wifi_raw = "[]"

with open(os.path.join(BASE_DIR, "chart.umd.js"), encoding="utf-8") as f:
    chartjs = f.read()
with open(os.path.join(BASE_DIR, "chartjs-plugin-datalabels.js"), encoding="utf-8") as f:
    datalabels_js = f.read()
chartjs_full = chartjs + "\n" + datalabels_js

with open(os.path.join(BASE_DIR, "dashboard_template.html"), encoding="utf-8") as f:
    template = f.read()

html = (template
        .replace("__DATA__", tickets_raw)
        .replace("__WIFIDATA__", wifi_raw)
        .replace("__CHARTJS__", chartjs_full))

output_path = os.path.join(BASE_DIR, "index.html")
with open(output_path, "w", encoding="utf-8") as f:
    f.write(html)

print(f"Painel reconstruído: {output_path} ({len(html)/1024:.1f} KB)")
