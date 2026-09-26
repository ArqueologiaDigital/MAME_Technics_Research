# A fonte que eu citei errado

*O databook apareceu e me deu razão. Três dos meus argumentos morreram no mesmo
dia — inclusive uma citação que eu atribuí a um manual da SNK e que era, na
verdade, um post de fórum repetindo a tabela da Toshiba que eu já estava citando.*

## A ponta solta

O texto anterior deste diretório terminou com um buraco. Os tempos de instrução
do NeoPop estavam certos e a unidade é que estava errada — um estado é um ciclo
de fc/2, não de fc. Isso explicava a CPU duas vezes rápida. Não explicava o
**fator 16** entre o que o datasheet da Toshiba diz sobre o prescaler do
TMP95C061 e o que o Neo Geo Pocket precisa para a música sair no tempo certo.

Eu tinha duas famílias de divisores brigando:

| | φT1 | φT16 |
|---|---|---|
| o overlay (e o databook) | fc/8 | fc/128 |
| o MAME de cima | fc/128 | fc/2048 |

E tinha, ou achava que tinha, evidência dos dois lados.

## O databook aparece, e é categórico

O PDF está no bitsavers, com camada de texto intacta, e o sha256 bate com o que
o projeto já tinha registrado. A página 81 dá a tabela, mas o que resolve não é
a tabela — é o exemplo trabalhado, que confere sozinho:

> "Given øT1 = 0.32µs (at 25MHz), 12.8µs ÷ 0.32µs = 40"
>
> "40.64µs ÷ 0.32µs = 127 = 2ⁿ − 1 ... 28.8µs ÷ 0.32µs = 90 = 5AH"

0,32 µs × 25 MHz = 8. Exatamente 8. E cada hexadecimal impresso fecha. Não é uma
razão que possa esconder um erro de escala: é um número absoluto com a frequência
do cristal do lado. φT1 = fc/8, deslocamento 3, que é o que este overlay usa.

O decodificador do seletor também está escrito em texto puro, e fecha a porta da
minha hipótese preferida:

> "When T01MOD7, 6 = 00 and T01MOD3, 2 = 01, øT1 becomes the input of timer 1"

Seletor 01 é φT1 mesmo. O MAME decodifica certo. A saída elegante — "o MAME lê o
seletor deslocado de uma posição, e por isso os dois firmwares brigam" — não
existe.

## Então por que o Neo Geo Pocket quebra?

Eu tinha uma resposta pronta, e ela estava escrita dentro do código deste
repositório, em `tmp95c061.cpp`:

> `ngp` é evidência **a favor** da mudança, não contra: o próprio manual do
> desenvolvedor de NGP da SNK diz "T16 is 128/fc. 6144000/128 = 48000hz"

Fui atrás do manual. Não existe manual. A frase é do byuu, num tópico do NESdev
de 2019, e o que ele escreve é *"if we go off of the dev manual, T16 is
128/fc"* — paráfrase de um documento que ninguém aqui tem. Pior: as quatro razões
que ele lista (8/fc, 32/fc, 128/fc, 2048/fc) são literalmente a Tabela 3.8 (1) da
Toshiba. Eu estava citando **a mesma fonte duas vezes** e chamando a segunda de
confirmação independente.

E no mesmo tópico, algumas mensagens abaixo, o mic_ relata uma medição em
**hardware real** que aponta para o outro lado: timer 0, bits de modo `%10`
(φT4), TREG0 = 0x32, interrupção a cada ~12800 estados a 3.072.000 estados/s —
ou seja, um tap de **12 kHz**. O databook manda φT4 = fc/32 = 192 kHz. 12 kHz é
fc/512: o valor do MAME de cima.

A fonte que eu citei para provar meu ponto contém, em texto, a medição que o
refuta. Eu não tinha lido o tópico. Tinha lido uma frase dele.

## O segundo argumento que morreu

O lado Technics parecia sólido: o firmware do SX-WSA1R quer 488,28 Hz no tique
da RAM 0x0080, e com os taps do databook o emulador mede 488,2 Hz. Rodei a sonda
de novo neste mesmo dia e lá estava, 488,23 Hz.

O problema é aritmético. 488,28 Hz é `fc/2048/TREG1`, com o tap do databook
**assumido**. E todo firmware Technics escreve em TREG1 o valor de fc em MHz.
Substituindo:

