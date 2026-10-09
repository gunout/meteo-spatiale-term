#!/usr/bin/env python3
"""
SPACEWATCH — Dashboard terminal de meteo spatiale (NOAA SWPC)
Sources : NOAA Space Weather Prediction Center uniquement.
Export JSON horodate dans ./export/
"""

import os
import json
import time
import shutil
import argparse
import requests
from datetime import datetime, timezone
from pathlib import Path

# --- Chemins ---
BASE_DIR = Path(__file__).resolve().parent
CACHE_DIR = BASE_DIR / "cache"
EXPORT_DIR = BASE_DIR / "export"
CONFIG_PATH = BASE_DIR / "config.json"
CACHE_DIR.mkdir(exist_ok=True)
EXPORT_DIR.mkdir(exist_ok=True)

# --- Config ---
def load_config():
    defaults = {
        "sources": {"noaa_swpc": "https://services.swpc.noaa.gov"},
        "refresh_seconds": 60,
        "timeout_seconds": 20,
        "noaa_endpoints": {
            "kp": "products/noaa-planetary-k-index.json",
            "kp_forecast": "products/noaa-planetary-k-index-forecast.json",
            "wind": "json/rtsw/rtsw_wind_1m.json",
            "mag": "json/rtsw/rtsw_mag_1m.json",
            "propagated": "products/geospace/propagated-solar-wind.json",
            "xray": "json/goes/primary/xrays-7-day.json",
            "dst": "products/kyoto-dst.json",
            "f107": "json/f107_cm_flux.json",
            "alerts": "products/alerts.json",
            "regions": "json/solar_regions.json",
        },
        "export": {"enabled": True, "keep_last": 50},
    }
    if CONFIG_PATH.exists():
        try:
            user = json.loads(CONFIG_PATH.read_text())
            for k, v in user.items():
                if isinstance(v, dict) and k in defaults:
                    defaults[k].update(v)
                else:
                    defaults[k] = v
        except Exception as e:
            print(f"[!] config.json illisible ({e}), defauts utilises.")
    return defaults

CFG = load_config()
SWPC = CFG["sources"]["noaa_swpc"]
TIMEOUT = CFG.get("timeout_seconds", 20)

# --- ANSI ---
R = "\033[0m"; BOLD = "\033[1m"; DIM = "\033[2m"
RED = "\033[91m"; YEL = "\033[93m"; GRN = "\033[92m"
CYA = "\033[96m"; MAG = "\033[95m"; WHT = "\033[97m"
BG_RED = "\033[41m"; BG_YEL = "\033[43m"; BG_GRN = "\033[42m"

def term_width():
    return shutil.get_terminal_size((110, 30)).columns

def hr(char="─"):
    return char * term_width()

def header(title):
    w = term_width()
    inner = max(w - 4, len(title) + 2)
    return (f"\n{BOLD}{CYA}┌{'─' * (inner + 2)}┐{R}\n"
            f"{BOLD}{CYA}│ {title:<{inner}} │{R}\n"
            f"{BOLD}{CYA}└{'─' * (inner + 2)}┘{R}")

def now_utc():
    return datetime.now(timezone.utc)

def fetch_json(url, timeout=None):
    timeout = timeout or TIMEOUT
    try:
        r = requests.get(url, timeout=timeout,
                         headers={"User-Agent": "SpaceWatch/3.0"})
        r.raise_for_status()
        return r.json()
    except Exception as e:
        return {"_error": str(e)[:80]}

def fetch_text(url, timeout=None):
    timeout = timeout or TIMEOUT
    try:
        r = requests.get(url, timeout=timeout,
                         headers={"User-Agent": "SpaceWatch/3.0"})
        r.raise_for_status()
        return r.text
    except Exception:
        return ""

def _age_minutes(iso_time):
    """Age en minutes d'un timestamp ISO. Retourne None si invalide."""
    if not iso_time:
        return None
    try:
        t = iso_time.replace("Z", "+00:00")
        dt = datetime.fromisoformat(t)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        delta = (now_utc() - dt).total_seconds() / 60.0
        return max(0, int(delta))
    except Exception:
        return None

