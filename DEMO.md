# Script de démo — dbt × Elementary, la pyramide de confiance

Fait pour être **déroulé tel quel** pendant la présentation : terminal partagé, ouvert dans
`/Users/jeremy.nadal/repos/perso/dbt-dq-pyramide`, target `prod` (défaut de `mise.toml`).
Zéro modèle dbt dans ce projet — uniquement des `sources:` (`raw.restaurants`, `raw.menu_items`,
`raw.orders`, `raw.order_lines`) avec des tests dessus. dbt sert de moteur de test, pas de
transformation.

Chaque acte donne : l'objectif, le talking point, la commande exacte, et le résultat
**vérifié** (chiffres réels observés, pas des estimations).

---

## Le message central

> Un restaurant vient de s'inscrire. Son premier soir, le volume de commandes explose. Panique
> ou juste... un nouveau client qui démarre fort ?

| Niveau | Question | Outils montrés | Angle mort |
|---|---|---|---|
| **N1 — Valide ?** | la forme est-elle correcte ? | `unique`, `relationships`, `dbt_utils.unique_combination_of_columns` | ne voit que ce qu'on a anticipé |
| **N2 — Présente ?** | la donnée est-elle arrivée ? | `dbt source freshness` | ne dit rien sur le contenu |
| **N3 — Plausible ?** | est-ce normal ? | `elementary.volume_anomalies`, `elementary.schema_changes_from_baseline` | a besoin d'historique |
| **N4 — Actionnable ?** | qui le sait ? | `--store-failures`, `edr monitor` → Slack, rapport | — |

---

## Budget temps (~25 min)

| Acte | Durée | Contenu |
|---|---|---|
| 0 — Ouverture | 2 min | accroche, état du jour |
| 1 — N1 | 6 min | `duplicate_menu_item` + `orphan_menu_item`, `--store-failures` |
| 2 — N2 | 3 min | `late_restaurant` |
| 3 — N3 | 8 min | le twist : tout vert, puis `new_restaurant_volume` + `drop_column` |
| 4 — N4 | 5 min | `demo:alert` + rapport Elementary |
| Clôture | 1 min | punchline |

---

## Avant de commencer

### Une seule fois, à l'initialisation (pas à refaire avant chaque présentation)

- [ ] `mise run demo:reset && mise run demo:history` — charge les 30 premiers jours propres.
- [ ] `uv run dbt run -s elementary --target prod && uv run dbt test --target prod` — attendu :
      `Done. PASS=31 WARN=0 ERROR=0 SKIP=0 TOTAL=31`.
- [ ] `mise run demo:freshness` — attendu : `PASS freshness of raw_catalog.restaurants`.
- [ ] Vérifier que le workflow `.github/workflows/generate-daily-data.yml` tourne (cron
      quotidien, ou déclenchement manuel `workflow_dispatch` tant que `pyramide` n'est pas la
      branche par défaut — voir README). Chaque run ajoute un jour propre de plus, sans
      jamais toucher aux scénarios de chaos.

### Le jour de la présentation

- [ ] `mise run demo:status` — vérifier que la dernière journée avec des commandes est bien
      **hier** (par rapport à maintenant) et que le restaurant le plus récemment synchronisé
      est à quelques heures.
- [ ] Si le job quotidien a manqué un jour (dernière commande à J-2 ou plus) : `uv run
      generator_new_day`, à répéter une fois par jour manquant jusqu'à rattraper hier.
- [ ] **Ne PAS relancer `demo:reset && demo:history`** le jour même — ça jetterait tout
      l'historique accumulé par les runs quotidiens.
- [ ] `mise run webapp:build:force` puis `mise run webapp:serve` — filet de sécurité : si un
      scénario live échoue, on bascule sur ce rapport déjà généré.
- [ ] Tester le bot Slack séparément (voir Annexe B) avant de compter sur `demo:alert` en live.

---

## Acte 0 — Ouverture (2 min)

**À dire** : « Une marketplace de restaurants. Deux équipes : Catalog (référentiel
restaurants/cartes, owner Mathieu) et Orders (commandes, owner moi). »

```bash
uv run generator_status
```
**Résultat attendu** : ~30 lignes, une par jour, un panier moyen stable, et « most recently
synced restaurant » à quelques heures.

---

## Acte 1 — N1 : le contrat (6 min)

**Objectif** : la première ligne de défense est déterministe et rapide — mais ne voit qu'une
malformation ligne par ligne, jamais un déséquilibre d'ensemble.

### 1.1 — `unique` sur `menu_items.item_id`

