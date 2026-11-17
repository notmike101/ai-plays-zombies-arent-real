"""Episode harness for Zombies Aren't Real automation.

Manages one game instance (a copy under game-copies/), injects the virtual-input DLL,
drives planning/battle via virtual keyboard+mouse, monitors via screenshots, and records
episodes under D:/zar-scratch/sessions/.

Primitives (all unfocused, per-instance virtual):
  Instance.launch()          launch a copy, inject, attach VirtualInput
  inst.nav_boston_l5()       keyboard navigation to Boston campaign level 5 planning
  inst.arm(n)                arm planning unit n (1 Garrison, 2 Mortar, 3 Sniper, 4 Turret)
  inst.click_at(x, y)        virtual click in client coords
  inst.zone(corners)         draw a safe zone (B, click corners, Enter)
  inst.ready()               Space (with YES confirm)
  inst.set_speed(n)          admin console "game speed n"
  inst.run_battle(poll=...)  wait for the end screen, return episode result
  inst.close()               kill the process

Usage:
  python harness.py --instance inst2 --episode test1
"""
import sys, os, time, json, shutil, subprocess, ctypes
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from zar_input import VirtualInput, SC
from game_drive import grab

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
COPIES = os.path.join(ROOT, "game-copies")
SESSIONS = os.path.join(ROOT, "sessions")

EXE = "zombies-arent-real.exe"


