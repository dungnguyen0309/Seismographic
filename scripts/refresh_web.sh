#!/usr/bin/env bash
# Rebuilds the static site in a copy of web/, checks the copy, and only then copies it over web/. The refresh workflows
# run it; if the build, the validation, the JS tests or the smoke test of every route fails, web/ is left untouched.
#   bash scripts/refresh_web.sh [staticbuild options, e.g. --only news,videos]
# Env: RUNNER_TEMP (where the copy is built; GitHub Actions sets it), PYTHON (default python), PORT (default 8650).
set -euo pipefail
py=${PYTHON:-python}
port=${PORT:-8650}
tmp=${RUNNER_TEMP:?set RUNNER_TEMP to a scratch folder}/web

rm -rf "$tmp"
cp -a web "$tmp"  # start from the last good files: a source that fails keeps its old file
"$py" -m staticbuild "$@" --out "$tmp"
"$py" -m staticbuild.validate "$tmp"
node --test "$tmp"/tests/*.test.mjs  # the JS tests read the new data files too

"$py" scripts/serve_web.py --root "$tmp" --port "$port" > /dev/null &
server=$!
trap 'kill "$server" 2> /dev/null || true' EXIT
for _ in $(seq 50); do curl -fso /dev/null "http://127.0.0.1:$port/" && break; sleep 0.2; done
node scripts/smoke_web.mjs --base "http://127.0.0.1:$port"
# unscored and unknown countries, bad links and the API (--routes splits on commas, so commas in a URL are %2C)
node scripts/smoke_web.mjs --base "http://127.0.0.1:$port" --widths 1280 --routes "/country?country=ASM,/country?country=XXX,/?w=1%2C2%2C3,/country?country=NGA&tab=nope,/stress?shock=garbage,/compare?c=ZZZ%2CQQQ,/api/v1,/api/v1/dictionary,/api/v1/countries,/api/v1/countries?tier=High,/api/v1/countries/KEN"

cp -a "$tmp"/. web/
echo "web/ updated from $tmp"
