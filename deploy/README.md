# Running a hosted Panko

Panko on a server for you and a few people you invite (docs/SPEC-hosted.md). This sets it up on an **Oracle Cloud
Always Free** Arm machine with a free **DuckDNS** name, at no cost. Later you can move to your own domain with a
Cloudflare Tunnel; only the address changes.

What runs: Caddy (HTTPS) → the front door (`panko host serve`: accounts, invites, admin) → each user's own Panko,
started when they arrive and stopped when idle. All data is in `/srv/panko` on the server; the image holds none.

## 1. The server (Oracle Cloud)

1. Sign up at cloud.oracle.com. Pick a home region near you that has Arm capacity (you can't change it later).
2. Free Arm machines that stay idle can be reclaimed. To avoid that, upgrade the account to **Pay As You Go**
   (the Always Free allowance stays free) and add a **budget alert at $1** under Billing. Check Oracle's current
   Always Free page when you do this: the limits changed in 2026 (now 2 cores and 12 GB for Arm).
3. Create an instance: image **Canonical Ubuntu 24.04** (aarch64), shape **VM.Standard.A1.Flex** with 2 OCPUs and
   12 GB, a public IPv4 address, and your SSH public key. Give the boot volume enough room for everyone's media
   (stay within the free block storage total).
4. Open the web ports, in two places:
   - In the instance's subnet → Security List, add ingress rules for TCP **80** and **443** from `0.0.0.0/0`.
   - On the machine (Oracle's Ubuntu images block everything but SSH):
     ```bash
     # insert above the catch-all REJECT (its line number varies between images)
     N=$(sudo iptables -L INPUT --line-numbers -n | awk '/REJECT/ {print $1; exit}')
     sudo iptables -I INPUT $N -m state --state NEW -p tcp --dport 443 -j ACCEPT
     sudo iptables -I INPUT $N -m state --state NEW -p tcp --dport 80 -j ACCEPT
     sudo netfilter-persistent save
     ```

## 2. The name (DuckDNS)

Sign in at duckdns.org, add a subdomain (e.g. `yourname`), and set its IP to the instance's public IP. The IP stays
the same as long as the instance exists.

## 3. Install and start

```bash
sudo apt update && sudo apt install -y docker.io docker-compose-v2 git sqlite3 restic
sudo usermod -aG docker $USER    # then log out and in again
git clone https://github.com/NotAHill/panko.git && cd panko
cp deploy/env.example deploy/.env && nano deploy/.env    # your DuckDNS name, quotas
# uid 1000 is the container's panko user (on Oracle's image the host calls it opc)
sudo mkdir -p /srv/panko && sudo chown 1000:1000 /srv/panko && sudo chmod 700 /srv/panko
docker compose -f deploy/compose.yml up -d --build
```

The first build takes a few minutes. Add `--build-arg WITH_CAMEL=1` to `docker compose build` for CAMeL Tools
(Standard Arabic checks; about 1 GB more). Caddy gets the HTTPS certificate on the first visit.

## 4. Your account, then invites

```bash
docker compose -f deploy/compose.yml exec panko panko host invite --admin --note "me"
```

Open the link it prints, pick a name and a password: that's the admin account. Invite others from **admin** in the
front door (a link that works once, for 7 days; send it yourself). `panko host users` lists everyone.

## 5. Backups (before inviting anyone)

1. Make a restic repository somewhere off this server (Oracle Object Storage, Backblaze B2, …) and put its settings
   in `/etc/panko-backup.env` (mode 600):
   ```bash
   RESTIC_REPOSITORY=…
   RESTIC_PASSWORD_FILE=/etc/panko-restic-password
   # and the storage's keys, e.g. AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY for S3-compatible storage
   ```
   Keep a copy of the password somewhere else: without it the backups can't be read.
2. `sudo restic init`, then run `sudo deploy/backup.sh` once by hand.
3. Nightly: `sudo crontab -e` and add `30 3 * * * /home/ubuntu/panko/deploy/backup.sh`.
4. **Try a restore** into a scratch folder: `sudo restic restore latest --target /tmp/panko-restore`. Its
   `srv/panko/` holds the folders and `var/backups/panko-db/` the stores, as `<name>.db.bak` in the same layout:
   copy each back to its place without the `.bak` when restoring for real.

## Updating

```bash
sh deploy/update.sh
```

It pulls, builds the new image while the old one keeps serving, waits until no one's Panko is running a job
(`panko host busy`, up to `WAIT_MINUTES`, 30 by default), then switches. `FORCE=1 sh deploy/update.sh` switches
without waiting. Everyone's Panko stops with the old container. A job cut off anyway isn't lost: each Panko keeps
its jobs in `data/work/jobs.json`, the front door starts the Pankos that had one when it comes back, and free jobs
carry on by themselves (once); paid ones wait on the jobs page with a resume button that prices what's left.

## Looking after it

- `docker compose -f deploy/compose.yml logs panko`: the front door. Each user's Panko logs to
  `/srv/panko/logs/<id>.log`.
- Deleting an account in admin moves the folder to `/srv/panko/deleted/`; `panko host purge` removes it for good.
- Disk use per person is on the admin page; quotas are set there or in `deploy/.env`.
