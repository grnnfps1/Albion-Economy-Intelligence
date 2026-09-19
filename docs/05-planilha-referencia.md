# 05 — Planilha de referência (Albion VIP / Jovens Pensante v5.1): mapa de lacunas

> Analisado em **19/09/2026** contra
> `Wemas - Refino e Ilha 📋 Jovens Pensante v5.1📋 .xlsx` (13 MB, 15 abas).
>
> **Nada aqui foi implementado.** Este documento é um mapa para decidir ordem de
> trabalho, não um plano aprovado.
>
> O arquivo **não está no repositório** — ele vive fora, em
> `docs/referencia/` de um checkout local. Se for virar referência permanente,
> precisa de uma decisão sobre versionar 13 MB de binário.

## Como ler este documento

**As fórmulas se perderam na exportação.** É uma planilha do Google Sheets com
funções customizadas, e o `.xlsx` guardou só o resultado. Restaram fragmentos em
cabeçalhos e células de anotação — três deles foram úteis e estão citados
literalmente onde aparecem.

Tudo o mais é **inferência a partir dos números**, e inferência não é fonte. A
convenção deste documento:

- **Confirmado** — a conta fecha em várias linhas independentes, e digo quantas.
- **Indício** — bate em algumas linhas, mas não tenho amostra ou não tenho a
  fórmula.
- **Não fechou** — testei e não explica os valores. Fica registrado como não
  fechou, sem fórmula inventada para salvar a hipótese.

**Sobre copiar números:** nenhum valor desta planilha foi para
`config_parameters`, e vários são claramente de uma sessão específica — a taxa
da loja de 184, os preços por cidade, os níveis de spec do dono do arquivo. A
seção final lista o que é candidato a constante e o que não é.

---

## Achado principal: a fórmula da taxa de estação **fecha** aqui

Isto revisa a conclusão de `docs/04-taxas.md` §11, que dizia que a fórmula tinha
fonte oficial mas não reproduzia o observado.

**Ela reproduz.** O que não reproduzia eram os três resíduos que chegaram no
briefing (5,17 / 29,98 / 2.496,79) — e eles **não correspondem à coluna de taxa
de estação da planilha**. A planilha tem a taxa numa coluna própria, e ela bate.

### Confirmação 1 — `BD_Itens_Craft`, coluna "Taxa Loja"

Um coeficiente por item. Dividido pelo `@itemvalue` do dump:

| Item | Taxa Loja | `@itemvalue` | Taxa Loja ÷ iv × 100 |
|---|---|---|---|
| `T3_LEATHER` | 0,008958333 | 8 | **0,11198** |
| `T4_LEATHER` | 0,018020833 | 16 | **0,11263** |
| `T4_LEATHER_LEVEL2@2` | 0,071979167 | 64 | **0,11247** |
| `T6_LEATHER_LEVEL4@4` | 1,151724138 | 1024 | **0,11247** |
| `T8_LEATHER_LEVEL2@2` | 1,151979167 | 1024 | **0,11250** |

**23 de 24 linhas dão 0,1125** (±0,0005). A coluna é literalmente
`item_value × 0,1125 ÷ 100` — a nutrição por craft, dividida por 100 para
multiplicar pela prata por 100 de nutrição.

### Confirmação 2 — `Crafters`, coluna "Taxa da Loja", contra o próprio config

A planilha declara `Taxa da Loja = 184` no seu bloco de configuração
(`Crafters` L16) e no `Menu`. Invertendo a fórmula sobre a coluna de taxa, com a
produção diária de 139 unidades:

```
F = taxa × 100 ÷ (item_value × 0,1125 × 139)
```

| Tier | Taxa da Loja | `@itemvalue` | F implicado |
|---|---|---|---|
| T4.0 | 460,901 | 16 | 184,21 |
| T5.0 | 921,802 | 32 | 184,21 |
| T6.3 | 14.732,842 | 512 | 184,01 |
| T7.4 | 58.912,993 | 2048 | 183,96 |
| T8.4 | 117.855,384 | 4096 | **184,00** |