def _age_str(iso_time):
    """Retourne une chaine lisible : 'il y a X min'."""
    m = _age_minutes(iso_time)
    if m is None:
        return "?"
    if m < 1:
        return "a l'instant"
    if m < 60:
        return f"il y a {m} min"
    h = m // 60
    return f"il y a {h} h {m % 60} min"

def _num(v):
    """Convertit en float ou None."""
    try:
        return float(v)
    except (TypeError, ValueError):
        return None

# ============================================================
#  COLLECTE NOAA SWPC
# ============================================================
def fetch_realtime():
    """Donnees temps reel NOAA SWPC. Tolerant aux 2 formats JSON."""
    ep = CFG["noaa_endpoints"]
    data = {}

    # --- Kp (format 2026 : liste de dicts avec 'Kp' et 'time_tag') ---
    kp = fetch_json(f"{SWPC}/{ep['kp']}")
    if isinstance(kp, list) and kp:
        last = kp[-1]
        if isinstance(last, dict):
            data["kp"] = {"value": last.get("Kp"),
                          "time": last.get("time_tag")}
        elif isinstance(last, list) and len(last) >= 2:
            data["kp"] = {"value": last[1], "time": last[0]}

    # --- Vent solaire RTSW (liste de dicts avec 'active', 'proton_speed') ---
    wind = fetch_json(f"{SWPC}/{ep['wind']}")
    if isinstance(wind, list) and wind:
        got = False
        for row in reversed(wind):
            if isinstance(row, dict) and row.get("active", True):
                sp = _num(row.get("proton_speed"))
                if sp is not None:
                    data["wind"] = {
                        "speed": sp,
                        "density": _num(row.get("proton_density")),
                        "temp": _num(row.get("proton_temperature")),
                        "time": row.get("time_tag"),
                        "source": row.get("source", "?"),
                    }
                    got = True
                    break
        if not got:
            last = wind[-1]
            if isinstance(last, list) and len(last) >= 3:
                data["wind"] = {
                    "speed": _num(last[2]),
                    "density": _num(last[1]),
                    "temp": _num(last[3]) if len(last) > 3 else None,
                    "time": last[0],
                    "source": "?",
                }

    # --- Champ magnetique RTSW (liste de dicts avec 'bz_gsm', 'bt') ---
    mag = fetch_json(f"{SWPC}/{ep['mag']}")
    if isinstance(mag, list) and mag:
        got = False
        for row in reversed(mag):
            if isinstance(row, dict) and row.get("active", True):
                bz = _num(row.get("bz_gsm"))
                if bz is not None:
                    data["mag"] = {
                        "bx": _num(row.get("bx_gsm")),
                        "by": _num(row.get("by_gsm")),
                        "bz": bz,
                        "bt": _num(row.get("bt")),
                        "time": row.get("time_tag"),
                        "source": row.get("source", "?"),
                    }
                    got = True
                    break
        if not got:
            last = mag[-1]
            if isinstance(last, list) and len(last) >= 7:
                data["mag"] = {
                    "bx": _num(last[1]),
                    "by": _num(last[2]),
                    "bz": _num(last[3]),
                    "bt": _num(last[6]),
                    "time": last[0],
                    "source": "?",
                }

    # --- Rayons X GOES (0.1-0.8 nm) ---
    xray = fetch_json(f"{SWPC}/{ep['xray']}")
    if isinstance(xray, list):
        for entry in reversed(xray):
            if isinstance(entry, dict) and entry.get("energy") == "0.1-0.8nm":
                data["xray"] = {"flux": _num(entry.get("flux")),
                                "time": entry.get("time_tag")}
                break

    return data

def fetch_propagated():
    """Vent solaire propage : conditions attendues a l'impact Terre."""
    data = fetch_json(f"{SWPC}/{CFG['noaa_endpoints']['propagated']}")
    if not isinstance(data, list) or len(data) < 2:
        return None
    # data[0] = header, data[1..] = lignes
    # Colonnes : time_tag, speed, density, temperature, bx, by, bz, bt, vx, vy, vz, propagated_time_tag
    last = data[-1]
    if not isinstance(last, list) or len(last) < 12:
        return None
    return {
        "time_tag": last[0],              # Heure mesure a L1
        "speed": _num(last[1]),
        "density": _num(last[2]),
        "temperature": _num(last[3]),
        "bx": _num(last[4]),
        "by": _num(last[5]),
        "bz": _num(last[6]),
        "bt": _num(last[7]),
        "propagated_time_tag": last[11],  # Heure arrivee Terre
    }

