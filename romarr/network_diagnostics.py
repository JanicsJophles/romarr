"""Read-only, bounded qBittorrent network evidence, without tracker addresses.

An answering Web UI does not establish working outbound connectivity. Tracker
errors are evidence, not proof that a VPN is broken or that a release is dead.
"""


def tracker_summary(trackers):
    external = [t for t in trackers if str(t.get("url", "")).startswith(("http://", "https://", "udp://"))]
    failed = [t for t in external if t.get("status") == 4]
    dns = sum(any(term in str(t.get("msg", "")).lower() for term in (
        "host not found", "name resolution", "resolve host", "dns", "name or service not known"
    )) for t in failed)
    return {"trackers_checked": len(external), "trackers_failed": len(failed), "tracker_dns_errors": dns}


def inspect_qbit(client, jobs=None):
    """Sample at most three incomplete jobs in this app's category.

    Every network operation has a short timeout. Never returns raw exceptions,
    tracker messages, URLs, peer addresses, names, or job hashes.
    """
    result = {"status": "unknown", "detail": "Outbound download connectivity has not been verified.",
              "jobs_checked": 0, "trackers_checked": 0, "trackers_failed": 0, "tracker_dns_errors": 0}
    try:
        if jobs is None:
            response = client._get("torrents/info", params={"category": client._config.category}, timeout=2)
            response.raise_for_status()
            jobs = response.json()
        if not isinstance(jobs, list):
            return result
        pending = [j for j in jobs if isinstance(j, dict) and isinstance(j.get("progress"), (int, float))
                   and j["progress"] < 1]
        if any(isinstance(j.get("dlspeed"), (int, float)) and j["dlspeed"] > 0 for j in pending):
            return {**result, "status": "transferring", "detail": "The download client is receiving data."}
        for job in pending[:3]:
            job_hash = job.get("hash", "")
            if not isinstance(job_hash, str) or len(job_hash) not in (40, 64) or any(c not in "0123456789abcdefABCDEF" for c in job_hash):
                continue
            response = client._get("torrents/trackers", params={"hash": job_hash}, timeout=2)
            response.raise_for_status()
            trackers = response.json()
            if not isinstance(trackers, list) or any(not isinstance(t, dict) for t in trackers):
                continue
            result["jobs_checked"] += 1
            for key, value in tracker_summary(trackers).items():
                result[key] += value
        if result["tracker_dns_errors"]:
            result.update(status="dns-errors", detail="The client API answers, but trackers report DNS failures. Check the downloader's DNS and network/VPN health; peer availability is not established.")
        elif result["trackers_failed"]:
            result.update(status="tracker-errors", detail="The client API answers, but some trackers report errors. Check downloader connectivity and tracker health.")
        elif pending:
            result.update(status="idle", detail="The client API answers, but no download data is arriving. No tracker DNS failure was identified in this sample.")
    except Exception:
        result.update(status="unknown", detail="Could not inspect outbound connectivity. API availability alone does not verify downloads.")
    return result
