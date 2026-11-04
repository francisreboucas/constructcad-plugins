# Plugins do ConstructCAD

[English](README.md)

O índice comunitário de plugins do [ConstructCAD](https://github.com/francisreboucas/constructcad). Um plugin é uma pasta com um manifesto `plugin.toml` e código Lua que acrescenta comandos ao ConstructCAD. Os comandos dele funcionam como os nativos: no aplicativo, com `ccad run`, em scripts e para agentes de IA via MCP. Como escrever um está no [guia de automação](https://github.com/francisreboucas/constructcad/blob/main/docs/automacao.md#plugins) do ConstructCAD.

Este repositório não guarda o código dos plugins. Cada plugin fica no repositório do seu autor, e este índice o lista: um arquivo por plugin em [`plugins/`](plugins), com de onde baixar cada versão e o checksum SHA-256 dela. O [`index.json`](index.json) reúne todos para o ConstructCAD ler e é regenerado automaticamente quando uma entrada muda:

```
https://raw.githubusercontent.com/francisreboucas/constructcad-plugins/main/index.json
```

## Instalando um plugin

Enquanto o gerenciador de plugins do ConstructCAD não lê este índice, baixe o arquivo do plugin indicado na entrada, confira o checksum, descompacte numa pasta e carregue-o:

```sh
ccad --plugins /caminho/para/plugins plugins     # lista o que carregou
ccad --plugins /caminho/para/plugins run <plugin>__<comando> chave=valor
```

Os plugins rodam em sandbox: só chegam ao projeto pelos comandos do ConstructCAD, não acessam arquivos nem a rede e têm limites de instruções e de memória. Um plugin só importa, exporta ou salva arquivos se pedir a permissão `files`. Mesmo assim, examine um plugin antes de instalá-lo: o índice verifica as entradas, não o que os plugins fazem.

## Enviando um plugin

Abra um pull request que acrescente `plugins/<id>.toml`. O [CONTRIBUTING.md](CONTRIBUTING.md) descreve a entrada, o arquivo compactado e as verificações (em inglês).

## Organização

| | |
|---|---|
| `plugins/<id>.toml` | uma entrada por plugin, escrita pelo autor |
| `index.json` | todas as entradas num arquivo (gerado; não edite) |
| `scripts/index.py` | verifica entradas e arquivos, gera o `index.json` (Python 3.11+, só a biblioteca padrão) |
| `tests/` | testes do verificador |

## Licença

O índice (entradas, scripts e documentação) está sob a [Licença MIT](LICENSE). Cada plugin mantém a sua própria licença, indicada na entrada dele.
