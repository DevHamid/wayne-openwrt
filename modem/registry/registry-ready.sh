#!/bin/sh
# Exit 1 permits another discovery check; exit 2 forbids a query retry.
[ "$#" = 3 ] || exit 2
ROLE=$1
BIN=$2
TIMEOUT=$3
case "$ROLE" in nameserver|mapper) ;; *) exit 2;; esac
[ -x "$BIN/qrtr-lookup" ] && [ -x "$TIMEOUT" ] || exit 2
if OUT=$("$TIMEOUT" timeout -k 1 2 "$BIN/qrtr-lookup" 64 2>/dev/null); then :; else exit 1; fi
printf '%s\n' "$OUT" | awk 'NR==1 {ok=(NF==5 && $1=="Service" && $2=="Version" && $3=="Instance" && $4=="Node" && $5=="Port")} END{exit !ok}' || exit 2
[ "$ROLE" = nameserver ] && exit 0
if PORT=$(printf '%s\n' "$OUT" | awk '
 NR>1 && NF {
  if($1!=64 || $2!=1 || $3!=1 || $4!=1 || $5!~/^[0-9]+$/ || length($5)>10 || $5+0<=0 || $5+0>=4294967294)bad=1;
  n++; port=$5
 }
 END {if(!n && !bad)exit 1; if(n!=1 || bad)exit 2; print port}'); then :; else exit $?; fi
[ -x "$BIN/locator-query" ] || exit 2
if "$TIMEOUT" timeout -k 1 3 "$BIN/locator-query" "$PORT"; then exit 0; else exit 2; fi
