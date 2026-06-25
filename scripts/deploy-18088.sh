#!/usr/bin/env bash
set -Eeuo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEFAULT_COMPOSE_DIR="${DEPLOY_18088_DEFAULT_COMPOSE_DIR:-/home/yu/projects/dify-rag/docker}"
if [[ -n "${COMPOSE_DIR:-}" ]]; then
  COMPOSE_DIR="$COMPOSE_DIR"
elif [[ -f "$REPO_ROOT/docker/.env" ]]; then
  COMPOSE_DIR="$REPO_ROOT/docker"
elif [[ -f "$DEFAULT_COMPOSE_DIR/.env" ]]; then
  COMPOSE_DIR="$DEFAULT_COMPOSE_DIR"
else
  COMPOSE_DIR="$REPO_ROOT/docker"
fi
API_IMAGE="${DIFY_API_IMAGE:-mmbai/dify-api:local}"
WEB_IMAGE="${DIFY_WEB_IMAGE:-mmbai/dify-web:local}"
LOCAL_VERIFY_URL="${LOCAL_VERIFY_URL:-http://127.0.0.1/admin}"
LOCAL_API_VERIFY_URL="${LOCAL_API_VERIFY_URL:-http://127.0.0.1/console/api/setup}"
PUBLIC_VERIFY_URL="${PUBLIC_VERIFY_URL:-http://118.196.65.83:18088/admin}"
PUBLIC_API_VERIFY_URL="${PUBLIC_API_VERIFY_URL:-http://118.196.65.83:18088/console/api/setup}"
STATE_FILE="${DEPLOY_18088_STATE_FILE:-/tmp/dify-rag-deploy-18088-last-sha}"

AUTO=1
BUILD_API=0
BUILD_WEB=0
RUN_MIGRATIONS=0
VERIFY=1
DRY_RUN=0
REQUIRE_CLEAN=0
BASE_REF=""
TARGET_REF="HEAD"

usage() {
  cat <<'EOF'
Usage: scripts/deploy-18088.sh [options]

Deploy the Dify fork to the public node http://118.196.65.83:18088.

Default behavior:
  Detect changed paths since the last successful deploy recorded in
  /tmp/dify-rag-deploy-18088-last-sha, build only the needed image(s), run
  migrations only when api/migrations changed, restart the needed services,
  restart nginx when api or web changed, and verify both local and public UI/API entrypoints.
  When run from a clean deploy worktree, the script automatically uses the
  canonical compose directory /home/yu/projects/dify-rag/docker for .env files.

Options:
  --from <ref>       Diff base for auto detection. Defaults to last deploy ref,
                     then HEAD~1 when no state file exists.
  --to <ref>         Target ref to deploy. Defaults to HEAD.
  --api              Build API image and restart API/worker services.
  --web              Build web image, restart web, then restart nginx.
  --migrate          Run database migrations. Implies --api.
  --all              Build API and web, run migrations, restart all app services.
  --skip-verify      Skip curl verification.
  --dry-run          Print actions without running them.
  --require-clean    Fail if the git working tree is dirty.
  -h, --help         Show this help.

Examples:
  scripts/deploy-18088.sh
  scripts/deploy-18088.sh --web
  scripts/deploy-18088.sh --from HEAD~3 --to HEAD
  scripts/deploy-18088.sh --all
EOF
}

log() {
  printf '\n[deploy-18088] %s\n' "$*"
}

warn() {
  printf '\n[deploy-18088] WARNING: %s\n' "$*" >&2
}

die() {
  printf '\n[deploy-18088] ERROR: %s\n' "$*" >&2
  exit 1
}

run() {
  printf '+ '
  printf '%q ' "$@"
  printf '\n'
  if [[ "$DRY_RUN" == "0" ]]; then
    "$@"
  fi
}

mark_manual_mode() {
  AUTO=0
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --from)
      [[ $# -ge 2 ]] || die "--from requires a ref"
      BASE_REF="$2"
      shift 2
      ;;
    --to)
      [[ $# -ge 2 ]] || die "--to requires a ref"
      TARGET_REF="$2"
      shift 2
      ;;
    --api)
      mark_manual_mode
      BUILD_API=1
      shift
      ;;
    --web)
      mark_manual_mode
      BUILD_WEB=1
      shift
      ;;
    --migrate)
      mark_manual_mode
      BUILD_API=1
      RUN_MIGRATIONS=1
      shift
      ;;
    --all)
      mark_manual_mode
      BUILD_API=1
      BUILD_WEB=1
      RUN_MIGRATIONS=1
      shift
      ;;
    --skip-verify)
      VERIFY=0
      shift
      ;;
    --dry-run)
      DRY_RUN=1
      shift
      ;;
    --require-clean)
      REQUIRE_CLEAN=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      die "unknown option: $1"
      ;;
  esac
done

cd "$REPO_ROOT"

