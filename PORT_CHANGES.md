# Port Configuration Changes for WMS Chatbot

## New Development Ports (Changed from defaults)

| Service | Old Port | New Port | Description |
|---------|----------|----------|-------------|
| **FastAPI API** | 8000 | **5000** | Main WMS Chatbot API |
| **Grafana Monitoring** | 3000 | **5001** | Monitoring Dashboard |
| **Weaviate Vector DB** | 8080 | **5002** | Vector Database |
| **PostgreSQL Database** | 5432 | **5433** | PostgreSQL Database |
| **Redis Cache** | 6379 | **6380** | Redis Cache |
| **Prometheus Metrics** | 9090 | **9091** | Metrics Collection |

## Access URLs (Development)

- **API**: http://localhost:5000
- **API Documentation**: http://localhost:5000/docs
- **Monitoring Dashboard**: http://localhost:5001
- **Vector Database**: http://localhost:5002
- **Database**: localhost:5433
- **Redis**: localhost:6380
- **Metrics**: http://localhost:9091

## Why These Ports Were Changed

✅ **Avoid Common Conflicts:**
- Port 3000: React development servers
- Port 8000: Django development servers
- Port 8080: Various development tools
- Port 5432: Default PostgreSQL installations

✅ **Easy to Remember:**
- Sequential numbering (5000, 5001, 5002)
- Grouped related services
- Non-conflicting with system services

## How to Run the App

### Using Docker Compose (Recommended)
```bash
# Start all services with new ports
docker-compose up -d

# Access the application
curl http://localhost:5000/health/
```

### Using Local Development
```bash
# Install dependencies
pip install -r requirements.txt

# Set environment variables
export API_PORT=5000
export POSTGRES_PORT=5433
export WEAVIATE_URL=http://localhost:5002

# Run the application
python -m uvicorn src.api.main:app --host 0.0.0.0 --port 5000 --reload
```

### Quick Test Commands
```bash
# Test API health
curl -X GET "http://localhost:5000/health/"

# Test API documentation
open http://localhost:5000/docs

# Test monitoring dashboard
open http://localhost:5001

# Connect to database
psql -h localhost -p 5433 -U wms_user -d wms_chatbot
```

## Configuration Files Updated

All configuration files have been updated to use the new ports:

- ✅ `.env.example` - Environment template
- ✅ `docker-compose.yml` - Development orchestration
- ✅ `docker/production.docker-compose.yml` - Production deployment
- ✅ `src/core/config.py` - Application configuration
- ✅ `src/api/main.py` - FastAPI application
- ✅ `Dockerfile` - Container configuration
- ✅ `scripts/setup_environment.py` - Setup script
- ✅ `scripts/deploy.sh` - Deployment script

## Environment Variables

Update your `.env` file with these new values:

```bash
# API Configuration
API_PORT=5000

# Database Configuration
POSTGRES_PORT=5433

# Vector Database Configuration
WEAVIATE_URL=http://localhost:5002

# Monitoring Configuration  
METRICS_PORT=9091

# CORS Configuration
CORS_ORIGINS=http://localhost:5001,http://localhost:5002
```

## Production Deployment

For production deployment, the same port scheme is used with additional security:

```bash
# Deploy to production with new ports
./scripts/deploy.sh production --build

# Access production services
# API: http://your-server:5000
# Monitoring: http://your-server:5001
```

## Troubleshooting

If you encounter port conflicts:

1. **Check if ports are in use:**
   ```bash
   netstat -tulpn | grep :5000
   netstat -tulpn | grep :5001
   ```

2. **Stop conflicting services:**
   ```bash
   # Stop any services using the ports
   sudo lsof -ti:5000 | xargs kill -9
   sudo lsof -ti:5001 | xargs kill -9
   ```

3. **Use custom ports:**
   ```bash
   # Set custom ports in .env file
   API_PORT=6000
   # Update docker-compose.yml accordingly
   ```

## Benefits of New Port Configuration

1. **No Conflicts** - Avoids common development port conflicts
2. **Easy Development** - Sequential ports are easy to remember
3. **Production Ready** - Same configuration for dev and prod
4. **Scalable** - Ports don't interfere with other services
5. **Security** - Non-standard ports reduce attack surface

---

**Note:** If you have any existing `.env` files, make sure to update them with the new port configurations before running the application.