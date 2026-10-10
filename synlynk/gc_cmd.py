import os
import subprocess
import json
import shutil
import time
from pathlib import Path

def cmd_gc(dry_run: bool = True, yes: bool = False, retention_days: int = 14, size_budget_mb: int = 1024):
    """
    Garbage collect merged worktrees and orphaned state.db shards.
    """
    if yes:
        dry_run = False
        
    print(f"Running synlynk gc (dry_run={dry_run}, retention_days={retention_days}, size_budget_mb={size_budget_mb})")
    
    # 1. Find worktrees
    worktrees = []
    try:
        wt_out = subprocess.check_output(["git", "worktree", "list", "--porcelain"], stderr=subprocess.DEVNULL).decode()
    except subprocess.CalledProcessError:
        print("Not a git repository. Skipping worktree GC.")
        wt_out = ""
        
    if wt_out:
        current_wt = {}
        for line in wt_out.splitlines():
            if line.startswith("worktree "):
                if current_wt:
                    worktrees.append(current_wt)
                current_wt = {"path": line.split(" ", 1)[1]}
            elif line.startswith("branch "):
                current_wt["branch"] = line.split(" ", 1)[1].replace("refs/heads/", "")
        if current_wt:
            worktrees.append(current_wt)
            
        # Get PRs
        try:
            pr_out = subprocess.check_output(["gh", "pr", "list", "--state", "all", "--json", "headRefName,state,mergedAt"], stderr=subprocess.DEVNULL).decode()
            prs = json.loads(pr_out)
        except Exception:
            prs = []
            
        merged_branches = {pr["headRefName"] for pr in prs if pr.get("state") == "MERGED" or pr.get("mergedAt")}
        
        try:
            main_ref = subprocess.check_output(["git", "rev-parse", "origin/main"], stderr=subprocess.DEVNULL).decode().strip()
        except subprocess.CalledProcessError:
            main_ref = None

        to_delete_wts = []
        for wt in worktrees:
            path = wt["path"]
            branch = wt.get("branch")
            if not branch:
                continue
            if branch in ("main", "master", "origin/main", "origin/master"):
                continue
                
            merged = False
            if branch in merged_branches:
                merged = True
            elif main_ref:
                try:
                    subprocess.check_call(["git", "merge-base", "--is-ancestor", branch, main_ref], stderr=subprocess.DEVNULL)
                    merged = True
                except subprocess.CalledProcessError:
                    pass
                    
            if merged:
                to_delete_wts.append(wt)
                
        print(f"\nWorktrees to remove: {len(to_delete_wts)}")
        for wt in to_delete_wts:
            print(f"  - {wt['path']} (branch: {wt['branch']})")
            if not dry_run:
                try:
                    subprocess.check_call(["git", "worktree", "remove", "--force", wt['path']])
                    print(f"    ✓ Removed {wt['path']}")
                except subprocess.CalledProcessError as e:
                    print(f"    ✗ Failed to remove {wt['path']}: {e}")
                    
    # 2. State.db shards / job records
    projects_dir = Path(os.path.expanduser("~/.synlynk/projects"))
    if projects_dir.exists():
        now = time.time()
        retention_secs = retention_days * 86400
        
        all_shards = []
        total_size_bytes = 0
        
        for shard in projects_dir.iterdir():
            if shard.is_dir():
                state_db = shard / "state.db"
                if state_db.exists():
                    mtime = state_db.stat().st_mtime
                    shard_size = sum(f.stat().st_size for f in shard.rglob('*') if f.is_file())
                    total_size_bytes += shard_size
                    all_shards.append({
                        "path": shard,
                        "name": shard.name,
                        "mtime": mtime,
                        "size": shard_size
                    })
                    
        # Sort by oldest first
        all_shards.sort(key=lambda x: x["mtime"])
        
        to_delete_shards = []
        
        # 1. Enforce retention window
        for shard in all_shards:
            if now - shard["mtime"] > retention_secs:
                to_delete_shards.append(shard)
                total_size_bytes -= shard["size"]
                
        # 2. Enforce size budget (MB)
        # Re-evaluate total size against budget
        size_budget_bytes = size_budget_mb * 1024 * 1024
        
        if total_size_bytes > size_budget_bytes:
            print(f"Remaining shards ({total_size_bytes/1024/1024:.2f} MB) exceed budget ({size_budget_mb} MB). Aggressive pruning.")
            for shard in [s for s in all_shards if s not in to_delete_shards]:
                if total_size_bytes <= size_budget_bytes:
                    break
                to_delete_shards.append(shard)
                total_size_bytes -= shard["size"]
                
        shards_freed_bytes = sum(s["size"] for s in to_delete_shards)
        print(f"\nScanning state.db shards in {projects_dir} ...")
        print(f"Shards to remove: {len(to_delete_shards)} (Freeing {shards_freed_bytes/1024/1024:.2f} MB)")
        
        for shard in to_delete_shards:
            days_old = (now - shard["mtime"]) / 86400
            print(f"  - {shard['name']} ({days_old:.1f} days old, size: {shard['size']/1024/1024:.2f} MB)")
            if not dry_run:
                try:
                    shutil.rmtree(shard["path"])
                    print(f"    ✓ Removed shard {shard['name']}")
                except Exception as e:
                    print(f"    ✗ Failed to remove shard {shard['name']}: {e}")

    if dry_run:
        print("\nThis was a dry run. Use --yes to apply changes.")
