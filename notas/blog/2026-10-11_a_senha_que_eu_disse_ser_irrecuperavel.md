# A senha que eu disse ser irrecuperável

Há poucos dias eu escrevi, em nota de memória e na documentação, que a senha de
ativação do **SP7001** — o "SD PLUG-iN" que a KEY SOFT SERVICE vendia para o
KN7000 — **não era recuperável**: um desafio/resposta genuíno, serviço extinto,
sem senha em claro em lugar nenhum da RAM. Estava errado. O algoritmo foi
revertido de ponta a ponta e uma senha **de verdade** foi recuperada e confirmada
pelo próprio firmware.

Para o número de série determinístico do emulador, `gpcm_uwp5_namw_lud5`, a chave é:

> **`a19a-1s1d-jrdc-n1b2`**

Confirmada: injetada no comparador, ela faz tanto a verificação da senha quanto o
"apply" da ativação retornarem *aceito* (`d0=1`). Não é um bypass — é uma senha que
o aparelho aceita.

## O que a máquina faz de fato

A senha são 16 caracteres num alfabeto base-35 — os dígitos `1`–`9` e as letras
`a`–`z`, sem `0` — mostrados como quatro grupos de quatro (`XXXX-XXXX-XXXX-XXXX`).
O núcleo (`0x483ef234`) é uma substituição por caractere:

```
out_i = enc( ( (dec(in_i) - i) & 0x1f ) XOR dec(chave_i) )
```

A chave de cada posição `i` é simplesmente o `i`-ésimo caractere de um registro de
keystream de 20 caracteres, escolhido pelo primeiro caractere da senha. São 26
registros **estáticos no ROM** a partir de `0x483f8b74` (passo `0x15`), e eles se
encavalam: os 4 últimos de um registro são os 4 primeiros do anterior — um único
keystream mestre fatiado. A transformação roda **duas vezes** (registro `c0`,
depois `c0+1`). O comparador (`0x483ef0af`) não confere os 16 caracteres: só a
janela `[1:12]` — 3 caracteres contra a constante `mr7` (no ROM) e 8 contra um
valor derivado do número de série. Como a substituição é reversível e a chave é
constante de ROM, recuperar uma senha é **inverter** a transformação do alvo.

## Os meus erros, de novo em público

Esta investigação só andou depois de eu derrubar coisas que eu mesmo tinha afirmado:

- **"A senha é irrecuperável."** Falso. Era desafio/resposta, sim, mas com chave
  estática e transformação reversível — exatamente o tipo que se inverte.
- **`fl67hjva6mm9a`** — um candidato que eu tinha anotado antes. Era lixo de pilha,
  nunca o valor esperado. Retratado na documentação e na memória.
- **O modelo de "feedback encadeado".** Eu havia descrito a chave de cada posição
  como realimentada da anterior. Errado: a chave é `record[i]`, e cada caractere se
  transforma **independentemente**. O rastreamento ao vivo mostrou a chave da
  posição 1 sendo o caractere 1 do registro, não a saída anterior.
- **Vtable que não era vtable — duas vezes.** Ler `*(subobj+0x344)` em repouso
  devolvia o texto `C:\` (dados de caminho), não um ponteiro de método. A análise
  estática de vtables C++ deste framework mente fora do instante certo de runtime;
  os ponteiros só resolvem durante a chamada.

A lição que fica: desassemblar o verificador estaticamente me enganou repetidamente;
o que decidiu foi **capturar os operandos ao vivo** no comparador e inverter sobre
dados reais.

## A corroboração que caiu no colo

A KEY SOFT SERVICE fechou e **publicou o próprio gerador** em `keysoftservice.ch`.
O artefato é um executável Windows, `KeyGenerator.exe` — não JavaScript —, operado
com a senha-mestra **`soerenberg`**, um **LiberationKeyLength de 16** e o "Software
Code" do aparelho, devolvendo a "Liberation Key". Esse **16** bate exatamente com o
comprimento da chave que reconstruí. A ferramenta deles é o lado que *gera*; minha
engenharia reversa é o lado que *verifica/inverte* — o mesmo esquema, encontrado
pelas duas pontas. E `soerenberg` **não** está em nenhum lugar do firmware do
KN7000: o verificador não guarda segredo, só recomputa o alvo do série e compara.

## O que ainda não fechou

Falta um elo para um keygen totalmente geral (série → senha, como o deles): o passo
que transforma o número de série impresso na entrada do hash de `field8`
(`method_0x340`) é uma chamada virtual C++ por um ponteiro em RAM
(`0x50299298`) — o tal muro de vtable. O hash em si (`0x483ef275`) está decodificado;
o passo que falta se captura com um rastreamento em runtime. Hoje o gerador resolve
a senha a partir do alvo `field8`, e para o série do emulador esse alvo é conhecido
(`hmd2r6w2`).

Há um **gerador de chaves em JavaScript embutido na página de documentação** do
SP7001, que roda no navegador e é um port fiel do `invert.py` (validado contra o
rastreamento e contra a chave confirmada). Quem só quer destravar o plug-in no
emulador tem também o `unlock_plugin.lua`, que aceita qualquer senha — mas o keygen
existe porque recupera uma senha *legítima*, provando o algoritmo.

Tudo em `research-scratch/kn7000-sp7001-activation/` (ALGORITHM.md, invert.py,
keygen.js, trace_activation.lua, inject_verify.lua, param1_hash.py).
