import os
import time
import shutil
import threading
import schedule
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any
import json

from .logger import LoggerMixin
from .config_manager import ConfigManager
from .database_manager import DatabaseManager

class BackupScheduler(LoggerMixin):
    """
    Manages automated database backups with scheduling and retention policies
    """
    
    def __init__(self, db_manager: DatabaseManager, config_manager: ConfigManager = None):
        super().__init__()
        
        self.db_manager = db_manager
        self.config_manager = config_manager or ConfigManager()
        
        # Initialize backup configuration
        self.backup_config = self.config_manager.get("backup", {
            "schedule": {
                "daily": "03:00",  # Daily backup at 3 AM
                "weekly": "sunday",  # Weekly backup on Sunday
                "monthly": 1  # Monthly backup on 1st day
            },
            "retention": {
                "daily": 7,    # Keep 7 daily backups
                "weekly": 4,   # Keep 4 weekly backups
                "monthly": 3   # Keep 3 monthly backups
            },
            "backup_path": "backup",
            "compress_backups": True
        })
        
        # Ensure backup directory exists
        self.backup_path = Path(self.backup_config["backup_path"])
        self.backup_path.mkdir(parents=True, exist_ok=True)
        
        # Initialize scheduler
        self.scheduler = schedule.Scheduler()
        self.scheduler_thread = None
        self.is_running = False
        
        self.log_info("Backup scheduler initialized")
    
    def start(self):
        """Start the backup scheduler"""
        if self.is_running:
            self.log_warning("Backup scheduler is already running")
            return
        
        try:
            # Schedule backups
            schedule_config = self.backup_config["schedule"]
            
            # Daily backup
            self.scheduler.every().day.at(schedule_config["daily"]).do(
                self.create_backup, backup_type="daily"
            )
            
            # Weekly backup
            self.scheduler.every().sunday.at("04:00").do(
                self.create_backup, backup_type="weekly"
            )
            
            # Monthly backup (1st day of each month)
            self.scheduler.every().day.at("05:00").do(
                self._check_and_run_monthly_backup
            )
            
            # Start scheduler thread
            self.is_running = True
            self.scheduler_thread = threading.Thread(target=self._run_scheduler)
            self.scheduler_thread.daemon = True
            self.scheduler_thread.start()
            
            self.log_info("Backup scheduler started")
            
        except Exception as e:
            self.log_error(f"Failed to start backup scheduler: {e}")
            self.is_running = False
    
    def stop(self):
        """Stop the backup scheduler"""
        if not self.is_running:
            return
        
        self.is_running = False
        if self.scheduler_thread:
            self.scheduler_thread.join(timeout=5)
        self.scheduler.clear()
        self.log_info("Backup scheduler stopped")
    
    def _check_and_run_monthly_backup(self):
        """Check if it's the first day of the month and run monthly backup if it is"""
        if datetime.now().day == 1:
            self.create_backup(backup_type="monthly")
    
    def _run_scheduler(self):
        """Run the scheduler loop"""
        while self.is_running:
            self.scheduler.run_pending()
            time.sleep(60)  # Check every minute
    
    def create_backup(self, backup_type: str = "daily") -> bool:
        """
        Create a backup with specified type
        
        Args:
            backup_type: Type of backup (daily/weekly/monthly)
            
        Returns:
            True if backup was successful
        """
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_name = f"wms_backup_{backup_type}_{timestamp}"
            
            # Create backup directory
            backup_dir = self.backup_path / backup_type / backup_name
            backup_dir.mkdir(parents=True, exist_ok=True)
            
            # Backup SQLite database
            sqlite_backup = backup_dir / "wms_screenshots.db"
            success = self.db_manager.backup_database(str(sqlite_backup))
            
            if not success:
                raise Exception("SQLite backup failed")
            
            # Backup ChromaDB
            chroma_backup = backup_dir / "chroma_db"
            shutil.copytree(
                self.db_manager.chroma_path,
                chroma_backup,
                dirs_exist_ok=True
            )
            
            # Create backup metadata
            metadata = {
                "backup_type": backup_type,
                "timestamp": timestamp,
                "sqlite_path": str(sqlite_backup),
                "chroma_path": str(chroma_backup),
                "database_stats": self.db_manager.get_database_stats()
            }
            
            with open(backup_dir / "backup_metadata.json", "w") as f:
                json.dump(metadata, f, indent=2)
            
            # Compress backup if enabled
            if self.backup_config["compress_backups"]:
                shutil.make_archive(
                    str(backup_dir),
                    "zip",
                    str(backup_dir)
                )
                shutil.rmtree(backup_dir)
            
            # Apply retention policy
            self._apply_retention_policy(backup_type)
            
            self.log_info(f"{backup_type.capitalize()} backup created successfully: {backup_name}")
            return True
            
        except Exception as e:
            self.log_error(f"Failed to create {backup_type} backup: {e}")
            return False
    
    def _apply_retention_policy(self, backup_type: str):
        """Apply retention policy for specified backup type"""
        try:
            retention_days = self.backup_config["retention"][backup_type]
            backup_dir = self.backup_path / backup_type
            
            if not backup_dir.exists():
                return
            
            # Get list of backups
            backups = []
            for item in backup_dir.glob("*"):
                if item.is_dir() or (item.is_file() and item.suffix == ".zip"):
                    backups.append(item)
            
            # Sort by creation time
            backups.sort(key=lambda x: x.stat().st_mtime, reverse=True)
            
            # Remove old backups
            for backup in backups[retention_days:]:
                if backup.is_dir():
                    shutil.rmtree(backup)
                else:
                    backup.unlink()
                
                self.log_info(f"Removed old backup: {backup.name}")
            
        except Exception as e:
            self.log_error(f"Failed to apply retention policy for {backup_type} backups: {e}")
    
    def restore_backup(self, backup_path: str) -> bool:
        """
        Restore database from backup
        
        Args:
            backup_path: Path to backup directory or zip file
            
        Returns:
            True if restore was successful
        """
        try:
            backup_path = Path(backup_path)
            restore_dir = backup_path
            
            # Extract if zip file
            if backup_path.is_file() and backup_path.suffix == ".zip":
                restore_dir = self.backup_path / "temp_restore"
                shutil.unpack_archive(str(backup_path), str(restore_dir))
            
            # Verify backup metadata
            metadata_file = restore_dir / "backup_metadata.json"
            if not metadata_file.exists():
                raise Exception("Invalid backup - metadata file not found")
            
            with open(metadata_file) as f:
                metadata = json.load(f)
            
            # Stop database connections
            self.db_manager.close()
            
            # Restore SQLite database
            sqlite_backup = restore_dir / "wms_screenshots.db"
            if not sqlite_backup.exists():
                raise Exception("SQLite backup file not found")
            
            shutil.copy2(sqlite_backup, self.db_manager.sqlite_path)
            
            # Restore ChromaDB
            chroma_backup = restore_dir / "chroma_db"
            if not chroma_backup.exists():
                raise Exception("ChromaDB backup directory not found")
            
            shutil.rmtree(self.db_manager.chroma_path, ignore_errors=True)
            shutil.copytree(chroma_backup, self.db_manager.chroma_path)
            
            # Cleanup temp directory
            if backup_path.suffix == ".zip":
                shutil.rmtree(restore_dir)
            
            # Reinitialize database connections
            self.db_manager.init_sqlite()
            self.db_manager.init_chromadb()
            
            self.log_info(f"Database restored successfully from: {backup_path}")
            return True
            
        except Exception as e:
            self.log_error(f"Failed to restore backup: {e}")
            return False
    
    def list_backups(self) -> Dict[str, List[Dict[str, Any]]]:
        """
        List available backups
        
        Returns:
            Dictionary with backup types and their available backups
        """
        try:
            backups = {
                "daily": [],
                "weekly": [],
                "monthly": []
            }
            
            for backup_type in backups.keys():
                backup_dir = self.backup_path / backup_type
                if not backup_dir.exists():
                    continue
                
                # Get all backups (directories and zip files)
                for item in backup_dir.glob("*"):
                    if not (item.is_dir() or (item.is_file() and item.suffix == ".zip")):
                        continue
                    
                    # Get backup metadata
                    if item.is_dir():
                        metadata_file = item / "backup_metadata.json"
                    else:  # zip file
                        continue  # Skip zip files for now as they require extraction
                    
                    if metadata_file.exists():
                        with open(metadata_file) as f:
                            metadata = json.load(f)
                            metadata["path"] = str(item)
                            metadata["is_compressed"] = item.suffix == ".zip"
                            backups[backup_type].append(metadata)
            
            return backups
            
        except Exception as e:
            self.log_error(f"Failed to list backups: {e}")
            return {}