# O estado valia dois clocks

*Como uma "correção" tirada do datasheet estragou o som do Neo Geo Pocket, e
como a explicação que eu dei para isso — a que eu cheguei a escrever dentro do
código do MAME — estava errada.*

## O relatório

25 de setembro de 2026, um mantenedor do MAME comenta num PR já mesclado:

> suspeito que isso causou uma regressão feia no som do ngpc/ngp (inicie o
> driver → aperte F1 para ligar → música completamente distorcida)

O PR era o do driver do Technics WSA1R. Não tem nada a ver com Neo Geo Pocket —
a não ser por um detalhe: os dois usam a mesma CPU, o Toshiba TMP95C061, da
família TLCS-900/H. E dentro daquele PR havia um commit que mexia no
temporizador dela.

## A correção que parecia óbvia

O commit dizia, com todas as letras, o que tinha feito:

> O databook dá phiT1 = fc/8, phiT4 = fc/32, phiT16 = fc/128 e phiT256 = fc/2048.
> Cada deslocamento aqui tinha quatro bits a mais, então todo temporizador de 8
> bits contava dezesseis vezes mais devagar.

E estava certo quanto ao hardware. A página 91 do datasheet do TMP95C061B traz a
tabela com os números já calculados: phiT1 (8/fc) = 320 ns a 25 MHz, phiT4
(32/fc) = 1,28 µs, e assim por diante. O divisor do MAME era mesmo dezesseis
vezes maior do que o do chip.

Só que aplicar o número do datasheet quebrou o som do Neo Geo Pocket. O reverso
foi mesclado em 55 segundos — e usuários confirmaram depois que o som voltou.

## A explicação errada

A pista que parecia resolver tudo estava num fórum de 2018. O autor do NeoPop,
o emulador de onde o núcleo TLCS-900 do MAME descende, escreveu:

> posso ao menos confirmar que os tempos das instruções são praticamente
> inventados e não têm relação nenhuma com o hardware real

Pronto: se os ciclos por instrução são inventados, então o divisor do
temporizador nunca foi uma constante de hardware — é uma calibração contra
aqueles ciclos falsos. O número do datasheet só valeria depois de consertar os
tempos. Os dois valores estariam certos, cada um para a sua máquina.

Essa explicação fechava. Ela explicava a regressão, explicava por que o
`tmp94c241` do KN5000 podia ficar com um valor e os irmãos com outro, e eu a
escrevi em comentário nos três arquivos, como aviso para o próximo que passasse
por ali.

Ela estava errada.

## A medição

O jeito de acabar com a calibração era dar ao núcleo tempos de instrução de
verdade. O livro de instruções da Toshiba tem a tabela — coluna "State", por
mnemônico, byte/word/long — nas páginas 165 a 174, em PDF só de imagem. Depois
de transcrever as 227 formas e cruzá-las com as tabelas de opcode do MAME (2784
das 2785 entradas reais), o número que apareceu não era o esperado:

    ciclos médios do MAME 7,55   ->   estados médios do databook 7,66   (x1,02)

E, entrada por entrada:

    2599 dos 2784 opcodes já traziam exatamente o valor do databook   (93,4%)

Os 185 restantes erram por um ou dois estados. A tabela do NeoPop nunca foi
inventada. O autor estava sendo modesto sobre o próprio trabalho — ou tirou os
números do mesmo livro que eu.

## O que estava errado, então

A unidade. O databook define:

> One cycle clock divided by 2 oscillation frequency is called 1 state.

Um estado é um ciclo de fc/2. O mesmo documento repete isso de outras duas
formas — "10 states: 800ns with a 25MHz" e um watchdog de "8 to 20 states
(640ns to 1.6µs @ 25MHz)", ambos dando 80 ns por estado a 25 MHz.

O MAME dava clock fc ao dispositivo e gastava um "ciclo" por clock. Contagens
certas, cobradas na moeda errada: a CPU rodava duas vezes mais rápido que o chip,
e o divisor do temporizador tinha de absorver a diferença. Não era calibração
contra números inventados — era um fator de dois numa conversão de unidade, com
vinte anos de idade.

## O conserto

Converter clock em ciclo a fc/2, corrigir os 185 opcodes, e aí os três chips
podem receber o valor do datasheet ao mesmo tempo: phiT1 = fc/8 são 4 estados,
phiT256 = fc/2048 são 1024. A divergência entre `tmp94c241` e `tmp95c061`
desaparece sozinha, porque ela só existia para compensar a unidade.

Duas máquinas servem de prova, e as duas continuam certas com a mesma regra:

| | antes | depois |
|---|---|---|
| tique do escalonador do KN5000 | 2,97 ms | 2,97 ms |
| phiT1 do Neo Geo Pocket | 48 kHz (16× lento) | 768 kHz = fc/8 |

O tique do KN5000 não é chute: o firmware do subprocessador tem uma rotina que
o próprio desassemblado do projeto já tinha batizado de
`TaskSched_ConfigAndDispatch`, e ela programa o temporizador 3 em phiT256 com
`TREG3 = 0x1D`. Foi esse número que mostrou, antes de qualquer código mudar, que
alinhar o `tmp94c241` aos irmãos — coisa que eu tinha implementado e testado —
teria deixado o escalonador do KN5000 dezesseis vezes lento. A engenharia
reversa que o projeto já tinha feito respondeu a pergunta que o datasheet não
respondia.

## O que fica

Três coisas que eu levaria para qualquer investigação parecida.

A primeira: um valor que contradiz o datasheet não é necessariamente um erro.
Pode ser a compensação de outro erro, e trocá-lo sozinho quebra a máquina.

A segunda: "está inventado" é uma afirmação sobre dados, e dá para medir. Eu
aceitei a palavra do autor — que era autodepreciativa — e escrevi essa palavra
no código-fonte do MAME como se fosse achado. Bastou comparar 2784 números com o
livro para ver que 93,4% deles estavam certos.

A terceira: o datasheet diz o que o *hardware* faz; só a engenharia reversa do
firmware diz o que o *software esperava*. Para uma constante de calibração, a
segunda é que manda.
