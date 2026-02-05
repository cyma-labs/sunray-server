---
marp: true
theme: default
paginate: true
backgroundColor: #fff
backgroundImage: url('https://marp.app/assets/hero-background.svg')
---

<!-- _class: lead -->

# **Inouk Sunray**
## Solution Européenne et Open Source de Contrôle d'Accès Zero Trust Web

**Protection moderne, souveraine et économique pour vos applications internes et extranets**

🌞 Sécurité sans complexité • Souveraineté sans compromis • Performance native

---

# La Réalité des Cybermenaces en 2025

## **Toute application exposée sur Internet est une cible**

- **Attaques automatisées 24/7** : Bots malveillants scannent en permanence
- **Exploitation immédiate des CVE** : Les failles sont exploitées dans les heures suivant leur publication
- **Sophistication croissante** : IA générative utilisée pour créer des attaques personnalisées
- **Aucune application n'est trop petite** : Même les outils internes sont ciblés

> 💡 **Fait** : Une application lambda reçoit en moyenne de plusieurs centaines à plusieurs milliers de scans / attaques par jour

---

# Le Coût Réel d'un WAF Efficace

## **Protection Enterprise : Un investissement conséquent**

**WAF SaaS/CDN** (Cloudflare, Akamai, AWS, Azure)
- **Business** : 3 000-10 000€/mois
- **Enterprise** : >10 000€/mois

**Appliances/VM** (Fortinet, F5, Barracuda)
- **TCO annuel** : 15 000-50 000€

**Open Source** (ModSecurity)
- **Coût réel** : 35 000-40 000€/an

> ⚠️ **Réalité** : Protection WAF efficace = minimum 15 000€/an par application
> ... et vos données transitent par des infrastructures soumises au Cloud Act américain

---

# Le Dilemme des DSI

## **Protéger sans se ruiner — sans perdre le contrôle de ses données**

### Applications critiques mais à faible valeur ajoutée directe :

- Portails fournisseurs
- Outils de reporting interne
- Applications métier WEB
- Interfaces de gestion WEB
- Extranets partenaires
- Applications soumises au RGPD et à la conformité NIS2

> *"Ces applications ont une audience nominative et connue
> — ont-elles vraiment besoin d'un WAF enterprise américain ?"*

---

# Statistiques Alarmantes (2025)

📊 **Les chiffres qui font peur :**

- **56%** des organisations ont subi une compromission d'application web dans les 12 derniers mois

- **25%** de toutes les violations de sécurité proviennent de failles applicatives

> 💡 **La réalité** : Les applications **à accès nominatif** mal protégées deviennent les portes d'entrée privilégiées des attaquants

---

# Repenser l'Exposition des Applications Web

## **Deux catégories, deux stratégies de protection**

