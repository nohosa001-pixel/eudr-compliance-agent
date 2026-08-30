# 🚀 eudragent.com Complete Production Deployment & Go-Live Guide

This document outlines the end-to-end production deployment, domain DNS setup, SSL certificates, backup procedures, and ERP integration for **eudragent.com**.

---

## 1. 🌐 DNS Configuration (`eudragent.com`)

At your domain registrar (e.g. Cloudflare, Namecheap, Route53, Gabia), configure the following DNS records pointing to your server's static Public IP:

| Type | Name / Host | Value / Target | TTL | Description |
|---|---|---|---|---|
| `A` | `@` (root) | `YOUR_SERVER_PUBLIC_IP` | Auto / 300 | Main Landing Page (`eudragent.com`) |
| `A` | `www` | `YOUR_SERVER_PUBLIC_IP` | Auto / 300 | WWW subdomain |
| `A` | `api` | `YOUR_SERVER_PUBLIC_IP` | Auto / 300 | Programmatic REST API (`api.eudragent.com`) |

---

## 2. 🖥️ Server Environment Setup (Ubuntu 22.04 / 24.04 LTS)

```bash
# 1. Update system packages
sudo apt update && sudo apt upgrade -y

# 2. Install Docker & Docker Compose
sudo apt install -y docker.io docker-compose-plugin git ufw
sudo systemctl enable docker && sudo systemctl start docker

# 3. Configure Firewall (UFW)
sudo ufw allow 22/tcp
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw enable
```

---

## 3. 🚀 Deploying EUDRAgent Stack

```bash
# 1. Clone repository to server
git clone <YOUR_GIT_REPO_URL> /opt/eudragent
cd /opt/eudragent

# 2. Configure Production Secrets
cp .env.production.example .env.production
nano .env.production
# Set strong passwords for POSTGRES_PASSWORD, REDIS_PASSWORD, and SECRET_KEY_FOR_SIGNING

# 3. Launch One-Click Deployment
chmod +x deploy.sh
./deploy.sh
```

---

## 4. 🔒 Initial SSL Certificate Issuance (Let's Encrypt)

If deploying for the first time, issue initial certificates via Certbot:

```bash
docker compose -f docker-compose.prod.yml run --rm --entrypoint "\
  certbot certonly --webroot -w /var/www/certbot \
  --email admin@eudragent.com \
  -d eudragent.com -d www.eudragent.com -d api.eudragent.com \
  --agree-tos --no-eff-email --force-renewal" certbot

# Reload Nginx to activate SSL
docker compose -f docker-compose.prod.yml exec nginx nginx -s reload
```

---

## 5. 🏢 ERP / SAP SCM B2B Integration Guide

Clients can generate API keys directly in the Console (`/dashboard` -> `🔑 API Keys`) or via API.

```bash
# Example: Submitting a Due Diligence Batch from SAP/WMS
curl -X POST "https://api.eudragent.com/api/v1/eudr/evaluate" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: eudr_live_3f9a7b1c4e6d8a2f0b1a" \
  -d '{
    "operator_name": "Global Importer Corp",
    "commodity": "COFFEE",
    "hs_code": "0901.11.00",
    "net_mass_kg": 50000.0,
    "plots": [
      {
        "plot_id": "PLOT-VN-001",
        "country_code": "VN",
        "geometry": {
          "type": "Polygon",
          "coordinates": [[[108.438, 11.940], [108.442, 11.940], [108.442, 11.9435], [108.438, 11.9435], [108.438, 11.940]]]
        },
        "declared_area_ha": 15.2
      }
    ]
  }'
```

---

## 6. 💾 Database Backup & Maintenance

```bash
# Automated daily PostGIS backup cron
0 3 * * * docker exec eudr-prod-postgis pg_dump -U postgres eudr_compliance > /opt/backups/eudr_$(date +\%F).sql
```
