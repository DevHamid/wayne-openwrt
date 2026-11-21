#!/bin/sh
# Offline-only specimen: refuse before any staging or hardware access.
printf '%s\n' 'Unarmed collector specimen; run offline fixtures only.' >&2
exit 126
#!/bin/sh
# Temporary read-only firmware server; no modem handle or persistent install.
set -eu
D=/tmp/wayne-tftp-stock-profiles
BB=/bin/busybox-static
LOOKUP=/usr/lib/wayne/radio/qrtr-lookup
RESULT="$D.result"
RESULT_OWNED=0
TIMER=
SERVER_STATUS=not_started
record() {
 printf '%s\n' "$*" >> "$RESULT"
 printf '%s\n' "$*"
}
server_summary() {
 [ -f "$D/server.log" ] || return 0
 awk '
 /^readonly_firmware_open=accepted file=(wlanmdsp[.]mbn|WLANMDSP[.]MBN)$/ {opens++}
 /^readonly_request=denied$/ {denied++}
 /^readonly_write=denied$/ {writes++}
 /^readonly_window=denied$/ {windows++}
 /^readonly_sessions=limited$/ {sessions++}
 /^Reader received end of transfer from [0-9]+:[0-9]+$/ {ends++}
 /^failed to open qrtr socket$/ {open_errors++}
 /^failed to publish service registry service$/ {publish_errors++}
 /^select failed$/ {select_errors++}
 /^unable to decode qrtr packet$/ {decode_errors++}
 /^recvfrom failed on control socket: -[0-9]+$/ {recv_errors++;recv_code=$NF}
 END {printf "tftp_read_opens=%d\ntftp_denied_requests=%d\ntftp_denied_writes=%d\ntftp_denied_windows=%d\ntftp_session_limits=%d\ntftp_end_notifications=%d\n",opens,denied,writes,windows,sessions,ends}
 END {printf "tftp_socket_open_errors=%d\ntftp_publish_errors=%d\ntftp_select_errors=%d\ntftp_decode_errors=%d\ntftp_recv_errors=%d\ntftp_last_recv_error=%d\n",open_errors,publish_errors,select_errors,decode_errors,recv_errors,recv_code}
 ' "$D/server.log"
}
discovery_summary() {
 awk '
 NR==1 {header=($1=="Service" && $2=="Version" && $3=="Instance" && $4=="Node" && $5=="Port");next}
 NF {rows++;badrow=0;for(i=1;i<=5;i++)if($i!~/^[0-9]+$/ || length($i)>10)badrow=1
 if(badrow){invalid++;next}
 printf "observed_service=%s version=%s instance=%s node=%s port=%s\n",$1,$2,$3,$4,$5}
 END {printf "publication_rows=%d\npublication_invalid_rows=%d\npublication_header_valid=%d\n",rows,invalid,header}
 ' "$D/after.txt"
}
stop_server() {
 if [ -r "$D/server.pid" ]; then
  read -r pid < "$D/server.pid"
  case "$pid" in ''|*[!0-9]*) return 1;; esac
  if [ "$(readlink /proc/$pid/exe 2>/dev/null || :)" = "$D/tqftpserv-ro" ]; then
   kill -TERM "$pid" 2>/dev/null || :
  fi
 fi
 if [ -n "$TIMER" ]; then
  if wait "$TIMER" 2>/dev/null; then SERVER_STATUS=0; else SERVER_STATUS=$?; fi
  TIMER=
 fi
}
cleanup() {
 status=$?
 trap - EXIT HUP INT TERM PIPE
 trap '' PIPE
 set +e
 stop_server
 if [ "$RESULT_OWNED" = 1 ]; then server_summary >> "$RESULT"; fi
 rm -rf -- "$D"
 if [ -e "$D" ] || [ -L "$D" ]; then
  status=9
  [ "$RESULT_OWNED" != 1 ] || printf 'probe_cleanup=failed\n' >> "$RESULT"
 elif [ "$RESULT_OWNED" = 1 ]; then
  printf 'probe_cleanup=complete\n' >> "$RESULT"
 fi
 [ "$RESULT_OWNED" != 1 ] || printf 'server_exit_status=%s\nprobe_exit_status=%s\n' "$SERVER_STATUS" "$status" >> "$RESULT"
 echo tftp_probe_cleanup=finished
 exit "$status"
}
trap cleanup EXIT
trap 'exit 5' HUP INT TERM
trap 'exec >/dev/null; exit 5' PIPE
guard() {
 printf "%s\n" "No native baseline guard is supplied in this specimen." >&2
 return 126
}
server_alive() {
 [ "$(readlink /proc/$pid/exe 2>/dev/null || :)" = "$D/tqftpserv-ro" ] || {
  echo tftp_probe_error=server_exited >&2
  return 6
 }
}
lookup4096() { "$BB" timeout -k 1 3 "$LOOKUP" 4096; }
guard
(umask 077; set -C; : > "$RESULT") || exit 7
RESULT_OWNED=1
record probe_evidence_version=2
lookup4096 > "$D/before.txt"
awk 'NR==1 {ok=($1=="Service" && $2=="Version" && $3=="Instance" && $4=="Node" && $5=="Port");next} NF {n++} END{exit !(ok && n==0)}' "$D/before.txt"
printf '%s  %s\n' f77e315414f47a421c6020800a9f54d29f68971998b938243bd5f5f337549f50 /lib/firmware/WLANMDSP.MBN | sha256sum -c - >/dev/null
mkdir -m 700 "$D/fw"
cp /lib/firmware/WLANMDSP.MBN "$D/fw/wlanmdsp.mbn"
chmod 400 "$D/fw/wlanmdsp.mbn"
ln "$D/fw/wlanmdsp.mbn" "$D/fw/WLANMDSP.MBN"
"$D/server-fixture" "$D/fw" validate >/dev/null
"$D/tqftpserv-ro" -r "$D/fw" -n
"$BB" timeout -k 1 75 /bin/sh -c 'set -e; echo "$$" > "$1/server.pid"; exec "$1/tqftpserv-ro" -r "$1/fw"' sh "$D" > "$D/server.log" 2>&1 &
TIMER=$!
ready=0
for attempt in 1 2 3 4 5; do
 sleep 1
 if [ "$attempt" = 1 ]; then
  read -r pid < "$D/server.pid"
  case "$pid" in ''|*[!0-9]*) exit 6;; esac
  record "server_pid=$pid"
 fi
 lookup4096 > "$D/after.txt"
 discovery_summary >> "$RESULT"
 if awk -v expected_node=1 -f "$D/verify-profiles.awk" "$D/after.txt"; then ready=1; break; fi
