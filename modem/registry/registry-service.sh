# Shared procd lifecycle for the two AP-side registry services.
start_service() {
 [ -x "$RADIO_BIN_DIR/$REGISTRY_DAEMON" ] &&
 [ -x "$RADIO_BIN_DIR/registry-ready.sh" ] && [ -x "$RADIO_TIMEOUT" ] || {
  logger -t wayne-registry "missing registry executable or readiness helper"; return 1;
 }
 if [ "$REGISTRY_ROLE" = mapper ]; then
  "$RADIO_BIN_DIR/pd-mapper" -n -d "$RADIO_MAP_DIR" >/dev/null 2>&1 || {
   logger -t wayne-registry "map validation failed; mapper not registered"; return 1;
  }
 fi
 procd_open_instance main
 if [ "$REGISTRY_ROLE" = mapper ]; then
  procd_set_param command "$RADIO_BIN_DIR/pd-mapper" -d "$RADIO_MAP_DIR"
 else
  procd_set_param command "$RADIO_BIN_DIR/qrtr-ns" -f
 fi
 procd_set_param stdout 1
 procd_set_param stderr 1
 procd_set_param term_timeout 3
 procd_close_instance
}

service_started() {
 local service attempt status
 service=$(basename "${basescript:-$initscript}")
 for attempt in 1 2 3 4 5; do
  if procd_running "$service" main; then
   if "$RADIO_BIN_DIR/registry-ready.sh" "$REGISTRY_ROLE" "$RADIO_BIN_DIR" "$RADIO_TIMEOUT"; then
    logger -t wayne-registry "registry_ready=$REGISTRY_ROLE"
    return 0
   else
    status=$?
    [ "$status" != 2 ] || break
   fi
  fi
  sleep 1
 done
 procd_kill "$service" main
 logger -t wayne-registry "registry_not_ready=$REGISTRY_ROLE; instance stopped"
 return 1
}
