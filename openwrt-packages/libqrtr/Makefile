#
# Package: libqrtr (raw) — for rmtfs
#
# The OpenWrt feed ships libqrtr-glib (glib wrapper), but rmtfs links
# against the RAW libqrtr (-lqrtr) and uses libqrtr.h directly
# (qrtr_open/qrtr_sendto/qmi_encode_message...). This is the
# linux-msm/qrtr library, pinned to a working commit.
#
# Build: meson (qrtr uses meson.build).
#

include $(TOPDIR)/rules.mk

PKG_NAME:=libqrtr
PKG_VERSION:=1.2
PKG_RELEASE:=1

PKG_SOURCE_PROTO:=git
PKG_SOURCE_URL:=https://github.com/linux-msm/qrtr.git
PKG_SOURCE_VERSION:=29e36ae164389580a0f8ea7a7fdb728140ae978d
PKG_SOURCE_DATE:=2026-01-01
PKG_MIRROR_HASH:=skip

PKG_BUILD_DEPENDS:=meson/host
PKG_INSTALL:=1
PKG_BUILD_FLAGS:=gc-sections

include $(INCLUDE_DIR)/package.mk
include $(INCLUDE_DIR)/meson.mk

define Package/libqrtr
  SECTION:=libs
  CATEGORY:=Libraries
  TITLE:=Raw Qualcomm QRTR userspace library (for rmtfs)
  URL:=https://github.com/linux-msm/qrtr
  LICENSE:=BSD-3-Clause
endef

define Package/libqrtr/description
  Raw QRTR (Qualcomm Router Transport) userspace library as used by
  rmtfs. Provides libqrtr.h, qrtr_open, qmi_encode_message etc.
  This is NOT libqrtr-glib (which is a separate glib wrapper).
endef

define Package/libqrtr/install
	$(INSTALL_DIR) $(1)/usr/lib
	$(CP) $(PKG_INSTALL_DIR)/usr/lib/libqrtr.so* $(1)/usr/lib/
endef

define Build/InstallDev
	$(INSTALL_DIR) $(1)/usr/include
	$(CP) $(PKG_INSTALL_DIR)/usr/include/libqrtr.h $(1)/usr/include/
	$(INSTALL_DIR) $(1)/usr/lib
	$(CP) $(PKG_INSTALL_DIR)/usr/lib/libqrtr.so* $(1)/usr/lib/
endef

$(eval $(call BuildPackage,libqrtr))
