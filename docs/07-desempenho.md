# 07 — Desempenho do calculador: onde está o tempo

> Medição de **19/09/2026**, antes de qualquer otimização. Nada foi mudado: o
> pedido era mostrar onde o tempo está, e a arquitetura de calcular no servidor
> só se reconsidera se a medição provar que é ela o gargalo. **Não provou** —
> ela responde por menos de 2% do tempo.

## O número que importa

```
GET /api/v1/crafting/calculator?family=LEATHER&quantity=100
  2123 ms · 46 KB
  2380 ms · 46 KB
  1976 ms · 46 KB
```

Cerca de **2 segundos, e são do servidor.** O cliente recebe 46 KB — nada que
justifique tempo de render perceptível.

## Onde estão os 2 segundos

Cronometrando cada etapa de `build_calculator` separadamente:

| ms | Etapa |
|---:|---|
| 66 | itens da família (27 linhas) |
| **1526** | **`list_recipes(tracked_only=False, limit=50_000)` — 12.917 receitas** |
| 6 | `load_items` (250 itens) |
| 0 | sobreposição de preço manual |
| 23 | `search_prices` (312 linhas) |
| 8 | `load_material_sourcing` (229 materiais) |
| 9 | liquidez |
| **1638** | **total** |

**93% do tempo é uma linha.** O serviço carrega a tabela **inteira** de
receitas, com os materiais de cada uma por `selectinload`, e depois joga fora
tudo menos as ~54 que pertencem à família pedida:

```python
todas = await recipes_repo.list_recipes(session, tracked_only=False, limit=50_000)
receitas: dict[int, list] = {}
for receita in todas:
    receitas.setdefault(receita.output_item_id, []).append(receita)
```

`list_recipes` filtra por `output_unique_name` (um item), por `station_category`
e por `tier` — nenhum desses serve para "as 27 saídas desta família". O caminho
mais curto é um filtro novo por lista de `output_item_id`, que o serviço já tem
em mãos antes da chamada.

A diferença entre os 1.638 ms medidos por etapa e os ~2.100 ms da requisição
inteira é a serialização dos 46 KB pelo Pydantic e o overhead de HTTP.

## As suspeitas, uma a uma

### Requisição por tecla — **não acontece**

`PriceInput` grava em `onBlur` e em `Enter`, nunca em `onChange`:

```tsx
onChange={(e) => setRascunho(e.target.value)}
onBlur={gravar}
onKeyDown={(e) => { if (e.key === "Enter") e.currentTarget.blur(); ... }}
```

Digitar `230000` dispara **zero** requisições; sair do campo dispara duas — o
`PUT` do preço manual e o `router.refresh()`. Um debounce de 300 ms não teria o
que atrasar. A suspeita era razoável e o código já a tinha resolvido.

### Recalcular tudo para uma célula — **acontece, e é o segundo maior custo**

`router.refresh()` refaz a página inteira: as 27 linhas, com o
`list_recipes` completo de novo. Então **cada edição de preço custa os mesmos 2
segundos**.

Mas o custo não está em recalcular 27 linhas — a aritmética das 27 é
irrelevante perto de 1.526 ms de I/O. Responder só a linha afetada seria
otimizar a parte barata e manter a cara. **Consertar o `list_recipes` resolve os
dois casos de uma vez**, e sem mexer na arquitetura de ida ao servidor.

### N+1 de preço — **não existe**

O cuidado da fase 4 foi repetido. Três consultas, uma por conjunto, nenhuma por
item:

- `search_prices(location_slugs=[sell_location], limit=50_000)` → 312 linhas, 23 ms;
- `load_material_sourcing(item_unique_names=[...229])` → 8 ms;
- `liquidity_by_item_location(ids)` → 9 ms.

Somadas, 40 ms: **2% do tempo**.

### Ícones — **já estão certos**

108 imagens (27 linhas × item + até 3 materiais). `ItemIcon` já usa
`loading="lazy"` e `decoding="async"`, e a URL é derivada do `unique_name`, o
que a torna estável entre renders.

O CDN responde `cache-control: no-transform, max-age=86400` — 24 h de cache no
navegador. A primeira visita paga ~500 ms por ícone, em paralelo e só pelos
visíveis; as seguintes não pagam nada.

