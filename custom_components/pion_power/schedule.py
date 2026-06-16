"""Pure helpers for parsing/building Pion TOU schedules.

Kept dependency-free (no HA imports) so both the coordinator and the entity
platforms can use it without circular imports.

Period model used throughout the integration (normalized, percent units):
    {StartTime, EndTime, SOC, RunPower, ChargeOrDis, GridChargeEn, SellGridEn}
where RunPower/SOC are 0-100 and ChargeOrDis is 0=auto, 1=charge, 2=discharge.

The Pion API stores RunPower as percent x100 (10000 = 100%, 7600 = 76%) inside
StraDayPeriods[] -> StraWeekInfos[] -> StraTimePeriods[].
"""
from __future__ import annotations

from copy import deepcopy

# Pion weekday numbering: 0=Sun, 1=Mon ... 6=Sat.
WEEKDAY_ABBR = {0: "Sun", 1: "Mon", 2: "Tue", 3: "Wed", 4: "Thu", 5: "Fri", 6: "Sat"}
ALL_WEEK = [0, 1, 2, 3, 4, 5, 6]


def run_power_pct(value) -> int | None:
    """API RunPower (percent x100) -> percent int."""
    try:
        return round(float(value) / 100)
    except (TypeError, ValueError):
        return None


def weekdays_label(weeks) -> str:
    if not isinstance(weeks, list) or not weeks:
        return "every day"
    s = sorted(int(w) for w in weeks)
    if s == ALL_WEEK:
        return "every day"
    if s == [1, 2, 3, 4, 5]:
        return "Mon–Fri"
    if s == [0, 6]:
        return "Sat–Sun"
    return ", ".join(WEEKDAY_ABBR.get(w, str(w)) for w in s)


def norm_period(p: dict) -> dict:
    """Normalize one StraTimePeriod (RunPower -> percent)."""
    return {
        "StartTime": p.get("StartTime"),
        "EndTime": p.get("EndTime"),
        "SOC": p.get("SOC"),
        "RunPower": run_power_pct(p.get("RunPower")),
        "ChargeOrDis": p.get("ChargeOrDis"),
        "GridChargeEn": bool(p.get("GridChargeEn")),
        "SellGridEn": bool(p.get("SellGridEn")),
    }


def denorm_period(p: dict) -> dict:
    """Normalized period -> API StraTimePeriod (RunPower -> percent x100)."""
    return {
        "StartTime": p.get("StartTime"),
        "EndTime": p.get("EndTime"),
        "RunPower": int(p.get("RunPower") or 0) * 100,
        "SOC": int(p.get("SOC") or 0),
        "ChargeOrDis": int(p.get("ChargeOrDis") or 0),
        "GridChargeEn": bool(p.get("GridChargeEn")),
        "SellGridEn": bool(p.get("SellGridEn")),
    }


def template_groups(template: dict) -> list[dict]:
    """Faithfully flatten ANY template into rule-groups:
    [{date_range, weekdays, weeks, periods:[normalized...]}, ...]."""
    groups: list[dict] = []
    for dp in template.get("StraDayPeriods") or []:
        all_year = (
            dp.get("StartMonth") == 1 and dp.get("StartDay") == 1
            and dp.get("EndMonth") == 12 and dp.get("EndDay") == 31
        )
        date_range = (
            "all year" if all_year
            else f"{dp.get('StartMonth')}/{dp.get('StartDay')}–{dp.get('EndMonth')}/{dp.get('EndDay')}"
        )
        for wi in dp.get("StraWeekInfos") or []:
            groups.append(
                {
                    "date_range": date_range,
                    "weekdays": weekdays_label(wi.get("Weeks")),
                    "weeks": wi.get("Weeks") or [],
                    "periods": [norm_period(p) for p in wi.get("StraTimePeriods") or []],
                }
            )
    return groups


def primary_periods(template: dict) -> list[dict]:
    """Normalized periods of the template's first rule-group (the editable one)."""
    groups = template_groups(template)
    return deepcopy(groups[0]["periods"]) if groups else []


