LOCAL_PATH := $(call my-dir)

include $(CLEAR_VARS)
LOCAL_MODULE    := mc_zombie_mod
LOCAL_SRC_FILES := src/mod_main.cpp
LOCAL_LDLIBS    := -llog
include $(BUILD_SHARED_LIBRARY)
