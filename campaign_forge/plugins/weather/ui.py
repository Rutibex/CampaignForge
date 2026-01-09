from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QComboBox, QSpinBox, QDoubleSpinBox, QCheckBox, QGroupBox,
    QFormLayout, QListWidget, QListWidgetItem, QTextEdit, QLineEdit,
    QMessageBox, QSplitter, QTableWidget, QTableWidgetItem
)

from campaign_forge.core.context import ForgeContext
from .generator import (
    WeatherConfig, load_biome_pack, load_extremes, load_calendars,
    get_biome, get_calendar, simulate_year
)
from .exports import export_year_pack


def _tables_dir() -> Path:
    return Path(__file__).resolve().parent / "tables"


def _short_day_label(d: Dict[str, Any]) -> str:
    date = d.get("date", {})
    m = date.get("month", "")
    dd = date.get("day", "")
    wd = d.get("weekday", "")
    cond = d.get("condition", "")
    t = d.get("temperature_c", 0.0)
    precip = d.get("precip", {}).get("type", "None")
    pmark = "" if precip == "None" else " • " + precip
    return f"{wd} {m[:3]} {dd:>2} — {cond}{pmark} — {t:.0f}°C"


class WeatherWidget(QWidget):
    """
    Weather Almanac module.

    Features:
    - Biome selection (data-driven packs)
    - Full-year deterministic simulation
    - Day-by-day browser with detail view
    - Overrides & day locking
    - Exports (session pack: md/csv/json)
    - Scratchpad sends (day/month/events)
    """

    def __init__(self, ctx: ForgeContext):
        super().__init__()
        self.ctx = ctx
        self.plugin_id = "weather"

        self.biome_pack = load_biome_pack(_tables_dir())
        self.extremes = load_extremes(_tables_dir())
        self.calendars = load_calendars(_tables_dir())

        self.cfg = WeatherConfig()
        self.year: Optional[Dict[str, Any]] = None

        # overrides:
        # { day_index: { ...partial fields... , "locked": bool } }
        self.overrides: Dict[int, Dict[str, Any]] = {}

        self._build_ui()
        self._populate_biomes()
        self._populate_calendars()
        self._refresh_seed_label()

    # ---------------- UI ----------------

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)

        top = QSplitter(Qt.Horizontal)
        root.addWidget(top, 1)

        # Left panel: controls + day list
        left = QWidget()
        left_l = QVBoxLayout(left)

        # Controls
        box = QGroupBox("Simulation")
        form = QFormLayout(box)

        self.biome_combo = QComboBox()
        self.calendar_combo = QComboBox()

        self.year_spin = QSpinBox()
        self.year_spin.setRange(0, 9999)
        self.year_spin.setValue(0)

        self.hem_combo = QComboBox()
        self.hem_combo.addItems(["north", "south"])

        self.lat_spin = QDoubleSpinBox()
        self.lat_spin.setRange(-80.0, 80.0)
        self.lat_spin.setSingleStep(1.0)
        self.lat_spin.setValue(45.0)

        self.elev_spin = QDoubleSpinBox()
        self.elev_spin.setRange(-500.0, 9000.0)
        self.elev_spin.setSingleStep(50.0)
        self.elev_spin.setValue(0.0)

        self.anom_spin = QDoubleSpinBox()
        self.anom_spin.setRange(-2.0, 2.0)
        self.anom_spin.setSingleStep(0.25)
        self.anom_spin.setValue(0.0)

        self.wet_spin = QDoubleSpinBox()
        self.wet_spin.setRange(0.5, 2.0)
        self.wet_spin.setSingleStep(0.1)
        self.wet_spin.setValue(1.0)

        self.storm_spin = QDoubleSpinBox()
        self.storm_spin.setRange(0.5, 2.0)
        self.storm_spin.setSingleStep(0.1)
        self.storm_spin.setValue(1.0)

        self.extreme_spin = QDoubleSpinBox()
        self.extreme_spin.setRange(0.0, 2.0)
        self.extreme_spin.setSingleStep(0.1)
        self.extreme_spin.setValue(1.0)

        self.narr_style = QComboBox()
        self.narr_style.addItems(["Neutral", "OSR Minimal", "Grimdark", "Pastoral", "Mythic"])

        self.chk_narr = QCheckBox("Generate narrative text")
        self.chk_narr.setChecked(True)

        self.seed_label = QLabel("Seed: -")
        self.seed_label.setTextInteractionFlags(Qt.TextSelectableByMouse)

        form.addRow("Biome", self.biome_combo)
        form.addRow("Calendar", self.calendar_combo)
        form.addRow("Year index", self.year_spin)
        form.addRow("Hemisphere", self.hem_combo)
        form.addRow("Latitude", self.lat_spin)
        form.addRow("Elevation (m)", self.elev_spin)
        form.addRow("Year anomaly", self.anom_spin)
        form.addRow("Wetness", self.wet_spin)
        form.addRow("Storminess", self.storm_spin)
        form.addRow("Extreme rate", self.extreme_spin)
        form.addRow("Narrative style", self.narr_style)
        form.addRow("", self.chk_narr)
        form.addRow("", self.seed_label)

        btns = QHBoxLayout()
        self.btn_generate = QPushButton("Generate / Regenerate Year")
        self.btn_generate.clicked.connect(self.on_generate)
        self.btn_export = QPushButton("Export Session Pack")
        self.btn_export.clicked.connect(self.on_export)
        btns.addWidget(self.btn_generate, 1)
        btns.addWidget(self.btn_export, 0)
        left_l.addWidget(box)
        left_l.addLayout(btns)

        # Filter + day list
        flt = QGroupBox("Browse")
        fl = QFormLayout(flt)
        self.month_filter = QComboBox()
        self.month_filter.addItems(["All months"])
        self.month_filter.currentIndexChanged.connect(self._rebuild_day_list)
        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("Filter text (e.g. Storm, Snow, Heat)")
        self.search_box.textChanged.connect(self._rebuild_day_list)
        fl.addRow("Month", self.month_filter)
        fl.addRow("Search", self.search_box)
        left_l.addWidget(flt)

        self.day_list = QListWidget()
        self.day_list.currentRowChanged.connect(self.on_day_selected)
        left_l.addWidget(self.day_list, 1)

        self.btn_day_to_scratch = QPushButton("Send Selected Day → Scratchpad")
        self.btn_day_to_scratch.clicked.connect(self.on_send_day_to_scratchpad)
        left_l.addWidget(self.btn_day_to_scratch)

        top.addWidget(left)

        # Right panel: detail + month stats + events
        right = QWidget()
        right_l = QVBoxLayout(right)

        # Detail
        dbox = QGroupBox("Day Detail")
        dl = QVBoxLayout(dbox)

        self.day_header = QLabel("No day selected.")
        self.day_header.setTextInteractionFlags(Qt.TextSelectableByMouse)
        dl.addWidget(self.day_header)

        self.day_detail = QTextEdit()
        self.day_detail.setReadOnly(True)
        dl.addWidget(self.day_detail, 1)

        # Override controls
        obox = QGroupBox("Overrides")
        of = QFormLayout(obox)

        self.ov_temp = QDoubleSpinBox()
        self.ov_temp.setRange(-80.0, 80.0)
        self.ov_temp.setSingleStep(0.5)

        self.ov_cond = QComboBox()
        self.ov_cond.addItems(["(no change)", "Clear", "Cloudy", "Rain", "Storm", "Snow", "Fog", "Hail", "Dust"])

        self.ov_precip = QComboBox()
        self.ov_precip.addItems(["(no change)", "None", "Rain", "Snow", "Sleet", "Hail", "Ash"])

        self.ov_intensity = QComboBox()
        self.ov_intensity.addItems(["(no change)", "None", "Light", "Moderate", "Heavy", "Violent"])

        self.ov_wind = QSpinBox()
        self.ov_wind.setRange(0, 200)

        self.ov_notes = QLineEdit()
        self.ov_notes.setPlaceholderText("Optional notes to append/replace (override)")

        self.ov_lock = QCheckBox("Lock this day (keeps override on regenerate)")

        self.btn_apply_ov = QPushButton("Apply Override")
        self.btn_apply_ov.clicked.connect(self.on_apply_override)
        self.btn_clear_ov = QPushButton("Clear Override")
        self.btn_clear_ov.clicked.connect(self.on_clear_override)

        of.addRow("Temp °C", self.ov_temp)
        of.addRow("Condition", self.ov_cond)
        of.addRow("Precip type", self.ov_precip)
        of.addRow("Precip intensity", self.ov_intensity)
        of.addRow("Wind kph", self.ov_wind)
        of.addRow("Notes", self.ov_notes)
        of.addRow("", self.ov_lock)

        obtns = QHBoxLayout()
        obtns.addWidget(self.btn_apply_ov, 1)
        obtns.addWidget(self.btn_clear_ov, 1)
        of.addRow(obtns)

        dl.addWidget(obox)

        right_l.addWidget(dbox, 3)

        # Month stats
        mbox = QGroupBox("Month Stats")
        ml = QVBoxLayout(mbox)
        self.month_table = QTableWidget(0, 8)
        self.month_table.setHorizontalHeaderLabels(["Month", "Avg °C", "Min °C", "Max °C", "Precip", "Storm", "Snow", "Fog"])
        self.month_table.setEditTriggers(QTableWidget.NoEditTriggers)
        ml.addWidget(self.month_table, 1)

        btn_month = QHBoxLayout()
        self.btn_month_to_scratch = QPushButton("Send Monthly Summary → Scratchpad")
        self.btn_month_to_scratch.clicked.connect(self.on_send_month_to_scratchpad)
        self.btn_events_to_scratch = QPushButton("Send Extreme Events → Scratchpad")
        self.btn_events_to_scratch.clicked.connect(self.on_send_events_to_scratchpad)
        btn_month.addWidget(self.btn_month_to_scratch, 1)
        btn_month.addWidget(self.btn_events_to_scratch, 1)
        ml.addLayout(btn_month)
        right_l.addWidget(mbox, 2)

        top.addWidget(right)
        top.setStretchFactor(0, 1)
        top.setStretchFactor(1, 2)

        # Wire changes to seed label
        self.biome_combo.currentIndexChanged.connect(self._refresh_seed_label)
        self.calendar_combo.currentIndexChanged.connect(self._refresh_seed_label)
        self.year_spin.valueChanged.connect(self._refresh_seed_label)
        self.hem_combo.currentIndexChanged.connect(self._refresh_seed_label)
        self.lat_spin.valueChanged.connect(self._refresh_seed_label)
        self.elev_spin.valueChanged.connect(self._refresh_seed_label)
        self.anom_spin.valueChanged.connect(self._refresh_seed_label)
        self.wet_spin.valueChanged.connect(self._refresh_seed_label)
        self.storm_spin.valueChanged.connect(self._refresh_seed_label)
        self.extreme_spin.valueChanged.connect(self._refresh_seed_label)
        self.narr_style.currentIndexChanged.connect(self._refresh_seed_label)
        self.chk_narr.stateChanged.connect(self._refresh_seed_label)

    # ---------------- state ----------------

    def serialize_state(self) -> Dict[str, Any]:
        return {
            "version": 1,
            "config": self._ui_to_cfg_dict(),
            "overrides": {str(k): v for k, v in self.overrides.items()},
            "year_cache": self.year,  # optional cache (keeps browsing after restart)
        }

    def load_state(self, state: Dict[str, Any]) -> None:
        if not state:
            return
        try:
            cfg = state.get("config", {})
            self._cfg_dict_to_ui(cfg)
            ov = state.get("overrides", {})
            self.overrides = {int(k): v for k, v in ov.items()} if isinstance(ov, dict) else {}
            self.year = state.get("year_cache", None)
            self._rebuild_month_filter()
            self._rebuild_day_list()
            self._refresh_month_table()
        except Exception as e:
            self.ctx.log(f"[Weather] Failed to load state: {e}")

    # ---------------- generation ----------------

    def _ui_to_cfg(self) -> WeatherConfig:
        biome_id = self.biome_combo.currentData()
        cal_id = self.calendar_combo.currentData()
        return WeatherConfig(
            biome_id=str(biome_id or "temperate_forest"),
            year_index=int(self.year_spin.value()),
            calendar_id=str(cal_id or "gregorian_365"),
            hemisphere=str(self.hem_combo.currentText()),
            latitude=float(self.lat_spin.value()),
            elevation_m=float(self.elev_spin.value()),
            anomaly=float(self.anom_spin.value()),
            wetness=float(self.wet_spin.value()),
            storminess=float(self.storm_spin.value()),
            extreme_rate=float(self.extreme_spin.value()),
            narrative_style=str(self.narr_style.currentText()),
            generate_narrative=bool(self.chk_narr.isChecked()),
        )

    def _ui_to_cfg_dict(self) -> Dict[str, Any]:
        c = self._ui_to_cfg()
        return {
            "biome_id": c.biome_id,
            "year_index": c.year_index,
            "calendar_id": c.calendar_id,
            "hemisphere": c.hemisphere,
            "latitude": c.latitude,
            "elevation_m": c.elevation_m,
            "anomaly": c.anomaly,
            "wetness": c.wetness,
            "storminess": c.storminess,
            "extreme_rate": c.extreme_rate,
            "narrative_style": c.narrative_style,
            "generate_narrative": c.generate_narrative,
        }

    def _cfg_dict_to_ui(self, d: Dict[str, Any]) -> None:
        # biome/calendar combos are populated later; store desired IDs, then set in populate methods
        desired_biome = d.get("biome_id", None)
        desired_cal = d.get("calendar_id", None)

        self.year_spin.setValue(int(d.get("year_index", 0)))
        hem = str(d.get("hemisphere", "north"))
        self.hem_combo.setCurrentText(hem if hem in ("north", "south") else "north")
        self.lat_spin.setValue(float(d.get("latitude", 45.0)))
        self.elev_spin.setValue(float(d.get("elevation_m", 0.0)))
        self.anom_spin.setValue(float(d.get("anomaly", 0.0)))
        self.wet_spin.setValue(float(d.get("wetness", 1.0)))
        self.storm_spin.setValue(float(d.get("storminess", 1.0)))
        self.extreme_spin.setValue(float(d.get("extreme_rate", 1.0)))
        self.narr_style.setCurrentText(str(d.get("narrative_style", "Neutral")))
        self.chk_narr.setChecked(bool(d.get("generate_narrative", True)))

        # Try to set biome/calendar after combos are loaded
        self._set_combo_by_data(self.biome_combo, desired_biome)
        self._set_combo_by_data(self.calendar_combo, desired_cal)

        self._refresh_seed_label()

    def _set_combo_by_data(self, combo: QComboBox, desired: Any) -> None:
        if desired is None:
            return
        for i in range(combo.count()):
            if combo.itemData(i) == desired:
                combo.setCurrentIndex(i)
                return

    def _seed_for_ui(self) -> int:
        cfg = self._ui_to_cfg()
        return int(self.ctx.derive_seed(
            "weather",
            cfg.calendar_id,
            cfg.biome_id,
            cfg.year_index,
            cfg.hemisphere,
            round(cfg.latitude, 2),
            round(cfg.elevation_m, 1),
            round(cfg.anomaly, 2),
            round(cfg.wetness, 2),
            round(cfg.storminess, 2),
            round(cfg.extreme_rate, 2),
            cfg.narrative_style,
            int(cfg.generate_narrative),
        ))

    def _refresh_seed_label(self) -> None:
        seed = self._seed_for_ui()
        self.seed_label.setText(f"Seed: {seed}  (project master {self.ctx.master_seed})")

    def _populate_biomes(self) -> None:
        self.biome_combo.clear()
        biomes = self.biome_pack.get("biomes", [])
        for b in biomes:
            self.biome_combo.addItem(f"{b.get('name','Biome')}  [{', '.join(b.get('tags', []))}]", b.get("id"))
        if self.biome_combo.count() == 0:
            self.biome_combo.addItem("Temperate Forest", "temperate_forest")

    def _populate_calendars(self) -> None:
        self.calendar_combo.clear()
        cals = self.calendars.get("calendars", [])
        for c in cals:
            self.calendar_combo.addItem(str(c.get("name", c.get("id"))), c.get("id"))
        if self.calendar_combo.count() == 0:
            self.calendar_combo.addItem("Gregorian 365", "gregorian_365")

    def on_generate(self) -> None:
        try:
            cfg = self._ui_to_cfg()
            self.cfg = cfg
            biome = get_biome(self.biome_pack, cfg.biome_id)
            cal = get_calendar(self.calendars, cfg.calendar_id)

            seed = self._seed_for_ui()
            rng = self.ctx.derive_rng("weather_sim", seed)

            year = simulate_year(rng=rng, biome=biome, cal=cal, cfg=cfg, extremes_table=self.extremes)

            # Apply locked overrides after regen
            self.year = self._apply_overrides_to_year(year)

            self._rebuild_month_filter()
            self._rebuild_day_list()
            self._refresh_month_table()

            self.ctx.log(f"[Weather] Generated year {cfg.year_index} for biome '{biome.get('name')}' ({cal.name}). Seed={seed}")
        except Exception as e:
            self.ctx.log(f"[Weather] Generation failed: {e}")
            QMessageBox.critical(self, "Weather Generation Failed", str(e))

    def _apply_overrides_to_year(self, year: Dict[str, Any]) -> Dict[str, Any]:
        if not year or not year.get("days"):
            return year
        days = year["days"]
        for k, ov in list(self.overrides.items()):
            if k < 0 or k >= len(days):
                continue
            # Only apply if locked OR the year exists already (we keep overrides always, lock means survive regen).
            # For simplicity: always apply overrides; regen keeps them too. "Lock" is a UI affordance,
            # but the key meaning is "don't clear on regenerate". We'll keep all overrides unless cleared manually.
            self._apply_override_to_day(days[k], ov)
        return year

    def _apply_override_to_day(self, day: Dict[str, Any], ov: Dict[str, Any]) -> None:
        if "temperature_c" in ov:
            day["temperature_c"] = float(ov["temperature_c"])
        if "condition" in ov:
            day["condition"] = str(ov["condition"])
        if "precip_type" in ov:
            day["precip"]["type"] = str(ov["precip_type"])
        if "precip_intensity" in ov:
            day["precip"]["intensity"] = str(ov["precip_intensity"])
        if "wind_kph" in ov:
            day["wind"]["speed_kph"] = int(ov["wind_kph"])
        if "notes" in ov:
            day["notes"] = str(ov["notes"])
        if ov.get("locked"):
            day.setdefault("tags", []).append("Locked:Weather")

    # ---------------- browse ----------------

    def _rebuild_month_filter(self) -> None:
        self.month_filter.blockSignals(True)
        self.month_filter.clear()
        self.month_filter.addItem("All months")
        if self.year:
            months = self.year.get("calendar", {}).get("months", [])
            for m in months:
                self.month_filter.addItem(str(m))
        self.month_filter.blockSignals(False)

    def _rebuild_day_list(self) -> None:
        self.day_list.clear()
        if not self.year:
            return
        days = self.year.get("days", [])
        if not days:
            return

        month_name = self.month_filter.currentText()
        if month_name == "All months":
            allowed = None
        else:
            allowed = month_name

        needle = (self.search_box.text() or "").strip().lower()

        for d in days:
            date = d.get("date", {})
            if allowed and date.get("month") != allowed:
                continue
            label = _short_day_label(d)
            if needle:
                blob = (label + " " + " ".join(d.get("tags", [])) + " " + (d.get("notes","") or "")).lower()
                if needle not in blob:
                    continue

            it = QListWidgetItem(label)
            it.setData(Qt.UserRole, d.get("day_index"))
            # mark overrides
            if int(d.get("day_index", -1)) in self.overrides:
                it.setText("★ " + label)
            self.day_list.addItem(it)

    def on_day_selected(self, row: int) -> None:
        if row < 0 or not self.year:
            self.day_header.setText("No day selected.")
            self.day_detail.setPlainText("")
            return
        it = self.day_list.item(row)
        if not it:
            return
        idx = it.data(Qt.UserRole)
        if idx is None:
            return
        day = self.year.get("days", [])[int(idx)]
        self._show_day(day)
        self._load_override_controls(int(idx), day)

    def _show_day(self, d: Dict[str, Any]) -> None:
        date = d.get("date", {})
        date_str = f"{date.get('month','')} {date.get('day','')}".strip()
        self.day_header.setText(f"Day {d.get('day_index')} — {date_str} ({d.get('weekday','')})")

        precip = d.get("precip", {})
        wind = d.get("wind", {})
        lines: List[str] = []
        lines.append(f"Condition: {d.get('condition','')}")
        lines.append(f"Temperature: {d.get('temperature_c',0.0):.1f} °C")
        lines.append(f"Precip: {precip.get('type','None')} ({precip.get('intensity','None')})")
        lines.append(f"Wind: {wind.get('speed_kph',0)} kph {wind.get('direction','')} {'(gusts)' if wind.get('gusts') else ''}".strip())
        lines.append(f"Visibility: {d.get('visibility','')}")
        lines.append(f"Daylight: {d.get('daylight_hours',0.0):.1f} h")
        if d.get("tags"):
            lines.append("")
            lines.append("Tags: " + ", ".join(d.get("tags", [])))
        if d.get("notes"):
            lines.append("")
            lines.append("Notes:\n" + str(d.get("notes","")))
        if d.get("narrative"):
            lines.append("")
            lines.append(str(d.get("narrative","")))
        self.day_detail.setPlainText("\n".join(lines))

    def _load_override_controls(self, day_index: int, d: Dict[str, Any]) -> None:
        # Default controls to current values, but condition/precip combos use "(no change)"
        self.ov_temp.setValue(float(d.get("temperature_c", 0.0)))
        self.ov_wind.setValue(int(d.get("wind", {}).get("speed_kph", 0)))

        self.ov_cond.setCurrentIndex(0)
        self.ov_precip.setCurrentIndex(0)
        self.ov_intensity.setCurrentIndex(0)
        self.ov_notes.setText("")
        self.ov_lock.setChecked(False)

        ov = self.overrides.get(day_index)
        if ov:
            if "temperature_c" in ov:
                self.ov_temp.setValue(float(ov["temperature_c"]))
            if "wind_kph" in ov:
                self.ov_wind.setValue(int(ov["wind_kph"]))
            if "condition" in ov and ov["condition"]:
                self.ov_cond.setCurrentText(str(ov["condition"]))
            if "precip_type" in ov and ov["precip_type"]:
                self.ov_precip.setCurrentText(str(ov["precip_type"]))
            if "precip_intensity" in ov and ov["precip_intensity"]:
                self.ov_intensity.setCurrentText(str(ov["precip_intensity"]))
            if "notes" in ov:
                self.ov_notes.setText(str(ov["notes"]))
            self.ov_lock.setChecked(bool(ov.get("locked", False)))

    # ---------------- overrides ----------------

    def on_apply_override(self) -> None:
        if not self.year:
            return
        row = self.day_list.currentRow()
        if row < 0:
            return
        it = self.day_list.item(row)
        if not it:
            return
        idx = int(it.data(Qt.UserRole))

        ov: Dict[str, Any] = {}
        ov["temperature_c"] = float(self.ov_temp.value())
        ov["wind_kph"] = int(self.ov_wind.value())

        cond = self.ov_cond.currentText()
        if cond != "(no change)":
            ov["condition"] = cond

        ptype = self.ov_precip.currentText()
        if ptype != "(no change)":
            ov["precip_type"] = ptype

        pint = self.ov_intensity.currentText()
        if pint != "(no change)":
            ov["precip_intensity"] = pint

        notes = (self.ov_notes.text() or "").strip()
        if notes:
            ov["notes"] = notes

        ov["locked"] = bool(self.ov_lock.isChecked())

        self.overrides[idx] = ov
        # Apply immediately to current year data
        day = self.year["days"][idx]
        self._apply_override_to_day(day, ov)

        self._rebuild_day_list()
        self._show_day(day)
        self.ctx.log(f"[Weather] Override applied to day {idx} (locked={ov['locked']}).")

    def on_clear_override(self) -> None:
        if not self.year:
            return
        row = self.day_list.currentRow()
        if row < 0:
            return
        it = self.day_list.item(row)
        if not it:
            return
        idx = int(it.data(Qt.UserRole))
        if idx in self.overrides:
            del self.overrides[idx]
            self.ctx.log(f"[Weather] Cleared override for day {idx}. Regenerate to restore original simulation values.")
            # Re-generate to restore baseline values (quick but correct)
            self.on_generate()

    # ---------------- scratchpad ----------------

    def on_send_day_to_scratchpad(self) -> None:
        if not self.year:
            return
        row = self.day_list.currentRow()
        if row < 0:
            return
        it = self.day_list.item(row)
        idx = int(it.data(Qt.UserRole))
        d = self.year["days"][idx]
        date = d.get("date", {})
        date_str = f"{date.get('month','')} {date.get('day','')}".strip()
        biome = self.year.get("biome", {}).get("name", "Biome")

        md = f"## Weather — {date_str}\n\n"
        md += f"**Biome:** {biome}\n\n"
        md += f"- Condition: **{d.get('condition','')}**\n"
        md += f"- Temp: **{d.get('temperature_c',0.0):.1f}°C**\n"
        p = d.get("precip", {})
        md += f"- Precip: **{p.get('type','None')}** ({p.get('intensity','None')})\n"
        w = d.get("wind", {})
        md += f"- Wind: **{w.get('speed_kph',0)} kph {w.get('direction','')}** {'(gusts)' if w.get('gusts') else ''}\n"
        md += f"- Visibility: **{d.get('visibility','')}** | Daylight: **{d.get('daylight_hours',0.0):.1f}h**\n"
        if d.get("notes"):
            md += f"\n**Notes:**\n{d.get('notes','')}\n"
        if d.get("narrative"):
            md += f"\n{d.get('narrative','')}\n"

        tags = ["Weather", f"Biome:{biome}", f"Weather:{d.get('condition','')}", f"Month:{date.get('month','')}"]
        self.ctx.scratchpad_add(md, tags=tags)
        self.ctx.log(f"[Weather] Sent day {idx} to scratchpad.")

    def on_send_month_to_scratchpad(self) -> None:
        if not self.year:
            return
        month_name = self.month_filter.currentText()
        if month_name == "All months":
            # send year summary
            summary = self.year.get("summary", {})
            biome = self.year.get("biome", {}).get("name", "Biome")
            md = f"## Weather Summary — {biome}\n\n"
            md += f"- Avg temp: **{summary.get('avg_temp_c',0):.1f}°C** (min {summary.get('min_temp_c',0):.1f}°C, max {summary.get('max_temp_c',0):.1f}°C)\n"
            md += f"- Precip days: **{summary.get('precip_days',0)}**\n"
            md += f"- Storm: **{summary.get('storm_days',0)}** | Snow: **{summary.get('snow_days',0)}** | Fog: **{summary.get('fog_days',0)}**\n"
            self.ctx.scratchpad_add(md, tags=["Weather", "Weather:Summary"])
            self.ctx.log("[Weather] Sent year summary to scratchpad.")
            return

        # find month stats
        ms = None
        for m in self.year.get("summary", {}).get("months", []):
            if m.get("month") == month_name:
                ms = m
                break
        if not ms:
            return

        biome = self.year.get("biome", {}).get("name", "Biome")
        md = f"## Weather — {month_name} Summary\n\n"
        md += f"**Biome:** {biome}\n\n"
        md += f"- Avg temp: **{ms.get('avg_temp_c',0):.1f}°C** (min {ms.get('min_temp_c',0):.1f}°C, max {ms.get('max_temp_c',0):.1f}°C)\n"
        md += f"- Precip days: **{ms.get('precip_days',0)}**\n"
        md += f"- Storm: **{ms.get('storm_days',0)}** | Snow: **{ms.get('snow_days',0)}** | Fog: **{ms.get('fog_days',0)}**\n"
        self.ctx.scratchpad_add(md, tags=["Weather", "Weather:Month", f"Month:{month_name}"])
        self.ctx.log(f"[Weather] Sent month '{month_name}' summary to scratchpad.")

    def on_send_events_to_scratchpad(self) -> None:
        if not self.year:
            return
        events = self.year.get("extreme_events", [])
        if not events:
            QMessageBox.information(self, "No Extreme Events", "This year has no injected extreme events (try increasing Extreme rate).")
            return

        biome = self.year.get("biome", {}).get("name", "Biome")
        md = f"## Extreme Weather Events — {biome}\n\n"
        for e in events:
            md += f"### {e.get('name', e.get('id','Event'))}\n"
            md += f"- Days: {e.get('start_day_index')}–{e.get('end_day_index')} ({e.get('duration_days')} days)\n"
            if e.get("effects"):
                md += "- Effects:\n"
                for eff in e["effects"]:
                    md += f"  - {eff}\n"
            if e.get("note"):
                md += f"- Note: {e.get('note')}\n"
            md += "\n"

        self.ctx.scratchpad_add(md, tags=["Weather", "Weather:Extreme"])
        self.ctx.log("[Weather] Sent extreme events to scratchpad.")

    # ---------------- exports ----------------

    def on_export(self) -> None:
        if not self.year:
            QMessageBox.information(self, "Nothing to export", "Generate a year first.")
            return
        try:
            seed = self._seed_for_ui()
            biome = self.year.get("biome", {}).get("name", "biome")
            slug = f"{biome}_y{self.cfg.year_index}"
            pack = export_year_pack(self.ctx, self.year, slug=slug, seed=seed, include_daily_md=True)
            self.ctx.log(f"[Weather] Exported session pack: {pack}")
            QMessageBox.information(self, "Export Complete", f"Exported to:\n{pack}")
        except Exception as e:
            self.ctx.log(f"[Weather] Export failed: {e}")
            QMessageBox.critical(self, "Export Failed", str(e))

    # ---------------- month stats table ----------------

    def _refresh_month_table(self) -> None:
        self.month_table.setRowCount(0)
        if not self.year:
            return
        months = self.year.get("summary", {}).get("months", [])
        self.month_table.setRowCount(len(months))
        for r, m in enumerate(months):
            vals = [
                m.get("month",""),
                f"{m.get('avg_temp_c',0):.1f}",
                f"{m.get('min_temp_c',0):.1f}",
                f"{m.get('max_temp_c',0):.1f}",
                str(m.get("precip_days",0)),
                str(m.get("storm_days",0)),
                str(m.get("snow_days",0)),
                str(m.get("fog_days",0)),
            ]
            for c, v in enumerate(vals):
                self.month_table.setItem(r, c, QTableWidgetItem(v))

        self.month_table.resizeColumnsToContents()
