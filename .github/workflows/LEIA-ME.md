# Integração Tom Ticket → Painel de TI (atualização automática)

Este pacote conecta seu painel diretamente à API do Tom Ticket, para que ele se
atualize sozinho todo dia — sem precisar exportar Excel e me enviar de novo.

## ⚠️ Primeiro passo: proteja sua chave

Você compartilhou um print com a Chave de Acesso visível. Antes de configurar
tudo, eu recomendo gerar um **Token de Acesso novo** (botão "Criar Token" na
mesma tela), e usar esse token daqui pra frente — não a "Chave de Acesso"
antiga que apareceu no print.

## 📁 O que tem neste pacote

```
sync_tomticket.py       → busca os chamados na API e gera tickets.json
build_dashboard.py      → reconstrói o painel HTML com os dados novos
dashboard_template.html → o "molde" do painel (não precisa mexer)
wifi_survey.json        → dados da pesquisa de WiFi do hotel
vendor/                 → bibliotecas usadas pelo painel (Chart.js)
.github/workflows/
  sync-dashboard.yml    → a automação do GitHub Actions
```

## 🚀 Passo a passo para ativar a automação

### 1. Suba estes arquivos para o seu repositório

No repositório `indicadores-ti-kpi` (o mesmo que já tem o `index.html`),
adicione TODOS os arquivos deste pacote na raiz do repositório, mantendo a
pasta `.github/workflows/` exatamente como está.

> O `index.html` que já existe lá será **substituído automaticamente** pela
> automação a partir de agora — não precisa mais subir manualmente.

### 2. Cadastre o token como "Secret" no GitHub (local seguro)

1. No repositório, vá em **Settings → Secrets and variables → Actions**
2. Clique em **New repository secret**
3. Nome: `TOMTICKET_TOKEN`
4. Valor: cole o token gerado no passo anterior
5. **Add secret**

Isso garante que o token nunca aparece no código nem fica público.

### 3. Teste manualmente (sem esperar o agendamento)

1. Vá na aba **Actions** do repositório
2. Clique em **"Atualizar Painel de TI (Tom Ticket)"** na lista à esquerda
3. Clique em **Run workflow → Run workflow**
4. Acompanhe a execução — se tudo der certo, em 2-3 minutos o `index.html`
   é atualizado automaticamente com um novo commit

### 4. Pronto — a partir daqui roda sozinho

O workflow está agendado para rodar **todo dia às 06h** (horário de Brasília).
O link do GitHub Pages sempre vai mostrar os dados mais recentes.

## 🔧 Se algo não bater

Os campos "Qual empresa", "ERP", "Equipamento" etc. são campos personalizados
da sua conta. Eu montei a busca deles com base na documentação oficial da
API, mas não consegui testar contra a conta real (não tenho acesso à
internet externa). Se esses campos vierem vazios no painel:

1. Rode localmente: `DEBUG_FIRST_TICKET=1 TOMTICKET_TOKEN=seu_token python3 sync_tomticket.py`
2. Isso imprime o JSON bruto do primeiro chamado no terminal
3. Me envie esse JSON (pode apagar dados sensíveis de cliente) que eu ajusto
   o script para casar exatamente com o formato retornado pela sua conta

## 💡 Sobre a Pesquisa de WiFi

Essa aba não tem endpoint de API (é uma planilha separada). Por enquanto,
ela continua "congelada" com os dados que você já me enviou. Se quiser
automatizar isso também no futuro, dá pra criar um Google Form/Sheet
conectado, mas é um projeto à parte.
