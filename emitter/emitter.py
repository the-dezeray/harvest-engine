import asyncio
import httpx
import random
import time
import os
import glob
import pandas as pd

# configuration
API_URL = os.getenv("API_URL", "http://localhost:8000/ingest")
SCENARIO_URL = os.getenv("SCENARIO_URL", "http://localhost:8000/scenario")
SEND_INTERVAL = float(os.getenv("SEND_INTERVAL", "2.0"))
DATA_FOLDER = os.getenv("DATA_FOLDER", "institution_subnets/agg_1_day")

# access points that are busier than normal
HOTSPOTS = {"LIB-AP-01", "SRC-AP-01", "SRC-AP-02"}

# all campus buildings and their access points
BUILDINGS = {
    "LIB":    ["LIB-AP-01", "LIB-AP-02", "LIB-AP-03"],
    "ENG":    ["ENG-AP-01", "ENG-AP-02", "ENG-AP-03", "ENG-AP-04"],
    "SRC":    ["SRC-AP-01", "SRC-AP-02"],
    "ADMIN":  ["ADMIN-AP-01", "ADMIN-AP-02"],
    "HOSTEL": [f"HOSTEL-AP-{i:02d}" for i in range(1, 11)],
    "LAB":    [f"LAB-AP-{i:02d}" for i in range(1, 8)],
    "SPORTS": ["SPORTS-AP-01", "SPORTS-AP-02"],
    "CAFE":   ["CAFE-AP-01", "CAFE-AP-02"],
    "HEALTH": ["HEALTH-AP-01"],
    "GATE":   ["GATE-AP-01"],
}

ALL_APS = [ap for aps in BUILDINGS.values() for ap in aps]

def load_replay_data():
    """loads 30% of the cesnet training data for replay."""
    csv_files = glob.glob(os.path.join(DATA_FOLDER, "*.csv"))
    csv_files.sort()

    if not csv_files:
        print(f"[warning] no data in {DATA_FOLDER} - using random mode")
        return {}

    # use 30% subset as requested
    n_replay = max(1, int(len(csv_files) * 0.30))
    replay_files = csv_files[:n_replay]
    print(f"[emitter] replaying {len(replay_files)} files (30% of training set)")

    profiles = {}
    for i, ap_id in enumerate(ALL_APS):
        path = replay_files[i % len(replay_files)]
        try:
            df = pd.read_csv(path)
            # scale large cesnet metrics to realistic AP values
            devices = (df["n_flows"].fillna(0) / 50000).clip(1, 200).astype(int).tolist()
            bandwidth = (df["n_bytes"].fillna(0) / 1e9).round(2).tolist()
            profiles[ap_id] = {"devices": devices, "bandwidth": bandwidth}
        except Exception as e:
            print(f"[error] loading {path}: {e}")
    return profiles

class AccessPoint:
    def __init__(self, ap_id, profile=None):
        self.ap_id = ap_id
        self.building = ap_id.split("-")[0]
        self.multiplier = 2 if ap_id in HOTSPOTS else 1
        self.alive = True
        self.profile = profile
        self.index = 0
        self.load = random.randint(10, 30)

    def next_metrics(self):
        if self.profile:
            idx = self.index % len(self.profile["devices"])
            d = self.profile["devices"][idx]
            b = self.profile["bandwidth"][idx]
            self.index += 1
            return int(d * self.multiplier), round(b * self.multiplier, 2)
        else:
            self.load = max(1, min(100, self.load + random.randint(-2, 2)))
            return int(self.load * self.multiplier), round(self.load * 0.5, 2)

    def generate(self, mode):
        if not self.alive: return None
        if mode == "failure" and random.random() < 0.2:
            self.alive = False
            return None

        base_devices, base_bw = self.next_metrics()

        if mode == "spike":
            base_devices = int(base_devices * 2.5)
            base_bw = round(base_bw * 3.0, 2)
            loss = round(random.uniform(5, 15), 2)
        elif mode == "cooldown":
            base_devices = max(1, int(base_devices * 0.3))
            base_bw = round(base_bw * 0.3, 2)
            loss = 0.0
        else:
            loss = round(random.uniform(0, 1.5), 2)

        return {
            "ap_id": self.ap_id,
            "timestamp": time.time(),
            "connected_devices": base_devices,
            "bandwidth_mbps": base_bw,
            "signal_strength_dbm": random.randint(-75, -40),
            "packet_loss_pct": loss,
            "building": self.building
        }

    def revive(self):
        self.alive = True

async def run_ap(ap, client):
    mode = "normal"
    while True:
        try:
            res = await client.get(SCENARIO_URL, timeout=3)
            new_mode = res.json().get("mode", "normal")
            if new_mode == "normal" and mode == "failure" and not ap.alive:
                ap.revive()
            mode = new_mode
        except Exception: pass

        reading = ap.generate(mode)
        if reading:
            try:
                await client.post(API_URL, json=reading, timeout=5)
            except Exception: pass
        await asyncio.sleep(SEND_INTERVAL)

async def main():
    profiles = load_replay_data()
    aps = [AccessPoint(ap_id, profiles.get(ap_id)) for ap_id in ALL_APS]
    print(f"\n[emitter] starting {len(aps)} APs (replay: {bool(profiles)})")
    
    async with httpx.AsyncClient() as client:
        tasks = [run_ap(ap, client) for ap in aps]
        await asyncio.gather(*tasks)

if __name__ == "__main__":
    asyncio.run(main())
