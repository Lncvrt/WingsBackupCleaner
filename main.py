import os
import logging
import hashlib
import mysql.connector

logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
log = logging.getLogger("wings-backup-purger")

if os.geteuid() != 0:
    log.error("Error: This script must be run as root.")
    exit(1)

WINGS_BACKUP_DIRECTORY = "/var/lib/pterodactyl/backups/"
PTERODACTYL_ENV_FILE = "/var/www/pterodactyl/.env"
CHECK_SHA1 = False

DB_HOST = ""
DB_PORT = ""
DB_DATABASE = ""
DB_USERNAME = ""
DB_PASSWORD = ""

if os.path.exists(PTERODACTYL_ENV_FILE) and os.path.isfile(PTERODACTYL_ENV_FILE):
    with open(PTERODACTYL_ENV_FILE, "r") as env_file:
        log.info("Found Pterodactyl .env file... checking for database credentials")
        for line in env_file:
            if line.startswith("DB_CONNECTION"):
                if line.split("=")[1].strip() != "mysql":
                    break
            if line.startswith("DB_HOST"):
                DB_HOST = line.split("=")[1].strip()
                log.info(f"Found database host from web .env file")
            elif line.startswith("DB_PORT"):
                DB_PORT = line.split("=")[1].strip()
                log.info(f"Found database port from web .env file")
            elif line.startswith("DB_DATABASE"):
                DB_DATABASE = line.split("=")[1].strip()
                log.info(f"Found database name from web .env file")
            elif line.startswith("DB_USERNAME"):
                DB_USERNAME = line.split("=")[1].strip()
                log.info(f"Found database username from web .env file")
            elif line.startswith("DB_PASSWORD"):
                DB_PASSWORD = line.split("=")[1].strip()
                log.info(f"Found database password from web .env file")

if not DB_HOST or not DB_PORT or not DB_DATABASE or not DB_USERNAME or not DB_PASSWORD:
    DB_HOST = input("Enter the database host: ").strip()
    DB_PORT = input("Enter the database port: ").strip()
    DB_DATABASE = input("Enter the database name: ").strip()
    DB_USERNAME = input("Enter the database username: ").strip()
    DB_PASSWORD = input("Enter the database password: ").strip()

CHECK_SHA1 = input("Check backup hash? (y/n): ").strip().lower() == "y"

try:
    DB_PORT = int(DB_PORT)
except ValueError:
    log.error(f"Error: The database port '{DB_PORT}' is not a valid integer.")
    exit(1)

try:
    connection = mysql.connector.connect(
        host=DB_HOST,
        port=DB_PORT,
        database=DB_DATABASE,
        user=DB_USERNAME,
        password=DB_PASSWORD
    )
    cursor = connection.cursor()
    log.info("Successfully connected to the database!")
except mysql.connector.Error as err:
    log.error(f"Failed to connect to database: {err}")
    exit(1)

if not os.path.exists(WINGS_BACKUP_DIRECTORY) or not os.path.isdir(WINGS_BACKUP_DIRECTORY):
    log.error(f"Error: The directory {WINGS_BACKUP_DIRECTORY} does not exist or is not a directory.")
    exit(1)

log.info("Wings directory seems valid, checking for backups...")

backup_files = [f for f in os.listdir(WINGS_BACKUP_DIRECTORY) if f.endswith(".tar.gz") or f.endswith(".zip")]
if not backup_files:
    log.error("No backups found in the directory.")
    exit(0)

log.info("Found backups, checking database for backups")

backup_data = cursor.execute("SELECT * FROM `backups`")
backup_data = cursor.fetchall()
if not backup_data:
    log.error("No backups found in the database.")
    exit(0)

log.info("Backup info found from database! Checking local backups...")

def sha1(file_path):
    """Calculate the SHA-1 hash of a file."""
    hash_sha1 = hashlib.sha1()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_sha1.update(chunk)
    return hash_sha1.hexdigest()

bytes_cleared = 0
backups_cleared = 0

for local_backup in backup_files:
    local_backup_path = os.path.join(WINGS_BACKUP_DIRECTORY, local_backup)
    local_backup_id = os.path.splitext(os.path.splitext(local_backup)[0])[0]
    backup_found = False

    for backup in backup_data:
        if backup[2] == local_backup_id:
            log.info(f"Checking: {local_backup}")
            backup_found = True
            if not backup[4]:
                log.info(f"Backup failed: {backup}")
                bytes_cleared += os.path.getsize(local_backup_path)
                backups_cleared += 1
                os.remove(local_backup_path)
                log.warning(f"Deleted backup: {local_backup} (failed)")
            elif CHECK_SHA1 and backup[9].split(":")[1] != sha1(local_backup_path):
                log.info(f"Hash is not the same: {backup}")
                bytes_cleared += os.path.getsize(local_backup_path)
                backups_cleared += 1
                os.remove(local_backup_path)
                log.warning(f"Deleted backup: {local_backup} (hash mismatch)")
            break

    if not backup_found:
        log.info(f"Backup not found in database: {local_backup}")
        bytes_cleared += os.path.getsize(local_backup_path)
        backups_cleared += 1
        os.remove(local_backup_path)
        log.warning(f"Deleted backup: {local_backup} (not found in database)")

log.info(f"Deleted {backups_cleared} backups, cleared {bytes_cleared / 1024 / 1024 / 1024:.2f} GB in total")
