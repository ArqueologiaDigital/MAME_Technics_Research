# O site dizia mais do que sabia

*Revisei o site de documentação dos teclados Technics de ponta a ponta: as 138 páginas
escritas à mão, cada afirmação conferida contra o desassemblado, o MAME e os dumps (as
outras 64 são geradas do desassemblado e foram regeneradas). Quase dois mil
trechos estavam desatualizados ou errados. Alguns eram só velhos; outros nunca tinham
sido verdade.*

## Por que revisar tudo de uma vez

O site cresceu mais rápido do que foi relido. Cada descoberta no desassemblado do
KN5000, no driver do MAME ou nos firmwares da família MN10300 virava um parágrafo
novo, e o parágrafo antigo que ela contradizia ficava onde estava. Em outubro, o
menu lateral ainda tinha um tópico raiz por seção do KN5000 (Hardware, Firmware,
Subsistemas...) enquanto os outros modelos tinham um tópico só — e a primeira coisa
pedida foi isso: um tópico por modelo, do mais novo para o mais antigo.

Para ordenar por ano, eu precisei saber os anos. E aí começou.

## Os anos que o site errava

| modelo          | o site dizia       | o certo | a evidência                                                 |
|-----------------|--------------------|---------|-------------------------------------------------------------|
| KN2400 / KN2600 | 1998–2000          | 2003    | lançados na Summer NAMM de 2003 (Harmony Central, 24/07)    |
| KN6000          | 2000               | 1999    | manual de serviço EMID9908016C0 (o número codifica 1999-08) |
| KN5000          | 1996 (numa página) | 1997    | demodb; a resenha da Sound On Sound é de abril de 1998      |

O próprio MAME erra dois deles: declara o `kn5000` como 1998 e o `kn2400`/`kn2600`
como 2000. Isso é correção para mandar para cima, não para o site.

## Como a revisão foi feita

Dividi as páginas em 25 faixas de até nove páginas. Em cada faixa, um agente
procurou problemas lendo cada linha e conferindo cada número, nome de símbolo,
endereço, número de PR e cada "ainda não" contra as fontes atuais; um segundo
agente, independente, tentou **refutar** cada achado refazendo a conta sozinho; só
o que sobreviveu foi aplicado, e cada faixa virou um commit. Depois, uma varredura
procurou contradições entre páginas, e duas rodadas menores trataram o que sobrou.

Os números:

- rodada 1: 1.264 achados, **1.254 confirmados** pelo verificador adversarial;
  mais 82 correções entre páginas;
- rodada 2 (o que a varredura e os próprios editores deixaram anotado): 568 achados,
  562 confirmados; 261 pistas foram descartadas porque já estavam resolvidas ou
  estavam erradas.

Uma taxa de confirmação de 99 % parece boa demais para um verificador que tinha
ordem de refutar na dúvida. Acho que diz mais sobre o site do que sobre os agentes:
quando quase tudo o que um leitor atento estranha está mesmo errado, o texto
envelheceu inteiro.

## O que estava errado, e não só velho

A maior parte era envelhecimento honesto: símbolos renomeados no desassemblado,
PRs que entraram no MAME, contagens que mudaram. Mas uma parte nunca tinha sido
verdade.

- **`rom-strings.md` tinha conteúdo que não está nos dumps.** Nomes de kits de
  bateria, "Tubular Bells C4", uma tabela de BPM por estilo, categorias de estilo e
  "créditos de autores" (Ray Conniff, entre eles) — nada disso ocorre nos ROMs.
  Foi tudo removido, e no lugar ficou o que os ROMs realmente contêm.
- **A página inicial dizia que todo o conteúdo era "verificado contra o
  comportamento do hardware real".** Não era: o projeto quase não tem tempo de
  bancada, e o próprio roteiro diz isso. A frase agora descreve a prática real —
  firmware, manuais de serviço e emulador, e cada página diz quando algo depende do
  hardware ou ainda não foi verificado. (A frase está na voz do dono do site, então
  fica para ele aprovar.)
- **"O KN6000 compartilha ~85 % das strings com o KN7000."** Medido em julho na
  metade de baixo da imagem do KN6000 — no mesmo dia em que se descobriu que a
  metade de cima tinha ficado de fora. Com a imagem inteira são **dois terços**
  (11.137 de 16.503). O banner `MILK MN10300 Ver1.0R1`, que o site dizia ausente no
  KN6000, está na metade que faltava.
- **O sinal "ALL INITIAL SETTING!"** era explicado como sintoma de um combo de
  botões. É, na verdade, o que aparece num boot a frio sem os checksums de
  desligamento salvos.

## O que a revisão respondeu de quebra

Duas perguntas que o site deixava em aberto tinham resposta em material público. Os
discos de atualização v5 a v10 do KN5000 estão no Internet Archive; decodificando o
`HKMSPRG.SLD` de cada um:

- os seis programas batem com os CRCs do MAME e têm `FF FF FF 00 FF` em `0x1FFEEB`.
  O caminho alternativo de carga do sub-CPU pela ROM de dados nunca foi o caminho
  ativo em nenhuma versão preservada;
- o segundo fluxo de cada disco é, byte a byte, o payload comprimido que o MAME
  associa àquela versão. Os pares v5/v6 ↔ v1.40, v7/v8 ↔ v1.41 e v9/v10 ↔ v1.42
  deixaram de ser inferência por nome de arquivo.

## A regra que mais trabalho deu

Todo número publicado precisa de um produtor commitado — o script que o gerou, num
repositório, com a pergunta que responde e o comando para rodar. Os agentes mediram
muita coisa com scripts de rascunho; cada vez que um desses números ia para uma
página, o script ia para `tools/` no repositório do site antes do commit. Foram
dezoito scripts de medição assim, além de três verificadores (links e âncoras, menu,
alinhamento de tabelas). Onde o produtor não existia, a correção esperou.

## O que ficou para o dono

Correções que não cabem no site: comentários desatualizados no desassemblado, os
anos no MAME, rótulos de tabela que não batem com os nomes que o próprio firmware
mostra. E uma que afeta a reprodutibilidade de tudo: o ramo público
`tlcs900_backend` do LLVM está 32 commits atrás da versão que o desassemblado exige,
então hoje ninguém de fora consegue reconstruir os ROMs a partir do que está
publicado. Isso se resolve com um `git push`.