def fetch_alerts():
    """Alertes et warnings actifs NOAA SWPC."""
    alerts = fetch_json(f"{SWPC}/{CFG['noaa_endpoints']['alerts']}")
    if not isinstance(alerts, list):
        return []
    return alerts[-10:] if len(alerts) > 10 else alerts

def fetch_kp_forecast():
    """Prevision Kp 3 jours. Tri decroissant + priorite aux entrees futures."""
    forecast = fetch_json(f"{SWPC}/{CFG['noaa_endpoints']['kp_forecast']}")
    if not isinstance(forecast, list) or not forecast:
        return []
    out = []
    for row in forecast:
        if isinstance(row, dict):
            out.append({
                "time": row.get("time_tag") or row.get("time"),
                "kp": _num(row.get("kp") or row.get("Kp")),
                "observed": str(row.get("observed", "")).lower(),
                "scale": row.get("noaa_scale") or "",
            })

    # Priorite : entrees futures (predicted)
    predicted = [r for r in out if r["observed"] == "predicted"]
    if predicted:
        # Trie par date, mais met en avant les Kp >= 5 (alertes G1+)
        predicted.sort(key=lambda x: x["time"] or "")
        alerts = [r for r in predicted if (r["kp"] or 0) >= 5]
        rest = [r for r in predicted if (r["kp"] or 0) < 5]
        return alerts + rest[:20]

    # Fallback : entrées estimees ou observees, plus recentes d'abord
    out.sort(key=lambda x: x["time"] or "", reverse=True)
    return out[:12]

def fetch_solar_regions():
    """Regions actives (JSON 2026). Garde la date la plus recente par region."""
    data = fetch_json(f"{SWPC}/{CFG['noaa_endpoints']['regions']}")
    if not isinstance(data, list) or not data:
        return []

    # Groupe par region, garde l'entree avec observed_date la plus recente
    by_region = {}
    for r in data:
        if not isinstance(r, dict):
            continue
        num = r.get("region")
        if num is None:
            continue
        date = r.get("observed_date", "")
        key = str(num)
        if key not in by_region or date > by_region[key].get("observed_date", ""):
            by_region[key] = r

    regions = []
    for num, r in by_region.items():
        area = r.get("area")
        regions.append({
            "num": num,
            "location": r.get("location", "?"),
            "area": str(area) if area is not None else "0",
            "mag_class": r.get("mag_class", "?") or "?",
            "spot_class": r.get("spot_class", "?"),
        })

    # Tri par aire decroissante (les plus grosses d'abord)
    def _area_key(x):
        try:
            return -int(x["area"])
        except (ValueError, TypeError):
            return 0
    regions.sort(key=_area_key)
    return regions[:12]

def fetch_omni_indices():
    """Dst (Kyoto/NOAA) + F10.7 (NOAA). AE indisponible (CDAWeb bloque)."""
    ep = CFG["noaa_endpoints"]
    out = {}

    # --- Dst (Kyoto mirror NOAA) ---
    dst = fetch_json(f"{SWPC}/{ep['dst']}")
    if isinstance(dst, list) and dst:
        for row in reversed(dst):
            if isinstance(row, list) and len(row) >= 2:
                v = _num(row[1])
                if v is not None:
                    out["dst"] = {"value": v, "time": row[0]}
                    break
            elif isinstance(row, dict):
                v = _num(row.get("dst") or row.get("value"))
                if v is not None:
                    out["dst"] = {"value": v,
                                  "time": row.get("time_tag")}
                    break

    # --- F10.7 ---
    f107 = fetch_json(f"{SWPC}/{ep['f107']}")
    if isinstance(f107, list) and f107:
        for row in reversed(f107):
            if isinstance(row, dict):
                v = _num(row.get("flux") or row.get("f107") or row.get("value"))
                if v is not None:
                    out["f107"] = {"value": v, "time": row.get("time_tag")}
                    break
            elif isinstance(row, list) and len(row) >= 2:
                v = _num(row[1])
                if v is not None:
                    out["f107"] = {"value": v, "time": row[0]}
                    break

    out["ae"] = {"error": "source bloquee (CDAWeb)"}
    return out