**26 de 27 linhas caem entre 183,9 e 184,3**, contra os **184** declarados. A
dispersão de ±0,2% é esperada: 139 é a produção do item final, e o número de
execuções em cada tier varia um pouco com o retorno.

### A linha que não fechou

`T5.4` (Couro Curtido Lendário) destoa nas **duas** conferências — F implicado
de 147,24 em vez de 184, e razão de 0,0900 em vez de 0,1125. A mesma linha, o
mesmo desvio proporcional, nas duas abas. É consistente com **uma célula
errada na planilha**, não com a fórmula. Registro sem explicar.

### O que isso significa para nós

1. `docs/04-taxas.md` §11 deve ser revisto: a fórmula tem fonte oficial **e**
   uma validação independente de 49 linhas em duas abas.
2. A medição no jogo continua valendo — ela é a única que fecha a questão sem
   depender de uma planilha de terceiro —, mas **deixa de ser urgente**.
3. Os três resíduos do briefing 1 continuam sem explicação. Eles não são a
   coluna de taxa de estação; são outra coisa que foi reconstruída. Não vale
   perseguir sem saber de que coluna saíram.

---

## As 15 abas

Legenda de custo: **campo** = acrescentar coluna/parâmetro · **motor** = mudança
em `calculations/` ou `services/` · **tela** = rota nova no frontend ·
**fase** = migration + motor + tela.

| # | Aba | Dim. | O que é | Já temos? | Custo |
|---|---|---|---|---|---|
| 1 | **Info** | 1000×11 | Encanamento: licença, idioma, fuso, links de suporte, validade da assinatura | Não se aplica — é o negócio deles, não a ferramenta | — |
| 2 | **Crafters** | 23066×106 | **Funcionalidade**: a tela principal (view filtrada de `Layer`) + config + cache de preços | Parcial — `/crafting` e `/refining` | ver §Crafters |
| 3 | **-----** | 22×13 | Encanamento: aviso de despedida da versão anterior | — | — |
| 4 | **Manual_Price** | 9990×33 | Funcionalidade: preço manual por item × cidade × ordem de compra/venda, **e demanda diária manual** | **Sim**, fase 17 (`manual_prices`) — menos a demanda | campo |
| 5 | **Spec** | 558×113 | Dado de entrada: nível de especialização **item a item**, agrupado por árvore do Destiny Board | Parcial — fase 16 faz por família (5 campos) | ver §Spec |
| 6 | **Menu** | 40×33 | Dado de entrada: configuração global e por tipo de item | Parcial — `PreferencesForm` | ver §Menu |
| 7 | **Layer** | 2988×72 | **Encanamento**: o motor de cálculo; `Crafters` é um `FILTER()` sobre ele | Sim — é o nosso backend | — |
| 8 | **DB_Preço** | 635×102 | Encanamento: resolução de preço por item e por papel na receita | Sim — `services/sourcing.py` + overlay manual | — |
| 9 | **Tradução** | 1014×10 | Encanamento: i18n da própria planilha (rótulos de interface) | Não — somos PT-BR only | tela |
| 10 | **Dados Remoto** | 1000×7 | Encanamento: links para outras planilhas, status das fontes | Sim — `/status` | — |
| 11 | **Validação** | 1444×25 | Dado de referência: listas de dropdown (categorias PT/EN/ES, qualidades, cidades) e **tabela de taxas de retorno** | Parcial — nossa matriz tem 6 valores, a deles lista 0,152 / 0,21 / 0,248 / 0,30 / 0,435 | campo |
| 12 | **BD_Itens_Craft** | 602×42 | Dado de referência: banco de receitas (até **7** materiais), foco base, peso, produção, flags de retorno, ponteiros para `Spec` | Sim — `recipes` + `recipe_materials` | — |
| 13 | **Foco** | 53×16 | Dado de referência: **tabela de pontos de eficiência por tipo de peça** + agregação do spec | Parcial — fase 16 gravou a tabela | campo |
| 14 | **API_Volume** | 6636×7 | Encanamento: cache do histórico do AODP (`Valor Medio`, `Hora`, `Quant`) | **Sim** — `market_history` | — |
| 15 | **API_Preço** | 30790×8 | Encanamento: cache de `/prices` do AODP | **Sim** — `market_prices` | — |

