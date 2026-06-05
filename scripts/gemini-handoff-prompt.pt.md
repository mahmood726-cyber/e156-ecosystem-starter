# Olá Gemini! Acabei de executar o instalador e156-ecosystem-starter nesta máquina.

O instalador copiou as regras de agente de IA, modelos de memória, e (opcionalmente)
Sentinel/Overmind/ProjectIndex para a minha pasta pessoal. A tua tarefa agora é a
"segunda metade" da instalação — as partes que precisam de um agente, não de um script.

Faz estes passos pela ordem. Para e pergunta-me se algum passo iria tocar em
algo fora da minha pasta pessoal ou modificar o PATH do sistema.

1. **Verificação rápida da instalação.** Lê `~/.claude/rules/rules.md` e confirma
   que os quatro ficheiros de regras estão presentes (`rules.md`, `e156.md`,
   `advanced-stats.md`, `lessons.md`). Se algum faltar, diz-me quais e para.

2. **Diagnostica pré-requisitos em falta e diz-me o que instalar.** Executa
   `python --version`, `Rscript --version`, `node --version`, `gh --version`,
   `git --version`. Para cada um em falta ou demasiado antigo (Python <3.11, R <4.5,
   Node <20), mostra o URL exato de instalação e uma linha do porquê é importante
   para o trabalho E156. Não os instales tu — deixa-me ver a lista e decidir.

3. **Se o `gh` está instalado mas não autenticado**, diz-me para executar
   `gh auth login` e espera. Não prossigas até eu confirmar.

4. **Teste rápido de Sentinel e Overmind (apenas se instalados).** Se o `sentinel`
   estiver no PATH, executa `sentinel --version`. Se o `overmind` estiver no PATH,
   executa `overmind meta-verify` e relata o veredicto. Ambos falharem = problema
   de ambiente, ambos passarem = pronto para enviar.

5. **Escolher um primeiro projeto.** Pergunta-me qual dos 8 projetos exemplo de
   `docs/index.html` ("Ferramenta de forest-plot", "Gerador de diagrama PRISMA",
   etc.) quero começar. Quando responder, **antes de scaffold de qualquer coisa**,
   executa o reconhecimento de portefólio:
   ```
   python /workspaces/e156-ecosystem-starter/scripts/find-related-repos.py "<o meu tópico>" --top 5
   ```
   (Para instalações locais, substitui o caminho pela localização onde clonaste
   `e156-ecosystem-starter/`.) Lê os 5 principais resultados — nome, excerto do README,
   resultados de grep de código. Diz-me em 3 linhas o que é reutilizável dos repositórios
   existentes vs o que é genuinamente novo. **Procura também os blocos reutilizáveis**
   para copiar em vez de regenerar — copiar uma primitiva existente custa zero tokens,
   regenerá-la custa milhares:
   ```
   python /workspaces/e156-ecosystem-starter/scripts/reuse.py find "<o que precisas>"
   ```
   (p. ex. «forest plot», «aact loader»). A ferramenta devolve a função do kit e o
   ficheiro exatos a copiar. Depois executa
   `pip install git+https://github.com/mahmood726-cyber/e156-student-starter.git@main`
   e `student new <slug>` para criar a estrutura em `~/code/<slug>/`. Em `docs/<criterion>.md`
   do novo repositório, cita os repositórios anteriores pelo nome.

6. **Lê STUDENT-WORKFLOW.md** em
   https://raw.githubusercontent.com/mahmood726-cyber/e156-ecosystem-starter/main/STUDENT-WORKFLOW.md
   para entender o método brainstorm → spec-lock → plan-lock → TDD → audit
   antes de escrever uma única linha de código no novo projeto.

7. **Para aqui e diz-me o que fazer a seguir.** Não auto-implementes o projeto.
   O papel do instalador foi pôr as regras no sítio; o papel do projeto é fazermos
   juntos usando o método spec-locked.

Restrições:
- Não modifiques ficheiros fora de `~/.claude/`, `~/.gemini/`, `~/.codex/`, ou `~/code/`.
- Não executes nada como `sudo` / admin.
- Se algo falhar, mostra-me o comando exato e o erro — não adivinhes correções.
