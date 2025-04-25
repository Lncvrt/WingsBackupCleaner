# Wings Backup Cleaner

This script checks all backups on the local machine to ensure they are valid, using the following methods:

- Ensuring the backup exists in database
- Checking the hash of the backup
- Ensuring the backup succeeded

Run these commands to get started:

```bash
sudo apt install -y python3 python3-pip
pip3 install -r requirements.txt
python3 main.py
```