E o `router.refresh()` **não** remonta os `<img>`: as chaves de linha
(`key={linha.item}`) e de material (`key={papel}`) são estáveis, então o React
reconcilia em vez de recriar, e o `src` não muda. Nenhuma busca refeita.

### Render do React — **não é o gargalo**

Com 46 KB de payload e 27 linhas, o custo de render é ordens de grandeza menor
que os 2 s do servidor. `memo` por linha otimizaria algo que não é o problema.
Depois de o servidor cair para a casa das dezenas de milissegundos, vale medir
de novo — aí sim com a aba Performance, que é a única parte desta lista que eu
não consigo instrumentar daqui.

## Adendo de 19/09/2026 — o intervalo de preço não custou nada

A fase 27 passou a carregar as cotações de **todas** as cidades mesmo no modo
CIDADE_UNICA, para poder mostrar o intervalo de preço por material. O comentário
que justificava consultar só a base dizia que "o modo padrão não pode ficar mais
caro em banco por causa de um recurso que ele não usa" — e a premissa deixou de
valer, porque agora ele usa.

Medido: `load_material_sourcing` leva **14 ms** para 50 materiais em sete
cidades, e calcular o intervalo de todos leva **1 ms**. A requisição inteira
continua em ~2.100 ms, inalterada — o gargalo segue sendo o `list_recipes`.

O que cresceu foi o corpo da resposta, de 46 KB para 108 KB, por causa da lista
de cidades por material. Vale o preço: é a informação que responde "vale a
viagem?", e 108 KB não é tempo de render perceptível.

## Adendo de 19/09/2026 — `/focus` estoura o tempo limite, e o gargalo mudou de lugar

> Medição a pedido, **antes** de qualquer mudança. Nada foi otimizado.

### O erro intermitente é real, e foi reproduzido

A tela `/focus` chama a rota com `limit=40` e o conjunto completo de parâmetros
de preferência. Oito execuções dessa chamada exata:

```
4596  4772  4998  5058  5078  5321  6150  10547   ms
mediana 5068 · máximo 10547
```

**Uma em oito passou dos 10.000 ms** e seria cancelada pelo
`AbortSignal.timeout` do frontend — aparecendo como "a API não respondeu", sem
nada anormal no log do backend.

Isso corrige uma medição anterior minha, feita com `limit=3` e sem parâmetros,
que deu 2,8–3,3 s e subestimou o risco. **O `limit` real é 40, e os parâmetros
de preferência mudam o tempo**: com a taxa da estação preenchida mais linhas
ficam calculáveis, e mais trabalho acontece depois.

### Onde está o tempo

`/focus` chama duas rotas pesadas em sequência:

| ms | Etapa |
|---:|---|
| 463 | `find_crafting_opportunities(limit=200)` |
| **3739** | **`find_refining_opportunities(limit=200)`** |
| 4202 | soma |

**O refino é 89% do tempo.** Perfilando dentro dele (cProfile, tempo cumulativo
— o profiler infla o absoluto, o que vale é a proporção):

| Chamadas | cumulativo | Função |
|---:|---:|---|
| **51.407** | 3,39 s | `chain.resolve_unit_cost` |
| 42.514 | 3,36 s | `chain._avaliar` |
| **51.292** | 2,23 s | `refining_service.receitas_de` |
| **43.900** | 1,47 s | `specialization_service.focus_cost_of` |
| 43.900 | 0,96 s | └ `specialization_service.profile_of` |
| 59 | 2,30 s | `recipes_repo.list_recipes` |

### O que isso muda em relação ao diagnóstico anterior

Este documento dizia que o gargalo era `list_recipes` lendo 12.917 receitas. Isso
continua verdade **para o calculador**. Para `/focus` não é a mesma história:

- A recursão da cadeia resolve **51 mil vezes** para 200 oportunidades — cerca
  de 250 resoluções por oportunidade. A cadeia T2→T8 compartilha subárvores (o
  T6 é insumo do T7 e do T8), e aparentemente cada caminho as recalcula.
- `profile_of` é reconstruído **43.900 vezes**. É trabalho de CPU puro,
  determinístico, sobre os mesmos níveis de especialização.
