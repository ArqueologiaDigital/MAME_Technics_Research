# O "sprite" que não era transparente

*O núcleo de desenho da interface do KN7000 — as dezenove rotinas que põem bitmaps,
ícones, molduras, JPEGs e texto na tela, 7.716 bytes de código — deixou de ser bytes
crus no desassemblado e virou uma listagem com nomes, rótulos e comentários, que
continua remontando a imagem byte a byte. No caminho caíram três coisas que o próprio
projeto afirmava, e apareceu um defeito no desassemblador do MAME.*

## De bytes a listagem

O desassemblado do KN7000 começa como um esqueleto: cada byte do firmware entra por
`.incbin_range`, e o trabalho é trocar esses blocos por instruções de verdade sem que a
imagem remontada mude um bit (`make verify` confere). Até ontem, o trecho de
`0x48423B56` a `0x4842597A` — `DrawBitmap` até `DrawStringCentered` — era só isso:
dezenove blocos opacos.

Agora cada rotina tem um cabeçalho que diz quais registradores recebe, o que faz, onde
não recorta e o que tem de estranho; cada desvio cai num rótulo com nome
(`DrawBitmapSP2_Impl_ZeroBit`, `GetJpegSize_SkipSegment`); cada chamada nomeia o alvo;
endereços de dados aparecem como `FrameBuffer`, `DrawEnable`, `BitmapTablePtr`. Os
comentários de fim de linha dizem o que um valor *significa* ("y >= 240: abaixo da
tela, para"), não repetem o mnemônico.

O desenho de todas elas é o mesmo do KN5000, e explica muita coisa. Quem chama
`DrawBitmap` fora da tarefa de desenho não desenha: copia os argumentos num registro,
cujo primeiro campo é o endereço de uma rotina de "repetição", e o põe numa fila; a
tarefa de desenho depois chama essa rotina com o registro. Os registros saem de uma
arena circular de 8 KB — por isso a função que "libera" um registro é um `retf` vazio:
a arena simplesmente passa por cima. E por isso os registros guardam *ponteiros* para
os pixels, paletas e arquivos, não cópias: quem pede o desenho precisa manter os dados
vivos até a tarefa de desenho rodar (só `DrawString` copia a sua string).

## O que estava errado

**"SP" não quer dizer transparente.** O site de documentação dizia que as variantes
"SP" (de *sprite*) respeitam o índice transparente `0xF7`, e listava `DrawBitmap` e
`DrawBitmapFast` como "genéricas". O código diz outra coisa: só `DrawBitmap`,
`DrawBitmapSP` e `DrawFrameSP` pulam o `0xF7`. `DrawBitmapSPFast`, `SPFast4`,
`SPFast16`, `SPFast256` e `SP2` são opacas — e `DrawBitmapFast` é a `DrawBitmap` com o
teste de transparência removido. A tabela da página foi refeita a partir do código.

**Nomes que não eram o que diziam.** `JpegHeaderParse` não era uma função: era a
entrada de `GetJpegSize` logo depois do prólogo, e o que ela faz é medir a imagem, não
analisar o cabeçalho. A tabela chamada `InitBlockTable` não tem 48 blocos de
inicialização, tem 32 — a partir do byte `0x80` ela vira a API de gráficos e objetos
(`UpdateScreen`, `DrawBitmap`, `DrawString`...). E um comentário antigo descrevia uma
chamada à biblioteca como "consulta de objeto (id 0x11)": é um `memcpy` de 0x11 bytes.

**O desassemblador do MAME imprimia registradores que não existem.** No meio do código
apareciam linhas como `mov d97, (0x494, sp)`. O MN10300 tem `d0` a `d3`. Em
`mn103dasm.cpp`, a família `FA 9x` (gravar um registrador na pilha com deslocamento de
16 bits) usa a string de formato `"d%d"` com três argumentos onde deveria ser `"%c%d"`:
imprime a *letra* do registrador como número (`'a'` = 97, `'d'` = 100) e descarta o
número dele. `d97` é `a0`. É um defeito de um caractere, bom candidato a correção no
MAME. O montador do projeto tinha o defeito simétrico: codificava essas mesmas
gravações com o byte errado (o resultado decodifica como gravação relativa a `a0` ou
`a1`, não à pilha). Nenhum fonte usava a forma, então nada do que foi construído até aqui saiu
errado — mas o primeiro programa novo que usasse sairia, em silêncio.

## Defeitos do próprio firmware

Ler cada linha com cuidado também achou defeitos no código da Technics, agora
anotados nos cabeçalhos:

- **Nenhum blitter de imagem recorta na horizontal.** Uma imagem mais larga que
  `640 - x` continua na linha seguinte do framebuffer; dos lados, só um canto superior
  esquerdo fora da tela impede o desenho (e o JPEG nem isso).
- **`DrawBitmapSPFast4` (2 bits por pixel) escreve um pixel a mais** em cada linha
  quando a largura não é múltipla de 4: o laço compara com `>` onde deveria ser `>=`.
- **`DrawString` mede texto proporcional pela largura do último caractere**, não pela
  soma — o mesmo erro do KN5000. A caixa de fundo sai do tamanho errado.
- **`DrawBitmapFileEx` nunca desenha.** Carrega a paleta do BMP, prepara cada linha e
  a descarta; o único efeito visível é a troca de cores. Pela leitura do código, não
  dá para saber se é uma função de "só carregar a paleta" ou uma cópia quebrada de
  `DrawBitmapFile`.
- **O "R" de `DrawJpegFileR` é de *rounded*:** antes de desenhar a foto, ela guarda 8
  pixels de cada canto e depois os devolve, e o fundo aparece nos cantos.

## Como foi feito

O montador ganhou rótulos que podem ser usados antes de definidos (ele repete a
passada até os endereços pararem de mudar) e passou a conferir que cada rótulo de
função cai no mesmo endereço que a tabela de símbolos diz. As anotações ficam num
arquivo à parte, indexado por endereço (`annotations/gfx_draw.ann`), que o gerador
mistura ao código; os bytes nunca dependem delas.

O texto foi escrito por oito agentes, um por grupo de rotinas, e cada grupo passou
depois por um revisor independente instruído a supor que estava tudo errado e
conferir cada frase contra as instruções e contra chamadas reais. Os revisores
fizeram 56 correções; todas, e as dúvidas que cada um deixou em aberto, estão em
`notes/gfx-draw-review.md`. A cobertura honesta do desassemblado — a fração da imagem
que é código-fonte de verdade, não bytes copiados — foi de 3,64% para 3,83% com a
conversão; rótulos e comentários não mudam esse número, e não deveriam.

## O que fica para o dono

- O defeito do `unidasm` merece um PR no MAME (é a string de formato em
  `disassemble_fa`, casos `0x10`–`0x13`).
- Ficaram perguntas que o código sozinho não responde: o que os pixels `0xF4` das
  molduras deveriam mostrar (eles copiam de um segundo plano de imagem); se o MN10300
  aceita a gravação de meia-palavra desalinhada que `DrawBitmapSP` faz em `x` ímpar;
  quais fontes têm tabela de kanji, e se todas têm 16 linhas de altura, como o
  desenho de caracteres de dois bytes supõe.

---

*Fontes:* `kn7000_disassembly` commits `38a334e` (gerador e montador), `ebf860e`
(conversão), `b5e198b` (rótulos e comentários), `notes/gfx-draw-review.md` (as 56
correções); `kn5000-docs` `71c109d` (a tabela corrigida). Cobertura:
`python3 tools/coverage_score.py` e `notes/coverage-history.tsv`. Para conferir que
não sobrou byte cru no trecho:

```
sed -n '/^# DrawBitmap  (CPU/,/^# DrawStringLeftJustify  (CPU/p' src/program.s \
    | grep -cE '\.incbin_range|^\s+\.byte|^\s+(b[a-z]{1,2}|bra|jmp|calls?) +0x'
```

imprime `0`.
