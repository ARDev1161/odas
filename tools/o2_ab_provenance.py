#!/usr/bin/env python3
"""Fail-closed provenance gate for paired ODAS acoustic A/B runs.

This checks experimental comparability, NOT SSL/SST/SSS quality.
Input: JSON manifest for each variant with identical immutable stimulus,
oracle, geometry, channel map, algorithm configuration and seed.
"""
import argparse
import hashlib
import json
from pathlib import Path

COMMON = ("scenario", "wav_sha256", "oracle_sha256", "geometry_m",
          "pcm_channels", "ssl_config_sha256", "sst_config_sha256",
          "sss_config_sha256", "seed")
VARIANTS = ("upstream", "dev", "feature")


def validate(manifests):
    if set(manifests) != set(VARIANTS):
        raise ValueError("requires exactly upstream, dev and feature")
    base = manifests["upstream"]
    for variant in VARIANTS:
        m = manifests[variant]
        if not isinstance(m, dict):
            raise ValueError(f"{variant}: invalid manifest")
        for key in COMMON:
            if key not in m or m[key] is None:
                raise ValueError(f"{variant}: missing {key}")
            if m[key] != base[key]:
                raise ValueError(f"{variant}: incomparable {key}")
        if not isinstance(m.get("commit_sha"), str) or len(m["commit_sha"]) != 40 or any(
                c not in "0123456789abcdef" for c in m["commit_sha"]):
            raise ValueError(f"{variant}: invalid commit_sha")
        for key in ("wav_sha256", "oracle_sha256", "ssl_config_sha256",
                    "sst_config_sha256", "sss_config_sha256"):
            v = m[key]
            if not isinstance(v, str) or len(v) != 64 or any(
                    c not in "0123456789abcdef" for c in v):
                raise ValueError(f"{variant}: invalid {key}")
        if m["pcm_channels"] != [1, 2, 3, 4]:
            raise ValueError(f"{variant}: incorrect PCM channel map")
        if m["geometry_m"] != [[0.032, 0, 0], [0, 0.032, 0],
                                [-0.032, 0, 0], [0, -0.032, 0]]:
            raise ValueError(f"{variant}: incorrect ReSpeaker geometry")
        if type(m["seed"]) is not int:
            raise ValueError(f"{variant}: invalid seed")
    return {"status": "COMPARABLE_INPUTS_ONLY_NOT_QUALITY_PASS",
            "scenario": base["scenario"],
            "variants": {v: manifests[v]["commit_sha"] for v in VARIANTS},
            "stimulus_sha256": base["wav_sha256"]}


def main():
    parser = argparse.ArgumentParser()
    for name in VARIANTS:
        parser.add_argument(name, type=Path)
    args = parser.parse_args()
    manifests = {name: json.loads(getattr(args, name).read_text())
                 for name in VARIANTS}
    print(json.dumps(validate(manifests), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