def humanize_period(p: dict) -> str:
    cod = p.get("ChargeOrDis")
    action = {1: "charge", 2: "discharge"}.get(cod, "target")
    parts = [
        f"{p.get('StartTime', '?')}-{p.get('EndTime', '?')}",
        f"{action} {p.get('SOC', '?')}% SOC",
        f"@{p.get('RunPower', '?')}% power",
    ]
    if p.get("GridChargeEn"):
        parts.append("grid-charge ON")
    if p.get("SellGridEn"):
        parts.append("sell-to-grid ON")
    return "  ".join(parts)


def humanize_groups(groups: list[dict]) -> list[str]:
    if len(groups) == 1:
        return [humanize_period(p) for p in groups[0]["periods"]]
    lines: list[str] = []
    for g in groups:
        lines.append(f"[{g['date_range']} · {g['weekdays']}]")
        lines.extend(f"  {humanize_period(p)}" for p in g["periods"])
    return lines


def apply_periods_to_template(template: dict, periods: list[dict]) -> dict:
    """Return a deep copy of `template` with its primary group's StraTimePeriods
    replaced by `periods` (normalized). Other groups/weeks/date-ranges and all
    template metadata are preserved, so multi-group schedules stay intact."""
    tpl = deepcopy(template) if template else {}
    tpl = {k: v for k, v in tpl.items() if not str(k).startswith("_")}
    day_periods = tpl.get("StraDayPeriods")
    if not day_periods:
        day_periods = [
            {
                "StartMonth": 1, "StartDay": 1, "EndMonth": 12, "EndDay": 31,
                "StraWeekInfos": [{"Weeks": list(ALL_WEEK), "StraTimePeriods": []}],
            }
        ]
        tpl["StraDayPeriods"] = day_periods
    week_infos = day_periods[0].setdefault("StraWeekInfos", [{}])
    if not week_infos:
        week_infos.append({})
    week_infos[0].setdefault("Weeks", list(ALL_WEEK))
    week_infos[0]["StraTimePeriods"] = [denorm_period(p) for p in periods]
    tpl["CompanyCode"] = tpl.get("CompanyCode") or "PionPower"
    tpl.setdefault("StraSpecialDayInfos", tpl.get("StraSpecialDayInfos") or [])
    return tpl


def build_stra_day_periods(groups: list[dict]) -> list[dict]:
    """Convert service-style rule-groups into the Pion StraDayPeriods structure.
    Groups sharing a date range merge into one StraDayPeriod with multiple
    StraWeekInfos. `periods` use percent RunPower (scaled to x100 here)."""
    by_range: dict[tuple, list[dict]] = {}
    order: list[tuple] = []
    for g in groups:
        key = (g["start_month"], g["start_day"], g["end_month"], g["end_day"])
        if key not in by_range:
            by_range[key] = []
            order.append(key)
        periods = [denorm_period(p) for p in g["periods"]]
        by_range[key].append({"Weeks": list(g["weeks"]), "StraTimePeriods": periods})
    out = []
    for sm, sd, em, ed in order:
        out.append(
            {
                "StartMonth": sm, "StartDay": sd, "EndMonth": em, "EndDay": ed,
                "StraWeekInfos": by_range[(sm, sd, em, ed)],
            }
        )
    return out


def workmode_charge_periods(periods: list[dict]) -> list[dict]:
    """Extract the grid-charge windows for the inverter WORKMODE.

    The HAS executes the workmode's TOUModeStraPeriods, NOT the template — so a
    schedule only takes effect once its grid-charge windows are written there.
    Discharge/daytime is default self-consumption bounded by the reserve floor,
    so only GridChargeEn periods need pushing. RunPower stays in percent (the
    workmode's unit); an end time of "00:00" becomes "23:59" (workmode form)."""
    out = []
    for p in periods:
        if not p.get("GridChargeEn"):
            continue
        end = p.get("EndTime")
        out.append(
            {
                "StartTime": p.get("StartTime"),
                "EndTime": "23:59" if end == "00:00" else end,
                "ChargeOrDis": 1,
                "SOC": int(p.get("SOC") or 0),
                "RunPower": int(p.get("RunPower") or 100),
                "GridChargeEn": True,
                "SellGridEn": bool(p.get("SellGridEn")),
            }
        )
    return out


def blank_period() -> dict:
    return {
        "StartTime": "00:00", "EndTime": "00:00", "SOC": 100, "RunPower": 100,
        "ChargeOrDis": 0, "GridChargeEn": False, "SellGridEn": False,
    }
