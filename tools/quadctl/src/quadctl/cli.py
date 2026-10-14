"""quadctl command line."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import platform
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

from . import checks, firmware, radio
from .compile import TUNE_SCRIPT, compile_config, defaults_file, tune_script
from .config import ConfigError, load
from .fc import SCRIPTS_DIR, FC, FCError, needs_reboot, read_param_file, write_param_file

PARAM_TOL = 1e-3


@dataclass
class Ctx:
    root: Path
    args: argparse.Namespace
    cfg: object = None
    desired: object = None
    lock: dict = field(default_factory=dict)
    fc: FC | None = None
    fc_params: dict | None = None
    fc_info: object = None
    fc_stamp: dict | None = None
    fc_script: str | None = None       # the tuning menu script on the FC, if read
    fc_script_read: bool = False
    volume: Path | None = None
    model: radio.ModelFile | None = None
    elrs: radio.ElrsState | None = None

    @property
    def scripts(self) -> Path:
        return self.root / "radio" / "SCRIPTS"

    @property
    def tune_script(self) -> str | None:
        """The FC tuning menu script quad.yaml wants, or None without tuning."""
        if not self.desired.tune_targets:
            return None
        template = (self.root / "fc" / "scripts" / TUNE_SCRIPT).read_text()
        return tune_script(template, self.desired.tune_targets)

    def want(self, device: str) -> bool:
        return self.args.only in (None, device)


def find_root(start: Path) -> Path:
    for p in [start, *start.parents]:
        if (p / "config" / "quad.yaml").exists():
            return p
    raise SystemExit("can't find config/quad.yaml above the current directory (use --root)")


def say(*a) -> None:
    print(*a, flush=True)


def confirm(args, question: str) -> bool:
    if args.yes:
        return True
    return input(f"{question} [y/N] ").strip().lower() in ("y", "yes")


# --- loading ------------------------------------------------------------------

def load_config(ctx: Ctx) -> None:
    try:
        ctx.cfg = load(ctx.root / "config" / "quad.yaml")
    except ConfigError as e:
        for err in e.errors:
            say(f"ERROR quad.yaml: {err}")
        raise SystemExit(1)
    ctx.desired = compile_config(ctx.cfg)
    lock = ctx.root / "config" / "firmware.lock"
    ctx.lock = firmware.load_lock(lock) if lock.exists() else {}


def connect(ctx: Ctx, required: bool) -> None:
    a = ctx.args
    if ctx.want("fc"):
        try:
            ctx.fc = FC.connect(a.port)
            ctx.fc_info = ctx.fc.info()
            say(f"FC: {ctx.fc.port}, ArduCopter {ctx.fc_info.version} ({ctx.fc_info.git_hash}), board {ctx.fc_info.board}")
            ctx.fc_params = ctx.fc.fetch_params()
            say(f"FC: {len(ctx.fc_params)} params")
            try:
                ctx.fc_stamp = ctx.fc.read_stamp()
            except Exception as e:  # FTP unsupported or SD missing
                say(f"FC: couldn't read the quadctl stamp ({e})")
            if ctx.desired.tune_targets:
                try:
                    ctx.fc_script = ctx.fc.get_file(f"{SCRIPTS_DIR}/{TUNE_SCRIPT}")
                    ctx.fc_script_read = True
                except Exception as e:
                    say(f"FC: couldn't read {SCRIPTS_DIR}/{TUNE_SCRIPT} ({e})")
        except FCError as e:
            if required:
                raise SystemExit(f"FC: {e}")
            say(f"FC: skipped ({e})")
    if ctx.want("radio"):
        try:
            ctx.volume = radio.find_volume(a.volume)
            ctx.model = radio.find_model(ctx.volume, ctx.desired.radio_model)
            ctx.elrs = radio.read_elrs_state(ctx.volume)
            say(f"Pocket: {ctx.volume}, EdgeTX {radio.edgetx_version(ctx.volume)}, model {ctx.model.path.name}")
        except radio.RadioError as e:
            if required:
                raise SystemExit(f"Pocket: {e}")
            say(f"Pocket: skipped ({e})")


def observed_state(ctx: Ctx) -> checks.State:
    s = checks.State()
    if ctx.fc_params is not None:
        s.fc_params = ctx.fc_params
        s.fc_version = ctx.fc_info.version
        s.fc_board = ctx.fc_info.board
        if ctx.desired.tune_targets:
            if ctx.fc_script_read:
                s.fc_tune_script = ctx.fc_script == ctx.tune_script
            else:
                s.skipped.append(f"FC {TUNE_SCRIPT} (MAVLink FTP)")
    else:
        s.skipped.append("FC")
    if ctx.model is not None:
        s.radio_mixes = ctx.model.mixes()
        s.radio_sticks = ctx.model.sticks()
        s.radio_module_crsf = ctx.model.module_is_crsf()
        s.radio_boot_script = ctx.model.has_boot_script()
        s.edgetx_version = radio.edgetx_version(ctx.volume)
    else:
        s.skipped.append("Pocket")
    if ctx.elrs is not None:
        s.elrs_tx = ctx.elrs.actual or None
        s.elrs_tx_version = ctx.elrs.tx_version
        s.elrs_rx_version = ctx.elrs.rx_version
        s.elrs_overrides = {k: (v, ctx.desired.elrs.get(k, "?")) for k, v in ctx.elrs.overrides.items()}
    elif ctx.model is not None:
        s.skipped.append("ELRS (no state.txt yet: the boot script hasn't run)")
    return s


def want_defaults(ctx: Ctx) -> str | None:
    if ctx.fc_params is None:
        return None
    return defaults_file(ctx.desired, ctx.fc_params)


def flash_statuses(ctx: Ctx) -> list[firmware.ChipStatus]:
    out = []
    if ctx.want("fc"):
        info = ctx.fc_info
        out.append(firmware.fc_status(ctx.lock, info and info.version, info and info.git_hash,
                                      ctx.fc_stamp, want_defaults(ctx)))
    if ctx.want("radio"):
        ver = radio.edgetx_version(ctx.volume) if ctx.volume else None
        out.append(firmware.simple_status("edgetx", ctx.lock, ver, "radio.yml semver"))
        tx = ctx.elrs.tx_version if ctx.elrs else None
        rx = ctx.elrs.rx_version if ctx.elrs else None
        out.extend(firmware.elrs_status(ctx.lock, tx, rx))
    return out


def print_findings(findings: list[checks.Finding]) -> int:
    errors = 0
    for f in findings:
        say(f"  {f}")
        errors += f.level == "error"
    if not findings:
        say("  all rules pass")
    return errors


# --- plans --------------------------------------------------------------------

def fc_changes(ctx: Ctx) -> dict[str, tuple[float | None, float]]:
    want = ctx.desired.resolve_params(ctx.fc_params)
    out = {}
    for name, v in sorted(want.items()):
        cur = ctx.fc_params.get(name)
        if cur is None or abs(cur - v) > PARAM_TOL:
            out[name] = (cur, v)
    return out


def print_plan(ctx: Ctx) -> bool:
    """Prints what apply would do. Returns True if anything would change."""
    any_change = False
    if ctx.fc_params is not None:
        ch = fc_changes(ctx)
        say(f"\nFC params ({len(ch)} to change):")
        for name, (cur, v) in ch.items():
            reboot = "  (needs reboot)" if needs_reboot(name) else ""
            missing = "  (missing on FC!)" if cur is None else ""
            say(f"  {name}: {_f(cur)} -> {_f(v)}{reboot}{missing}")
        any_change |= bool(ch)
        if script_pending(ctx):
            say(f"  install {SCRIPTS_DIR}/{TUNE_SCRIPT}  (needs reboot)")
            any_change = True
    if ctx.model is not None:
        mix = ctx.model.plan_mixes(ctx.desired.radio_mixes)
        scripts = radio.scripts_pending(ctx.volume, ctx.scripts)
        cfg_path = ctx.volume / radio.ELRS_CFG
        cfg_want = {k: v for k, v in ctx.desired.elrs.items()}
        cfg_have = radio.read_kv(cfg_path) if cfg_path.exists() else {}
        cfg_have.pop("reset", None)
        say(f"\nPocket model {ctx.model.path.name}:")
        for m in mix:
            say(f"  {m}")
        for s in scripts:
            say(f"  install {s}")
        if cfg_have != cfg_want:
            say(f"  write {radio.ELRS_CFG}: " + ", ".join(f"{k}={v}" for k, v in cfg_want.items()))
        if not (mix or scripts or cfg_have != cfg_want):
            say("  nothing to change")
        any_change |= bool(mix or scripts or cfg_have != cfg_want)
        if ctx.elrs is not None:
            pending = {k: v for k, v in cfg_want.items() if ctx.elrs.actual.get(k) != v and k not in ctx.elrs.overrides}
            if pending:
                say("  ELRS module (applied by the boot script next power-up): "
                    + ", ".join(f"{k} {ctx.elrs.actual.get(k, '?')} -> {v}" for k, v in pending.items()))
    return any_change


def script_pending(ctx: Ctx) -> bool:
    want = ctx.tune_script
    return want is not None and ctx.fc_script != want


def _f(v) -> str:
    if v is None:
        return "-"
    return str(int(v)) if float(v).is_integer() else f"{v:g}"


# --- commands -----------------------------------------------------------------

def cmd_check(ctx: Ctx) -> int:
    load_config(ctx)
    say("quad.yaml rules on the desired state:")
    return 1 if print_findings(checks.run(ctx.cfg, ctx.desired, checks.desired_state(ctx.cfg, ctx.desired))) else 0


def backup(ctx: Ctx) -> Path:
    ts = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    out = ctx.root / "backups" / ts
    out.mkdir(parents=True, exist_ok=True)
    if ctx.fc_params is not None:
        write_param_file(out / "fc.param", ctx.fc_params)
        info = ctx.fc_info
        if ctx.fc_script is not None:
            (out / TUNE_SCRIPT).write_text(ctx.fc_script)
        (out / "fc.json").write_text(json.dumps(
            {"version": info.version, "git_hash": info.git_hash, "board": info.board, "stamp": ctx.fc_stamp}, indent=2))
    if ctx.model is not None:
        shutil.copy2(ctx.model.path, out / ctx.model.path.name)
        shutil.copy2(ctx.volume / "RADIO" / "radio.yml", out / "radio.yml")
        for rel in (radio.ELRS_CFG, radio.ELRS_STATE):
            if (ctx.volume / rel).exists():
                shutil.copy2(ctx.volume / rel, out / Path(rel).name)
    say(f"backup: {out.relative_to(ctx.root)}")
    return out


def cmd_pull(ctx: Ctx) -> int:
    load_config(ctx)
    connect(ctx, required=False)
    if ctx.fc_params is None and ctx.model is None:
        say("nothing connected")
        return 1
    backup(ctx)
    return 0


def cmd_plan(ctx: Ctx) -> int:
    load_config(ctx)
    connect(ctx, required=False)
    errors = print_findings_desired(ctx)
    print_plan(ctx)
    say("\nFirmware:")
    for s in flash_statuses(ctx):
        say(f"  {s}")
    return 1 if errors else 0


def print_findings_desired(ctx: Ctx) -> int:
    findings = checks.run(ctx.cfg, ctx.desired, checks.desired_state(ctx.cfg, ctx.desired))
    bad = [f for f in findings if f.level != "info"]
    if bad:
        say("\nquad.yaml:")
        print_findings(bad)
    return sum(f.level == "error" for f in findings)


def cmd_verify(ctx: Ctx) -> int:
    load_config(ctx)
    connect(ctx, required=False)
    s = observed_state(ctx)
    say("\nRules on what the devices hold:")
    errors = print_findings(checks.run(ctx.cfg, ctx.desired, s))
    for sk in s.skipped:
        say(f"  not checked: {sk}")
    statuses = flash_statuses(ctx)
    say("\nFirmware:")
    for st in statuses:
        say(f"  {st}")
    errors += sum(st.status == firmware.REQUIRED for st in statuses)
    stamps = []
    if ctx.fc_stamp:
        stamps.append(("FC", ctx.fc_stamp.get("quad_sha256")))
    if ctx.volume and (ctx.volume / radio.STAMP).exists():
        stamps.append(("Pocket", radio.read_kv(ctx.volume / radio.STAMP).get("quad_sha256")))
    for who, h in stamps:
        if h != ctx.cfg.digest:
            say(f"  {who} was last applied from a different quad.yaml ({(h or '?')[:12]})")
    return 1 if errors else 0


def cmd_apply(ctx: Ctx) -> int:
    load_config(ctx)
    if print_findings_desired(ctx):
        say("fix quad.yaml first")
        return 1
    connect(ctx, required=True)
    statuses = flash_statuses(ctx)
    required = [s for s in statuses if s.status == firmware.REQUIRED]
    for s in statuses:
        if s.status in (firmware.REQUIRED, firmware.STALE):
            say(f"firmware: {s}")
    if required and not ctx.args.flash:
        say("firmware differs from firmware.lock: run `quadctl flash` (or `apply --flash`) first")
        return 1
    if required:
        if cmd_flash(ctx, statuses=statuses):
            return 1
        if ctx.fc is not None:
            ctx.fc.close()
            ctx.fc = None
        connect(ctx, required=True)  # re-read after flashing
    if not print_plan(ctx) and not ctx.args.reset_elrs:
        say("\nnothing to do")
        write_stamps(ctx)
        return 0
    if not confirm(ctx.args, "\napply these changes?"):
        return 1
    backup(ctx)

    if ctx.fc is not None:
        apply_fc(ctx)
    if ctx.model is not None:
        apply_radio(ctx)
    write_stamps(ctx)
    if ctx.volume is not None:
        eject(ctx.volume)
    say("done")
    return 0


def apply_fc(ctx: Ctx) -> None:
    fc = ctx.fc
    fc.require_disarmed()
    changes = fc_changes(ctx)
    for name, (cur, v) in changes.items():
        if cur is None:
            raise SystemExit(f"FC has no param {name}; wrong firmware? nothing else was written")
    for name, (_, v) in changes.items():
        fc.set_param(name, v)
        say(f"FC: {name} = {_f(v)}")
    ctx.fc_params = fc.fetch_params()
    left = fc_changes(ctx)
    if left:
        raise SystemExit("FC: params didn't stick: " + ", ".join(left) +
                         "\nThe Pocket was not touched. Restore with `quadctl restore <backup>`.")
    script = script_pending(ctx)
    if script:
        path = f"{SCRIPTS_DIR}/{TUNE_SCRIPT}"
        fc.put_file(path, ctx.tune_script)
        if fc.get_file(path) != ctx.tune_script:
            raise SystemExit(f"FC: {path} didn't read back as written. The Pocket was not touched.")
        ctx.fc_script = ctx.tune_script
        say(f"FC: installed {path}")
    if (script or any(needs_reboot(n) for n in changes)) and confirm(ctx.args, "FC: some changes need a reboot. reboot now?"):
        fc.reboot()
        say("FC: rebooting")
        time.sleep(5)
        ctx.fc.close()
        ctx.fc = FC.connect(ctx.args.port, timeout=15)
        ctx.fc_info = ctx.fc.info()


def apply_radio(ctx: Ctx) -> None:
    m = ctx.model
    problems = m.check_layout()
    if problems:
        raise SystemExit(f"Pocket: {m.path.name} has a layout quadctl doesn't know ({'; '.join(problems)}). "
                         "Nothing on the radio was changed.")
    if m.plan_mixes(ctx.desired.radio_mixes):
        m.set_mixes(ctx.desired.radio_mixes)
        m.save()
        again = radio.ModelFile(m.path, m.path.read_text())
        if again.plan_mixes(ctx.desired.radio_mixes):
            raise SystemExit("Pocket: model edit didn't read back as expected; restore it from the backup")
        say(f"Pocket: updated mixes in {m.path.name}")
    for s in radio.install_scripts(ctx.volume, ctx.scripts):
        say(f"Pocket: installed {s}")
    reset = str(int(time.time())) if ctx.args.reset_elrs else None
    radio.write_elrs_cfg(ctx.volume, ctx.desired.elrs, reset)
    say(f"Pocket: wrote {radio.ELRS_CFG}")
    if not m.has_boot_script():
        say("Pocket: add the boot script once on the radio: Model > Special Functions > ON > Lua Script > qelrs")


def write_stamps(ctx: Ctx) -> None:
    now = dt.datetime.now().isoformat(timespec="seconds")
    if ctx.volume is not None:
        (ctx.volume / radio.STAMP).write_text(f"quad_sha256={ctx.cfg.digest}\napplied={now}\n")
    if ctx.fc is not None:
        stamp = dict(ctx.fc_stamp or {})
        stamp.update({"quad_sha256": ctx.cfg.digest, "applied": now})
        try:
            ctx.fc.write_stamp(stamp)
            ctx.fc_stamp = stamp
        except Exception as e:
            say(f"FC: couldn't write the stamp ({e}); verify will report it")


def eject(volume: Path) -> None:
    subprocess.run(["sync"], check=False)
    if platform.system() == "Darwin":
        subprocess.run(["diskutil", "eject", str(volume)], check=False)
        say("Pocket: ejected")


def cmd_flash(ctx: Ctx, statuses=None) -> int:
    if statuses is None:
        load_config(ctx)
        connect(ctx, required=False)
        statuses = flash_statuses(ctx)
    for s in statuses:
        say(f"  {s}")
    if ctx.args.check:
        return 0
    todo = {s.chip for s in statuses if s.status == firmware.REQUIRED}
    if ctx.args.defaults and any(s.chip == "fc" and s.status == firmware.STALE for s in statuses):
        todo.add("fc")
    if not todo:
        say("nothing to flash")
        return 0
    if "fc" in todo:
        if ctx.fc is None:
            say("fc: not connected")
            return 1
        ctx.fc.require_disarmed()
        if not confirm(ctx.args, "flash the FC?"):
            return 1
        backup(ctx)
        text = want_defaults(ctx)
        image = firmware.build_fc_image(ctx.lock, text, firmware.CACHE / "fc-with-defaults.apj")
        port = ctx.fc.port
        ctx.fc.close()
        ctx.fc = None
        firmware.flash_fc(ctx.lock, image, port)
        say("fc: flashed, waiting for it to boot")
        time.sleep(8)
        ctx.fc = FC.connect(ctx.args.port, timeout=20)
        ctx.fc_info = ctx.fc.info()
        stamp = dict(ctx.fc_stamp or {})
        stamp["defaults_sha256"] = firmware.defaults_digest(text)
        stamp["firmware_sha256"] = ctx.lock["fc"]["sha256"]
        ctx.fc.write_stamp(stamp)
        ctx.fc_stamp = stamp
        say(f"fc: now ArduCopter {ctx.fc_info.version}")
    if "edgetx" in todo:
        say("edgetx: switch the Pocket off, then plug it into USB (it shows up as an STM32 bootloader)")
        if not confirm(ctx.args, "ready?"):
            return 1
        firmware.flash_edgetx(ctx.lock)
        say("edgetx: flashed. The radio may upgrade its model files on first boot; quadctl re-reads them before editing.")
    if todo & {"elrs-tx", "elrs-rx"}:
        v = (ctx.lock.get("elrs") or {}).get("version")
        say(f"elrs: flash both to {v} with ExpressLRS Configurator (same binding phrase):\n"
            "  1. RP1: power it, open the ELRS Lua and pick Enable WiFi (or wait 60 s), flash over WiFi.\n"
            "  2. Pocket module: Configurator method 'EdgeTX Passthrough', Pocket in USB Serial (VCP) mode.\n"
            "  Then power the radio once so the boot script records the new version.")
    return 0


def cmd_lock(ctx: Ctx) -> int:
    path = ctx.root / "config" / "firmware.lock"
    lock = firmware.load_lock(path)
    notes = firmware.lock_hashes(lock)
    firmware.save_lock(path, lock)
    for n in notes:
        say(n)
    say("firmware.lock is complete" if not notes else "updated firmware.lock; commit it")
    return 0


def cmd_restore(ctx: Ctx) -> int:
    load_config(ctx)
    src = Path(ctx.args.backup)
    connect(ctx, required=False)
    if ctx.fc is not None and (src / "fc.param").exists():
        ctx.fc.require_disarmed()
        old = read_param_file(src / "fc.param")
        diff = {k: v for k, v in old.items() if k in ctx.fc_params and abs(ctx.fc_params[k] - v) > PARAM_TOL}
        say(f"FC: {len(diff)} params differ from the backup")
        if diff and confirm(ctx.args, "restore them?"):
            for k, v in diff.items():
                ctx.fc.set_param(k, v)
            say("FC: restored (reboot if SERIAL/RCMAP/BATT_MONITOR/RC_OPTIONS changed)")
    if ctx.model is not None:
        saved = src / ctx.model.path.name
        if saved.exists() and confirm(ctx.args, f"restore {saved.name} on the Pocket?"):
            shutil.copy2(saved, ctx.model.path)
            say("Pocket: restored")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="quadctl", description=__doc__)
    ap.add_argument("--root", type=Path, help="repo root (default: found from the current directory)")
    ap.add_argument("--port", help="FC serial port (default: auto)")
    ap.add_argument("--volume", help="Pocket SD card mount (default: auto)")
    ap.add_argument("--only", choices=["fc", "radio"], help="work on one device")
    ap.add_argument("-y", "--yes", action="store_true", help="don't ask for confirmation")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("check", help="validate quad.yaml and run the rules offline")
    sub.add_parser("pull", help="back up both devices")
    sub.add_parser("plan", help="show what apply would change")
    p = sub.add_parser("apply", help="back up, then write the FC and the Pocket")
    p.add_argument("--flash", action="store_true", help="flash required firmware first")
    p.add_argument("--reset-elrs", action="store_true", help="drop ELRS overrides made on the radio")
    sub.add_parser("verify", help="read both devices and run the rules on what they hold")
    p = sub.add_parser("flash", help="flash firmware that differs from firmware.lock")
    p.add_argument("--check", action="store_true", help="only report")
    p.add_argument("--defaults", action="store_true", help="also reflash the FC when only its embedded defaults are stale")
    sub.add_parser("lock", help="fill sha256 values in firmware.lock")
    p = sub.add_parser("restore", help="put a backup back")
    p.add_argument("backup")
    args = ap.parse_args(argv)
    if not hasattr(args, "flash"):
        args.flash = False
    if not hasattr(args, "reset_elrs"):
        args.reset_elrs = False
    if not hasattr(args, "check"):
        args.check = False
    if not hasattr(args, "defaults"):
        args.defaults = False
    root = args.root or find_root(Path.cwd())
    ctx = Ctx(root=root, args=args)
    cmds = {"check": cmd_check, "pull": cmd_pull, "plan": cmd_plan, "apply": cmd_apply,
            "verify": cmd_verify, "flash": cmd_flash, "lock": cmd_lock, "restore": cmd_restore}
    try:
        return cmds[args.cmd](ctx)
    except (FCError, radio.RadioError, firmware.FirmwareError) as e:
        say(f"error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
