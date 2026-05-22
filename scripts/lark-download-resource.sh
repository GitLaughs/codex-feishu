#!/usr/bin/env bash
set -euo pipefail

message_id=""
file_key=""
resource_type="file"
output_name=""
as_identity="bot"
notes=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --message-id) message_id="$2"; shift 2 ;;
    --file-key) file_key="$2"; shift 2 ;;
    --type) resource_type="$2"; shift 2 ;;
    --output-name|--output) output_name="$2"; shift 2 ;;
    --as) as_identity="$2"; shift 2 ;;
    --notes) notes="$2"; shift 2 ;;
    *) echo "unknown argument: $1" >&2; exit 2 ;;
  esac
done

if [[ -z "$message_id" || -z "$file_key" ]]; then
  echo "--message-id and --file-key are required" >&2
  exit 1
fi
if [[ "$resource_type" != "file" && "$resource_type" != "image" ]]; then
  echo "--type must be file or image" >&2
  exit 1
fi

workspace="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
incoming="${workspace}/local_files/incoming"
audit_path="${workspace}/memory/lark-audit.jsonl"
import_script="${workspace}/scripts/import-local-file.sh"

mkdir -p "$incoming" "$(dirname "$audit_path")"

if ! command -v lark-cli >/dev/null 2>&1; then
  echo "lark-cli not found. Install with: npx @larksuite/cli@latest install" >&2
  exit 127
fi

safe_name="${output_name:-$file_key}"
if [[ "$safe_name" == */* || "$safe_name" == *\\* || "$safe_name" == *..* ]]; then
  echo "output name must be a file name, not a path" >&2
  exit 1
fi

set +e
(
  cd "$incoming" &&
  lark-cli im +messages-resources-download --as "$as_identity" --message-id "$message_id" --file-key "$file_key" --type "$resource_type" --output "$safe_name"
)
exit_code=$?
set -e

if [[ "$exit_code" -ne 0 ]]; then
  printf '{"time":"%s","action":"download_resource","ok":false,"exit_code":%s,"message_id":"%s","file_key":"%s"}\n' \
    "$(date -Is)" "$exit_code" "$message_id" "$file_key" >>"$audit_path"
  exit "$exit_code"
fi

downloaded="${incoming}/${safe_name}"
if [[ ! -f "$downloaded" ]]; then
  downloaded="$(find "$incoming" -maxdepth 1 -type f -printf '%T@ %p\n' | sort -nr | awk 'NR==1 {print substr($0, index($0,$2))}')"
fi
if [[ -z "$downloaded" || ! -f "$downloaded" ]]; then
  echo "download succeeded but no output file found in local_files/incoming" >&2
  exit 1
fi

note_text="${notes:-Feishu message resource archived, message_id ${message_id}, file_key ${file_key}}"
import_output="$(bash "$import_script" --path "$downloaded" --source-message "$message_id" --notes "$note_text" --move)"

printf '{"time":"%s","action":"download_resource","ok":true,"message_id":"%s","file_key":"%s","downloaded_path":"%s"}\n' \
  "$(date -Is)" "$message_id" "$file_key" "$downloaded" >>"$audit_path"
printf '%s\n' "$import_output"
