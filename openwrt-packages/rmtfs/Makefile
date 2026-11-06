#
# Package: rmtfs — Qualcomm remote-FS service for the modem
#
# rmtfs answers the modem's remote-FS (QMI RFSA) requests over the
# shared-memory uio node. Without it the modem has no EFS backing and
# the boot sequence (subsystem_get("modem")) never completes.
#
# Upstream uses a plain Makefile with:
#   LDFLAGS += -lqrtr -ludev -lpthread
# The qmi_rmtfs.c / qmi_rmtfs.qmi are already pre-generated in-tree, so
# no qmic codegen is needed at build time.
#
# Depends on raw libqrtr (openwrt-packages/libqrtr) + libudev-zero.
#

include $(TOPDIR)/rules.mk

PKG_NAME:=rmtfs
PKG_VERSION:=1.3
PKG_RELEASE:=1

PKG_SOURCE_PROTO:=git
PKG_SOURCE_URL:=https://github.com/linux-msm/rmtfs.git
PKG_SOURCE_VERSION:=b30a3eb38f9af283f18dbd3c7755653efc52c094
PKG_SOURCE_DATE:=2026-11-01
PKG_MIRROR_HASH:=skip

PKG_BUILD_FLAGS:=gc-sections

include $(INCLUDE_DIR)/package.mk
include $(INCLUDE_DIR)/nls.mk

TARGET_CFLAGS += -D_GNU_SOURCE -Wno-unused-function

define Package/rmtfs
  SECTION:=utils
  CATEGORY:=Utilities
  DEPENDS:=+libqrtr +libudev-zero +libpthread
  TITLE:=Qualcomm remote-FS service (modem EFS)
  URL:=https://github.com/linux-msm/rmtfs
  LICENSE:=BSD-3-Clause
endef

define Package/rmtfs/description
  Qualcomm rmtfs remote-FS service. Serves the modem's EFS read/write
  requests over the shared-memory uio node. Must be running before the
  modem boots (subsystem_get("modem")), or the modem watchdogs.
endef

define Build/Compile
	$(MAKE) -C $(PKG_BUILD_DIR) \
		CC="$(TARGET_CC)" \
		CFLAGS="$(TARGET_CFLAGS)" \
		LDFLAGS="$(TARGET_LDFLAGS) -lqrtr -ludev -lpthread" \
		RMTFS_EFS_PATH=/var/lib/rmtfs \
		rmtfs
endef

define Package/rmtfs/install
	$(INSTALL_DIR) $(1)/usr/bin
	$(INSTALL_BIN) $(PKG_BUILD_DIR)/rmtfs $(1)/usr/bin/
	$(INSTALL_DIR) $(1)/var/lib/rmtfs
endef

$(eval $(call BuildPackage,rmtfs))
