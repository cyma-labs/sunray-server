# Scénario Sunray — Mode sans extension

## Objectif

Permettre un accès sécurisé à une application protégée par Sunray, sans nécessiter d’extension navigateur, en s'inspirant du fonctionnement de Cloudflare Access mais en introduisant un second facteur (code PIN) et un contrôle de session renforcé.

## Déroulement

1. **Interception de la requête**  
   Lorsqu’un utilisateur tente d’accéder à une application protégée, la requête est interceptée par un **Worker Route Sunray** hébergé chez Cloudflare.

2. **Vérification du jeton d’accès (AccessToken)**  
   Le Worker vérifie si un cookie `AccessToken` est présent et :
   - Est signé,
   - Est valide pour l’adresse IP source,
   - Cible le domaine visé,
   - N’est pas expiré (validité typique : 60 secondes).

3. **Déclenchement de l’authentification**  
   Si le cookie est absent ou invalide, l’utilisateur est redirigé vers une **page d’authentification Sunray**. Cette page :

   3.1 Demande l’adresse email de l’utilisateur.  
   3.2 Le Worker crée un objet **AccessRequest** (IP, email, site cible).  
   3.3 Il chiffre cette requête et envoie un **email sécurisé** à l’utilisateur, contenant plusieurs options d’autorisation :
   - Refuser / Révoquer
   - Autoriser pour 1 heure
   - Autoriser pour 4 heures
   - Autoriser pour 12 heures

   3.4 L’utilisateur clique sur un lien, ce qui ouvre une page HTML hébergée par le Worker.  
   3.5 Il lui est demandé de saisir un **code PIN** (ou code PIN sous contrainte).  
   3.6 Si la saisie échoue plus de 3 fois :
   - Une alerte est envoyée aux administrateurs,
   - L’AccessRequest est révoquée,
   - L’utilisateur est bloqué temporairement.

   3.7 Si la saisie réussit :
   - Le Worker émet un `AccessToken` signé,
   - Ce token est valide 60 secondes,
   - Il est stocké dans un cookie sécurisé (`Secure`, `HttpOnly`).

4. **Renouvellement automatique de l’AccessToken**  
   Lorsqu’une requête est reçue avec un token expiré :
   - Si une **session autorisée** est toujours en cours (durée choisie dans l’email),
   - Et que l’IP source n’a pas changé,
   - Le Worker émet un **nouveau token court** (rolling token),
   - Et le retourne via un `Set-Cookie` HTTP.

   Si la session a expiré ou si l’IP change, l’utilisateur est redirigé vers l’authentification.

## Synthèse des garanties

- L’accès est restreint par domaine, IP et temps.
- Le code PIN est un second facteur local non transitable.
- La saisie sous contrainte permet d’alerter discrètement en cas de coercition.
- Le rolling token limite les effets d’une interception.
- L’utilisateur peut s’authentifier sans logiciel externe ni extension.

## Comparatif de robustesse et de sécurité — Cloudflare Access vs. Sunray

| Critère                                 | Cloudflare Access                     | Sunray (mode sans extension)                                              | Sunray (avec extension)                                                  |
|----------------------------------------|---------------------------------------|---------------------------------------------------------------------------|---------------------------------------------------------------------------|
| **Type d’authentification initiale**   | Basée sur IdP externe (SSO)           | Email + validation par code PIN                                          | Authentification par clé privée (extension)                              |
| **Jeton autoporteur**                  | Oui (JWT)                             | Oui (JWT ou token signé), durée courte                                   | Non (requêtes signées à la volée)                                        |
| **Durée de validité du jeton**         | Jusqu’à 24h                           | 60 secondes, renouvelé automatiquement                                   | N/A (chaque requête est validée par signature)                           |
| **Renouvellement du jeton**            | Aucun, nécessite reconnexion          | Rolling token tant que la session reste valide                           | N/A                                                                       |
| **Vérification de l’IP source**        | Non                                   | Oui                                                                       | Optionnelle                                                               |
| **Ciblage par domaine (`aud`)**        | Oui                                   | Oui                                                                       | Implémenté via filtrage d’URL dans l’extension                           |
| **Stockage côté client**               | Cookie sécurisé (`HttpOnly`, `Secure`)| Identique                                                                 | Clé privée stockée dans l’extension (localStorage ou WebCrypto)          |
| **Protection contre vol de jeton**     | Faible (jeton utilisable tel quel)    | Renforcée (IP + durée courte)                                            | Très forte (aucun jeton exposé, clé privée non exportable)               |
| **Protection contre vol de lien d’accès**| Non (lien suffit)                    | Oui (code PIN requis pour valider l’accès)                               | N/A                                                                       |
| **Protection contre phishing actif**   | Dépend du SSO                         | Partielle : code PIN protège, mais page fausse peut le voler             | Forte (authentification silencieuse, sans interaction manuelle)          |
| **Mécanisme de signal de détresse**    | Non                                   | Oui (code PIN sous contrainte)                                           | Optionnel (via UI de l’extension)                                        |
| **Détection de tentatives d’intrusion**| Non intégré                           | Oui (PIN erroné → alerte + blocage)                                      | Forte (tentatives de signature anormales détectables localement)         |
| **Indépendance vis-à-vis d’un IdP**    | Non (dépend d’un fournisseur SSO)     | Oui (base de données interne, profils locaux)                            | Oui                                                                       |
| **Matériel ou extension requis**       | Non                                   | Non                                                                       | Oui (extension navigateur installée)                                     |
| **Simplicité d’usage utilisateur**     | Très fluide (SSO, peu d’interactions) | Fluide, mais nécessite une validation par mail et saisie de PIN          | Très fluide (aucune interaction utilisateur après installation)          |
| **Souveraineté et maîtrise des données** | Faible (Cloudflare centralise tout) | Forte (clé privée et validation locale dans le Worker)                   | Très forte (clé privée sur le poste utilisateur, contrôle total local)   |