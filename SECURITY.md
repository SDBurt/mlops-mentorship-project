# Security & Secret Management

## Overview

This project uses Kubernetes Secrets for credential management. **Credentials are never committed to git.** All sensitive information is stored in separate Secret resources that are gitignored.

## Secret Management Approach

- All secrets are stored in Kubernetes Secret resources
- Secret files use `.example` templates that are committed to git
- Actual secret files (without `.example` suffix) are gitignored
- Credentials are injected into pods via environment variables or volume mounts
- **Pre-commit hooks** automatically detect and prevent credential commits

## Pre-commit Hooks

This project uses the [pre-commit](https://pre-commit.com/) framework to automatically check for secrets and other issues before commits.

### Installation

```bash
# Install pre-commit
pip install pre-commit

# Install git hooks
pre-commit install

# (Optional) Run on all files to check current state
pre-commit run --all-files
```

### What It Checks

- **detect-secrets**: Scans for potential secrets and credentials
- **yamllint**: Validates YAML syntax and formatting
- **bandit**: Checks Python code for security issues
- **Standard checks**: Trailing whitespace, merge conflicts, large files, etc.

### Updating Hooks

```bash
# Update all hooks to latest versions
pre-commit autoupdate
```

### Bypassing (Not Recommended)

If you need to bypass pre-commit checks:

```bash
git commit --no-verify
```

**Warning**: Only bypass if you're certain there are no secrets in your commit.

## .gitignore Protection

Multiple patterns protect secrets from being committed:

- `**/secrets.yaml` - Exact match "secrets.yaml" in any directory
- `**/*-secrets.yaml` - Suffix match (e.g., user-code-secrets.yaml)
- `**/*secrets.yaml` - Any file with "secrets" in name
- `**/secret-*.yaml` - Prefix match
- `**/.credentials/` - Credential directories

## Setup Secrets

### 1. MinIO S3 Credentials

MinIO provides S3-compatible storage for the lakehouse.

```bash
# Copy template
cp infrastructure/kubernetes/minio/minio-secrets.yaml.example \
   infrastructure/kubernetes/minio/minio-secrets.yaml

# Edit and replace CHANGEME_MINIO_PASSWORD
nano infrastructure/kubernetes/minio/minio-secrets.yaml

# Apply to cluster
kubectl apply -f infrastructure/kubernetes/minio/minio-secrets.yaml
```

**Note:** You can also override MinIO password via Helm:
```bash
helm upgrade minio bitnami/minio \
  --set auth.rootPassword="your-password" \
  -n lakehouse
```

### 2. Polaris PostgreSQL Secrets

PostgreSQL database for Polaris catalog metadata storage.

```bash
# Copy template
cp infrastructure/kubernetes/polaris-postgresql/postgres-secrets.yaml.example \
   infrastructure/kubernetes/polaris-postgresql/postgres-secrets.yaml

# Edit and replace placeholders:
# - CHANGEME_POLARIS_PASSWORD
# - CHANGEME_POSTGRES_PASSWORD
nano infrastructure/kubernetes/polaris-postgresql/postgres-secrets.yaml

# Apply to cluster
kubectl apply -f infrastructure/kubernetes/polaris-postgresql/postgres-secrets.yaml
```

**Note:** You can also override passwords via Helm:
```bash
helm upgrade polaris-postgresql bitnami/postgresql \
  --set global.postgresql.auth.password="your-password" \
  --set global.postgresql.auth.postgresPassword="your-postgres-password" \
  -n lakehouse
```

### 3. Polaris Catalog Secrets

Polaris REST catalog requires database connection and storage credentials.

```bash
# Copy template
cp infrastructure/kubernetes/polaris/polaris-secrets.yaml.example \
   infrastructure/kubernetes/polaris/secrets.yaml

# Edit and replace placeholders:
# - CHANGEME_POLARIS_PASSWORD (database password)
# - CHANGEME_MINIO_PASSWORD (storage credentials)
# - CHANGEME_BOOTSTRAP_SECRET (optional, for initial admin principal)
nano infrastructure/kubernetes/polaris/secrets.yaml

# Apply to cluster
kubectl apply -f infrastructure/kubernetes/polaris/secrets.yaml
```

### 4. Dagster User Code Secrets

Secrets for Dagster user code deployments (Polaris REST catalog, Reddit API, etc.).

```bash
# Copy template
cp infrastructure/kubernetes/dagster/user-code-secrets.yaml.example \
   infrastructure/kubernetes/dagster/user-code-secrets.yaml

# Edit and replace placeholders:
# - YOUR_POLARIS_CLIENT_ID_HERE
# - YOUR_POLARIS_CLIENT_SECRET_HERE
# - YOUR_REDDIT_CLIENT_ID_HERE
# - YOUR_REDDIT_CLIENT_SECRET_HERE
# - YOUR_MINIO_PASSWORD_HERE
nano infrastructure/kubernetes/dagster/user-code-secrets.yaml

# Apply to cluster
kubectl apply -f infrastructure/kubernetes/dagster/user-code-secrets.yaml
```

**Obtaining Polaris Credentials:**

Run the Polaris initialization script to create a principal and get credentials:

```bash
# Run init script (creates dagster_user principal)
./infrastructure/kubernetes/polaris/init-polaris.sh http://polaris:8181

# Credentials saved to:
# infrastructure/kubernetes/polaris/.credentials/dagster_user.txt
```

**Obtaining Reddit API Credentials:**

1. Go to https://www.reddit.com/prefs/apps
2. Create a "script" type application
3. Copy the client ID and secret

### 5. Trino OAuth Credentials

Trino uses OAuth2 to authenticate with Polaris REST catalog.

```bash
# Copy template
cp infrastructure/kubernetes/trino/trino-secrets.yaml.example \
   infrastructure/kubernetes/trino/trino-secrets.yaml

# Edit and replace placeholders:
# - CHANGEME_POLARIS_OAUTH_CREDENTIAL (format: "principal-name:secret")
# - CHANGEME_MINIO_PASSWORD
nano infrastructure/kubernetes/trino/trino-secrets.yaml

# Apply to cluster
kubectl apply -f infrastructure/kubernetes/trino/trino-secrets.yaml
```

**OAuth Credential Format:**

The `POLARIS_OAUTH_CREDENTIAL` should be in the format: `principal-name:secret`

Example: `polaris_admin:your_secret_here`

## Verifying Secrets

Check that secrets are created:

```bash
# List all secrets in lakehouse namespace
kubectl get secrets -n lakehouse

# View secret (base64 encoded)
kubectl get secret dagster-user-code-secrets -n lakehouse -o yaml

# Decode secret value
kubectl get secret dagster-user-code-secrets -n lakehouse \
  -o jsonpath='{.data.POLARIS_CLIENT_ID}' | base64 -d
```

## Best Practices

1. **Never commit secret files** - Always use `.example` templates
2. **Use pre-commit hooks** - Automatically prevents credential commits
3. **Rotate credentials regularly** - Especially if exposed or compromised
4. **Use strong passwords** - Generate random passwords for production
5. **Limit secret access** - Use RBAC to restrict who can read secrets
6. **Use external secret management** - For production, consider using:
   - HashiCorp Vault
   - AWS Secrets Manager
   - Azure Key Vault
   - Google Secret Manager

## Troubleshooting

### Secret file appears in git status

If a secret file shows up in `git status`, verify it's gitignored:

```bash
git check-ignore -v infrastructure/kubernetes/dagster/user-code-secrets.yaml
```

If it's not ignored, check `.gitignore` patterns and ensure the file matches one of the patterns.

### Pre-commit hook fails

If pre-commit detects a potential secret:

1. Review the flagged content
2. If it's a placeholder (CHANGEME, YOUR_, etc.), it's safe to ignore
3. If it's an actual credential:
   - Remove it from the file
   - Use environment variables or Kubernetes Secrets instead
   - Update `.secrets.baseline` if it's a false positive: `detect-secrets scan --baseline .secrets.baseline`

### Pod can't access secrets

1. Verify secret exists: `kubectl get secret <secret-name> -n lakehouse`
2. Check secret keys match what the pod expects
3. Verify pod has correct `envFrom` or `env` configuration
4. Check pod logs for errors: `kubectl logs <pod-name> -n lakehouse`

### Credentials not working

1. Verify credentials are correct in the secret
2. Check if credentials need to be base64 encoded (use `stringData` instead of `data`)
3. Ensure the secret is in the correct namespace
4. Verify the application is reading from the correct environment variable names
