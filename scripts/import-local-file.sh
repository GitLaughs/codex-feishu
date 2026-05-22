#!/usr/bin/env bash
set -euo pipefail

source_path=""
source_message=""
notes=""
move_file=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --path|-p) source_path="$2"; shift 2 ;;
    --source-message) source_message="$2"; shift 2 ;;
    --notes) notes="$2"; shift 2 ;;
    --move) move_file=1; shift ;;
    *) echo "unknown argument: $1" >&2; exit 2 ;;
  esac
done

if [[ -z "$source_path" || ! -f "$source_path" ]]; then
  echo "--path must point to an existing file" >&2
  exit 1
fi

workspace="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
local_files="${workspace}/local_files"
index_path="${local_files}/INDEX.md"

mkdir -p "${local_files}/incoming" "${local_files}/docs" "${local_files}/data" "${local_files}/media" "${local_files}/code" "${local_files}/assets"

name="$(basename "$source_path")"
safe_name="$(printf '%s' "$name" | sed -E 's#[/\\:*?"<>|]#_#g; s/[[:space:]]+/_/g; s/^_+|_+$//g')"
if [[ -z "$safe_name" ]]; then
  safe_name="file"
fi

lower="$(printf '%s' "$safe_name" | tr '[:upper:]' '[:lower:]')"
case "$lower" in
  *.pdf|*.doc|*.docx|*.md|*.txt|*.ppt|*.pptx) bucket="docs" ;;
  *.csv|*.tsv|*.xls|*.xlsx|*.json|*.jsonl|*.yaml|*.yml) bucket="data" ;;
  *.png|*.jpg|*.jpeg|*.gif|*.webp|*.mp4|*.mov|*.mp3|*.wav) bucket="media" ;;
  *.py|*.js|*.ts|*.tsx|*.jsx|*.ps1|*.sh|*.bat|*.c|*.cpp|*.h|*.hpp|*.rs|*.go|*.java|*.ipynb|*.zip|*.tar|*.gz|*.7z|*.rar) bucket="code" ;;
  *) bucket="incoming" ;;
esac

dest_dir="${local_files}/${bucket}"
dest_path="${dest_dir}/${safe_name}"
if [[ -e "$dest_path" ]]; then
  stem="${safe_name%.*}"
  ext=""
  if [[ "$safe_name" == *.* ]]; then
    ext=".${safe_name##*.}"
  fi
  dest_path="${dest_dir}/${stem}-$(date +%Y%m%d-%H%M%S)${ext}"
fi

if [[ "$move_file" -eq 1 ]]; then
  mv "$source_path" "$dest_path"
else
  cp "$source_path" "$dest_path"
fi

if command -v sha256sum >/dev/null 2>&1; then
  hash_short="$(sha256sum "$dest_path" | awk '{print substr($1,1,12)}')"
elif command -v shasum >/dev/null 2>&1; then
  hash_short="$(shasum -a 256 "$dest_path" | awk '{print substr($1,1,12)}')"
else
  hash_short="unknown"
fi

rel_path="${dest_path#${workspace}/}"
if [[ ! -f "$index_path" ]]; then
  {
    echo "# Local File Index"
    echo ""
    echo "| Date | Name | Path | Type | Notes |"
    echo "|---|---|---|---|---|"
  } >"$index_path"
fi

note_text="$notes"
if [[ -n "$source_message" ]]; then
  note_text="${note_text} source=${source_message}"
fi
note_text="${note_text} sha256=${hash_short}"
note_text="$(printf '%s' "$note_text" | tr '\n|' ' /')"

printf '| %s | %s | %s | %s | %s |\n' "$(date +%F)" "$safe_name" "$rel_path" "$bucket" "$note_text" >>"$index_path"

echo "imported: ${rel_path}"