```bash
uv run generator_chaos_duplicate_menu_item
uv run dbt run -s elementary --target prod
uv run dbt test --target prod
```
**Résultat attendu** :
```
FAIL 1 source_unique_raw_catalog_menu_items_item_id
Done. PASS=30 WARN=0 ERROR=1 SKIP=0 TOTAL=31
```
**Le `--store-failures`** — la ligne fautive, pas juste un compteur :
```bash
uv run dbt show --target prod --inline \
  "select * from jnadal_db.dq_failures.source_unique_raw_catalog_menu_items_item_id"
```
→ 2 lignes avec le même `item_id` (l'originale + le clone injecté).

### 1.2 — `relationships` sur `order_lines.item_id → menu_items.item_id`

```bash
uv run generator_chaos_orphan_menu_item
uv run dbt run -s elementary --target prod
uv run dbt test --target prod
```
**Résultat attendu** :
```
FAIL 1 source_relationships_raw_orders_order_lines_item_id__item_id__source_raw_catalog_menu_items_
Done. PASS=30 WARN=0 ERROR=1 SKIP=0 TOTAL=31
```

**À dire** : « Ces deux tests n'ont besoin d'aucun historique. Ils s'appliquent dès la première
ligne insérée. » (Mentionner verbalement, sans les rejouer en live : `dbt_utils.
unique_combination_of_columns(order_id, line_id)` sur `order_lines`, les regex
`dbt_expectations` sur `siret`/`contact_email`/`sku`, `accepted_values` sur `cuisine_type`/
`status`/`category` — tous déclarés et verts sur l'historique propre.)

**Repartir propre avant l'Acte 2** :
```bash
mise run demo:reset && mise run demo:history
uv run dbt run -s elementary --target prod && uv run dbt test --target prod
```

---

## Acte 2 — N2 : la présence (3 min)

**Objectif** : le contrat peut être respecté par une fiche qui, simplement, n'est plus
synchronisée.

```bash
uv run generator_chaos_late_restaurant
mise run demo:freshness
```
**Résultat attendu** :
```
1 of 1 ERROR STALE freshness of raw_catalog.restaurants
```
**À dire** : « Si on relance `dbt test`, tout reste vert — `unique`, `not_null`,
`accepted_values` ne regardent jamais l'horloge. » (Optionnel : `uv run dbt test --target prod`
pour le prouver — 31/31 PASS malgré la fiche gelée.)

**Repartir propre avant l'Acte 3** :
```bash
mise run demo:reset && mise run demo:history
uv run dbt run -s elementary --target prod
```

---

## Acte 3 — N3 : le twist (8 min)

**Objectif** : LE moment de la démo. N1 + N2 tout verts n'implique pas que les données sont
*plausibles*.

### 3.1 — Le point de départ : tout est vert

```bash
uv run dbt test --target prod
mise run demo:freshness
```
**Résultat attendu** : `PASS=31 WARN=0 ERROR=0 SKIP=0 TOTAL=31`, freshness `PASS`.

**À dire** : « Contrat respecté, référentiel synchronisé. »

### 3.2 — Injecter les deux anomalies (une seule fois, cumulées)

```bash
uv run generator_chaos_new_restaurant_volume
uv run generator_chaos_drop_column
uv run dbt run -s elementary --target prod
uv run dbt test --target prod
```
**Résultat attendu (vérifié)** :
```
FAIL 1 elementary_source_volume_anomalies_raw_orders_orders_30__ordered_at
FAIL 1 elementary_source_schema_changes_from_baseline_raw_catalog_menu_items_True
Done. PASS=29 WARN=0 ERROR=2 SKIP=0 TOTAL=31
```

**À dire, dans cet ordre précis** :
1. « Un restaurant qui vient de s'inscrire a reçu son premier gros volume de commandes hier —
   x10 par rapport à la veille. Est-ce que `unique`, `not_null`, `relationships` ont bougé ?
   Non. Chaque commande, individuellement, est parfaitement valide : le bon restaurant, les
   bons plats, un montant positif. Un seul test regarde la *série temporelle* :
   `elementary.volume_anomalies`. C'est le seul à réagir. »
2. « J'ai aussi retiré une colonne du référentiel restaurants sans prévenir personne —
   `schema_changes_from_baseline` le détecte dès ce premier run, pas besoin d'un deuxième
   passage (contrairement à `schema_changes`, qui exige un changement entre deux runs). »

### 3.3 — (optionnel) Zoomer sur le z-score

```bash
uv run dbt show --target prod --inline \
  "select ordered_at::date as day, count(*) as n from jnadal_db.raw.orders \
   where ordered_at >= dateadd(day, -5, sysdate()::date) group by 1 order by 1"
```
Montrer que le jour du pic est isolé au milieu d'un historique stable — c'est littéralement ce
que le z-score calcule.

---

## Acte 4 — N4 : l'action (5 min)

**Objectif** : une anomalie détectée qui ne réveille personne ne sert à rien.

**Ne PAS resetter avant cette étape** — on veut que les 2 anomalies de l'Acte 3 soient encore
« pending » pour que l'alerte ait quelque chose à envoyer.

```bash
mise run demo:alert
```
**À dire, avant d'exécuter** : « Un seul channel Slack. Le pic de volume appartient à
`raw_orders`, owner Orders (moi). Le changement de schéma touche `raw_catalog`, owner Catalog
(Mathieu). Deux vraies adresses email en subscriber — donc de vraies `@mentions` Slack, pas de
simples libellés. »

**Résultat attendu** : 2 messages dans le channel `demo-data-quality`, un par test en échec,
chacun mentionnant son owner réel (`@mlegall`, `@jnadal` une fois résolus par Slack).

**Ensuite, ouvrir le rapport** :
```bash
mise run webapp:build:force
mise run webapp:serve
```
Naviguer vers `docs/elementary_report/index.html` : historique des tests, résultats des
sources, et — si le rapport le permet — le graphe de la métrique de volume avec le pic visible.

---

## Clôture (1 min)

> On est passé de « tester ce qu'on a anticipé » à « détecter ce qu'on n'avait pas prévu ». Le
> contrat (N1) et la présence (N2) sont nécessaires mais pas suffisants. La plausibilité (N3) a
> besoin d'historique et de statistique. Et rien de tout ça ne compte si l'alerte (N4) ne trouve
> pas la bonne personne.

---

## Annexe A — Les 5 scénarios de chaos, résultats vérifiés

Chaque scénario testé isolément (reset + history avant, `dbt run -s elementary` +
`dbt test`/`demo:freshness` après) casse **exactement** le test attendu, rien d'autre.

| Scénario | Casse | Résultat exact vérifié | Owner |
|---|---|---|---|
| `duplicate_menu_item` | `unique(menu_items.item_id)` | FAIL 1, PASS=30 ERROR=1 SKIP=0 | Catalog |
| `orphan_menu_item` | `relationships(order_lines.item_id → menu_items.item_id)` | FAIL 1, PASS=30 ERROR=1 SKIP=0 | Orders |
| `new_restaurant_volume` | `elementary.volume_anomalies` (`raw_orders.orders`) | FAIL 1, PASS=30 ERROR=1 SKIP=0 | Orders |
| `late_restaurant` | freshness (`raw_catalog.restaurants`, jamais `dbt test`) | ERROR STALE ; `dbt test` reste 31/31 | Catalog |
| `drop_column` | `elementary.schema_changes_from_baseline` (`raw_catalog.menu_items`) | FAIL 1, PASS=30 ERROR=1 SKIP=0 | Catalog |

**`create_chaos`** (les 5 dans l'ordre `duplicate_menu_item → orphan_menu_item →
new_restaurant_volume → late_restaurant → drop_column`) — **vérifié** :
```
dbt test  : PASS=27 WARN=0 ERROR=4 SKIP=0 TOTAL=31   (les 4 tests ci-dessus, hors freshness)
freshness : ERROR STALE sur raw_catalog.restaurants
```
5 signaux au total, aucun de plus.

**Contrainte d'ordre unique, vérifiée par contre-preuve** : `drop_column` doit passer **après**
`duplicate_menu_item` — celui-ci fait un `INSERT` qui liste explicitement la colonne `label`.
Testé dans l'autre sens : `duplicate_menu_item` échoue avec
`SQL compilation error: invalid identifier 'LABEL'` si `drop_column` est passé avant. Les 4
autres scénarios n'ont aucune contrainte d'ordre entre eux (tables/lignes disjointes).

---

## Annexe B — Repli si quelque chose casse en direct

- **Un `dbt test` plante au lieu d'échouer proprement** → basculer sur le rapport déjà généré :
  `mise run webapp:serve`.
- **`mise run demo:alert` ne poste rien** → vérifier `SLACK_BOT_TOKEN` et que le bot est bien
  dans `demo-data-quality` :
  ```bash
  mise exec -- sh -c 'curl -s -X POST https://slack.com/api/chat.postMessage \
    -H "Authorization: Bearer $SLACK_BOT_TOKEN" \
    -d channel=demo-data-quality -d "text=ping"'
  ```
  `"error":"not_in_channel"` → inviter le bot. `"missing_scope"` → il manque `chat:write`,
  `channels:join`/`channels:read`, ou `users:read.email` (nécessaire pour résoudre les
  `@mentions` par email).
- **Besoin de tout remettre à zéro immédiatement** :
  ```bash
  mise run demo:reset && mise run demo:history
  uv run dbt run -s elementary --target prod && uv run dbt test --target prod
  ```
- **Un scénario individuel à rejouer proprement** : toujours repartir d'un `demo:reset &&
  demo:history` avant — les scénarios ne sont conçus isolés que contre un historique frais.
- **Besoin de regénérer le jour même de la présentation, sans attendre le backfill de 30
  jours** : `uv run generator_reset && uv run generator_history --recent-only` (hier +
  aujourd'hui seulement). N1 (`duplicate_menu_item`, `orphan_menu_item`) et N2
  (`late_restaurant`) restent parfaitement démontrables. **Attention** : dans ce mode,
  `elementary.volume_anomalies` échoue systématiquement (faux positif) dès le
  `dbt test` suivant, même sans lancer `new_restaurant_volume` — sa fenêtre de 30 jours
  se retrouve remplie de zéros sur les 29 jours sans commande, donc le volume réel d'hier
  ressort comme un pic. À réserver aux répétitions de l'Acte 1/2, pas de l'Acte 3.
