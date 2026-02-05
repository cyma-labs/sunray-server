---
marp: true
theme: default
paginate: true
backgroundColor: #fff
backgroundImage: url('https://marp.app/assets/hero-background.svg')
---

<!-- _class: lead -->

# **Inouk Sunray**
## Solution Open Source de Contrôle d'Accès Zero Trust Web

**Protection moderne et économique pour vos applications internes et extranets**

🌞 Sécurité sans complexité • Performance sans compromis

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

---

# Le Dilemme des DSI

## **Protéger sans se ruiner**

### Applications critiques mais à faible valeur ajoutée directe :

- Portails fournisseurs
- Outils de reporting interne
- Applications métier WEB
- Interfaces de gestion WEB
- Extranets partenaires

> *"Ces applications sont indispensables au fonctionnement de l'entreprise,
> mais leur budget ne permet pas une protection WAF enterprise"*

---

# Statistiques Alarmantes (2025)

📊 **Les chiffres qui font peur :**

- **56%** des organisations ont subi une compromission d'application web dans les 12 derniers mois

- **25%** de toutes les violations de sécurité proviennent de failles applicatives

> 💡 **La réalité** : Les applications "secondaires" mal protégées deviennent les portes d'entrée privilégiées des attaquants

---

# Sunray - La Solution pragmatique de Contrôle d'Accès Zero Trust Web

## **Protection Enterprise à Prix Accessible**

### Notre approche :
✅ **Open Source** : Transparence totale, pas de vendor lock-in
✅ **Surface d'attaque minimale** : Architecture serverless native
✅ **Authentification moderne** : Passkeys/WebAuthn (biométrie)
✅ **Scalabilité native** : De 10 à "x millions" d'utilisateurs
✅ **Déploiement sans modification** : Vos applications restent intactes

### Résultat :
**Division des coûts par 10** tout en maintenant un niveau de sécurité enterprise

---

# Deux Versions pour Tous les Besoins

## **Choisissez votre niveau de souveraineté**

#### 🏢 **Sunray Worker FASTAPI**
- Souveraineté totale des données
- Déploiement on-premise
- Intégration native Kubernetes/Traefik
- Idéal pour : Applications sensibles, conformité RGPD strict

#### 🌍 **Sunray Worker for Cloudflare**
- Performance globale maximale
- Protection DDoS incluse (Cloudflare)
- Latence minimale (150+ PoP mondiaux)
- Idéal pour : Applications globales, SaaS, sites publics

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

---

# Cas d'Usage Typiques

#### ✅ **Parfait pour :**
- **Portails clients/fournisseurs** : Accès sécurisé sans VPN
- **Applications métier** : ERP, CRM, outils internes exposés
- **APIs et webhooks** : Protection transparente des échanges M2M
- **Sites de staging** : Sécurisation des environnements de test
- **Extranets** : Collaboration sécurisée avec les partenaires

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

---

# Architecture Technique

## **Simple mais Puissant**

### **Sunray Server** (Odoo 18)
- Gestion centralisée des politiques
- Interface d'administration web
- API REST complète

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

### 🔮 **T3-T3 2026**
- Compliance (SOC2, ISO27001)

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

> *"Security is a pain, not a feature — so let’s make it affordable, usable, and invisible."*