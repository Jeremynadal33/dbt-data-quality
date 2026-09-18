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
  `profiles.yml`/`generator/utils/warehouse.py` si tu utilises un autre compte).

### Installation

```bash
git clone <ce repo>
cd dbt-data-quality   # ou le nom de ton worktree

cp .env.example .env  # si présent, sinon crée .env directement (voir ci-dessous)
mise run setup        # uv sync : installe dbt, Elementary et le générateur
```

`mise run setup` construit aussi le package `generator/` et installe ses commandes dans
`.venv/bin/` (`generator_history`, `generator_reset`, `generator_create_chaos`,
`generator_chaos_*`) — vérifiable avec `ls .venv/bin | grep generator_`.

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

Pour dérouler la démo complète (les 5 scénarios de chaos, un par un ou tous en une fois via
`mise run demo:chaos`), suis [`DEMO.md`](./DEMO.md).

### Tâches utiles

| Tâche | Rôle |
|---|---|
| `mise tasks` | liste toutes les tâches disponibles |
| `mise run demo:history` | (re)charge un historique propre de 30 jours |
| `uv run generator_new_day` | ajoute une journée propre supplémentaire à l'historique (job quotidien, voir plus bas) |
| `mise run demo:scenario <nom>` | injecte un seul scénario de chaos puis re-teste |
| `mise run demo:chaos` | injecte les 5 scénarios de chaos dans l'ordre sûr, puis re-teste |
| `mise run demo:scenarios` | liste les 5 scénarios disponibles |
| `mise run demo:freshness` | vérifie la fraîcheur de `raw_catalog.restaurants` |
| `mise run demo:alert` | envoie les alertes Elementary en attente vers Slack |
| `mise run demo:reset` | supprime le schéma `raw` |
| `mise run webapp:serve` | construit et sert en local les dbt docs + le rapport Elementary |

## Historique quotidien

Le flux prévu : `generator_history` une fois (30 jours propres, se terminant hier), puis
`generator_new_day` une fois par jour pour ajouter une journée propre supplémentaire — via le
workflow `.github/workflows/generate-daily-data.yml` (cron quotidien + déclenchement manuel).
Les scénarios de chaos ne sont joués que le jour de la présentation, jamais par ce job.

`generator_new_day` :
- ajoute exactement un jour (le lendemain du dernier jour présent dans `orders`) ;
- rafraîchit le `synced_at` du restaurant "dormant" (voir `generator/domain.py`) pour que le
  freshness reste vert chaque jour ;
- échoue explicitement (au lieu de dupliquer des données) si `orders` contient déjà des
  données pour aujourd'hui.

**Note GitHub Actions** : les déclencheurs `schedule` ne sont évalués que sur la version du
workflow présente sur la branche par défaut du repo. Tant que `pyramide` n'est pas mergée (ou
définie comme branche par défaut), le cron ne se déclenchera pas tout seul — utiliser
`workflow_dispatch` (bouton "Run workflow") en attendant.

## Développer le générateur

Le code du générateur vit dans `generator/` : `domain.py` (schéma + génération Faker),
`entrypoints/` (un module par commande, voir le pattern dans
`entrypoints/history.py`), `entrypoints/chaos/` (les 5 scénarios). Chaque entrypoint est
directement appelable en Python (`entrypoint(**kwargs)`) ou en CLI via son script installé.
