---
repo: architecture
path: docs/architecture/aw-app-code-server.md
source: generated
edited: false
checksum: sha256:c01069b070c655736e199b2081d0dc57e21ddc9a92842add2fd8d5f836633c73
---
# Code Server

- **repo**: aw-app-code-server
- **layer**: app-container
- **technologies**: docker
- **health** (derived): planned

VS Code in the browser (code-server), with this workspace's repos mounted read-only and a persistent $HOME so extensions and CLI agent logins (claude / codex / copilot) survive container recreates. Ported from the agentic-workspace monolith's code-server integration (src/api/routes/code_server.py, src/mcp/vscode.py, tools/code-server/).

## Connections
_none_

## MCP tools
_none exposed_

## Requirements
### Caminho do host é traduzido para o ponto de montagem de dentro do container
- Given quem chama a tool vive no workspace e conhece /opt/aw-workspace/repos/..., enquanto o code-server enxerga a mesma árvore como /home/coder/project/...
- When o caminho é normalizado pela cadeia de quatro regras, primeira que casar vence (repos/aw-app-code-server/mcp_server/server.py::_to_container_path:105)
- Then um caminho já dentro do workspace do container passa intacto, um absoluto sob a raiz do host vira o equivalente sob a raiz do container, um relativo é resolvido contra WORKSPACE_REPOS_HOST e retraduzido, e um absoluto em qualquer outro lugar é confiado ao chamador — sem essa tradução a URL abre um arquivo que não existe do lado de lá, e o editor mostra um painel vazio em vez de um erro, que é o modo de falha mais caro de diagnosticar aqui
- intended_status: `not_implemented` · derived health: `not_implemented`
- tests: `repos/aw-app-code-server/tests/test_mcp_server.py` (passing)

### A URL abre a pasta e o arquivo, via folder mais payload vscode-remote
- Given um pedido para abrir um arquivo específico, e não só a pasta do projeto
- When a URL é montada (repos/aw-app-code-server/mcp_server/server.py::_build_url:148)
- Then a base é ?folder=&lt;pasta no container&gt; e o arquivo viaja num &amp;payload= com o array [["openFile","vscode-remote:&lt;caminho&gt;"]] URL-encodado — o folder sozinho abre a janela na pasta certa mas sem o arquivo, e o payload é o único canal que o code-server aceita para isso. Quando não vem workspace, a pasta é inferida do dirname do arquivo (server.py:157), de modo que abrir um arquivo solto ainda abre uma árvore navegável em volta dele
- intended_status: `not_implemented` · derived health: `not_implemented`
- tests: `repos/aw-app-code-server/tests/test_mcp_server.py` (passing)

### A superfície MCP é exatamente uma tool, e chamada sem arquivo devolve erro em vez de estourar
- Given um cliente MCP negociando com este servidor, e uma chamada que chega com file_path vazio
- When o tools/list é respondido (repos/aw-app-code-server/mcp_server/server.py::handle_request:174) e a chamada é tratada (repos/aw-app-code-server/mcp_server/server.py::_open_file:269)
- Then a lista é exatamente ["open_file"] e o caso vazio volta como resultado com isError=True (montado por _tool_result:170) em vez de deixar o ValueError de _to_container_path:119 subir — um servidor MCP que morre com traceback derruba a sessão inteira do cliente, enquanto um isError deixa o agente ler o problema e corrigir a chamada. Fixar a lista em um item é o que faz uma tool nova acidental aparecer no teste antes de aparecer no gateway
- intended_status: `not_implemented` · derived health: `not_implemented`
- tests: `repos/aw-app-code-server/tests/test_mcp_server.py` (passing)
