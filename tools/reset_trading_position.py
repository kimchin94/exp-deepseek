#!/usr/bin/env python3
"""
Trading Position Reset Utility

This script helps manage the trading position file by:
1. Backing up the current position file
2. Resetting to a specific date or to initial state
3. Allowing you to restart trading from any date
"""

import os
import json
import shutil
from datetime import datetime
from pathlib import Path
import argparse


def backup_position_file(position_file: Path) -> Path:
    """Create a backup of the position file"""
    if not position_file.exists():
        print(f"[!] Position file does not exist: {position_file}")
        return None
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_dir = position_file.parent.parent / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    
    backup_file = backup_dir / f"position_backup_{timestamp}.jsonl"
    shutil.copy2(position_file, backup_file)
    print(f"[OK] Backup created: {backup_file}")
    return backup_file


def get_position_summary(position_file: Path) -> dict:
    """Get summary of current position file"""
    if not position_file.exists():
        return {"exists": False, "records": 0}
    
    records = []
    with open(position_file, "r") as f:
        for line in f:
            if line.strip():
                records.append(json.loads(line))
    
    if not records:
        return {"exists": True, "records": 0}
    
    return {
        "exists": True,
        "records": len(records),
        "first_date": records[0].get("date"),
        "last_date": records[-1].get("date"),
        "last_positions": records[-1].get("positions", {})
    }


def reset_to_date(position_file: Path, target_date: str, backup: bool = True):
    """Reset position file to keep only records up to target_date"""
    if not position_file.exists():
        print(f"[ERROR] Position file does not exist: {position_file}")
        return
    
    # Backup first
    if backup:
        backup_position_file(position_file)
    
    # Read all records
    records = []
    with open(position_file, "r") as f:
        for line in f:
            if line.strip():
                records.append(json.loads(line))
    
    # Filter records up to target_date
    filtered_records = []
    for record in records:
        record_date = record.get("date", "")
        # Handle both "YYYY-MM-DD" and "YYYY-MM-DD HH:MM:SS" formats
        record_date_str = record_date.split()[0] if ' ' in record_date else record_date
        target_date_str = target_date.split()[0] if ' ' in target_date else target_date
        
        if record_date_str <= target_date_str:
            filtered_records.append(record)
    
    # Write filtered records back
    with open(position_file, "w") as f:
        for record in filtered_records:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    
    print(f"[OK] Reset to date: {target_date}")
    print(f"   Kept {len(filtered_records)} records (removed {len(records) - len(filtered_records)})")


def reset_to_init(position_file: Path, backup: bool = True):
    """Reset position file to only the initial record"""
    if not position_file.exists():
        print(f"[ERROR] Position file does not exist: {position_file}")
        return
    
    # Backup first
    if backup:
        backup_position_file(position_file)
    
    # Read first record only
    init_record = None
    with open(position_file, "r") as f:
        first_line = f.readline()
        if first_line.strip():
            init_record = json.loads(first_line)
    
    if not init_record:
        print("[ERROR] No initial record found")
        return
    
    # Write only init record
    with open(position_file, "w") as f:
        f.write(json.dumps(init_record, ensure_ascii=False) + "\n")
    
    print(f"[OK] Reset to initial state")
    print(f"   Initial date: {init_record.get('date')}")


def list_backups(signature: str):
    """List all available backups"""
    project_root = Path(__file__).resolve().parents[1]
    backup_dir = project_root / "data" / "agent_data" / signature / "backups"
    
    if not backup_dir.exists():
        print(f"[INFO] No backups found for {signature}")
        return []
    
    backups = sorted(backup_dir.glob("position_backup_*.jsonl"), reverse=True)
    
    if not backups:
        print(f"[INFO] No backups found for {signature}")
        return []
    
    print(f"\n[BACKUPS] Available backups for {signature}:")
    for i, backup in enumerate(backups, 1):
        stat = backup.stat()
        size_kb = stat.st_size / 1024
        modified = datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S")
        print(f"   {i}. {backup.name} ({size_kb:.1f}KB, {modified})")
    
    return backups


def main():
    parser = argparse.ArgumentParser(description="Reset trading position to restart from a specific date")
    parser.add_argument(
        "--signature",
        default="deepseek-chat-v3.1",
        help="Agent signature (default: deepseek-chat-v3.1)"
    )
    parser.add_argument(
        "--reset-to",
        help="Reset to this date (YYYY-MM-DD), removes all records after this date"
    )
    parser.add_argument(
        "--reset-init",
        action="store_true",
        help="Reset to initial state (keeps only first record)"
    )
    parser.add_argument(
        "--no-backup",
        action="store_true",
        help="Skip creating backup before reset"
    )
    parser.add_argument(
        "--show",
        action="store_true",
        help="Show current position summary"
    )
    parser.add_argument(
        "--list-backups",
        action="store_true",
        help="List all available backups"
    )
    
    args = parser.parse_args()
    
    # Build position file path
    project_root = Path(__file__).resolve().parents[1]
    position_file = project_root / "data" / "agent_data" / args.signature / "position" / "position.jsonl"
    
    # List backups
    if args.list_backups:
        list_backups(args.signature)
        return
    
    # Show summary
    if args.show or (not args.reset_to and not args.reset_init):
        summary = get_position_summary(position_file)
        print(f"\n[SUMMARY] Position Summary for {args.signature}:")
        if not summary["exists"]:
            print("   [ERROR] Position file does not exist")
        elif summary["records"] == 0:
            print("   [INFO] Position file is empty")
        else:
            print(f"   Total records: {summary['records']}")
            print(f"   First date: {summary['first_date']}")
            print(f"   Last date: {summary['last_date']}")
            cash = summary['last_positions'].get('CASH', 0)
            print(f"   Current cash: ${cash:,.2f}")
        
        if not args.reset_to and not args.reset_init:
            print("\n[TIP] Use --reset-to DATE or --reset-init to reset the position")
        return
    
    # Perform reset
    if args.reset_init:
        reset_to_init(position_file, backup=not args.no_backup)
    elif args.reset_to:
        reset_to_date(position_file, args.reset_to, backup=not args.no_backup)
    
    # Show new summary
    print("\n[SUMMARY] New position summary:")
    summary = get_position_summary(position_file)
    if summary["records"] > 0:
        print(f"   Total records: {summary['records']}")
        print(f"   Last date: {summary['last_date']}")


if __name__ == "__main__":
    main()

