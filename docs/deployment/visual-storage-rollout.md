# Visual Storage Rollout (Phase 6 / VISUAL-009)

> **Goal**: Move the visuals pipeline off the local-disk fallback onto a
> production object store (MinIO self-hosted, or AWS S3 / GCS) without
> dropping a single rendered image, and surface per-article cost on
> the dashboard.

**Reading order:**

1. [Pre-flight](#pre-flight)
2. [Provision MinIO](#provision-minio)
3. [Apply the lifecycle policy](#apply-the-lifecycle-policy)
4. [Backfill the existing assets](#backfill-the-existing-assets)
5. [Rewrite stored URLs (one-shot SQL)](#rewrite-stored-urls-one-shot-sql)
6. [Switch traffic](#switch-traffic)
7. [Wire the cost dashboard](#wire-the-cost-dashboard)
8. [Rollback](#rollback)
9. [Notes / Out of scope](#notes--out-of-scope)

## Pre-flight

| Check | Command | Expected |
|-------|---------|----------|
| Phases 1–5 deployed | `git log --oneline origin/main \| grep VISUAL-` | At least VISUAL-004 through VISUAL-008 commits present. |
| Cost endpoint live | `curl -fsS $API_BASE/api/v1/visuals/cost?article_id=<known-article>` | 200 with the expected breakdown. |
| Cost aggregator green | `uv run pytest tests/unit/services/visuals/test_cost.py -q` | 7 passed. |
| Backfill script green | `uv run pytest tests/unit/scripts/test_backfill_visuals_to_minio.py -q` | 8 passed. |
| `.env` ready | `grep -E "^COGNIFY_MINIO_" .env \| sort` | Lists endpoint, access key, secret key, bucket, public URL. |

If any check fails, **stop and fix before proceeding** — the rollout assumes the cost aggregator is the source of truth.

## Provision MinIO

For self-hosted production deployments use the included compose overlay:

```bash
export COGNIFY_MINIO_ROOT_USER="$(openssl rand -hex 16)"
export COGNIFY_MINIO_ROOT_PASSWORD="$(openssl rand -hex 32)"
export COGNIFY_MINIO_BUCKET="cognify-visuals"
export COGNIFY_MINIO_CONSOLE_URL="https://minio.your-domain.tld"

docker compose -f docker-compose.yml -f docker-compose.minio.prod.yml \
  up -d minio minio-bucket-init
```

The overlay differs from the dev one (`docker-compose.minio.yml`) in:

- credentials are **required** via env vars (no `cognify_dev` defaults),
- a bucket lifecycle policy is applied automatically,
- resource limits + `unless-stopped` restart policy are set,
- log rotation is configured.

For AWS S3 / GCS deployments: skip the compose overlay, set the same
env vars to point at the managed bucket, and apply the lifecycle policy
via the cloud provider's console (the JSON body is the same — see
`infra/minio/lifecycle.json`).

## Apply the lifecycle policy

The init sidecar in `docker-compose.minio.prod.yml` runs `mc ilm import`
automatically on first boot. To re-apply or audit:

```bash
mc alias set cognify-prod http://minio:9000 "$COGNIFY_MINIO_ROOT_USER" "$COGNIFY_MINIO_ROOT_PASSWORD"
mc ilm import cognify-prod/cognify-visuals < infra/minio/lifecycle.json
mc ilm ls cognify-prod/cognify-visuals
```

Three rules are configured:

| ID | Effect |
|----|--------|
| `archive-cold-after-90-days` | Transitions `generated_assets/**` to `GLACIER` after 90 days. |
| `purge-orphaned-multipart-uploads` | Aborts incomplete multipart uploads older than 7 days. |
| `purge-tmp-uploads-after-30-days` | Deletes objects under `tmp/` after 30 days. |

## Backfill the existing assets

```bash
# Dry run first — emits the per-file plan without writing.
uv run python -m scripts.backfill_visuals_to_minio --dry-run

# Real run.
uv run python -m scripts.backfill_visuals_to_minio
```

The script:

- walks `generated_assets/visuals/`, `…/illustrations/`, `…/charts/`,
  `…/diagrams/`,
- uses the same `select_object_storage(settings)` resolver the API uses,
  so credentials / endpoint configuration is single-sourced from `.env`,
- is **idempotent**: re-running skips files whose key is already present
  in the supplied `already_uploaded` set. The default invocation walks
  every file; the bucket's atomic `put` semantics make repeat uploads
  safe.

## Rewrite stored URLs (one-shot SQL)

`canonical_articles.visuals[].url` rows from before the rollout still
point at relative paths (`/visuals/abc.png`) or `generated_assets/...`.
Run the rewrite migration **after** backfill so the API can serve from
MinIO without falling back to the static-file route.

```sql
-- Inside the cognify database. Update only rows whose URL is still local.
UPDATE canonical_articles
SET visuals = (
  SELECT jsonb_agg(
    CASE
      WHEN visual->>'url' LIKE 'http%' THEN visual
      ELSE jsonb_set(
        visual,
        '{url}',
        to_jsonb(
          'https://minio.your-domain.tld/cognify-visuals/'
          || ltrim(visual->>'url', '/')
        )
      )
    END
  )
  FROM jsonb_array_elements(visuals) AS visual
)
WHERE visuals IS NOT NULL
  AND jsonb_array_length(visuals) > 0
  AND EXISTS (
    SELECT 1
    FROM jsonb_array_elements(visuals) AS v
    WHERE v->>'url' NOT LIKE 'http%'
  );
```

Verify by sampling 10 rows:

```sql
SELECT id, title, jsonb_path_query(visuals, '$[*].url')
FROM canonical_articles
ORDER BY generated_at DESC
LIMIT 10;
```

Every URL should be absolute and start with the `MINIO_PUBLIC_URL`.

## Switch traffic

Flip the API to read/write through MinIO by setting the env vars in
`.env` (or your secret manager):

```bash
COGNIFY_MINIO_ENABLED=true
COGNIFY_MINIO_ENDPOINT=minio.your-domain.tld:9000
COGNIFY_MINIO_ACCESS_KEY=<rotated>
COGNIFY_MINIO_SECRET_KEY=<rotated>
COGNIFY_MINIO_BUCKET=cognify-visuals
COGNIFY_MINIO_PUBLIC_URL=https://minio.your-domain.tld
COGNIFY_MINIO_USE_SSL=true
```

Restart the API + worker:

```bash
docker compose up -d --force-recreate api worker
```

The provider registry rebuilds on boot; `select_object_storage(settings)`
now picks `MinioObjectStorage` instead of `LocalDiskObjectStorage`.

## Wire the cost dashboard

1. Import `infra/grafana/visual-cost-dashboard.json` into Grafana
   (`Dashboards → Import → Upload JSON file`).
2. Confirm the Prometheus datasource is named `Prometheus` (or rebind
   the panels).
3. Point your scraper at `${API_BASE}/metrics` (FastAPI middleware) **and**
   the MinIO Prometheus endpoint (`mc admin prometheus generate` was
   logged into the `init` sidecar — copy the scrape config from
   `docker exec cognify-minio-init cat /tmp/prom.yaml`).
4. Validate four panels render: `Visual cost · 24h`, `Render rate · 1h`,
   `Render latency · P95`, `MinIO bucket size`.

The cost panels expect three Prometheus series the API will start
emitting in a follow-up commit (`cognify_visual_cost_usd_total`,
`cognify_visual_renders_total`, `cognify_visual_render_duration_ms_bucket`)
. For Phase 6, the source-of-truth is still the per-article
`/api/v1/visuals/cost` endpoint — the Grafana panels become live as
the OpenTelemetry exporter wires those counters in (Phase 6 follow-up
or VISUAL-009.5).

## Rollback

If anything breaks:

1. **Revert the env flag** — set `COGNIFY_MINIO_ENABLED=false` and
   restart. The API resumes serving from `LocalDiskObjectStorage` and
   the static-file route at `/generated_assets/...`.
2. **Don't drop the bucket.** The backfill is idempotent; you can rerun
   it after the URL-rewrite migration is reverted. Restoring URLs is
   a single SQL `UPDATE … SET visuals = jsonb_path_query_array(...)`
   referencing the pre-migration backup.
3. **Audit cost endpoint** — `/api/v1/visuals/cost?article_id=…`
   continues to work without MinIO since cost data comes from the
   `metadata` JSONB, not the bucket itself.

## Notes / Out of scope

- **Helm charts**: not yet in the repo. When they land, they should
  template the same env vars used by the compose overlay above.
- **OpenTelemetry counters**: the per-image Prometheus emission is
  scaffolded in the dashboard JSON but not wired in code — see the
  observability follow-up tracked alongside this phase.
- **CDN in front of MinIO**: optional; if added, point
  `COGNIFY_MINIO_PUBLIC_URL` at the CDN base URL and confirm cache TTLs
  respect the lifecycle transitions.
- **CSP**: the article-detail page renders MinIO-hosted images directly.
  Add the bucket public URL to the `img-src` whitelist when production
  CSP headers go in.
