### Intro
* La présentation fait suite au premier meeting du SUGA en novembre 2025 dans lequel plusieurs boites (Floa, Technique Solaire, DomoFrance) avaient montré des outils de data quality dont SODA et DMF de Snowflake. 
* A mon avis, ces frameworks avec Great Expectations sont un peu compliqués à l'utilisation et je voulais montrer ce que nous mettons souvent en place chez nos clients

### Présentation du projet
* Montrer le repo [dbt-data-quality](https://github.com/Jeremynadal33/dbt-data-quality)
* Montrer la web app qui aura été générée la veille avec tous les tests au vert (https://jeremynadal33.github.io/dbt-data-quality/)
* Montrer l'état des tables dans snowflake
* expliquer dbt TRES RAPIDEMENT 
* expliquer compilation dans dbt
* Expliquer que les tests dbt ressortent les lignes qui ne sont pas compliant avec le test
* diffférence entre test unitaire, data test, test generic, test venant de package, test custom generic comme is_positive
* store failures et commande dans elementary
* Bien faire la différence entre le package dbt elementary et la cli elementary 
* Optional : comment fonctionne la cli elementary ? Package Python qui orchestre des macros dbt qui lance des query sur les tables générées par le package dbt elementary et qui vient construire un site statique ou envoyer des alertes


### Ouverture
* dbt charts : https://dbtcharts.com/ 
* dbt unit_tests : https://docs.getdbt.com/docs/build/unit-tests?version=2
* dbt x metric flow & semantic layer : https://docs.getdbt.com/docs/build/build-metrics-intro?version=2 
* widely used & community => easy to recrute & loads of ready to use packages