LOCAL_PATH := $(call my-dir)

include $(CLEAR_VARS)
LOCAL_MODULE     := cheat
LOCAL_SRC_FILES  := cheat.cpp \
                    imgui/imgui.cpp \
                    imgui/imgui_draw.cpp \
                    imgui/imgui_tables.cpp \
                    imgui/imgui_widgets.cpp \
                    imgui/backends/imgui_impl_opengl3.cpp
LOCAL_C_INCLUDES := $(LOCAL_PATH)/imgui \
                    $(LOCAL_PATH)/imgui/backends
LOCAL_CFLAGS     := -O2 -std=c++20 -fvisibility=hidden \
                    -ffunction-sections -fdata-sections \
                    -DIMGUI_IMPL_OPENGL_ES2 \
                    -fno-exceptions -fno-rtti
LOCAL_LDFLAGS    := -Wl,--gc-sections
LOCAL_LDLIBS     := -llog -landroid -lEGL -lGLESv2 -ldl
include $(BUILD_SHARED_LIBRARY)