**API_Volume fecha o briefing 4.** As colunas são `ID Name · City · Qualidade ·
Valor Medio · Hora · Quant`. É `avg_price` + `item_count` do endpoint de
histórico, exatamente o que `repositories/liquidity.py` já usa. Não há feed de
volume separado — era o mesmo dado, agregado diferente, como a investigação da
fase 15 já havia concluído contra a API.

---

## §Crafters — as 106 colunas

Primeiro a ressalva que muda a leitura: **106 colunas não são 106 grandezas.**
Contado no arquivo, no bloco de couro (L3–L31):

| | Colunas |
|---|---|
| Total | 106 |
| Com cabeçalho (L3 ou L4) | 54 |
| Com algum dado | 30 |
| **Carregam alguma coisa** | **61** |
| **Completamente vazias** | **45** |

E das 61, boa parte são slots repetidos: **8 pares** de preço por cidade
(preço + toggle) e **7 pares** de material (quantidade + nome). Descontando a
repetição, sobram cerca de **30 grandezas distintas** — que é a comparação
justa com as nossas.

Comparação honesta: a nossa tela de crafting, depois da fase 18, tem **12
colunas** (item, até 4 materiais, você gasta, você recebe, lucro ajustado,
prata/focus, focus, vender em, idade, giro).

### Identidade e preço

| Col | Rótulo | Temos? | Onde |
|---|---|---|---|
| D | `id_color` | ✅ | `tier` + faixa colorida |
| E | `Tier` (`T4.1`) | ✅ | `TierBadge` |
| F | `Nome do Item` | ✅ | `item_name` |
| G,I,K,… | toggle por cidade (`True/False`) | ❌ | **ligar/desligar cidade na consulta** |
| H | `Preço Venda` | ✅ | `sell_price` |
| J,L,N,P,R,T,V | `Preço de Compra` × 7 cidades | ⚠️ | temos o preço, mas **uma cidade por vez**; eles mostram as 7 lado a lado |

### Resultado

| Col | Rótulo | Temos? | Onde |
|---|---|---|---|
| Z | `Produção Diaria` | ❌ | **quanto dá para produzir por dia** |
| AA | `Demanda Diaria` | ⚠️ | temos `liquidity_units_per_day` (giro), eles têm demanda declarada |
| AB | `Custo de Produção` | ✅ | `material_cost_net` |
| AC | `Receita Bruta` | ✅ | `sale_revenue_net` |
| AD | `Lucro` | ✅ | `profit` |
| AE | `Lucro Por Dia` | ❌ | **lucro normalizado por dia** (temos só em `/farming`) |
| AF | `Margem de Lucro` | ✅ | `margin_pct` |
| AH | `Custo de Material` | ✅ | `material_cost_gross` |
| AI | `Taxa da Loja` | ✅ | `station_fee` (fase 15) |
| AJ | `Taxa De Compra` | ❌ | **setup fee da ordem de compra, como linha separada** |
| AK | `Taxa de Venda` | ✅ | `market_fees` |
| AL | `Diário Cheio` | ❌ | ligado ao sistema de diário/ilha |
| AM | `Selaria Com Foco` / `Açougue Com Foco` | ❌ | foco por **estação específica** |
| AN | `Foco Total` | ✅ | `focus_cost` |
| AO | `=custo de Foco*0,5^(spec/10000)` | ✅ | fase 16 — **e este cabeçalho é a fonte citável da fórmula** |

### Ilha, cultivo e criação — o bloco que não temos em craft

| Col | Rótulo | Temos? |
|---|---|---|
| AO | `Simulação de Produção Na ILHA` | ❌ **ilha não é modelada** |
| AP | `Tempo para Crescimento` | ⚠️ só em `/farming` |
| AQ | `Ciclo` | ⚠️ só em `/farming` |
| AR | `Retorno de Sementes` | ⚠️ só em `/farming` |
| AT | `Filhotes Utilizados` | ⚠️ só em `/farming` |
| AU | `Compra Total` | ❌ |
| AV–AX | `Venda de Filhotes`, `Venda Último Ciclo`, `Venda Total Filhote` | ❌ **vender o filhote em vez de criar** |
| AY | `Consumiu` | ⚠️ ração, só em `/farming` |
| BA | `Recurso para Selaria` | ❌ |