class Instance:
    def __init__(self, name, launch=True):
        self.name = name
        self.dir = os.path.join(COPIES, name)
        self.proc = None
        self.pid = None
        self.hwnd = None
        self.vi = None
        self.ep_dir = None
        if launch:
            self.launch()

    # ---- lifecycle -------------------------------------------------------------------
    def launch(self, wait=16):
        log = open(os.path.join(ROOT, "analysis", f"{self.name}_launch.log"), "wb")
        self.proc = subprocess.Popen([os.path.join(self.dir, EXE)], cwd=self.dir,
                                     stdout=log, stderr=subprocess.STDOUT)
        time.sleep(wait)
        self.pid = self.proc.pid
        self.hwnd = self._find_hwnd()
        if not self.hwnd:
            raise RuntimeError(f"window not found for pid {self.pid}")
        self.vi = VirtualInput(self.pid, hwnd=self.hwnd)
        return self

    def _find_hwnd(self):
        user32 = ctypes.windll.user32
        out = []

        @ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
        def cb(hwnd, lp):
            pid = ctypes.c_ulong()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            if pid.value == self.pid and user32.IsWindowVisible(hwnd):
                t = ctypes.create_unicode_buffer(128)
                user32.GetWindowTextW(hwnd, t, 128)
                if t.value:
                    out.append(hwnd)
            return True
        user32.EnumWindows(cb, 0)
        return out[0] if out else None

    def close(self):
        if self.proc:
            self.proc.kill()
            self.proc = None
        if self.vi:
            self.vi.close()
            self.vi = None

    # ---- episode recording -------------------------------------------------------------
    def start_episode(self, tag="ep"):
        self.ep_id = f"{tag}-{int(time.time())}"
        self.ep_dir = os.path.join(SESSIONS, self.name, self.ep_id)
        os.makedirs(self.ep_dir, exist_ok=True)
        self.actions = []
        return self.ep_dir

    def log_action(self, kind, **kw):
        rec = {"t": round(time.time(), 3), "kind": kind, **kw}
        self.actions.append(rec)
        with open(os.path.join(self.ep_dir, "actions.jsonl"), "a") as f:
            f.write(json.dumps(rec) + "\n")

    def shot(self, label):
        if self.ep_dir:
            p = os.path.join(self.ep_dir, f"{label}.png")
            grab(self.hwnd).save(p)
            return p
        grab(self.hwnd).save(os.path.join(ROOT, "analysis", f"{label}.png"))

    # ---- virtual input helpers -----------------------------------------------------------
    def key(self, vk, sc=None):
        self.vi.key_press(vk, sc if sc is not None else SC.get(vk, 0))
        self.log_action("key", vk=vk)

    def click_at(self, x, y):
        self.vi.click(x, y)
        self.log_action("click", x=x, y=y)

    def arm(self, n):
        """1 Garrison, 2 Mortar, 3 Sniper, 4 Turret (per the DEPLOY panel)."""
        self.key(0x30 + n)
        time.sleep(0.25)

    # ---- navigation ------------------------------------------------------------------------
    def nav_boston_l5(self):
        """Fresh launch -> welcome -> campaign -> Boston -> continue level 5."""
        time.sleep(1.0)
        self.key(0x20)  # Space: skip welcome
        time.sleep(1.2)
        self.key(0x0D)  # Enter: CAMPAIGN
        time.sleep(1.0)
        self.key(0x0D)  # Enter: Boston (first row)
        time.sleep(1.0)
        self.key(0x0D)  # Enter: CONTINUE (LEVEL 5)
        time.sleep(8)   # map install + camera intro
        # skip camera intro if it plays (any key skips)
        self.key(0x20)
        time.sleep(1.0)

    # ---- planning ------------------------------------------------------------------------
    def zone(self, corners):
        """Draw a safe zone through client-coord corners. Returns True if accepted."""
        self.key(0x42)  # B safe zone tool
        time.sleep(0.3)
        for (x, y) in corners:
            self.vi.move_to(x, y)
            time.sleep(0.12)
            self.vi.click()
            time.sleep(0.12)
        self.key(0x0D)  # Enter closes the lasso
        time.sleep(0.5)
        self.log_action("zone", corners=corners)

    def ready(self):
        self.key(0x20)  # opens READY confirm (zones sheltering < bronze)
        time.sleep(0.6)
        self.key(0x20)  # YES (SPACE)
        time.sleep(1.0)
        self.log_action("ready")

    # ---- admin console -----------------------------------------------------------------
    def admin(self, command):
        """Run an admin console command. Enter executes AND closes the console — do NOT
        send Esc afterwards (that opens the pause menu)."""
        self.vi.combo_press([0x11], 0x20, sc=0x39, hold=0.15)  # Ctrl+Space
        time.sleep(0.5)
        for ch in command:
            ctypes.windll.user32.PostMessageW(self.hwnd, 0x102, ord(ch), 1)  # WM_CHAR
            time.sleep(0.02)
        time.sleep(0.3)
        self.key(0x0D)  # Enter: runs and closes
        time.sleep(0.6)
        self.log_action("admin", command=command)

    def set_speed(self, n):
        self.admin(f"game speed {n}")

    # ---- battle monitoring -------------------------------------------------------------
    def run_battle(self, poll_s=5.0, max_s=3600, speed=8, reader=None, abort_below=0.10,
                   start_civ=209867):
        """Set speed, poll until the battle ends. Ends when: progress updates (win),
        or the screen stays static for 3 consecutive polls (defeat/end screen pauses the
        game). Returns dict with result info."""
        self.set_speed(speed)
        t0 = time.time()
        static_count = 0
        prev_small = None
        result = {"ended": False, "how": "timeout"}
        timeline = []
        retry_count = 0
        none_count = 0
        progress_path = os.path.join(self.dir, "steam_cloud", "progress", "Boston__MA.progress")
        prog_mtime0 = os.path.getmtime(progress_path) if os.path.exists(progress_path) else 0
        import numpy as np
        shots = 0
        while time.time() - t0 < max_s:
            time.sleep(poll_s)
            if reader is not None:
                cv = reader.read()
                if cv is None:
                    none_count += 1
                    if none_count in (3, 8):
                        reader.restart()   # heap moved / battle restarted: recalibrate
                else:
                    none_count = 0
                    timeline.append([round(time.time() - t0, 1), cv[0], cv[1]])
                    if cv[0] < abort_below * start_civ:
                        # user directive: don't watch doomed runs — R keeps the board
                        retry_count += 1
                        self.log_action("retry", civ=cv[0], zombies=cv[1])
                        self.key(0x52)
                        time.sleep(1.2)
                        self.key(0x52)
                        time.sleep(2.0)
                        self.set_speed(speed)
                        reader.restart()
                        prev_small = None
                        continue
            img = grab(self.hwnd).convert("RGB").resize((240, 160))
            small = np.asarray(img, dtype=np.int16)
            shots += 1
            if self.ep_dir and shots % 4 == 0:
                img.save(os.path.join(self.ep_dir, f"battle_{int(time.time()-t0):04d}.png"))
            if prev_small is not None:
                diff = float(np.abs(small - prev_small).mean())
                if diff < 0.6:
                    static_count += 1
                else:
                    static_count = 0
                if static_count >= 3:
                    # Could be a menu/pause opened by a stray key. Esc to recover, and if
                    # still static after two recovery attempts, treat the battle as ended.
                    self.key(0x1B)  # Esc closes pause menu / dialogs
                    time.sleep(1.2)
                    self.key(0x20)  # Space resumes a paused battle
                    time.sleep(2.0)
                    img2 = grab(self.hwnd).convert("RGB").resize((240, 160))
                    small2 = np.asarray(img2, dtype=np.int16)
                    if float(np.abs(small2 - small).mean()) < 0.6:
                        result = {"ended": True, "how": "static-screen"}
                        break
                    static_count = 0
                if os.path.exists(progress_path) and \
                        os.path.getmtime(progress_path) > prog_mtime0:
                    result = {"ended": True, "how": "progress-updated"}
                    break
            prev_small = small
        # capture the end state
        time.sleep(1.0)
        self.shot("battle_end")
        result["badge"] = self.read_progress_stage5()
        result["retries"] = retry_count
        result["civ_timeline"] = timeline[-200:]
        result["final_civ"] = timeline[-1][1] if timeline else None
        return result

    def read_progress_stage5(self):
        p = os.path.join(self.dir, "steam_cloud", "progress", "Boston__MA.progress")
        if not os.path.exists(p):
            return None
        for line in open(p, encoding="utf-8", errors="ignore"):
            if line.startswith("stage 5"):
                return line.strip()
        return None

    # ---- checkpoints ----------------------------------------------------------------------
    def snapshot(self, name):
        """Copy the whole steam_cloud folder as a checkpoint."""
        src = os.path.join(self.dir, "steam_cloud")
        dst = os.path.join(SESSIONS, "checkpoints", f"{self.name}-{name}-{int(time.time())}")
        shutil.copytree(src, dst, dirs_exist_ok=True)
        return dst

    def restore(self, path):
        """Restore a steam_cloud snapshot (instance must not be running)."""
        self.close()
        src = path
        dst = os.path.join(self.dir, "steam_cloud")
        shutil.rmtree(dst, ignore_errors=True)
        shutil.copytree(src, dst)
        return self.launch()


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--instance", default="inst2")
    ap.add_argument("--episode", default="ep")
    ap.add_argument("--speed", type=int, default=8)
    args = ap.parse_args()

    inst = Instance(args.instance)
    try:
        inst.start_episode(args.episode)
        inst.nav_boston_l5()
        inst.shot("planning_start")
        # baseline scripted plan (example): turret ring later; MVP = one turret center
        inst.arm(4)
        inst.click_at(960, 500)
        inst.shot("planning_after")
        reader = None
        try:
            from zarmem import SimReader
            reader = SimReader(inst.pid)
            n = reader.calibrate_planning()
            print(f"memory reader: {n} calibration candidates")
        except Exception as e:
            print("reader init failed:", e)
        inst.ready()
        res = inst.run_battle(speed=args.speed, reader=reader)
        print("battle result:", res)
        with open(os.path.join(inst.ep_dir, "result.json"), "w") as f:
            json.dump(res, f, indent=2)
    finally:
        inst.close()


if __name__ == "__main__":
    main()