command -v git >/dev/null 2>&1 || die "git is required"
command -v docker >/dev/null 2>&1 || die "docker is required"
command -v curl >/dev/null 2>&1 || die "curl is required"
[[ -d "$COMPOSE_DIR" ]] || die "compose directory not found: $COMPOSE_DIR"
[[ -f "$COMPOSE_DIR/docker-compose.yaml" || -f "$COMPOSE_DIR/compose.yaml" ]] || die "docker compose file not found in $COMPOSE_DIR"

TARGET_SHA="$(git rev-parse "$TARGET_REF")"

if ! git diff --quiet || ! git diff --cached --quiet || [[ -n "$(git ls-files --others --exclude-standard)" ]]; then
  if [[ "$REQUIRE_CLEAN" == "1" ]]; then
    die "working tree is dirty; commit or use a clean deploy worktree"
  fi
  warn "working tree is dirty. For production-safe deploys, prefer a clean worktree at the intended commit."
fi

if [[ "$AUTO" == "1" ]]; then
  if [[ -z "$BASE_REF" ]]; then
    if [[ -s "$STATE_FILE" ]] && git rev-parse --verify --quiet "$(cat "$STATE_FILE")^{commit}" >/dev/null; then
      BASE_REF="$(cat "$STATE_FILE")"
    elif git rev-parse --verify --quiet "$TARGET_SHA^" >/dev/null; then
      BASE_REF="$TARGET_SHA^"
    fi
  fi

  if [[ -z "$BASE_REF" ]]; then
    log "No deploy state or parent commit found; defaulting to full deploy."
    BUILD_API=1
    BUILD_WEB=1
    RUN_MIGRATIONS=1
  else
    log "Detecting changes from $BASE_REF to $TARGET_SHA"
    mapfile -t changed_files < <(git diff --name-only "$BASE_REF" "$TARGET_SHA")

    if [[ "${#changed_files[@]}" -eq 0 ]]; then
      log "No changed files detected. Runtime services will not be rebuilt."
    else
      printf '%s\n' "${changed_files[@]}" | sed 's/^/[deploy-18088] changed: /'
    fi

    for file in "${changed_files[@]}"; do
      case "$file" in
        api/migrations/*)
          BUILD_API=1
          RUN_MIGRATIONS=1
          ;;
        api/*|dify-agent/*)
          BUILD_API=1
          ;;
        web/*)
          BUILD_WEB=1
          ;;
        docker/*)
          BUILD_API=1
          BUILD_WEB=1
          ;;
      esac
    done
  fi
fi

if [[ "$RUN_MIGRATIONS" == "1" ]]; then
  BUILD_API=1
fi

log "Plan: api=$BUILD_API web=$BUILD_WEB migrations=$RUN_MIGRATIONS verify=$VERIFY target=$TARGET_SHA"

if [[ "$BUILD_API" == "1" ]]; then
  log "Building API image: $API_IMAGE"
  run docker build --build-arg "COMMIT_SHA=$TARGET_SHA" -f api/Dockerfile -t "$API_IMAGE" .
fi

if [[ "$BUILD_WEB" == "1" ]]; then
  log "Building web image: $WEB_IMAGE"
  run docker build --build-arg "COMMIT_SHA=$TARGET_SHA" -f web/Dockerfile -t "$WEB_IMAGE" .
fi

if [[ "$RUN_MIGRATIONS" == "1" ]]; then
  log "Running database migrations"
  (cd "$COMPOSE_DIR" && run docker compose run --rm --no-deps api flask db upgrade)
fi

services=()
if [[ "$BUILD_API" == "1" ]]; then
  services+=(api api_websocket worker worker_beat)
fi
if [[ "$BUILD_WEB" == "1" ]]; then
  services+=(web)
fi

if [[ "${#services[@]}" -gt 0 ]]; then
  log "Recreating services: ${services[*]}"
  (cd "$COMPOSE_DIR" && run docker compose up -d --no-build --force-recreate "${services[@]}")
else
  log "No runtime service changes detected; skipping rebuild and restart."
fi

if [[ "$BUILD_API" == "1" || "$BUILD_WEB" == "1" ]]; then
  log "Restarting nginx to refresh Docker DNS upstreams"
  (cd "$COMPOSE_DIR" && run docker compose restart nginx)
fi

if [[ "$VERIFY" == "1" ]]; then
  log "Verifying local UI entrypoint: $LOCAL_VERIFY_URL"
  run curl -fsSIL --max-time 20 "$LOCAL_VERIFY_URL"

  log "Verifying local API entrypoint: $LOCAL_API_VERIFY_URL"
  run curl -fsSIL --max-time 20 "$LOCAL_API_VERIFY_URL"

  log "Verifying public UI entrypoint: $PUBLIC_VERIFY_URL"
  run curl -fsSIL --max-time 20 "$PUBLIC_VERIFY_URL"

  log "Verifying public API entrypoint: $PUBLIC_API_VERIFY_URL"
  run curl -fsSIL --max-time 20 "$PUBLIC_API_VERIFY_URL"
fi

if [[ "$DRY_RUN" == "0" ]]; then
  printf '%s\n' "$TARGET_SHA" > "$STATE_FILE"
  log "Recorded deployed ref in $STATE_FILE"
fi

log "Done. If the browser still shows old assets, hard refresh with Ctrl+F5."