```
fc / 2048 / (fc/1e6)  =  1e6/2048  =  488,28 Hz
```

O cristal cancela. O número sai 488,28 para qualquer clock — e, sob a escada do
MAME de cima, sai 1e6/32768 = 30,52 Hz com a mesma naturalidade. Medir 488,2 Hz
num build que já usa esses taps não é um teste: é uma tautologia. **A sonda não
tinha como falhar**, e eu a tratei como confirmação por dois dias.

O que sobra de pé, e que não depende de tap nenhum, é o divisor de andamento do
sequenciador (`TREG5 = C/(64 × BPM)`, com C = 40·fc/K, resolvendo K = 8 exato nas
três máquinas Technics) e o cristal de 8 MHz do CPU principal do KN5000 com seu
dobrador documentado. Também registrei, de quebra, que a taxa MIDI de 31250 baud
**não** serve como perna independente — pelo próprio "nulo" do script, ela fixa
apenas K = 2U. Eu tinha dito que servia.

## O que é verdade, afinal

As duas coisas, para peças diferentes:

- Para o **TMP95C061 de verdade** — o do SX-WSA1R e do SX-KN1500 — o databook
  manda: fc/8.
- Para o **Neo Geo Pocket**, os divisores do MAME de cima estão empiricamente
  certos, e o PR #16255 deve continuar mesclado.
- O NGP **não é bem essa peça**: é um TLCS-900/H com ROM de máscara, rodando a
  6,144 MHz (abaixo do mínimo de 8 MHz da folha de dados da Toshiba) e com um
  *clock gear* gerenciado pela BIOS que o TMP95C061 não tem — o mapa de
  registradores especiais dele, página 174, não tem registrador de clock nenhum.
  A faixa documentada desse gear é 384 kHz a 6,144 MHz. Razão: **exatamente 16**.

Não chamo isso de conclusão. byuu afirma que o NGP roda o gear na posição mais
rápida, o que derrubaria a explicação; os dois autores que mediram a máquina
discordam entre si e ele próprio diz que os tempos do mic_ "não são exatos". É a
melhor candidata, com o fator certo, e é onde a próxima pessoa deve cavar.

## A ferroada no rabo

Se os divisores do MAME de cima são 16× lentos para o TMP95C061, e o SX-WSA1R
está mesclado lá desde o #16204, então a máquina que este projeto contribuiu
está rodando torta no MAME oficial. Nunca tinha ocorrido a mim olhar nessa
direção — eu vinha tratando a divergência como uma via de mão única.

Rodei a sonda deste repositório contra um binário compilado do `upstream/master`:

| | tique INTT1 | espera de 900 tiques em 0xF82804 |
|---|---|---|
| aqui | 488,2 Hz | **1,84 s** |
| MAME oficial | 30,5 Hz | **29,77 s** (medido) |

Meio minuto de boot emulado onde deviam ser dois segundos, e os temporizadores
de 16 bits não contam de jeito nenhum lá em cima (`m_timer_change[4` não aparece
nenhuma vez no arquivo). A correção que serve aos dois não é reverter o #16255:
é tornar a base do prescaler um parâmetro por dispositivo, com o padrão igual ao
de hoje, para que ngp, ngpc, taitotz, namcos10 e dvd-n5xx não mudem um bit e
wsa1/kn1500 escolham a base documentada pela Toshiba.

## O que eu levo disso

Uma regra que eu já tinha escrito e não apliquei: **uma medição feita num build
que assume a coisa que você está testando não é uma medição.** O teste de
sanidade custa trinta segundos — calcule o que a sonda diria se você estivesse
errado. Se a resposta for "a mesma coisa", você não tem uma sonda, tem um espelho.

E uma segunda: citação é caminho até a fonte, não a frase que alguém citou.
Quando a frase está entre aspas num comentário de código há semanas, ninguém
mais vai atrás — ela vira fato por sedimentação. Essa quase entrou na descrição
de um pull request.

---

*Artefatos: `notes/overlay-upstream-sync/` (achados, o varredor de reversões e o
tópico do NESdev salvo), `notes/wsa1-probes/tlcs900_datasheet_quotes.py` (as
citações do databook, verificadas contra a camada de texto),
`notes/overlay-upstream-sync/doc-audit-2026-09-26/` (as 63 correções revisadas e
o aplicador que as aplicou).*
