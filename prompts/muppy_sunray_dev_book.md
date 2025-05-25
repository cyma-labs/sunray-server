# Muppy Sunray — Journal de développement

> 📝 Note : Le projet Muppy Sunray repose sur un principe de souveraineté technologique. Le développement initial sera hébergé sur GitLab, avec une éventuelle migration vers GitHub prévue à des fins de diffusion open source plus large.

## Prochaines étapes

- [x] 🎯 **Définir le format final du fichier YAML**
  - [x] Ajouter un champ `version` explicite dans le fichier YAML
  - [x] Validation de schéma (JSON Schema ou équivalent)

- [ ] 🛠 **Développer le Worker Cloudflare**
  - [ ] Charger et parser la configuration YAML statique
  - [ ] Extraire domaine, IP, headers, signature depuis les requêtes
  - [ ] Appliquer les règles `allowed_ips` et `allowed_paths`
  - [ ] Vérifier les signatures ED25519 des en-têtes `X-MPY-SUNRAY`

- [ ] 🧩 **Développer l’extension Chrome**
  - [ ] Génération de la paire de clés ED25519 à l’installation
  - [ ] Signature des requêtes avec `username:timestamp`
  - [ ] Stockage local (clé privée) via `chrome.storage.local`
  - [ ] UI minimale : affichage de la clé publique et configuration du username

- [ ] 🔐 **Utilitaire CLI ou outil web pour générer une entrée utilisateur**
  - [ ] Entrée : username, clé publique
  - [ ] Sortie : bloc YAML prêt à intégrer

- [ ] 🔬 **Tests et validation**
  - [ ] Écriture de scénarios : valid auth, invalid token, bypass via IP/header
  - [ ] Tests manuels via `curl`, Postman, puis automatisés

- [ ] 📦 **Distribution open source**
  - [ ] Dépôt GitHub avec licence, README, mode d'emploi
  - [ ] Exemple de déploiement avec wrangler + YAML

- [ ] 🧪 **Améliorations futures**
  - [ ] Signature HTTP complète (optionnelle)
  - [ ] Expiration des clés, révocation
  - [ ] UI de gestion centralisée (facultative)