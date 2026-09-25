# Rascunhos de divulgação

Textos escritos para leitores de fora do projeto — não são transcrição nem
documentação interna. Ficam aqui em rascunho até o dono decidir se e onde
publicar.

As notas técnicas ficam em `notes/`; este diretório é o único lugar onde um
achado vira texto para alguém ler.

| Rascunho | Assunto | Estado |
|---|---|---|
| `2026-09-25_o_estado_valia_dois_clocks.md` | **Os tempos de instrução do NeoPop nunca foram inventados: 2599 dos 2784 opcodes (93,4%) já traziam exatamente o valor do databook da Toshiba.** O erro era a unidade — o databook define um estado como um ciclo de fc/2, e o MAME cobrava esses estados como se fossem clocks de fc, deixando a CPU duas vezes rápida e obrigando cada divisor de temporizador a absorver a diferença. Isso explica por que "corrigir" o prescaler do TMP95C061 para o valor do datasheet distorceu a música do Neo Geo Pocket (revertido em 55 s), e por que a explicação que eu dei para a regressão — e escrevi em comentário nos três arquivos do MAME — estava errada. Inclui o segundo oráculo: o tique de 2,97 ms do escalonador do KN5000, achado no desassemblado do próprio projeto, que mostrou que alinhar o `tmp94c241` aos irmãos teria estragado o KN5000 | **Não publicado.** Aguarda revisão |
