"""
campus network emitter
simulates 40 biust wifi access points sending data to the ingestion api.

uses real cesnet network traffic data if available.
falls back to random data if the dataset hasnt been downloaded yet.

run with: python emitter.py
"""

import asyncio
import httpx
import random
import time
import os
import glob

# where to send data
API_URL = "http://localhost:8000/ingest"
SCENARIO_URL = "http://localhost:8000/scenario"

# how often each AP sends a reading (seconds)
SEND_INTERVAL = 2

# cesnet dataset location
DATA_FOLDER = "./data/ip_addresses_sample/agg_10_minutes"

# access points that are busier than normal (2x load)
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


def load_cesnet_data():
    """
    loads real network traffic from cesnet dataset.
    each csv file = one ip address with 40 weeks of traffic data.
    we normalize the byte counts to a 1-150 device range.
    returns a dict of ap_id -> list of load values, or empty dict if no data.
    """
    csv_files = glob.glob(os.path.join(DATA_FOLDER, "*.csv"))

    if not csv_files:
        print("no cesnet data found - using random mode")
        print(f"download data to: {DATA_FOLDER}")
        return {}

    try:
        import pandas as pd
        import numpy as np
    except ImportError:
        print("pandas not installed - run: pip install pandas numpy")
        return {}

    print(f"loading cesnet data from {len(csv_files)} files...")
    profiles = {}

    for i, ap_id in enumerate(ALL_APS):
        if i >= len(csv_files):
            break  # more APs than files, rest will use random

        try:
            df = pd.read_csv(csv_files[i])

            # use n_bytes column as the traffic signal
            if "n_bytes" in df.columns:
                values = df["n_bytes"].fillna(0).values.astype(float)
            else:
                # fallback to first numeric column
                values = df.select_dtypes(include=[float, int]).iloc[:, 0].fillna(0).values

            # normalize to 1-150 range so it fits our connected_devices field
            v_min, v_max = values.min(), values.max()
            if v_max > v_min:
                normalized = (values - v_min) / (v_max - v_min)
                scaled = (normalized * 149 + 1).astype(int).tolist()
            else:
                scaled = [20] * len(values)  # flat if no variation

            profiles[ap_id] = scaled

        except Exception as e:
            print(f"could not load {csv_files[i]}: {e}")

    print(f"loaded {len(profiles)} cesnet profiles")
    return profiles


class AccessPoint:
    """
    represents one campus wifi access point.
    generates readings based on current scenario mode.
    """

    def __init__(self, ap_id, cesnet_profile=None):
        self.ap_id = ap_id
        self.building = ap_id.split("-")[0]
        self.multiplier = 2 if ap_id in HOTSPOTS else 1
        self.alive = True

        # cesnet replay
        self.profile = cesnet_profile or []
        self.index = 0

        # random mode - drifting base load
        self.load = random.randint(10, 30) * self.multiplier

    def next_load(self):
        """gets next load value from cesnet or random"""
        if self.profile:
            val = self.profile[self.index % len(self.profile)]
            self.index += 1
            return int(val * self.multiplier)
        else:
            self.load += random.randint(-2, 2)
            self.load = max(1, min(100, self.load))
            return int(self.load * self.multiplier)

    def generate(self, mode):
        """returns a reading dict, or None if AP is offline"""
        if not self.alive:
            return None

        # in failure mode, randomly kill this AP
        if mode == "failure" and random.random() < 0.3:
            self.alive = False
            print(f"{self.ap_id} went offline")
            return None

        base = self.next_load()

        # apply mode on top of base load
        if mode == "spike":
            base = min(150 * self.multiplier, int(base * 1.8) + random.randint(10, 30))
            packet_loss = round(random.uniform(5, 20), 2)
        elif mode == "cooldown":
            base = max(1, int(base * 0.5))
            packet_loss = round(random.uniform(0, 2), 2)
        else:
            packet_loss = round(random.uniform(0, 3), 2)

        return {
            "ap_id": self.ap_id,
            "timestamp": time.time(),
            "connected_devices": base,
            "bandwidth_mbps": round(base * random.uniform(0.4, 0.9), 2),
            "signal_strength_dbm": random.randint(-80, -30),
            "packet_loss_pct": packet_loss,
            "building": self.building
        }

    def revive(self):
        """brings AP back online after failure mode"""
        self.alive = True
        self.load = random.randint(10, 30) * self.multiplier
        print(f"{self.ap_id} back online")


async def run_ap(ap, client):
    """
    runs forever for one access point.
    every 2 seconds: check scenario, generate reading, post to api.
    """
    mode = "normal"

    while True:
        # check current scenario
        try:
            res = await client.get(SCENARIO_URL, timeout=3)
            new_mode = res.json().get("mode", "normal")

            # revive APs when switching back to normal
            if new_mode == "normal" and mode == "failure" and not ap.alive:
                ap.revive()

            mode = new_mode
        except Exception:
            pass  # keep last known mode if api is unreachable

        # generate and send reading
        reading = ap.generate(mode)
        if reading:
            try:
                await client.post(API_URL, json=reading, timeout=5)
                print(f"{ap.ap_id} | {reading['connected_devices']} devices | {mode}")
            except Exception as e:
                print(f"{ap.ap_id} failed: {e}")
        else:
            print(f"{ap.ap_id} is offline")

        await asyncio.sleep(SEND_INTERVAL)


async def main():
    # load cesnet data
    cesnet = load_cesnet_data()

    # create all access points
    aps = [AccessPoint(ap_id, cesnet.get(ap_id)) for ap_id in ALL_APS]

    mode = "cesnet replay" if cesnet else "random"
    print(f"\nstarting {len(aps)} access point emitters ({mode})")
    print(f"sending to {API_URL}\n")

    # run all APs at the same time
    async with httpx.AsyncClient() as client:
        tasks = [run_ap(ap, client) for ap in aps]
        await asyncio.gather(*tasks)


if __name__ == "__main__":
    asyncio.run(main())
