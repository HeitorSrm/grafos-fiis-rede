# Como contribuir (Gitflow simplificado)

Ninguém commita direto em `main`: ela é protegida e só recebe **Pull Request vindo de `develop`** (ou `hotfix/*`), aprovado pelo responsável do repositório (@HeitorSrm). Por convenção, o trabalho novo também entra em `develop` por PR, a partir de uma branch própria.

```
feature/*  ──PR──▶  develop  ──PR──▶  main
hotfix/*   ──PR──────────────────────▶ main (e depois volta para develop)
```

| Branch | Para quê | Quem entra nela |
|---|---|---|
| `main` | Versão estável / entrega (protegida) | só PR vindo de `develop` (ou `hotfix/*`), com aprovação do responsável |
| `develop` | Integração do trabalho em andamento | só PR vindo de `feature/*`, `fix/*`, `docs/*` |
| `feature/<tema>` | Trabalho novo (ex.: `feature/camada-c-knn`) | quem está desenvolvendo |

## Fluxo do dia a dia
1. Atualize: `git switch develop && git pull`
2. Crie sua branch: `git switch -c feature/nome-curto`
3. Faça commits pequenos, com mensagem clara (ex.: `Adiciona script de sensibilidade de threshold`).
4. Envie: `git push -u origin feature/nome-curto`
5. Abra um **Pull Request para `develop`** e peça revisão de 1 colega.
6. Depois de aprovado, faça o merge e apague a branch.
7. Na hora de fechar uma entrega, abra PR de `develop` para `main`; o responsável revisa e aprova antes do merge.

## Nomes de branch
`feature/…` (novo), `fix/…` (correção), `docs/…` (relatório/documentação), `hotfix/…` (urgência direto para `main`).

## Regras
- Não suba CSVs grandes de dados (`dados/*.csv` está no `.gitignore`).
- Rode `python src/main.py` antes de abrir o PR, para garantir que o pipeline não quebrou.