# ============================================================
#  CLASSIFICATIONS
# ============================================================
def classify_xray(flux):
    if flux is None:
        return "?", DIM
    if flux >= 1e-4: return "X", f"{BOLD}{BG_RED}{WHT}"
    if flux >= 1e-5: return "M", f"{BOLD}{RED}"
    if flux >= 1e-6: return "C", YEL
    if flux >= 1e-7: return "B", CYA
    return "A", DIM

def classify_kp(kp):
    if kp is None:
        return "?", DIM
    if kp >= 7: return "G3+", f"{BOLD}{BG_RED}{WHT}"
    if kp >= 6: return "G2", f"{BOLD}{RED}"
    if kp >= 5: return "G1", YEL
    return "G0", GRN

# ============================================================
#  RENDU
# ============================================================
def fmt(v, suffix=""):
    if v is None:
        return "?"
    if isinstance(v, float):
        return f"{v:.1f}{suffix}"
    return f"{v}{suffix}"

def render_realtime(rt, prop=None):
    """Conditions temps reel. Utilise propage si dispo (plus frais)."""
    lines = [header("🌍 CONDITIONS TEMPS RÉEL — NOAA SWPC")]

    # --- Source : propage prioritaire ---
    src_data = None
    src_label = ""
    src_time = None
    if prop and prop.get("speed") is not None:
        src_data = prop
        src_label = "PROPAGÉ (arrivée Terre)"
        src_time = prop.get("propagated_time_tag")
    else:
        src_data = rt
        src_label = "RTSW (L1)"
        src_time = rt.get("wind", {}).get("time")

    # --- Kp (toujours depuis rt, pas dans propage) ---
    kp_val = rt.get("kp", {}).get("value")
    kp_code, kp_color = classify_kp(kp_val)
    lines.append(f"  {BOLD}Kp planétaire{R}   {kp_color}{fmt(kp_val):>5}  [{kp_code}]{R}   "
                 f"{DIM}{rt.get('kp', {}).get('time', '?')}{R}")

    # --- Vent solaire (propage si dispo) ---
    if src_data is rt:
        w = rt.get("wind", {})
        lines.append(f"  {BOLD}Vent solaire{R}    {fmt(w.get('speed')):>7} km/s   "
                     f"densité {fmt(w.get('density')):>6} p/cc   "
                     f"temp {fmt(w.get('temp')):>8} K   "
                     f"{DIM}{w.get('time', '?')} src={w.get('source', '?')}{R}")
    else:
        lines.append(f"  {BOLD}Vent solaire{R}    {fmt(src_data.get('speed')):>7} km/s   "
                     f"densité {fmt(src_data.get('density')):>6} p/cc   "
                     f"temp {fmt(src_data.get('temperature')):>8} K   "
                     f"{CYA}{src_label}{R}")

    # --- Champ magnetique ---
    if src_data is rt:
        m = rt.get("mag", {})
        bz = m.get("bz")
        bz_color = GRN if (bz is not None and bz < 0) else R
        lines.append(f"  {BOLD}Champ mag.{R}      Bt {fmt(m.get('bt')):>5} nT   "
                     f"Bz {bz_color}{fmt(bz):>5}{R} nT   "
                     f"Bx {fmt(m.get('bx')):>5}  By {fmt(m.get('by')):>5}   "
                     f"{DIM}{m.get('time', '?')} src={m.get('source', '?')}{R}")
    else:
        bz = src_data.get("bz")
        bz_color = GRN if (bz is not None and bz < 0) else R
        lines.append(f"  {BOLD}Champ mag.{R}      Bt {fmt(src_data.get('bt')):>5} nT   "
                     f"Bz {bz_color}{fmt(bz):>5}{R} nT   "
                     f"Bx {fmt(src_data.get('bx')):>5}  By {fmt(src_data.get('by')):>5}   "
                     f"{CYA}{src_label}{R}")

    # --- Horodatage de fraicheur ---
    if src_time:
        age = _age_str(src_time)
        lines.append(f"  {DIM}Fraîcheur source : {age} ({src_time}){R}")

    # --- Rayons X (toujours depuis rt) ---
    x = rt.get("xray", {})
    flux = x.get("flux")
    if flux is not None:
        cls, color = classify_xray(flux)
        lines.append(f"  {BOLD}Rayons X{R}         {color}{cls}{R}   "
                     f"{flux:.2e} W/m²   {DIM}{x.get('time', '?')} "
                     f"({_age_str(x.get('time'))}){R}")
    else:
        lines.append(f"  {BOLD}Rayons X{R}         {DIM}indisponible{R}")

    return "\n".join(lines)

