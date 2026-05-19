# Squad Manager

Dashboard para visualizar, editar e conectar seus AI agents.

## Stack

- **Backend**: FastAPI (Python) + PostgreSQL
- **Frontend**: Next.js (TypeScript) + Tailwind CSS
- **Deploy**: Azure Container Apps + Azure Container Registry

## Dev local

```bash
# Copie e configure as variáveis de ambiente
cp backend/.env.example backend/.env

# Suba tudo com Docker Compose
docker compose up --build
```

- Frontend: http://localhost:3000
- Backend API: http://localhost:8000
- Docs (Swagger): http://localhost:8000/docs

## Deploy Azure

Configure os seguintes secrets no repositório GitHub:

| Secret | Descrição |
|---|---|
| `AZURE_CREDENTIALS` | JSON do service principal (`az ad sp create-for-rbac`) |
| `ACR_NAME` | Nome do Azure Container Registry |
| `ACR_REGISTRY` | URL do registry (ex: `squadmanager.azurecr.io`) |
| `RESOURCE_GROUP` | Resource group dos Container Apps |
| `API_URL` | URL pública do backend após deploy |

O pipeline roda automaticamente a cada push em `main`.
