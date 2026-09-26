# dbt × Elementary — Data Quality Demo

Démo dbt + Elementary sur un domaine fictif de marketplace de restaurants : uniquement des
`sources:` (aucun modèle dbt), un générateur Python qui charge un historique propre puis injecte
des défauts ciblés. La présentation de la démo est dans
[`docs/presentation/`](./docs/presentation/index.html), publiée avec les dbt docs, le rapport
Elementary et les dashboards dbt Charts sur
[jeremynadal33.github.io/dbt-data-quality](https://jeremynadal33.github.io/dbt-data-quality/).

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

Pour dérouler la démo complète, suis la [présentation](./docs/presentation/index.html) — chaque
scénario de chaos y est déclenché individuellement via sa tâche `mise run demo:chaos:<nom>`
(injection seule : enchaîner `mise run demo:verify` pour voir le test casser).

### Tâches utiles

| Tâche | Rôle |
|---|---|
| `mise tasks` | liste toutes les tâches disponibles |
| `mise run demo:history` | (re)charge un historique propre de 30 jours |
| `uv run --project data_generator generator_new_day` | ajoute une journée propre à l'historique (job quotidien, voir plus bas) |
| `mise run demo:verify` | reconstruit les modèles Elementary et rejoue `dbt test` + `dbt source freshness` |
| `mise run demo:chaos` | injecte les 5 scénarios de chaos dans l'ordre sûr, puis re-teste et alerte |
| `mise run demo:chaos:<nom>` | injecte un seul scénario : `duplicate-menu-item`, `orphan-menu-item`, `new-restaurant-volume`, `late-restaurant`, `drop-column` |
| `mise run demo:failures <test>` | affiche les lignes fautives stockées par `store_failures` pour un test |
| `mise run dbt:compile` | compile le projet (SQL des tests dans `dbt/target/compiled`) |
| `mise run demo:alert` | envoie les alertes Elementary en attente vers Slack |
| `mise run demo:reset` | supprime le schéma `raw` |
| `mise run webapp:serve` | construit et sert en local le site `docs/` (dbt docs, rapport Elementary, dashboards, présentation) |
| `mise run charts:serve` | sert les dashboards dbt Charts en direct, filtres actifs |

`drop-column` doit passer après `duplicate-menu-item` si les deux sont joués (le second insère
explicitement la colonne `label`, que le premier supprime). Toujours repartir d'un historique
propre (`mise run demo:reset && mise run demo:history`) avant de rejouer un scénario isolé.

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
workflow présente sur la branche par défaut du repo (`main`). Une modification du workflow
poussée sur une autre branche n'aura donc aucun effet sur le cron avant d'être mergée —
utiliser `workflow_dispatch` (bouton "Run workflow") pour la tester.

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
(`dbt-snowflake` + `elementary-data` + `dbt-charts`) et son propre `.venv`. Toute commande dbt/edr passe par
`--project-dir dbt --profiles-dir dbt` (voir les tâches `dbt:*`/`demo:*` de `mise.toml`) plutôt
que par un `cd dbt` — ça garde les chemins de sortie (`docs/dbt_docs`, `docs/elementary_report`)
relatifs à la racine du repo, inchangés pour le déploiement gh-pages.

## Les dashboards (dbt Charts)

Sous `dbt/charts/`, des dashboards [dbt Charts](https://docs.dbtcharts.com/) écrits en YAML,
qui lisent directement les sources dbt (`{{ source(...) }}`) via le profil de `dbt/profiles.yml`
(connexion déclarée dans `dbt/dbt_charts.yml`) :

- `index.yml` — page d'accueil : KPI des 7 derniers jours et liens vers les dashboards ;
- `restaurant_insights.yml` — commandes, chiffre d'affaires et panier moyen, filtrables par
  catégorie d'article ;
- `meta.yml` — thème (`vivid`) appliqué à tous les boards du dossier.

Deux modes :

- `mise run charts:serve` — serveur local, les requêtes partent vers Snowflake à chaque
  affichage ou changement de filtre ;
- `mise run charts:build` (appelé par `webapp:build`) — rendu HTML statique dans
  `docs/charts/`, publié sur gh-pages. Les filtres y sont figés sur leur valeur par défaut.

Les deux lancent d'abord `dbt parse` : `source()` est résolu à partir de
`dbt/target/manifest.json`. Les liens entre boards s'écrivent sous la forme `<board>/`
(ex. `restaurant_insights/`), la seule qui marche à la fois dans `dct serve` et dans le rendu
statique.