def render_propagated(prop):
    """Bandeau 'arrivee Terre' : uniquement l'info de timing."""
    if not prop:
        return ""
    measured = prop.get("time_tag", "?")
    impact = prop.get("propagated_time_tag", "?")
    lines = [header("🎯 VENT SOLAIRE PROPAGÉ — ARRIVÉE TERRE")]
    lines.append(f"  {BOLD}Mesuré à L1{R}      {DIM}{measured}{R}")
    lines.append(f"  {BOLD}Arrivée Terre{R}    {BOLD}{YEL}{impact}{R}")
    age_l1 = _age_str(measured)
    lines.append(f"  {DIM}Délai mesure → impact : ~{_age_minutes(measured) or '?'} min "
                 f"de transit L1→Terre{R}")
    lines.append(f"  {DIM}Fraîcheur mesure L1   : {age_l1}{R}")
    return "\n".join(lines)

def render_omni(omni):
    lines = [header("📊 INDICES GÉOMAGNÉTIQUES — Dst / F10.7 (NOAA)")]
    rows = [
        ("Dst",   "dst",  "nT",  "Ring current (Kyoto)"),
        ("F10.7", "f107", "sfu", "Flux radio solaire 10.7cm"),
        ("AE",    "ae",   "nT",  "Auroral electrojet"),
    ]
    for label, key, unit, desc in rows:
        entry = omni.get(key, {})
        val = entry.get("value")
        t = entry.get("time", "?")
        err = entry.get("error")
        if err:
            lines.append(f"  {BOLD}{label:<7}{R} {DIM}non disponible ({err}){R}")
        elif val is not None:
            if key == "dst":
                color = (f"{BOLD}{RED}" if val < -50
                         else YEL if val < -20 else GRN)
            else:
                color = CYA
            lines.append(f"  {BOLD}{label:<7}{R} {color}{val:>8.1f}{R} {unit:<5} "
                         f"{DIM}{desc:<28} {t}{R}")
        else:
            lines.append(f"  {BOLD}{label:<7}{R} {DIM}indisponible{R}")
    return "\n".join(lines)

def render_kp_forecast(forecast, limit=8):
    lines = [header("📈 PRÉVISION Kp — 3 PROCHAINS JOURS")]
    if not forecast:
        lines.append(f"  {DIM}Prévision indisponible.{R}")
        return "\n".join(lines)
    lines.append(f"  {DIM}{'HEURE UTC':<22}{'Kp':<6}{'ÉCHELLE':<10}{'STATUT'}{R}")
    for f in forecast[:limit]:
        kp = f["kp"]
        scale, color = classify_kp(kp)
        scale_txt = f["scale"] if f["scale"] not in (None, "", "none") else scale
        status = "PRÉVU" if f["observed"] == "predicted" else "OBSERVÉ"
        lines.append(f"  {f['time']:<22}{color}{fmt(kp):<6}{R}"
                     f"{scale_txt:<10}{DIM}{status}{R}")
    return "\n".join(lines)

def render_alerts(alerts, limit=8):
    lines = [header("🚨 ALERTES & WARNINGS — NOAA SWPC")]
    if not alerts:
        lines.append(f"  {DIM}Aucune alerte active.{R}")
        return "\n".join(lines)

    for a in alerts[-limit:]:
        msg = a.get("message", "").strip()
        issue = a.get("issue_datetime", "")
        kind = ""
        detail = ""
        for line in msg.splitlines():
            line = line.strip()
            if not line:
                continue
            for prefix in ("ALERT:", "WARNING:", "WATCH:", "SUMMARY:",
                           "EXTENDED WARNING:", "CANCEL"):
                if line.upper().startswith(prefix):
                    kind = prefix.rstrip(":")
                    detail = line[len(prefix):].strip()
                    break
            if kind:
                break
        if not kind:
            for line in msg.splitlines():
                line = line.strip()
                if line and not line.startswith(("Space", "Space Weather",
                                                 "NOAA", "SWPC", "-----",
                                                 "Serial Number")):
                    detail = line
                    break

        k = kind.upper()
        if "WARNING" in k or "ALERT" in k:
            color = f"{BOLD}{RED}"
        elif "WATCH" in k:
            color = YEL
        elif "SUMMARY" in k or "EXTENDED" in k:
            color = CYA
        else:
            color = DIM
        tag = f"{color}[{kind}]{R}" if kind else f"{DIM}[info]{R}"
        lines.append(f"  {tag} {DIM}{issue[:16]}{R} {detail[:80]}")
    return "\n".join(lines)