- `list_recipes` aparece com 59 chamadas, e a diferença entre os dois modos é
  grande: `tracked_only=False` custa **1131 ms** para 12.917 receitas;
  `tracked_only=True` custa **30 ms** para 435. Trinta e oito vezes.

Nenhuma dessas três é conserto de uma linha, e nenhuma foi feita. A medição
existe para a decisão ser tomada com os números na mesa.

### O paliativo que **não** foi aplicado

Subir o `AbortSignal.timeout(10_000)` faria o erro intermitente sumir sem
consertar nada — e trocaria "às vezes falha" por "sempre lento", que é pior de
diagnosticar. Fica registrado como opção consciente, não como esquecimento.

## Adendo de 19/09/2026 — o ataque ao gargalo de `/focus`

Duas mudanças, medidas **separadamente**, como pedido.

### Mudança 1 — memoizar `resolve_unit_cost`

Cache por requisição, chave `(unique_name, sourcing, return_rate)`.

| | antes | depois |
|---|---:|---:|
| `find_refining_opportunities(200)` | 3739 ms | **~1900 ms** |
| `/focus` em processo | — | **1999 ms** |

`resolve_unit_cost`, `_avaliar`, `receitas_de` e `focus_cost_of` **saíram do
topo do perfil** — não aparecem mais entre as trinta funções mais caras.

**Um bug que o cache introduziu, e o teste pegou.** A primeira versão escolhia
o cache com `preco is compras.base_price_of`, e isso é **sempre falso**: em
Python cada acesso a um método ligado cria um objeto novo, então `a.m is a.m`
dá `False`. O roteiro alternativo passou a ler o cache do principal e a
devolver o custo da cidade errada.
`test_refino_tambem_escolhe_a_cidade_de_cada_elo` falhou na hora. O cache agora
vem por parâmetro, não deduzido.

### Mudança 2 — memoizar `profile_of`

**Rendeu zero.** Medido com e sem, intercalado para a deriva de carga atingir
os dois igualmente, seis amostras cada:

```
com memo:  mediana 1794 ms   1586 1647 1763 1826 1846 2965
sem memo:  mediana 1765 ms   1606 1611 1693 1836 2029 3160
```

A razão é que as 43.900 chamadas **vinham de dentro da recursão da cadeia**.
A mudança 1 já as eliminou, e não sobrou o que memoizar. O código ficou, como
seguro barato e documentado como ganho **não** medido — mas a lição é a da
ordem: quando duas otimizações atacam o mesmo caminho, a segunda pode já estar
paga pela primeira, e só a medição separada mostra isso.

### O resultado na chamada real da tela

`/focus` com `limit=40` e o conjunto completo de preferências, por HTTP, dez
execuções:

```
2977  3157  3163  3312  3327  3369  3374  3708  3853  3927
mediana 3348 · máximo 3927
```

| | antes | depois | ganho |
|---|---:|---:|---:|
| mediana | 5068 ms | 3348 ms | 34% |
| máximo | 10547 ms | 3927 ms | **63%** |

**O erro intermitente acabou**: o pior caso saiu de 547 ms *acima* do teto de
10 s para 6 s de folga.

### E parou aqui, de propósito

A meta combinada era ficar **abaixo de 2 s**, e a mediana por HTTP é 3348 ms.
Nenhuma mudança estrutural foi feita — nada de cache entre requisições nem
desnormalização. O que sobra no perfil é `list_recipes`, com 58 chamadas e 1,4 s
cumulativos, e a diferença entre os modos continua enorme:
`tracked_only=False` custa 1131 ms para 12.917 receitas contra 30 ms para as
435 rastreadas.

## Conclusão

A escolha de calcular no servidor **não** é o gargalo e não precisa ser
revisitada. O gargalo é uma consulta que lê 12.917 linhas para usar 54, e ela
tem conserto local, dentro de `recipes_repo`, sem tocar em nenhuma fronteira do
sistema.

Ordem sugerida:

1. **Filtrar `list_recipes` por `output_item_id`.** Sozinho, deve derrubar os
   ~2.100 ms para a casa dos 150 ms. É a única mudança necessária para o
   sintoma relatado.
2. Medir de novo, no navegador, o que sobrar.
3. Só então considerar `memo` por linha ou resposta parcial — e só se a medição
   nova apontar para lá.
