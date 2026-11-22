#!/bin/sh
# Re-announce the AP-side QRTR services after every modem (re)boot.
#
# This 4.19 CAF kernel has no in-kernel nameserver and forwards control
# packets to remote nodes only, so a freshly booted modem incarnation
# learns AP services (rmtfs 14, servreg 64, tqftp 4096) solely from
# NEW_SERVER announcements that arrive AFTER its boot.  The daemons
# announce once at their own start, which is too early for any later
# modem boot; without a re-announce the modem's EFS/WLAN domain starves
# and the modem ERR_FATALs at ~42 s (verified root cause on wayne).
STATE=/sys/bus/msm_subsys/devices/subsys0/state

LAST=""
while :; do
	CUR=$(cat "$STATE" 2>/dev/null)
	if [ "$CUR" = "ONLINE" ] && [ "$LAST" != "ONLINE" ]; then
		sleep 2
		/etc/init.d/rmtfs restart 2>/dev/null
		/etc/init.d/pd-mapper restart 2>/dev/null
		/etc/init.d/tqftpserv restart 2>/dev/null
		logger -t wayne-qrefresh "services re-announced (modem ONLINE)"
	fi
	LAST=$CUR
	sleep 2
done