def render_regions(regions, limit=12):
    lines = [header("☀️  RÉGIONS ACTIVES SOLAIRES")]
    if not regions:
        lines.append(f"  {DIM}Aucune région active détectée.{R}")
        return "\n".join(lines)
    lines.append(f"  {DIM}{'NUM':<8}{'LOC':<12}{'AIRE':<8}{'MAG':<6}{'SPOT'}{R}")
    for r in regions[:limit]:
        try:
            area = int(r["area"])
        except (ValueError, TypeError):
            area = 0
        # Couleur selon l'aire (activite potentielle)
        color = YEL if area > 500 else (CYA if area > 200 else R)
        mag = r.get("mag_class", "?")
        # Rouge si config magnetique complexe (Beta-Gamma-Delta)
        mag_color = f"{BOLD}{RED}" if mag and mag[0] in "BCD" else R
        spot = r.get("spot_class", "?")
        lines.append(f"  {color}{str(r['num']):<8}{R}"
                     f"{str(r['location']):<12}"
                     f"{str(r['area']):<8}"
                     f"{mag_color}{str(mag):<6}{R}"
                     f"{DIM}{str(spot)}{R}")
    return "\n".join(lines)

# ============================================================
#  EXPORT JSON
# ============================================================
def build_snapshot(rt, alerts, kp_forecast, regions, omni):
    max_kp_forecast = None
    try:
        vals = [f["kp"] for f in kp_forecast if f["kp"] is not None]
        max_kp_forecast = max(vals) if vals else None
    except Exception:
        pass

    xray_flux = rt.get("xray", {}).get("flux")
    xray_class, _ = classify_xray(xray_flux)

    return {
        "generated_at": now_utc().isoformat(),
        "source": "noaa-swpc",
        "realtime": rt,
        "forecast": {
            "kp_3day": kp_forecast,
            "max_kp_forecast": max_kp_forecast,
        },
        "omni_indices": omni,
        "alerts": alerts,
        "solar_regions": regions,
        "summary": {
            "kp_current": rt.get("kp", {}).get("value"),
            "max_kp_forecast": max_kp_forecast,
            "xray_class": xray_class,
            "xray_flux": xray_flux,
            "alerts_count": len(alerts),
            "active_regions_count": len(regions),
        },
    }

def export_json(snapshot):
    if not CFG["export"]["enabled"]:
        return None
    ts = now_utc().strftime("%Y%m%dT%H%M%SZ")
    out = EXPORT_DIR / f"spacewatch_{ts}.json"
    out.write_text(json.dumps(snapshot, indent=2, ensure_ascii=False))
    keep = CFG["export"].get("keep_last", 50)
    files = sorted(EXPORT_DIR.glob("spacewatch_*.json"))
    for old in files[:-keep]:
        try:
            old.unlink()
        except Exception:
            pass
    latest = EXPORT_DIR / "latest.json"
    latest.write_text(json.dumps(snapshot, indent=2, ensure_ascii=False))
    return out