### 🌐 Applications Publiques
- Sites vitrines, e-commerce, portails grand public
- **Tout le monde** doit pouvoir y accéder
- → Nécessitent un **WAF très sophistiqué** (idéalement basé sur l'IA)
- Sans cela, toujours à la merci d'un exploit zero-day

### 🔒 Applications à Accès Nominatif
- Portails fournisseurs, ERP, extranets, outils métier
- Seule une **liste définie d'utilisateurs** doit y accéder
- → Doivent être protégées par une **solution Zero Trust souveraine**
- **C'est exactement pour cela que Sunray a été conçu — en Europe, en Open Source**

> 💡 **Conclusion** : Pourquoi payer un WAF Enterprise pour des applications dont on connaît chaque utilisateur par son nom ?

---

# Sunray — La Solution Zero Trust pour vos Applications Web à Accès Nominatif

## **Protection Enterprise Souveraine à Prix Accessible**

*Pour vos applications à accès nominatif, une approche Zero Trust est plus efficace et plus économique qu'un WAF*

### Notre approche :
✅ **Open Source** : Transparence totale, pas de vendor lock-in
✅ **Souveraineté européenne** : Conçu en Europe, hébergé où vous le décidez
✅ **Surface d'attaque minimale** : Architecture serverless native
✅ **Authentification moderne** : Passkeys/WebAuthn (biométrie)
✅ **Scalabilité native** : De 10 à "x millions" d'utilisateurs
✅ **Déploiement sans modification** : Vos applications restent intactes

### Résultat :
**Division des coûts par 10** tout en maintenant un niveau de sécurité enterprise

---

# Souveraineté Numérique : Un Impératif Européen

## **Vos données, vos règles, votre infrastructure**

### 📜 Le contexte réglementaire européen :
- **RGPD** : Protection des données personnelles — amendes jusqu'à 4% du CA mondial
- **Directive NIS2** (oct. 2024) : Obligations de cybersécurité renforcées
- **Arrêt Schrems II** : Transferts de données UE→US remis en question

### ⚠️ Le problème des solutions américaines :
- **Cloud Act / FISA 702** : Les autorités US peuvent exiger l'accès aux données, même hébergées en Europe
- Cloudflare Access, Zscaler, Okta, Auth0 : toutes soumises à la juridiction américaine

### 🇪🇺 Sunray : la réponse européenne
- **Conçu et développé en Europe**
- **Code source ouvert** : Auditabilité totale, aucune porte dérobée possible
- **Déploiement souverain** : Vos données ne quittent jamais votre infrastructure
- **Aucune dépendance envers un fournisseur non-européen** (option FastAPI)

> 💡 *"La souveraineté numérique n'est pas un luxe — c'est une responsabilité."*

---

# Deux Versions pour Tous les Besoins

## **Choisissez votre niveau de souveraineté**

#### 🏢 **Sunray Worker FASTAPI**
- **Souveraineté totale** : Aucune donnée ne quitte votre infrastructure
- Déploiement on-premise ou cloud européen de votre choix
- Intégration native Kubernetes/Traefik
- Conforme RGPD et NIS2 par conception
- Idéal pour : Applications sensibles, secteur public, banques, santé

#### 🌍 **Sunray Worker for Cloudflare**
- Performance globale maximale (150+ PoP mondiaux)
- Protection DDoS incluse (Cloudflare)
- Latence minimale
- Le serveur Sunray reste sous votre contrôle, jamais exposé
- Idéal pour : Applications globales, SaaS, sites à fort trafic

> 📌 **Dans les deux cas**, le serveur Sunray (cœur décisionnaire) reste entièrement sous votre contrôle et n'est jamais exposé sur Internet

---

# Architecture Zero Trust

## **Secure by Design**

```
Internet → [Sunray Worker]     →    Application
            - Interception
            - Edge Protection
                ↓
           [Sunray Server]
            - Décision Policy
            (Jamais exposé)
```
### Principes clés :  **Aucune confiance par défaut !**
1. **Serveur isolé** : Décisions critiques jamais exposées
2. **Workers stateless** : Aucune donnée sensible en périphérie
3. **Authentification forte** : Biométrie via Passkeys
4. **Souveraineté architecturale** : Le serveur décisionnaire reste dans votre infrastructure, aucune dépendance cloud obligatoire

---

# Fonctionnalités Clés

## **Tout ce dont vous avez besoin**

### 🔐 Contrôle d'accès
- Authentification sans mot de passe (Passkeys)
- Règles d'accès granulaires, support API/Webhooks natif

### 🛡️ Sécurité
- Protection Zero-Day complète, Audit trail complet

### 🎯 Simplicité
- Interface graphique évoluée, Configuration centralisée, Aucune modification des applications

### 🏛️ Conformité
- Compatible RGPD et NIS2, Audit trail complet, Déploiement souverain on-premise

---

# Cas d'Usage Typiques

#### ✅ **Parfait pour vos applications à accès nominatif :**
- **Portails clients/fournisseurs** : Accès sécurisé sans VPN
- **Applications métier** : ERP, CRM, outils internes exposés
- **APIs et webhooks** : Protection transparente des échanges M2M
- **Sites de staging** : Sécurisation des environnements de test
- **Extranets** : Collaboration sécurisée avec les partenaires
- **Applications réglementées** : Santé, finance, secteur public — conformité RGPD/NIS2 native

#### 💰 **ROI immédiat :**
- Réduction de 90% des coûts vs WAF traditionnel
- Déploiement en moins de 2 heures, Zéro modification du code existant

---

# Comparaison avec la Concurrence

| Critère | WAF Enterprise | VPN | Sunray |
|---------|---------------|-----|--------|
| **Coût mensuel** | 5000-15000€ | 500-2000€ | **50-500€** |
| **Complexité** | Élevée | Moyenne | **Faible** |
| **Modification apps** | Parfois | Non | **Jamais** |
| **Protection Zero-Day** | ✅ | ❌ | **✅** |
| **Expérience utilisateur** | Transparente | Contraignante | **Transparente** |
| **Scalabilité** | Coûteuse | Limitée | **Native** |
| **Open Source** | ❌ | Parfois | **✅** |
| **Souveraineté données** | ❌ (US) | Partielle | **✅ (FastAPI)** |
| **Conformité RGPD/NIS2** | Complexe | Partielle | **Native** |

> 📌 **Sunray ne remplace pas un WAF pour les applications publiques — il élimine le besoin d'un WAF pour les applications à accès nominatif, tout en garantissant la souveraineté de vos données**

---

# Architecture Technique

## **Simple mais Puissant**

### **Sunray Server** (Odoo 18)
- Gestion centralisée des politiques
- Interface d'administration web
- API REST complète
- Déploiement on-premise ou cloud souverain européen

### **Sunray Worker** (Edge)
- Interception des requêtes
- Validation des sessions / Access Rules
- Reporting temps réel

---

# Modèle de Licence

## **Choisissez votre niveau de support**

### 🆓 **Sunray Core** (Open Source)
- Fonctionnalités de base, Authentification Passkeys, Community support

### 💼 **Sunray Advanced** (Licence)
- Règles d'accès avancées, Audit log complet, Support professionnel

### 🏢 **Sunray Enterprise** (Package complet)
- Services professionnels, Formation et onboarding, Support dédié

---

# Roadmap Produit 2025-2026

## **Notre Vision**

### ✅ **Disponible aujourd'hui**
- Sunray Worker FASTAPI, Sunray Worker for Cloudflare, Authentification Passkeys et Mail, Multi hosts, API REST

### 🚧 **T2 2026**
- Analytics dashboard

### 🔮 **T3-T4 2026**
- Certifications de conformité (SOC2, ISO27001)
- Qualification SecNumCloud (ANSSI)

---

<!-- _class: lead -->

# **Protégez vos Applications dès Aujourd'hui**

## 🚀 **Essai Gratuit 30 jours**

### 📞 **Contact**
**Email** : cmorisse@oursbl.eu
**Source** : gitlab.com/cmorisse/inouk-sunray-server

### 💡 **Prochaines étapes**
1. Proof of Concept sur application pilote
2. Déploiement en production
3. Évaluation de conformité RGPD/NIS2

> *"Security is a pain, not a feature — so let's make it affordable, sovereign, and invisible."*