### Lista de compras

| Col | Rótulo | Temos? |
|---|---|---|
| BF | `Lista de Compra para à Fábrica` | ❌ |
| BG,BI,BK,BM,BO,BQ,BS | `UND para Compra` × 7 | ❌ **quantidade absoluta a comprar** |
| BH,BJ,BL,BN,BP,BR,BT | nome do material × 7 | ✅ (como célula, não como coluna) |
| BW | `Local Bonus` | ✅ | `material_return.best_city_name` |

**Sete slots de material** contra os nossos quatro. `BD_Itens_Craft` confirma:
`Quant_R1..R7` / `Recuso_1..R7`.

Conferido no nosso banco, e **não é hipotético** — a distribuição de materiais
por receita:

| Materiais | Receitas |
|---|---|
| 1 | 2.812 |
| 2 | 4.630 |
| 3 | 4.698 |
| 4 | 211 |
| **5** | **119** |
| **6** | **21** |
| **7** | **24** |

**164 receitas têm mais de quatro materiais**, e o máximo é exatamente 7 —
o mesmo limite da planilha. Exemplo real: `T7_POTION_ACID@1` usa sete.

A tabela de `/crafting` abre no máximo quatro colunas de material, então
**essas 164 receitas aparecem truncadas hoje**: os materiais do quinto em diante
somem da tela sem aviso. O custo continua certo — quem calcula é o backend, que
lê todos —, mas a linha mente sobre o que entra na receita. É lacuna nossa, não
da planilha, e é barata de fechar (subir o teto de `MAX_MATERIAIS` ou marcar o
excedente).

---

## §Layer e §Spec — o que são

### Layer = o motor

Estruturalmente **idêntica a `Crafters`**, coluna por coluna, mas com as
fórmulas quebradas (`#NAME?`) porque dependem das funções customizadas. A
resposta está numa célula de anotação (L63):

```
=FILTER(A3:BQ29; if(A1=3; D3:D29<>""; IF(A1=1; A3:A29; B3:B29)=Crafters!B8))
```

**`Crafters` é um `FILTER()` sobre `Layer`.** `Layer` contém as 28 linhas
calculadas (uma família de recurso × tier × encantamento) e `Crafters` mostra o
recorte que o usuário escolheu — `A1` decide o modo (3 = tudo, 1 = por tier,
senão por `id_color`).

"Layer" é a **camada de encantamento**: a coluna A é literalmente
`Encantamento`, com valores 0–4.

**Equivalente nosso:** é a separação `services/` (calcula tudo) → rota (filtra e
pagina). Já temos. Nenhuma lacuna.

### Spec = a entrada de especialização, item a item

558 linhas × 113 colunas, organizadas por **árvore do Destiny Board**:
`Árvore de Mago`, `Árvore do Caçador`, `Árvore do Guerreiro`, `Ferramentas`,
`Refino`, `Mestre Cuca`, `Herborista`, `Alquimista`, `Fazendeiro`.

Cada árvore ocupa uma faixa de ~5 colunas, e uma delas é o **nível que o usuário
digita**. Conferido: a coluna 38 traz `Couro Trabalhado = 23`,
`Couro Curtido = 20`, `Couro Endurecido = 10`, `Couro Reforçado = 0`,
`Couro Fortificado = 0` — e a aba `Foco` repete exatamente esses cinco números.

As colunas 87–111 são um **dicionário PT↔EN de nomes de item** (`Capote de
Erudito` ↔ `Scholar Cowl`).

**A lacuna:** nós pedimos **5 níveis** (um por família de recurso); eles pedem
**centenas** (um por item). A decisão da fase 16 — "comece simples, por família"
— continua defensável para refino, onde a linha inteira costuma ser
especializada junta. **Mas ela não cobre craft de equipamento**, onde spec é
item a item de verdade: quem especializou Capuz de Mercenário não especializou
Capuz de Caçador.