# ============================================================
#  ASSEMBLAGE
# ============================================================
def render_threat_summary(rt, kp_forecast, omni):
    """Bandeau de synthese des menaces actives."""
    threats = []

    # Kp actuel
    kp_now = rt.get("kp", {}).get("value")
    if kp_now is not None and kp_now >= 5:
        threats.append(f"Kp {kp_now} G1+ ACTIF")

    # Kp max prevu
    if kp_forecast:
        max_kp = max((f["kp"] or 0) for f in kp_forecast)
        if max_kp >= 5:
            threats.append(f"Kp max prevu {max_kp}")

    # Bz fortement negatif (sud)
    bz = rt.get("mag", {}).get("bz")
    if bz is not None and bz < -10:
        threats.append(f"Bz {bz} nT (sud)")

    # X-ray en cours
    flux = rt.get("xray", {}).get("flux")
    if flux is not None and flux >= 1e-5:
        threats.append("Eruption M/X en cours")

    # Dst
    dst = omni.get("dst", {}).get("value")
    if dst is not None and dst < -50:
        threats.append(f"Dst {dst} nT")

    if not threats:
        return f"\n{BOLD}{BG_GRN}{WHT}  ✅ AUCUNE MENACE ACTIVE — Conditions calmes  {R}"
    else:
        return (f"\n{BOLD}{BG_RED}{WHT}  ⚠ MENACES ACTIVES : "
                f"{' · '.join(threats)}  {R}")

def render_all(rt, alerts, kp_forecast, regions, omni, prop=None):
    os.system("clear" if os.name != "nt" else "cls")
    w = term_width()
    print(f"{BOLD}{MAG}╔{'═' * (w - 2)}╗{R}")
    title = f"  SPACEWATCH — {now_utc().strftime('%Y-%m-%d %H:%M:%S')} UTC  "
    print(f"{BOLD}{MAG}║{title:^{w - 2}}║{R}")
    print(f"{BOLD}{MAG}╚{'═' * (w - 2)}╝{R}")
    print(render_threat_summary(rt, kp_forecast, omni))
    print(render_realtime(rt, prop))
    if prop:
        print(render_propagated(prop))
    print(render_omni(omni))
    print(render_kp_forecast(kp_forecast))
    print(render_alerts(alerts))
    print(render_regions(regions))
    print(f"\n{DIM}{hr()}{R}")
    print(f"{DIM}  Source : NOAA SWPC — services.swpc.noaa.gov{R}")

def collect_all():
    rt = fetch_realtime()
    prop = fetch_propagated()
    omni = fetch_omni_indices()
    alerts = fetch_alerts()
    kp_forecast = fetch_kp_forecast()
    regions = fetch_solar_regions()
    return rt, alerts, kp_forecast, regions, omni, prop

def compute_state(rt, alerts, kp_forecast, regions):
    return (str(rt.get("kp", {}).get("value")),
            str(rt.get("xray", {}).get("flux", ""))[:6],
            len(alerts), len(kp_forecast), len(regions))

def cycle(export=True, render=True):
    rt, alerts, kp_forecast, regions, omni, prop = collect_all()
    if render:
        render_all(rt, alerts, kp_forecast, regions, omni, prop)
    snapshot = build_snapshot(rt, alerts, kp_forecast, regions, omni)
    path = None
    if export:
        path = export_json(snapshot)
        if path and render:
            print(f"{DIM}  Export : {path}{R}")
    return compute_state(rt, alerts, kp_forecast, regions), snapshot

# ============================================================
#  CLI
# ============================================================
def main():
    p = argparse.ArgumentParser(description="SpaceWatch NOAA-only")
    p.add_argument("--watch", action="store_true")
    p.add_argument("--interval", type=int, default=CFG["refresh_seconds"])
    p.add_argument("--alert", action="store_true")
    p.add_argument("--json-only", action="store_true")
    p.add_argument("--no-export", action="store_true")
    args = p.parse_args()

    do_export = not args.no_export

    if args.json_only:
        _, snap = cycle(export=True, render=False)
        print(json.dumps(snap, indent=2, ensure_ascii=False))
        return

    if not args.watch:
        cycle(export=do_export, render=True)
        return

    last_state = None
    try:
        while True:
            state, _ = cycle(export=do_export, render=True)
            if last_state is not None and state != last_state and args.alert:
                print(f"\a{BOLD}{BG_RED}{WHT}  ⚠ CHANGEMENT D'ÉTAT DÉTECTÉ  {R}\a")
            last_state = state
            for i in range(args.interval, 0, -1):
                print(f"\r{DIM}  Prochain rafraîchissement dans {i:>3}s...{R}",
                      end="", flush=True)
                time.sleep(1)
            print()
    except KeyboardInterrupt:
        print(f"\n\n{DIM}Arrêt.{R}")

if __name__ == "__main__":
    main()