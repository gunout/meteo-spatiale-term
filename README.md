# 🛰️ SpaceWatch — Météo Spatiale Terminal

> Dashboard terminal de météo spatiale en temps réel
> Données NOAA Space Weather Prediction Center

[![Python](https://img.shields.io/badge/Python-3.9%2B-3776AB?style=flat-square&logo=python&logoColor=white)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg?style=flat-square)](https://opensource.org/licenses/MIT)
[![Data: NOAA SWPC](https://img.shields.io/badge/Data-NOAA%20SWPC-1f6feb?style=flat-square)](https://services.swpc.noaa.gov/)
[![Platform](https://img.shields.io/badge/Platform-Linux%20%7C%20macOS%20%7C%20WSL-2ea44f?style=flat-square)]()
[![Status](https://img.shields.io/badge/Status-Operational-brightgreen?style=flat-square)]()
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg?style=flat-square)](http://makeapullrequest.com)
[![GitHub stars](https://img.shields.io/github/stars/gunout/meteo-spatiale-term?style=flat-square)](https://github.com/gunout/meteo-spatiale-term/stargazers)
[![GitHub issues](https://img.shields.io/github/issues/gunout/meteo-spatiale-term?style=flat-square)](https://github.com/gunout/meteo-spatiale-term/issues)
[![Last commit](https://img.shields.io/github/last-commit/gunout/meteo-spatiale-term?style=flat-square)](https://github.com/gunout/meteo-spatiale-term/commits/main)

---

## 📋 Présentation

**SpaceWatch** est un dashboard terminal qui agrège les **données de météo spatiale en temps réel** de la NOAA (SWPC) dans une interface unique et lisible.

Conçu pour les opérateurs, chercheurs et passionnés qui ont besoin d'une conscience situationnelle immédiate sans navigateur.

---

## ✨ Fonctionnalités

| Fonctionnalité | Description |
|---|---|
| 🌍 **Conditions temps réel** | Kp, vitesse vent solaire, densité, température |
| 🧲 **Champ magnétique** | Bt, Bz, Bx, By en coordonnées GSM |
| 🎯 **Vent solaire propagé** | Mesure L1 → heure d'impact Terre |
| 📊 **Indices géomagnétiques** | Dst (Kyoto), flux F10.7 |
| 📈 **Prévision Kp** | Prévision 3 jours avec priorité G1+ |
| 🚨 **Alertes NOAA** | WATCH / ALERT / CANCEL typées |
| ☀️ **Régions actives** | AR avec aire, classe magnétique, classe de taches |
| 💾 **Export JSON** | Snapshots horodatés + latest.json |
| 🔄 **Mode watch** | Rafraîchissement continu avec détection de changement |
| ⚡ **Zéro dépendance** | Seulement requests |

---

## 🚀 Installation

    git clone https://github.com/gunout/meteo-spatiale-term.git
    cd meteo-spatiale-term
    pip install requests
    chmod +x run.sh
    ./run.sh

---

## 🎮 Utilisation

    ./run.sh                    # Affichage unique
    ./run.sh --watch            # Surveillance continue
    ./run.sh --watch --interval 30 --alert
    ./run.sh --json-only        # Export JSON seul
    ./run.sh --no-export        # Sans export

| Option | Description | Défaut |
|---|---|---|
| --watch | Mode rafraîchissement continu | off |
| --interval N | Intervalle en secondes | 60 |
| --alert | Bip audio sur changement d'état | off |
| --json-only | Export JSON et sortie | off |
| --no-export | Pas d'export JSON | off |

### Cron

    */5 * * * * cd ~/meteo-spatiale-term && ./run.sh --json-only >> cron.log 2>&1

---

## 📊 Sources de données

Toutes les données viennent des endpoints publics **NOAA SWPC** — aucune clé API requise.

| Endpoint | Donnée | Mise à jour |
|---|---|---|
| noaa-planetary-k-index.json | Indice Kp | 1 min |
| noaa-planetary-k-index-forecast.json | Prévision Kp | 3 h |
| rtsw/rtsw_wind_1m.json | Vent solaire (L1) | 1 min |
| rtsw/rtsw_mag_1m.json | Champ magnétique (L1) | 1 min |
| geospace/propagated-solar-wind.json | **Impact Terre** | 1 min |
| goes/primary/xrays-7-day.json | Flux X | 1 min |
| kyoto-dst.json | Indice Dst | 1 h |
| f107_cm_flux.json | Flux F10.7 | quotidien |
| alerts.json | Alertes NOAA | événement |
| solar_regions.json | Régions actives | quotidien |

---

## 📁 Structure du projet

    meteo-spatiale-term/
    ├── spacewatch.py         # Dashboard principal (fichier unique)
    ├── config.json           # Configuration
    ├── run.sh                # Raccourci d'exécution
    ├── README.md             # Ce fichier
    ├── LICENSE               # MIT
    ├── .gitignore            # Exclut exports et caches
    └── export/               # (gitignored) Snapshots JSON
        ├── latest.json       # Snapshot le plus récent
        └── spacewatch_*.json # Historique (50 derniers)

---

## 🎨 Échelles d'alerte

### Tempêtes géomagnétiques (échelle G)

| Niveau | Kp | Description |
|---|---|---|
| **G0** | < 5 | Calme |
| **G1** | 5 | Mineur |
| **G2** | 6 | Modéré |
| **G3** | 7 | Fort |
| **G4** | 8 | Sévère |
| **G5** | 9 | Extrême |

### Éruptions X

| Classe | Flux (W/m²) | Impact |
|---|---|---|
| **A** | < 1e-7 | Fond |
| **B** | 1e-7 – 1e-6 | Mineur |
| **C** | 1e-6 – 1e-5 | Petit |
| **M** | 1e-5 – 1e-4 | Moyen (R1-R2) |
| **X** | > 1e-4 | Grand (R3+) |

---

## ⚠️ Limitations connues

- **Indice AE** — Source (CDAWeb) peut être inaccessible sur certains réseaux
- **F10.7** — Publié avec délai (consolidation quotidienne/mensuelle)
- **NASA DONKI** — Non utilisé (nécessite accès à 169.154.x.x, souvent bloqué)

---

## 🤝 Contribution

1. Fork le dépôt
2. Créer une branche (git checkout -b feature/AmazingFeature)
3. Commit (git commit -m 'Add AmazingFeature')
4. Push (git push origin feature/AmazingFeature)
5. Ouvrir une Pull Request

---

## 📜 Licence

Distribué sous **MIT License**. Voir LICENSE.

---

## 🙏 Remerciements

- [NOAA Space Weather Prediction Center](https://www.swpc.noaa.gov/) — Fournisseur de données
- [Kyoto World Data Center](https://wdc.kugi.kyoto-u.ac.jp/) — Source indice Dst

---

<p align="center">
  <sub>Construit avec ☕ et un sain respect pour l'activité solaire</sub>
</p>