done
[ "$ready" = 1 ]
read -r pid < "$D/server.pid"
server_alive
record 'firmware_service=published read_only=yes'
n=0
while [ "$n" -lt 12 ]; do
 sleep 5
 n=$((n+1))
 guard
 server_alive
 "$BB" timeout -k 1 3 "$LOOKUP" 69 > "$D/wlfw.txt"
 server_alive
 rows=$(awk 'NR>1 && $1==69 {n++} END{print n+0}' "$D/wlfw.txt")
 count=0
 for phy in /sys/class/ieee80211/phy*; do [ ! -d "$phy" ] || count=$((count+1)); done
 record "sample=$n wlfw_rows=$rows phy_count=$count"
 [ "$count" = 0 ] || break
done
stop_server
record firmware_server=stopped
dmesg | awk '
 {s=tolower($0)} s~/kernel command line/ {next}
 s~/wlan fw is ready/ {fw++}
 s~/connection established with the service locator/ {locator++}
 s~/connection established between qmi handle and/ {notifier++}
 s~/fatal error on the modem/ {fatal++}
 END{printf "kernel_fw_ready_events=%d\nkernel_locator_connections=%d\nkernel_notifier_connections=%d\nkernel_modem_fatal_events=%d\n",fw,locator,notifier,fatal}
 ' >> "$RESULT"
guard
record tftp_probe=complete
