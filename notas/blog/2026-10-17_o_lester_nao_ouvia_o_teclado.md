# O Lester não ouvia o teclado

*O Another World roda no KN7000 — a máquina virtual do jogo pegando carona no plug-in de cartão
SD do teclado. Num mesmo dia, três erros de entrada caíram: um que eu achava que era só do MIDI e
não era, um que só aparecia depois da primeira fase, e um que nem é do jogo. E, de quebra, a
comparação parte a parte com a máquina virtual de referência achou dois lugares onde a própria
referência se afasta do motor original.*

## Ler as teclas pelas vozes do gerador de som

O teclado do KN7000 não entrega as teclas para quem quiser: o firmware lê a FIFO de make/break do
teclado 500 vezes por segundo e a esvazia. A primeira versão do porte lia, em vez disso, a lista de
vozes ativas do gerador de som — se uma voz está tocando a nota C6, então C6 está apertada.

Funcionava quase sempre. O Felipe tocou com um controlador USB-MIDI e anotou os erros; eu reproduzi a
sessão byte a byte pelo MIDI IN do MAME e comparei, quadro a quadro, o que o jogo aplicou com o que o
motor canônico faria com as mesmas teclas: **62 quadros errados em 18 trechos**. Achei a causa — um nó
de voz reaproveitado guarda o byte da nota anterior, então o jogo via C4 (ação) enquanto o dedo estava
em C6 (direita) — e concluí que era um problema do MIDI.

Não era. Toquei a mesma sessão no **teclado** do instrumento, nota por nota nos mesmos instantes:
**59 quadros errados em 16 trechos**, o mesmo defeito. A lista de vozes simplesmente não é uma
identidade confiável de tecla, venha a nota de onde vier. Procurei na RAM uma tabela de teclas
apertadas e não existe — os únicos bits que acompanham as notas são das próprias vozes.

O que existe são os fluxos de bytes MIDI do próprio firmware: o anel de recepção do MIDI IN 1, que a
interrupção da UART enche byte a byte, e o anel de transmissão do MIDI OUT 1 — onde o firmware põe,
em MIDI, **cada nota do teclado**. O jogo agora lê os dois com um ponteiro próprio, sem consumir
nada, e reconstrói as notas apertadas: **0 quadros errados** pelo MIDI e **0** pelo teclado, nos 717
quadros da fase. Custa 805 instruções por quadro em vez de 127 (medido no depurador do MAME): uns
0,03 % de um quadro.

## A segunda entrada MIDI perde bytes

O KN7000 tem duas entradas MIDI. A segunda não serve para o jogo: enquanto o plug-in roda, o firmware
lê a UART dela por sondagem, uns 4 ms depois de cada byte, e bytes MIDI chegam a cada 0,32 ms — um
sobrescreve o outro. As quatro primeiras mensagens da sessão chegam como `90 4C 40 56 4A` em vez de
`90 3C 4C 80 3C 40 90 52 56 90 3C 4A`. Uma nota-off perdida deixaria uma direção presa, então o jogo
lê só a primeira.

## A prisão não respondia

O Felipe jogou a primeira fase inteira. Quando a máquina virtual carregou a prisão, o Lester parou de
responder: não andava, não balançava a jaula. A causa era uma linha: a rotina de entrada só traduzia
os controles se a parte atual fosse a do lago — em qualquer outra, voltava sem escrever nada. O motor
original lê a entrada igual em todas as partes.

O incômodo é que a ferramenta de verificação tinha o mesmo ponto cego: ela só comparava quadros da
fase do lago. As duas foram corrigidas. Balançando a jaula desde o início da prisão, **0 de 677
quadros** se afastam do tratamento canônico das teclas, e a mesma entrada reproduzida nas duas
máquinas virtuais dá **600 de 600 quadros idênticos**.

## O jogo inteiro na memória — e a referência também erra

Os 146 recursos do jogo (sons, músicas, telas, paletas, bytecode, polígonos) agora vão no cartão e
ficam todos na RAM: 1,73 MB, desempacotados de uma ferramenta nova que dá resultado idêntico, byte a
byte, ao desempacotador da referência. Abrir arquivo custa ~71 ms no SD do plug-in, então eles vão em
31 pacotes de até 64 KB: 10,6 s de carga em vez de 19,3 s com um arquivo por recurso.

Com tudo carregado, dá para entrar em cada parte do jogo nas duas máquinas virtuais e comparar.
**Todas abrem idênticas, 600 de 600 quadros** — mas só depois de corrigir dois desvios da referência
(o rustyworld) em relação ao motor original:

- Ao entrar numa parte, o rustyworld decodifica também os polígonos compartilhados (o "video2") como se
  fossem uma tela, por cima da página 0. São 25.108 bytes, então só as linhas 0 a 27 são escritas — e
  isso aparece uma única vez, no terceiro quadro da parte final, onde uma cópia com rolagem deixa
  essas linhas à mostra.
- Uma cópia de página com rolagem vertical além de ±199 linhas faz o rustyworld abortar (`assert`);
  o motor original simplesmente não copia. A parte final faz isso no quadro 349. O porte tinha o seu
  próprio desvio no mesmo lugar: limitava a rolagem a 199 e copiava uma linha.

Uma surpresa no caminho: a pasta de dados compartilhada tem **duas** versões do jogo para DOS —
arquivos em maiúsculas e em minúsculas — com 128 dos 146 recursos diferentes, e a de minúsculas tem um
banco vazio. Seis telas da versão do KN5000 vinham dela. O KN7000 usa a outra, a mesma da referência.

## O que ficou de fora

Som e música: os recursos estão na memória, mas como o KN7000 pode tocar PCM cru ainda é pergunta
aberta. E o porte agora tem as cortesias do KN5000 — a abertura com logo e créditos, as telas de ajuda
com os quinze códigos de fase, a tela de código num botão — e a borda preta em volta da janela do
jogo, repintada a cada quadro porque o firmware redesenha a tela inteira quando se aperta OCTAVE +.

*Produtores dos números: `kn5000-anotherworld/kn7000/probes/` — `raw_vs_applied.py`,
`awkbreplay.lua`, `events_to_mid.py`, `awricost.lua`, `awmidi2loss.lua`, `awpartkeys.lua`,
`awparts.sh`, `awresverify.lua`, `awloadtime.lua`; `tools/aw_extract.py`, `tools/aw_release_diff.py`; as mudanças na referência em
`research-scratch/kn7000-aw-reference/replay-mods/`. O plano para o resto do jogo:
`kn7000/FULL-GAME-PLAN.md`.*
