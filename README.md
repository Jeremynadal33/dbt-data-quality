# dbt × Elementary — Data Quality Demo

Démo dbt + Elementary sur un domaine fictif de marketplace de restaurants : uniquement des
`sources:` (aucun modèle dbt), un générateur Python qui charge un historique propre puis injecte
des défauts ciblés. Le script de présentation complet est dans [`DEMO.md`](./DEMO.md).

## Setup

### Prérequis

- [`mise`](https://mise.jdx.dev/getting-started.html) — task runner + gestion des versions
  Python.
- [`uv`](https://docs.astral.sh/uv/getting-started/installation/) — package manager Python
  (installé automatiquement via `mise` au premier `mise run`, sinon `pip install uv`).
- Accès à un warehouse Snowflake (base `jnadal_db`, rôle `r_jnadal` par défaut — adapter
  `dbt/profiles.yml`/`data_generator/src/data_generator/utils/warehouse.py` si tu utilises un
  autre compte).

### Installation

```bash
git clone <ce repo>
cd dbt-data-quality   # ou le nom de ton worktree

cp .env.example .env  # si présent, sinon crée .env directement (voir ci-dessous)
mise run setup        # uv sync : installe dbt, Elementary et le générateur
```

Deux projets `uv` indépendants, chacun avec son propre `.venv` : `dbt/` (dbt + le CLI
Elementary `edr`) et `data_generator/` (le générateur Python). `mise run setup` installe les
deux (`uv sync --project dbt` puis `uv sync --project data_generator`) ; `mise.toml` orchestre
tout depuis la racine sans jamais `cd`, via `uv run --project <dbt|data_generator> ...`.

`mise run setup` construit aussi le package `data_generator/` et installe ses commandes dans
`data_generator/.venv/bin/` (`generator_history`, `generator_reset`, `generator_create_chaos`,
`generator_chaos_*`) — vérifiable avec `ls data_generator/.venv/bin | grep generator_`.

### Variables d'environnement (`.env`, jamais commité)

```
DBT_SNOWFLAKE_ACCOUNT=<compte Snowflake>
DBT_SNOWFLAKE_PAT=<personal access token>
SLACK_BOT_TOKEN=<xoxb-... pour les alertes Elementary>
```

`mise.toml` charge `.env` automatiquement (`[env] _.file = ".env"`).

### Premiers pas

```bash
mise run dbt:deps      # installe les packages dbt (elementary, dbt_utils, dbt_expectations)
mise run demo:history  # charge 30 jours de donnees propres + rafraichit Elementary/le rapport
mise run demo:status   # verifie l'etat (commandes/jour, fraicheur) avant de presenter
```

Pour dérouler la démo complète, suis [`DEMO.md`](./DEMO.md) — chaque scénario de chaos y est
déclenché individuellement en appelant directement son script (`uv run --project data_generator
generator_chaos_<nom>`), pas via une tâche `mise` dédiée : `mise` n'expose que `demo:chaos`, qui
enchaîne les 5 scénarios d'un coup.

### Tâches utiles

| Tâche | Rôle |
|---|---|
| `mise tasks` | liste toutes les tâches disponibles |
| `mise run demo:history` | (re)charge un historique propre de 30 jours |
| `uv run --project data_generator generator_new_day` | ajoute une journée propre à l'historique (job quotidien, voir plus bas) |
| `mise run demo:verify` | reconstruit les modèles Elementary et rejoue `dbt test` + `dbt source freshness` |
| `mise run demo:chaos` | injecte les 5 scénarios de chaos dans l'ordre sûr, puis re-teste et alerte |
| `mise run demo:alert` | envoie les alertes Elementary en attente vers Slack |
| `mise run demo:reset` | supprime le schéma `raw` |
| `mise run webapp:serve` | construit et sert en local les dbt docs + le rapport Elementary |

Pas de tâche `mise` pour lancer un seul scénario de chaos à la fois : ça multipliait les tâches
pour un simple alias de `uv run --project data_generator generator_chaos_<nom>`. Utilise le
script directement (voir `DEMO.md`), ou `mise run demo:chaos` pour les 5 d'un coup.

## Historique quotidien

Le flux prévu : `generator_history` une fois (30 jours propres, se terminant hier), puis
`generator_new_day` une fois par jour pour ajouter une journée propre supplémentaire — via le
workflow `.github/workflows/generate-daily-data.yml` (cron quotidien + déclenchement manuel).
Les scénarios de chaos ne sont joués que le jour de la présentation, jamais par ce job.

`generator_new_day` :
- ajoute exactement un jour (le lendemain du dernier jour présent dans `orders`) ;
- rafraîchit le `synced_at` du restaurant "dormant" (voir
  `data_generator/src/data_generator/domain.py`) pour que le freshness reste vert chaque jour ;
- échoue explicitement (au lieu de dupliquer des données) si `orders` contient déjà des
  données pour aujourd'hui.

**Note GitHub Actions** : les déclencheurs `schedule` ne sont évalués que sur la version du
workflow présente sur la branche par défaut du repo. Tant que `pyramide` n'est pas mergée (ou
définie comme branche par défaut), le cron ne se déclenchera pas tout seul — utiliser
`workflow_dispatch` (bouton "Run workflow") en attendant.

## Développer le générateur

Projet indépendant sous `data_generator/` (son propre `pyproject.toml`, son propre `.venv`).
Le code vit dans `data_generator/src/data_generator/` : `domain.py` (schéma + génération
Faker), `entrypoints/` (un module par commande, voir le pattern dans `entrypoints/history.py`),
`entrypoints/chaos/` (les 5 scénarios). Chaque entrypoint est directement appelable en Python
(`entrypoint(**kwargs)`) ou en CLI via son script installé (`uv run --project data_generator
generator_<nom>`, ou directement `generator_<nom>` une fois le venv activé).

## Le projet dbt

Sous `dbt/` : `dbt_project.yml`, `profiles.yml`, `packages.yml`, `src/` (uniquement des
`sources:` avec des tests dessus — zéro modèle). Son propre `pyproject.toml`
(`dbt-snowflake` + `elementary-data`) et son propre `.venv`. Toute commande dbt/edr passe par
`--project-dir dbt --profiles-dir dbt` (voir les tâches `dbt:*`/`demo:*` de `mise.toml`) plutôt
que par un `cd dbt` — ça garde les chemins de sortie (`docs/dbt_docs`, `docs/elementary_report`)
relatifs à la racine du repo, inchangés pour le déploiement gh-pages.