**Custo:** motor (já pronto — `SpecializationPolicy` aceita nível por chave) +
tela (uma página de spec com as árvores) + migration se virar preferência
salva.

---

## §Menu — configuração global, comparada com as nossas preferências

O `Menu` tem um bloco global e **sete blocos por tipo de item**
(`tipoItem == 2`, `>= 2 && <= …`, `== 9`, `== 10`, `== 12`, `== 13`, `== 14`),
cada um com a sua própria taxa de retorno, taxa de loja, foco e local.

| Parâmetro do Menu | Valor na sessão | Temos? |
|---|---|---|
| `Taxa de Retorno` | 0,367 | ✅ matriz de retorno (fase 14) |
| `Taxa da Loja` | 184 | ✅ `stationFeePer100Nutrition` (fase 15) |
| `Retorno Sem Foco` / `Com Foco` | 0,152 / 0,435 | ✅ células da matriz |
| `Usar Diário` | True | ❌ |
| `Conta Premio` | True | ✅ `premium` |
| `Taxa de Venda` | True | ✅ `salesTaxPct` |
| `Usar FOCO` | True | ✅ `useFocus` |
| `Preço Manual` | True | ✅ fase 17 |
| `Carregar API` | False | ⚠️ implícito — não dá para desligar a coleta pela interface |
| **`Local da Ilha`** | Caerleon | ❌ **ilha não existe no nosso modelo** |
| **`Dias na Ilha`** | 1 | ❌ |
| **`FOCO no SPOT`** | 10.000 / 5.000 | ⚠️ temos `focusBudget` único, eles têm **por estação** |
| **`FOCO na Selaria`** | 5.000 | ❌ |
| **`FOCO no Açougue`** | 5.000 | ❌ |

**A lacuna estrutural:** eles orçam Focus **por estação** (spot, selaria,
açougue) e por **dias de ilha**; nós temos um orçamento único. Quem joga a sério
divide o Focus entre estações, e o ranking muda com isso.

**O que nós temos e o Menu não:** perda por zona (azul / vermelha-preta), modo
de sourcing (`CIDADE_UNICA` / `MAIS_BARATO` / `COMPARAR`), bônus diário de
produção, limite de frescor.

---

## O que a planilha faz e nós não — por valor para quem joga

1. **Ilha / produção em base própria.** `Local da Ilha`, `Dias na Ilha`,
   `Simulação de Produção Na ILHA`, foco por estação. É o tema do título do
   arquivo ("Refino e **Ilha**") e atravessa `Menu`, `Crafters`, `Layer` e
   `BD_Itens_Craft`. **Não modelamos nada disso.** É a maior lacuna, e é uma
   fase inteira.
2. **Orçamento de Focus por estação**, não único. Muda o ranking de `/focus`,
   que hoje assume um bolso só. *Custo: campo + motor.*
3. **Produção diária e lucro por dia em craft e refino.** Nós normalizamos por
   dia só em `/farming`; eles normalizam em tudo. É o que torna comparável um
   refino rápido com uma criação de um mês. *Custo: campo + motor.*
4. **Spec item a item para equipamento.** Nossa granularidade por família cobre
   refino e não cobre craft. *Custo: tela + motor.*
5. **Lista de compras com quantidade absoluta.** "Compre 176 Pelego Médio e 88
   Couro Grosso" é acionável; "preço unitário 144" exige conta na cabeça.
   *Custo: campo.*
6. **As 7 cidades lado a lado**, com liga/desliga por cidade. Nós escolhemos uma
   cidade de compra e mostramos a alternativa; eles mostram a grade inteira.
   *Custo: tela.*
7. **Venda do filhote como alternativa a criá-lo.** `Venda de Filhotes`,
   `Venda Último Ciclo`. Em `/farming` só modelamos criar até o adulto.
   *Custo: motor.*
8. **Demanda diária manual**, ao lado do preço manual. *Custo: campo.*
9. **Até 7 materiais por receita**; nossa tabela mostra 4, e **164 receitas
   reais passam disso** — hoje elas aparecem truncadas. *Custo: campo.*
10. **i18n** (PT/EN/ES/Mandarim/Filipino). *Custo: tela.*

## O que nós fazemos e a planilha não

1. **Risco de rota.** `lucro × (1−p) − investimento × p`, com zona classificada
   pelas pontas. A planilha não tem nenhuma coluna de risco, perda ou zona —
   ela assume que a carga chega.
2. **Detecção de outlier com MAD**, e o ponto marcado em vez de apagado. A
   planilha usa `Valor Medio` cru do AODP, que é média e carrega o pico
   manipulado inteiro.
3. **Idade por campo de preço.** Cada ponta tem a sua data e o seu frescor.
   `DB_Preço` tem data por preço, mas nada consome isso como frescor — não há
   limite de idade nem alerta de dado velho.
4. **Score com confiança**, e a recusa de publicar score abaixo de 50% de
   confiança. A planilha não pontua oportunidades.
5. **Cadeia recursiva de refino** com as três políticas (`MERCADO`, `PRODUZIR`,
   `MAIS_BARATO`) resolvidas elo a elo, com corte de ciclo e limite de
   profundidade. A planilha resolve dois níveis fixos (`Recuso_1`, `Recuso_2`).
6. **`UNKNOWN` como estado de primeira classe.** Material sem cotação derruba o
   craft inteiro e diz por quê. A planilha propaga `0` e `#VALUE!`, e um zero
   silencioso vira lucro inflado.
7. **Liquidez com cobertura declarada** (`3/30d`), e `UNKNOWN` abaixo de 3
   buckets.
8. **Preço manual que envelhece.** O deles vence para sempre; o nosso expira no
   limite de frescor e a tela avisa.
9. **Procedência gravada** (`config_parameters.source`). A planilha tem números
   soltos sem dizer de onde vieram — que é exatamente o problema que este
   documento teve de resolver na marra.
10. **Multi-servidor** (west/east/europe). A planilha fixa um servidor no `Info`.

---

## Números que NÃO devem ir para `config_parameters` sem decisão

São da sessão de quem montou o arquivo, não do jogo:

- `Taxa da Loja = 184` — escolha da estação daquele jogador;
- `Taxa de Retorno = 0,367` — já temos, com procedência própria;
- todos os preços por cidade em `DB_Preço`, `Manual_Price`, `API_Preço`;
- `Produção Diaria = 139` — plano de produção daquele usuário;
- os níveis de spec em `Spec` e `Foco` (23, 20, 10, 100, 44, 31…) — são do dono
  do arquivo;
- `FOCO no SPOT = 10.000` — coincide com a geração diária de uma conta Premium,
  mas aqui é orçamento escolhido, não constante.

Candidatos legítimos a constante, **e já temos os dois**:

- `0,1125` de nutrição por item value — agora com validação independente;
- a tabela de pontos por tipo de peça em `Foco` (MAIN 250, OFF 250/90, BAG 310,
  CAPE 370, GATHERER 250/mastery 60, Refino 250, FOOD 250, POOT 250/18,
  BACKPACK 0/mastery2 250, TOOL 0/mastery2 250, TRACKING 60/250).

**Uma correção à fase 16:** eu expliquei BAG 310 e CAPE 370 como
`250 + irmãos × 30`. A aba `Foco` simplesmente **tabula** esses valores, em
colunas `primary · secondary · secondary artefato · mastery · mastery2`. Minha
explicação continua compatível com os números, mas é **inferência minha e não
está na planilha** — o comentário em `calculations/specialization.py` a
apresenta com mais confiança do que a fonte sustenta. Vale suavizar.

**Duas linhas novas** que a nossa tabela não tem: `TRACKING` (primary 60,
secondary 250 — invertido) e `POOT`/poção (secondary 18).

---

## Nota sobre o nome do arquivo

Já existe `docs/05-custo-de-focus.md`. Este documento usa o nome pedido
(`05-planilha-referencia.md`), então há dois `05`. Se incomodar, o número livre
é `06`.
