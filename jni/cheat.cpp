// ============================================================
//  Standoff 2 — ARM64 Internal Cheat (.so)
//  Target  : libgamex64.so (Unity IL2CPP, Photon netcode)
//  Arch    : ARM64 (aarch64-linux-android)
//  Sources : dump_so2_1_0_0_64_bit.cs | offsets.hpp (normal6)
//            il2cpp_api_so2_1_0.txt | message.txt (zenin14)
//            offsets__1_.txt | Zenin_Internal_funct_dump.txt
//  Author  : hwidoholy
// ============================================================
//  BUILD:
//    ndk-build NDK_PROJECT_PATH=. APP_BUILD_SCRIPT=Android.mk
//              NDK_APPLICATION_MK=Application.mk -j8
//    Output : libs/arm64-v8a/libcheat.so
//    Inject : System.loadLibrary("cheat") in patched dex
// ============================================================

// ─── Standard headers ────────────────────────────────────────
#include <jni.h>
#include <android/log.h>
#include <EGL/egl.h>
#include <GLES2/gl2.h>
#include <dlfcn.h>
#include <pthread.h>
#include <unistd.h>
#include <sys/mman.h>
#include <cstring>
#include <cmath>
#include <string>
#include <vector>
#include <array>
#include <mutex>
#include <algorithm>
#include <cstdio>
#include <cstdlib>
#include <limits>
#include <type_traits>

// ─── ImGui ───────────────────────────────────────────────────
#include "imgui.h"
#include "imgui_impl_opengl3.h"

#define LOG_TAG "HWIDOHOLY"
#define LOGI(...) __android_log_print(ANDROID_LOG_INFO,  LOG_TAG, __VA_ARGS__)
#define LOGE(...) __android_log_print(ANDROID_LOG_ERROR, LOG_TAG, __VA_ARGS__)

// ============================================================
// SECTION 1 — MEMORY PRIMITIVES
// ============================================================

template<typename T>
static inline T Rd(uintptr_t a) {
    if (!a) return T{};
    return *reinterpret_cast<T*>(a);
}
template<typename T>
static inline void Wr(uintptr_t a, T v) {
    if (a) *reinterpret_cast<T*>(a) = v;
}
static inline uintptr_t Rp(uintptr_t a) { return Rd<uintptr_t>(a); }

static inline bool vp(uintptr_t a) {
    return a >= 0x10000ULL && a <= 0x7FFFFFFFFFFFULL;
}

// ============================================================
// SECTION 2 — OFFSETS  (normal6/offsets.hpp + dumps)
// ============================================================

// ─── Library ─────────────────────────────────────────────────
#define OFF_PLAYER_MANAGER      180740496ULL  // TypeInfo slot in libgamex64.so

// ─── PlayerManager ───────────────────────────────────────────
#define OFF_PM_LOCAL_PLAYER     0x70
#define OFF_PM_PLAYER_LIST      0x28

// ─── PlayerList ──────────────────────────────────────────────
#define OFF_LIST_COUNT          0x20
#define OFF_LIST_BUFFER         0x18
#define OFF_LIST_ENTRY_BASE     0x30
#define OFF_LIST_ENTRY_STRIDE   0x18

// ─── PlayerController ────────────────────────────────────────
#define OFF_PLAYER_TEAM             0x79
#define OFF_PLAYER_AIM_ANIM_CTRL    0xA0
#define OFF_PLAYER_VIEW_1           0x48
#define OFF_PLAYER_VIEW_2           0x50
#define OFF_PLAYER_AIM_CONTROLLER   0x80
#define OFF_PLAYER_WEAPON_ROOT      0x88
#define OFF_PLAYER_MOVEMENT_CTRL    0x98
#define OFF_PLAYER_OCCLUSION        0xB8
#define OFF_PLAYER_MAIN_CAMERA      0xE8
#define OFF_PLAYER_PHOTON_PTR       0x160

// ─── View / BipedMap ─────────────────────────────────────────
#define OFF_VIEW_BIPED_MAP      0x48
#define OFF_BONE_HEAD_1         0x28
#define OFF_BONE_HEAD_2         0x20
#define OFF_BONE_NECK           0x28     // BipedMap
#define OFF_BONE_SPINE2         0x40
#define OFF_BONE_SPINE1         0x38
#define OFF_BONE_SPINE          0x30
#define OFF_BONE_HIP            0x88
#define OFF_BONE_L_SHOULDER     0x48
#define OFF_BONE_L_UPPERARM     0x50
#define OFF_BONE_L_FOREARM      0x58
#define OFF_BONE_L_HAND         0x60
#define OFF_BONE_R_SHOULDER     0x68
#define OFF_BONE_R_UPPERARM     0x70
#define OFF_BONE_R_FOREARM      0x78
#define OFF_BONE_R_HAND         0x80
#define OFF_BONE_L_UPLEG        0x90
#define OFF_BONE_L_KNEE         0x98
#define OFF_BONE_L_FOOT         0xA0
#define OFF_BONE_R_UPLEG        0xB0
#define OFF_BONE_R_KNEE         0xB8
#define OFF_BONE_R_FOOT         0xC0

// ─── Transform system ────────────────────────────────────────
#define OFF_TRANSFORM_NATIVE        0x10
#define OFF_NATIVE_TRANSFORM_DATA   0x38
#define OFF_NATIVE_TRANSFORM_INDEX  0x40
#define OFF_TRANSFORM_DATA_ARRAY    0x18

// ─── AimController / AimingData ──────────────────────────────
#define OFF_AIM_CONTROLLER_DATA 0x90
#define OFF_AIMDATA_PITCH       0x18   // float pitch (normal6/offsets.hpp verified)
#define OFF_AIMDATA_YAW         0x1C   // float yaw   (normal6/offsets.hpp verified)

// ─── Camera ──────────────────────────────────────────────────
#define OFF_CAM_SETTINGS        0x28
#define OFF_CAM_FOV             0x38
#define OFF_NATIVE_CAM_FOV      0x180
#define OFF_CAMERA_NATIVE       0x10   // managed Camera → native ptr

// ─── WeaponController (GunController) ────────────────────────
#define OFF_WRC_ACTIVE_WEAPON   0xA0
#define OFF_WC_FIRE_DURATION    0x108  // SafeFloat
#define OFF_WC_AMMO_CURRENT     0x120  // SafeInt
#define OFF_WC_AMMO_MAX         0x128  // SafeInt
#define OFF_WC_RECOIL_MULT      0x240
#define OFF_WC_RECOIL_MULT2     0x244
#define OFF_WC_GUN_PARAMS       0x168
#define OFF_WC_ACCURACY_DATA    0x228
#define OFF_WC_FIRE_BUTTON      0x148  // uint8_t fire button
#define OFF_WC_WEAPON_PROPS     0xA8

// ─── RecoilController ────────────────────────────────────────
#define OFF_WC_RECOIL_CTRL      0x160
#define OFF_RC_RECOIL_0         0x18
#define OFF_RC_RECOIL_1         0x1C
#define OFF_RC_RECOIL_2         0x20
#define OFF_RC_RECOIL_3         0x24
#define OFF_RC_RECOIL_4         0x28
#define OFF_RC_RECOIL_5         0x2C

// ─── GunParameters / RecoilParameters ────────────────────────
#define OFF_GP_RECOIL_PARAMS    0x158
#define OFF_RP_HORIZONTAL       0x10
#define OFF_RP_VERTICAL         0x14
#define OFF_ACCDATA_ANGLE       0x10
#define OFF_ACCDATA_RECOIL      0x14

// ─── WeaponProperties (wallshot) ─────────────────────────────
#define OFF_WP_PENETRATION      0x264  // float; write 0x7F7FFFFF = max

// ─── Occlusion ───────────────────────────────────────────────
#define OFF_OCCLUSION_CURRENT   0x34   // int: 2=visible
#define OFF_OCCLUSION_NEXT      0x38

// ─── MovementController ──────────────────────────────────────
#define OFF_MC_TRAJECTORY       0xA8
#define OFF_MC_THRUST_DATA      0xB0
#define OFF_TP_JUMP_PARAMS      0x50
#define OFF_TP_CROUCH_PARAMS    0x48
#define OFF_JP_JUMP_SPEED       0x10
#define OFF_JP_JUMP_SPEED2      0x60
#define OFF_CP_SPEED_MULT       0x10
#define OFF_CP_SPEED_MULT2      0x14
#define OFF_TD_THRUST_VEC       0x68

// ─── Anti-aim (from antiaim.cpp) ─────────────────────────────
#define OFF_AA_MOV_CTRL         0xB8   // aim_ctrl + 0xB8
#define OFF_AA_MOV_TRANSFORM    0xC0   // mov_ctrl + 0xC0
#define OFF_AA_CHARACTER        0xD0   // aim_ctrl + 0xD0

// ─── PhotonPlayer ────────────────────────────────────────────
#define OFF_PHOTON_NAME         0x20
#define OFF_PHOTON_ACTOR_ID     0x18
#define OFF_PHOTON_IS_LOCAL     0x30

// ─── SafeFloat/SafeInt ───────────────────────────────────────
#define OFF_SAFE_SALT           0x10
#define OFF_SAFE_VALUE          0x14

// ─── IL2CPP class statics ────────────────────────────────────
#define ILCLS_STATIC_FIELDS     0x90   // [confirmed il2cpp_api_1_0_0.txt]

// ─── RVAs (libunity.so) from offsets__1_.txt ─────────────────
#define RVA_SHADER_FIND             0x75FAF74ULL
#define RVA_MATERIAL_CTOR_SHADER    0x75F3798ULL
#define RVA_MATERIAL_SET_COLOR_INT  0x75FC688ULL
#define RVA_MATERIAL_SET_COLOR_STR  0x761134CULL
#define RVA_MATERIAL_SET_FLOAT_STR  0x75F6C44ULL
#define RVA_MATERIAL_SET_SHADER     0x7602D8CULL
#define RVA_MATERIAL_SET_QUEUE      0x75FCB04ULL
#define RVA_RENDERER_GET_MAT        0x75E7C48ULL
#define RVA_RENDERER_SET_MAT        0x75F2DE8ULL
#define RVA_RENDERER_GET_SHARED     0x7612138ULL
#define RVA_RENDERER_SET_SHARED     0x75EB8A0ULL
#define RVA_COMPONENT_GET_GAMEOBJ   0x67D4FBCULL
#define RVA_COMPONENT_GET_TRANSFORM 0x67E3358ULL
#define RVA_RENDERSETTINGS_SET_FOG  0x75F0BD4ULL
#define RVA_RENDERSETTINGS_SET_FOG_COLOR 0x760931CULL
#define RVA_RENDERSETTINGS_SET_AMB  0x75F8A00ULL
#define RVA_RENDERSETTINGS_SET_AMB_INTENSITY 0x75F05F4ULL
#define RVA_LIGHT_SET_INTENSITY     0x7613524ULL
#define RVA_TRANSFORM_SET_EULER     0x67F4378ULL

// ─── RVAs (libgamex64.so) ────────────────────────────────────
#define RVA_IL2CPP_RESOLVE_ICALL    0x63279F4ULL  // il2cpp_api_so2_1_0
#define RVA_IL2CPP_DOMAIN_GET       0x6327B70ULL
#define RVA_IL2CPP_THREAD_ATTACH    0x6327D70ULL
#define RVA_IL2CPP_STRING_NEW       0x6327D54ULL  // approximate

// ─── Zenin14 fire hook RVAs ──────────────────────────────────
// Source: message.txt — "fire hook at RVA 0xC9381C"
// "routine at RVA 0xC62E80" = CalculateAngles
// Both in libgamex64.so
#define RVA_ZENIN_FIRE_HOOK         0xC9381CULL
#define RVA_ZENIN_CALC_ANGLES       0xC62E80ULL

// ─── Player position (RVA normal6/offsets.hpp) ───────────────
// ake.xdzx() RVA 0x9489018 — direct call for position
#define RVA_PLAYER_GET_POSITION     0x9489018ULL

// Triggerbot
#define TRIGGER_SHOT_DURATION       0.08f
#define TRIGGER_MAX_RADIUS_PX       80.f

// ─── Noclip values (from normal6/noclip.cpp) ─────────────────
static constexpr uint32_t NOCLIP_SEARCH  = 0x3F80003Du;  // float search bit
static constexpr uint32_t NOCLIP_REPLACE = 0x42280000u;  // float 42.0 bit

// ─── Chams ───────────────────────────────────────────────────
static constexpr uint32_t CHAMS_SEARCH  = 1073741859u;
static constexpr uint32_t CHAMS_REPLACE_WHITE = 1073741910u;

// ============================================================
// SECTION 3 — MATH
// ============================================================

struct Vec2 { float x, y; };
struct Vec3 { float x, y, z; };
struct Vec4 { float x, y, z, w; };
struct Quat { float x, y, z, w; };
struct Color4 { float r, g, b, a; };

struct TMatrix {
    Vec4 position;
    Quat rotation;
    Vec4 scale;
};

struct Matrix4x4 { float m[16]; };

static inline float VLen(const Vec3& v) {
    return sqrtf(v.x*v.x + v.y*v.y + v.z*v.z);
}
static inline float VDot(const Vec3& a, const Vec3& b) {
    return a.x*b.x + a.y*b.y + a.z*b.z;
}
static inline Vec3 VCross(const Vec3& a, const Vec3& b) {
    return {a.y*b.z - a.z*b.y, a.z*b.x - a.x*b.z, a.x*b.y - a.y*b.x};
}
static inline Vec3 VNorm(const Vec3& v) {
    float l = VLen(v);
    return l > 1e-6f ? Vec3{v.x/l, v.y/l, v.z/l} : Vec3{0,0,1};
}
static inline float VDist2D(const Vec3& a, const Vec3& b) {
    float dx=a.x-b.x, dz=a.z-b.z;
    return sqrtf(dx*dx + dz*dz);
}
static inline float VDist3D(const Vec3& a, const Vec3& b) {
    float dx=a.x-b.x, dy=a.y-b.y, dz=a.z-b.z;
    return sqrtf(dx*dx + dy*dy + dz*dz);
}

// zenin14::FireQuaternion (from message.txt)
static Quat FireQuaternion(float yaw, float pitch) noexcept {
    constexpr float rad = 0.01745329238474369049f;
    const float hp = (pitch * rad) * 0.5f;
    const float hy = (yaw   * rad) * 0.5f;
    const float sp = sinf(hp), cp = cosf(hp);
    const float sy = sinf(hy), cy = cosf(hy);
    return {sp*cy, sy*cp, -(sp*sy), cy*cp};
}

// zenin14::CalculateAngles (from message.txt)
static bool CalculateAngles(const Vec3& origin, const Vec3& target,
                             float cur_yaw, float cur_pitch,
                             float smoothing, bool snap,
                             float& out_yaw, float& out_pitch) noexcept {
    const Vec3 delta{target.x-origin.x, target.y-origin.y, target.z-origin.z};
    float sq = std::fma(delta.x,delta.x, std::fma(delta.y,delta.y, delta.z*delta.z));
    const float len = sqrtf(sq);
    if (len < 0.0001f) return false;
    const Vec3 dir{delta.x/len, delta.y/len, delta.z/len};
    const float horiz = sqrtf(std::fma(dir.x,dir.x, dir.z*dir.z));
    constexpr float deg = 57.295780181884765625f;
    const float desired_yaw   = atan2f(dir.x, dir.z) * deg;
    const float desired_pitch = atan2f(dir.y, horiz) * -deg;
    const float lim = smoothing > 0.95f ? 0.95f : smoothing;
    const float fac = (snap || smoothing < 0.0f) ? 1.0f : 1.0f - lim;
    // Wrap deltas
    auto wrap = [](float v) {
        while (v > 180.f) v -= 360.f;
        while (v < -180.f) v += 360.f;
        return v;
    };
    out_yaw   = std::fma(wrap(desired_yaw   - cur_yaw),   fac, cur_yaw);
    out_pitch = std::fma(wrap(desired_pitch - cur_pitch),  fac, cur_pitch);
    return true;
}

// Slerp
static Quat QuatSlerp(const Quat& a, const Quat& b, float t) {
    float dot = a.x*b.x + a.y*b.y + a.z*b.z + a.w*b.w;
    Quat bb = b;
    if (dot < 0.f) { bb={-b.x,-b.y,-b.z,-b.w}; dot=-dot; }
    if (dot > 0.9995f)
        return {a.x+t*(bb.x-a.x), a.y+t*(bb.y-a.y), a.z+t*(bb.z-a.z), a.w+t*(bb.w-a.w)};
    float ang = acosf(dot), sina = sinf(ang);
    float sa = sinf((1.f-t)*ang)/sina, sb = sinf(t*ang)/sina;
    return {sa*a.x+sb*bb.x, sa*a.y+sb*bb.y, sa*a.z+sb*bb.z, sa*a.w+sb*bb.w};
}

static Quat EulerToQuat(float rx, float ry, float rz) {
    float hr=rx*0.5f, hp=ry*0.5f, hy=rz*0.5f;
    float cr=cosf(hr),sr=sinf(hr), cp=cosf(hp),sp=sinf(hp), cy=cosf(hy),sy=sinf(hy);
    return {sr*cp*cy-cr*sp*sy, cr*sp*cy+sr*cp*sy, cr*cp*sy-sr*sp*cy, cr*cp*cy+sr*sp*sy};
}

static Quat DegeneratQuat() {
    return {(float)(rand()%200000-100000)*0.01f,
            (float)(rand()%200000-100000)*0.01f,
            (float)(rand()%200000-100000)*0.01f, 0.f};
}

// ============================================================
// SECTION 4 — LIBRARY BASES
// ============================================================

static uintptr_t g_Base      = 0;  // libgamex64.so (IL2CPP API RVAs)
static uintptr_t g_UnityBase = 0;  // libunity.so   (TypeInfo + Transform data)

static uintptr_t GetLibBase(const char* name) {
    FILE* f = fopen("/proc/self/maps", "r");
    if (!f) return 0;
    char line[512]; uintptr_t base = 0;
    while (fgets(line, sizeof(line), f)) {
        if (strstr(line, name) && strstr(line, "r-xp")) {
            base = (uintptr_t)strtoull(line, nullptr, 16);
            break;
        }
    }
    fclose(f); return base;
}

// Huawei APK ships libro.so as a pre-injected stub.
// The actual game code is still in libgamex64.so + libunity.so.
// libro.so is NOT the IL2CPP game library — it's a loader/wrapper.
// On Huawei: libgamex64.so IL2CPP API RVAs differ from standard build.
// We detect Huawei at runtime and swap RVAs accordingly.
static bool g_IsHuawei = false;

static void DetectHuawei() {
    // Presence of libro.so in maps = Huawei APK variant
    FILE* f = fopen("/proc/self/maps","r"); if(!f) return;
    char line[512];
    while(fgets(line,sizeof(line),f)) {
        if(strstr(line,"libro.so") || strstr(line,"com.axlebolt.standoff2.huawei")) {
            g_IsHuawei = true; break;
        }
    }
    fclose(f);
    if(g_IsHuawei) LOGI("Huawei build detected — using HW IL2CPP RVAs");
}

// ============================================================
// SECTION 5 — IL2CPP API
// ============================================================

static void* (*il2cpp_resolve_icall)(const char*) = nullptr;
static void* (*il2cpp_domain_get)()               = nullptr;
static void* (*il2cpp_thread_attach)(void*)        = nullptr;

// Huawei IL2CPP RVAs (from il2cpp_api_huawei_1_0_0.txt)
#define RVA_HW_RESOLVE_ICALL    0x640769CULL
#define RVA_HW_DOMAIN_GET       0x6407824ULL
#define RVA_HW_THREAD_ATTACH    0x6407A24ULL

static bool InitIL2CPP() {
    if (!g_Base) return false;
    DetectHuawei();
    if (g_IsHuawei) {
        // Huawei build: libro.so present, libgamex64.so uses different IL2CPP RVAs
#define R(p,rva) p = reinterpret_cast<decltype(p)>(g_Base+(rva))
        R(il2cpp_resolve_icall, RVA_HW_RESOLVE_ICALL);
        R(il2cpp_domain_get,    RVA_HW_DOMAIN_GET);
        R(il2cpp_thread_attach, RVA_HW_THREAD_ATTACH);
#undef R
    } else {
        // Standard build
#define R(p,rva) p = reinterpret_cast<decltype(p)>(g_Base+(rva))
        R(il2cpp_resolve_icall, RVA_IL2CPP_RESOLVE_ICALL);
        R(il2cpp_domain_get,    RVA_IL2CPP_DOMAIN_GET);
        R(il2cpp_thread_attach, RVA_IL2CPP_THREAD_ATTACH);
#undef R
    }
    LOGI("IL2CPP init: %s build, base=0x%llX",
         g_IsHuawei?"Huawei":"Standard",
         (unsigned long long)g_Base);
    return il2cpp_resolve_icall != nullptr;
}

// ============================================================
// SECTION 6 — PLAYER MANAGER
// ============================================================

// GetPlayerManager: libunity.so + TI_NJH → njh klass*
// Confirmed by: Amnesia TI_NJH=0xC2062E0, Wolsaw v100::registry_typeinfo=0xC203D50
// Note: Wolsaw's 0xC203D50 = registry (gat), Amnesia's 0xC2062E0 = njh (world)
// We use TI_NJH (world/njh) as the entry point to player list
static uintptr_t g_NJHKlass  = 0;
static uintptr_t g_AKEKlass  = 0;
static uintptr_t g_DWCKlass  = 0;
static uintptr_t g_CAMKlass  = 0;
static uintptr_t g_WorldObj  = 0;  // cached njh world object

static void RefreshKlasses() {
    if (!g_UnityBase) return;
    g_NJHKlass = Rp(g_UnityBase + TI_NJH);
    g_AKEKlass = Rp(g_UnityBase + TI_AKE);
    g_DWCKlass = Rp(g_UnityBase + TI_DWC);
    g_CAMKlass = Rp(g_UnityBase + TI_CAMERA);
}

// njh chain (Amnesia EspEngine): njh+0x40→gat, gat+0x30→gzx, gzx+0x18→coll
// coll+0x10→items*, coll+0x18→count
#define NJH_REGISTRY    0x40   // njh → gat (registry)
#define GAT_STORE       0x30   // gat → gzx (store)
#define GZX_OBJECTS     0x18   // gzx → collection
#define COLL_ITEMS      0x10   // collection → items*
#define COLL_COUNT      0x18   // collection → count (int64)
#define MFC_LOCAL       0x44   // mfc.LocalOwned (bool)
#define MFC_PARTS       0x28   // mfc → parts container (rct)
#define PARTS_LIST      0x10   // rct → List<eur>

static uintptr_t GetPlayerManager() {
    // Returns the njh world object (Amnesia: 'world' variable)
    if (!vp(g_WorldObj)) return 0;
    if (Rp(g_WorldObj) != g_NJHKlass) { g_WorldObj = 0; return 0; }
    return g_WorldObj;
}

// Scan memory for njh world object (called once per session)
// Strategy: scan [data_relro..data_end] of libunity.so for g_NJHKlass value
// Confirmed range: Wolsaw v100::data_relro_begin=0xB886F80, data_end=0xC46CF80
#define UNITY_DATA_BEGIN  0xB886F80ULL
#define UNITY_DATA_END    0xC46CF80ULL

static void ScanForWorld() {
    if (!g_UnityBase || !vp(g_NJHKlass)) return;
    uintptr_t scan_start = g_UnityBase + UNITY_DATA_BEGIN;
    uintptr_t scan_end   = g_UnityBase + UNITY_DATA_END;
    // Clamp to safe range
    if (scan_start >= scan_end || scan_end - scan_start > 0x10000000ULL) return;
    int best_score = -1;
    uintptr_t best_addr = 0;
    for (uintptr_t a = scan_start; a + 8 <= scan_end; a += 8) {
        uintptr_t val = Rp(a);
        if (val != g_NJHKlass) continue;
        // Score: check registry chain
        uintptr_t reg = Rp(a + NJH_REGISTRY);
        if (!vp(reg)) continue;
        uintptr_t store = Rp(reg + GAT_STORE);
        if (!vp(store)) continue;
        uintptr_t coll = Rp(store + GZX_OBJECTS);
        if (!vp(coll)) continue;
        int64_t cnt = Rd<int64_t>(coll + COLL_COUNT);
        if (cnt < 0 || cnt > 16384) continue;
        int score = (int)cnt;
        if (score > best_score) { best_score=score; best_addr=a; }
    }
    if (best_addr) { g_WorldObj = best_addr; LOGI("World @ 0x%llX score=%d", (unsigned long long)best_addr, best_score); }
}

// ============================================================
// SECTION 7 — SAFE VALUE HELPERS
// ============================================================

static float DecodeSF(uintptr_t p) {
    if (!p) return 0.f;
    uint32_t s=Rd<uint32_t>(p+OFF_SAFE_SALT), v=Rd<uint32_t>(p+OFF_SAFE_VALUE);
    uint32_t r=v^s; float f; memcpy(&f,&r,4); return f;
}
static int32_t DecodeSI(uintptr_t p) {
    if (!p) return 0;
    return Rd<int32_t>(p+OFF_SAFE_VALUE) ^ Rd<int32_t>(p+OFF_SAFE_SALT);
}
static void EncodeSI(uintptr_t p, int32_t val) {
    if (!p) return;
    Wr<int32_t>(p+OFF_SAFE_VALUE, val ^ Rd<int32_t>(p+OFF_SAFE_SALT));
}

// ============================================================
// SECTION 8 — TRANSFORM POSITION (icall)
// ============================================================

static void (*icall_get_pos)(void*, Vec3*)       = nullptr;
static void (*icall_get_wv)(void*, Matrix4x4*)   = nullptr;
static void (*icall_get_proj)(void*, Matrix4x4*) = nullptr;
static void (*icall_set_fov)(void*, float)        = nullptr;
static void (*icall_get_rotation)(void*, Quat*)   = nullptr;

static bool InitICalls() {
    if (!il2cpp_resolve_icall) return false;
#define RI(p,n) p = (decltype(p))il2cpp_resolve_icall(n); \
    if (!p) p = (decltype(p))il2cpp_resolve_icall(n "_Injected");
    RI(icall_get_pos,    "UnityEngine.Transform::get_position_Injected")
    RI(icall_get_wv,     "UnityEngine.Camera::get_worldToCameraMatrix_Injected")
    RI(icall_get_proj,   "UnityEngine.Camera::get_projectionMatrix_Injected")
    RI(icall_set_fov,    "UnityEngine.Camera::set_fieldOfView")
    RI(icall_get_rotation,"UnityEngine.Transform::get_rotation_Injected")
#undef RI
    return icall_get_pos && icall_get_wv;
}

static Vec3 GetPos(uintptr_t tr) {
    Vec3 v{}; if (tr && icall_get_pos) icall_get_pos((void*)tr, &v); return v;
}

// ============================================================
// SECTION 9 — WORLD TO SCREEN
// ============================================================

static float g_SW = 1080.f, g_SH = 1920.f;
static uintptr_t g_LocalPC = 0;

static bool W2S(const Vec3& w, float& sx, float& sy) {
    if (!g_LocalPC) return false;
    uintptr_t pmc = Rp(g_LocalPC + OFF_PLAYER_MAIN_CAMERA);
    if (!pmc) return false;
    uintptr_t cam = Rp(pmc + 0x20);
    if (!cam) return false;
    Matrix4x4 view{}, proj{};
    if (icall_get_wv && icall_get_proj) {
        icall_get_wv  ((void*)cam, &view);
        icall_get_proj((void*)cam, &proj);
    } else {
        // Direct native read fallback: Amnesia NCAMERA_VIEW=+0x70, PROJ=+0xB0
        uintptr_t nat = Rp(cam + OFF_CAMERA_NATIVE);
        if (!vp(nat)) return false;
        view = Rd<Matrix4x4>(nat + 0x70);
        proj = Rd<Matrix4x4>(nat + 0xB0);
        // Validate matrix sanity (Amnesia EspEngine.readCamera checks)
        if (fabsf(view.m[15]-1.f)>0.01f || fabsf(proj.m[11]+1.f)>0.01f
            || fabsf(proj.m[15])>0.01f  || fabsf(proj.m[5])<1e-4f) return false;
    }
    float vx = view.m[0]*w.x + view.m[4]*w.y + view.m[8] *w.z + view.m[12];
    float vy = view.m[1]*w.x + view.m[5]*w.y + view.m[9] *w.z + view.m[13];
    float vz = view.m[2]*w.x + view.m[6]*w.y + view.m[10]*w.z + view.m[14];
    float vw = view.m[3]*w.x + view.m[7]*w.y + view.m[11]*w.z + view.m[15];
    float cx = proj.m[0]*vx + proj.m[4]*vy + proj.m[8] *vz + proj.m[12]*vw;
    float cy = proj.m[1]*vx + proj.m[5]*vy + proj.m[9] *vz + proj.m[13]*vw;
    float cw = proj.m[3]*vx + proj.m[7]*vy + proj.m[11]*vz + proj.m[15]*vw;
    if (cw < 0.01f) return false;
    sx = ( cx/cw + 1.f) * 0.5f * g_SW;
    sy = (-cy/cw + 1.f) * 0.5f * g_SH;
    return true;
}

// ============================================================
// SECTION 10 — PLAYER DATA
// ============================================================

struct BoneSet {
    Vec3 head, neck, spine2, spine1, spine, hip;
    Vec3 lShoulder, lUpperarm, lElbow, lHand;
    Vec3 rShoulder, rUpperarm, rElbow, rHand;
    Vec3 lUpLeg, lKnee, lFoot;
    Vec3 rUpLeg, rKnee, rFoot;
};

struct PlayerEntry {
    uintptr_t   pc;
    std::string name;
    uint8_t     team;
    bool        isLocal;
    bool        visible;
    int32_t     ammo, ammoMax;
    float       yawDeg;
    Vec3        pos;      // hip world position
    BoneSet     bones;
};

static std::vector<PlayerEntry> g_Players;
static uintptr_t g_LocalAim = 0;

static uintptr_t GetBM(uintptr_t pc) {
    uintptr_t v = Rp(pc + OFF_PLAYER_VIEW_1);
    if (!vp(v)) v = Rp(pc + OFF_PLAYER_VIEW_2);
    return vp(v) ? Rp(v + OFF_VIEW_BIPED_MAP) : 0;
}

static Vec3 BP(uintptr_t bm, uintptr_t off) {
    uintptr_t tr = Rp(bm + off);
    return GetPos(tr);
}

static bool IsVisible(uintptr_t pc) {
    uintptr_t occ = Rp(pc + OFF_PLAYER_OCCLUSION);
    if (!vp(occ)) return false;
    int vis = Rd<int>(occ + OFF_OCCLUSION_CURRENT);
    int nxt = Rd<int>(occ + OFF_OCCLUSION_NEXT);
    return (vis == 2 && nxt != 1);
}

static std::string ReadStr(uintptr_t s) {
    if (!s) return "";
    int len = Rd<int32_t>(s + 0x10);
    if (len <= 0 || len > 256) return "";
    std::string r; r.reserve(len);
    for (int i = 0; i < len; i++) {
        uint16_t c = Rd<uint16_t>(s + 0x14 + i*2);
        r.push_back(c < 128 ? (char)c : '?');
    }
    return r;
}

static uintptr_t FindPartByKlass(uintptr_t obj, uintptr_t klass) {
    // Amnesia findPart: obj+MFC_PARTS→rct, rct+PARTS_LIST→list, list+LIST_ITEMS→items
    uintptr_t rct  = Rp(obj  + MFC_PARTS);    if (!vp(rct))  return 0;
    uintptr_t list = Rp(rct  + PARTS_LIST);   if (!vp(list)) return 0;
    uintptr_t items= Rp(list + OFF_LIST_ITEMS);if (!vp(items))return 0;
    int32_t   size = Rd<int32_t>(list + OFF_LIST_SIZE); if (size<=0||size>128) return 0;
    for (int i=0;i<size;i++) {
        uintptr_t p = Rp(items + OFF_ARRAY_DATA + (uintptr_t)i*8);
        if (vp(p) && Rp(p)==klass) return p;
    }
    return 0;
}

static void UpdatePlayers() {
    g_Players.clear(); g_LocalPC = 0; g_LocalAim = 0;
    if (!vp(g_WorldObj)) ScanForWorld();
    uintptr_t world = GetPlayerManager();
    if (!vp(world)) return;

    // Walk njh → gat → gzx → collection → items[] (Amnesia EspEngine.refreshPlayers)
    uintptr_t reg   = Rp(world + NJH_REGISTRY);  if (!vp(reg))   return;
    uintptr_t store = Rp(reg   + GAT_STORE);      if (!vp(store)) return;
    uintptr_t coll  = Rp(store + GZX_OBJECTS);   if (!vp(coll))  return;
    uintptr_t items = Rp(coll  + COLL_ITEMS);     if (!vp(items)) return;
    int64_t   cnt   = Rd<int64_t>(coll + COLL_COUNT);
    if (cnt<=0||cnt>4096) return;

    uint8_t myTeam = 255;

    for (int64_t i=0; i<cnt && (int)g_Players.size()<64; i++) {
        uintptr_t pc = Rp(items + OFF_ARRAY_DATA + (uintptr_t)i*8);
        if (!vp(pc) || Rp(pc)!=g_AKEKlass) continue;
        // Find dwc (transform component) via parts list
        uintptr_t dwc = FindPartByKlass(pc, g_DWCKlass);
        if (!dwc) continue;
        PlayerEntry e{};
        e.pc      = pc;
        // Amnesia: MFC_LOCAL @ 0x44, team @ AKE_TEAM=0x90, stats @ AKE_STATS=0x70
        e.isLocal = Rd<uint8_t>(pc + MFC_LOCAL) != 0;
        e.team    = Rd<uint8_t>(pc + 0x90);  // AKE_TEAM confirmed Amnesia+Wolsaw
        e.visible = IsVisible(pc);
        // HP and armor from stats object (ylw)
        uintptr_t stats = Rp(pc + 0x70);  // AKE_STATS
        if (vp(stats)) {
            e.ammo    = Rd<uint16_t>(stats + 0x10);  // YLW_HP
            e.ammoMax = Rd<uint16_t>(stats + 0x14);  // YLW_MAXHP
        }
        // Name from photon player
        uintptr_t ph = Rp(pc + OFF_PLAYER_PHOTON_PTR);
        if (vp(ph)) {
            e.name = ReadStr(Rp(ph + OFF_PHOTON_NAME));
        }
        if (e.isLocal) myTeam = e.team;
        // Primary position: dwc transform A (foot level)
        // Confirmed: Amnesia DWC_TRANSFORM_A=0x28, DWC_TRANSFORM_B=0x30
        uintptr_t tr_a = Rp(dwc + 0x28);  // TransformA (foot)
        uintptr_t tr_b = Rp(dwc + 0x30);  // TransformB (alternate)
        Vec3 foot_pos = GetPos(tr_a ? tr_a : tr_b);
        // Head = foot + PLAYER_HEIGHT (Amnesia: 1.78f)
        Vec3 head_pos = {foot_pos.x, foot_pos.y + 1.78f, foot_pos.z};
        e.pos              = foot_pos;
        e.bones.head       = head_pos;
        e.bones.neck       = {foot_pos.x, foot_pos.y + 1.55f, foot_pos.z};
        e.bones.spine2     = {foot_pos.x, foot_pos.y + 1.35f, foot_pos.z};
        e.bones.spine1     = {foot_pos.x, foot_pos.y + 1.15f, foot_pos.z};
        e.bones.spine      = {foot_pos.x, foot_pos.y + 0.98f, foot_pos.z};
        e.bones.hip        = {foot_pos.x, foot_pos.y + 0.88f, foot_pos.z};
        // Arms/legs: approximate from hip (good for box ESP; bone detail needs jgi)
        e.bones.lShoulder  = {foot_pos.x-0.22f, foot_pos.y+1.35f, foot_pos.z};
        e.bones.rShoulder  = {foot_pos.x+0.22f, foot_pos.y+1.35f, foot_pos.z};
        e.bones.lUpperarm  = {foot_pos.x-0.30f, foot_pos.y+1.25f, foot_pos.z};
        e.bones.rUpperarm  = {foot_pos.x+0.30f, foot_pos.y+1.25f, foot_pos.z};
        e.bones.lElbow     = {foot_pos.x-0.38f, foot_pos.y+1.05f, foot_pos.z};
        e.bones.rElbow     = {foot_pos.x+0.38f, foot_pos.y+1.05f, foot_pos.z};
        e.bones.lHand      = {foot_pos.x-0.42f, foot_pos.y+0.85f, foot_pos.z};
        e.bones.rHand      = {foot_pos.x+0.42f, foot_pos.y+0.85f, foot_pos.z};
        e.bones.lUpLeg     = {foot_pos.x-0.12f, foot_pos.y+0.82f, foot_pos.z};
        e.bones.rUpLeg     = {foot_pos.x+0.12f, foot_pos.y+0.82f, foot_pos.z};
        e.bones.lKnee      = {foot_pos.x-0.12f, foot_pos.y+0.44f, foot_pos.z};
        e.bones.rKnee      = {foot_pos.x+0.12f, foot_pos.y+0.44f, foot_pos.z};
        e.bones.lFoot      = {foot_pos.x-0.10f, foot_pos.y+0.04f, foot_pos.z};
        e.bones.rFoot      = {foot_pos.x+0.10f, foot_pos.y+0.04f, foot_pos.z};
        uintptr_t wrc = Rp(pc + OFF_PLAYER_WEAPON_ROOT);
        uintptr_t wc  = vp(wrc) ? Rp(wrc + OFF_WRC_ACTIVE_WEAPON) : 0;
        if (vp(wc)) {
            e.ammo    = DecodeSI(wc + OFF_WC_AMMO_CURRENT);
            e.ammoMax = DecodeSI(wc + OFF_WC_AMMO_MAX);
        }
        uintptr_t ac = Rp(pc + OFF_PLAYER_AIM_CONTROLLER);
        uintptr_t ad = vp(ac) ? Rp(ac + OFF_AIM_CONTROLLER_DATA) : 0;
        if (vp(ad)) e.yawDeg = Rd<float>(ad + OFF_AIMDATA_YAW);
        g_Players.push_back(e);
    }
}

// ============================================================
// SECTION 11 — CONFIG
// ============================================================

namespace cfg {
    // ESP
    bool esp_enabled     = false;
    bool esp_box2d       = true;
    bool esp_box3d       = false;
    bool esp_box_fill    = true;
    bool esp_skeleton    = false;
    bool esp_name        = true;
    bool esp_health      = true;
    bool esp_armor       = false;
    bool esp_ammo        = false;
    bool esp_weapon      = false;
    bool esp_distance    = true;
    bool esp_snapline    = false;
    bool esp_offscreen   = false;
    bool esp_vis_only    = false;
    bool esp_team_check  = true;
    ImVec4 col_ct_vis    = {0.00f,0.55f,1.00f,0.9f};
    ImVec4 col_ct_occ    = {0.00f,0.22f,0.60f,0.5f};
    ImVec4 col_t_vis     = {1.00f,0.78f,0.00f,0.9f};
    ImVec4 col_t_occ     = {0.55f,0.30f,0.00f,0.5f};

    // Aimbot / Silent
    bool  aimbot         = false;
    bool  silent_aim     = false;
    float aim_fov        = 100.f;
    float aim_speed      = 0.15f;
    bool  aim_vis_only   = true;
    bool  aim_head       = true;

    // Triggerbot
    bool  triggerbot     = false;
    float trigger_delay  = 0.05f;
    float trigger_fov    = 40.f;

    // Anti-aim
    bool  anti_aim       = false;
    bool  anti_afk       = false;

    // Weapon
    bool  no_recoil      = false;
    bool  no_spread      = false;
    bool  inf_ammo       = false;
    bool  inf_mag        = false;
    bool  wallshot       = false;
    bool  rapid_fire     = false;

    // Movement
    bool  air_jump       = false;
    bool  bunny_hop      = false;
    bool  high_jump      = false;
    float hj_force       = 5.f;
    bool  air_strafe     = false;
    bool  noclip         = false;
    bool  crouch_speed   = false;
    bool  third_person   = false;
    float tp_dist        = 3.0f;

    // Visuals
    bool  chams_enemies  = false;
    bool  chams_allies   = false;
    bool  chams_local    = false;
    bool  chams_visible_only = false;
    bool  fast_knife     = false;
    bool  wide_fov       = false;
    float fov_value      = 90.f;
    bool  night_mode     = false;
    bool  fullbright     = false;
    bool  no_fog         = false;
    float fog_start      = 50.f;
    float fog_end        = 200.f;
    bool  custom_crosshair = false;
    float crosshair_size = 8.f;
    ImVec4 crosshair_col = {1.f,1.f,1.f,1.f};
    bool  hitmarker      = false;
    bool  bullet_tracer  = false;
    bool  hitlog         = false;
    bool  damage_indicator = false;

    // Skin changer
    bool     skin_enabled = false;
    uint32_t skin_id      = 0;
    int      skin_idx     = 0;

    // Backtrack
    bool  backtrack      = false;
    int   bt_ticks       = 12;
}

// ============================================================
// SECTION 12 — FEATURES: WEAPON
// ============================================================

static uintptr_t GetLocalWC() {
    if (!vp(g_LocalPC)) return 0;
    uintptr_t wrc = Rp(g_LocalPC + OFF_PLAYER_WEAPON_ROOT);
    return vp(wrc) ? Rp(wrc + OFF_WRC_ACTIVE_WEAPON) : 0;
}

static void F_NoRecoil() {
    uintptr_t wc = GetLocalWC(); if (!vp(wc)) return;
    Wr<float>(wc + OFF_WC_RECOIL_MULT,  0.f);
    Wr<float>(wc + OFF_WC_RECOIL_MULT2, 0.f);
    uintptr_t rc = Rp(wc + OFF_WC_RECOIL_CTRL);
    if (vp(rc)) {
        for (int i=0;i<6;i++) Wr<float>(rc + OFF_RC_RECOIL_0 + i*4, 0.f);
    }
    uintptr_t gp = Rp(wc + OFF_WC_GUN_PARAMS);
    if (vp(gp)) {
        uintptr_t rp = Rp(gp + OFF_GP_RECOIL_PARAMS);
        if (vp(rp)) { Wr<float>(rp+OFF_RP_HORIZONTAL,0.f); Wr<float>(rp+OFF_RP_VERTICAL,0.f); }
    }
}

static void F_NoSpread() {
    uintptr_t wc = GetLocalWC(); if (!vp(wc)) return;
    Wr<float>(wc + OFF_WC_ACCURACY_DATA + OFF_ACCDATA_ANGLE,  0.f);
    Wr<float>(wc + OFF_WC_ACCURACY_DATA + OFF_ACCDATA_RECOIL, 0.f);
}

static void F_InfAmmo() {
    uintptr_t wc = GetLocalWC(); if (!vp(wc)) return;
    int max = DecodeSI(wc + OFF_WC_AMMO_MAX);
    if (max <= 0) max = 30;
    EncodeSI(wc + OFF_WC_AMMO_CURRENT, max);
}

static void F_InfMag() {
    uintptr_t wc = GetLocalWC(); if (!vp(wc)) return;
    // Write max ammo directly (auto-reload bypass: keep current == max each frame)
    int max = DecodeSI(wc + OFF_WC_AMMO_MAX);
    if (max <= 0) max = 30;
    EncodeSI(wc + OFF_WC_AMMO_CURRENT, max);
    EncodeSI(wc + OFF_WC_AMMO_MAX, max);
}

static void F_Wallshot() {
    uintptr_t wc = GetLocalWC(); if (!vp(wc)) return;
    uintptr_t wp = Rp(wc + OFF_WC_WEAPON_PROPS);
    if (!vp(wp)) return;
    // Write max float as penetration (from normal6/offsets.hpp comment)
    Wr<uint32_t>(wp + OFF_WP_PENETRATION, 0x7F7FFFFFu);
}

static void F_RapidFire() {
    uintptr_t wc = GetLocalWC(); if (!vp(wc)) return;
    // Write fire button to simulate trigger (triggerbot-like, every frame)
    Wr<uint8_t>(wc + OFF_WC_FIRE_BUTTON, 1u);
}

static void F_FastKnife() {
    // Fast knife: write fire button on active weapon if weapon type is knife
    uintptr_t wc = GetLocalWC(); if (!vp(wc)) return;
    uintptr_t wp = Rp(wc + OFF_WC_WEAPON_PROPS);
    if (!vp(wp)) return;
    // weapon_id 0 = knife slot (approximate — check OFF_WP_WEAPON_ID)
    // Just pulse fire each frame; combine with no-spread for fast swing
    Wr<uint8_t>(wc + OFF_WC_FIRE_BUTTON, 1u);
}

// ============================================================
// SECTION 13 — FEATURES: AIMBOT / SILENT
// ============================================================

// zenin14 RotationState (from message.txt)
struct RotState {
    void*    transform = nullptr;
    Quat     rotation  = {};
    uint32_t depth     = 0;
};
static thread_local RotState g_RotState;

struct PendingFire {
    uint8_t ready = 0;
    float   pitch = 0.f, yaw = 0.f;
    bool Consume(float& op, float& oy) {
        if (ready != 1) return false;
        op = pitch; oy = yaw; ready = 0; return true;
    }
};
static thread_local PendingFire g_PendingFire;

// Shot detection
static float g_PrevFireDur = -1.f;
static bool  g_ShotFired   = false;

static void DetectShot() {
    g_ShotFired = false;
    uintptr_t wc = GetLocalWC(); if (!vp(wc)) return;
    float cur = DecodeSF(wc + OFF_WC_FIRE_DURATION);
    if (g_PrevFireDur >= 0.f && fabsf(cur - g_PrevFireDur) > 0.001f)
        g_ShotFired = true;
    g_PrevFireDur = cur;
}

// Aim target
struct AimTarget { bool valid=false; Vec3 head; float yaw=0,pitch=0; Quat quat; };
static AimTarget g_AimTgt;

static void UpdateAimTarget() {
    g_AimTgt.valid = false;
    if (!vp(g_LocalPC)) return;
    uint8_t myTeam = Rd<uint8_t>(g_LocalPC + OFF_PLAYER_TEAM);
    uintptr_t bm = GetBM(g_LocalPC);
    Vec3 myHead = vp(bm) ? BP(bm, OFF_BONE_HEAD_1) : Vec3{};
    uintptr_t ac = Rp(g_LocalPC + OFF_PLAYER_AIM_CONTROLLER);
    uintptr_t ad = vp(ac) ? Rp(ac + OFF_AIM_CONTROLLER_DATA) : 0;
    float myCurYaw=0, myCurPitch=0;
    if (vp(ad)) { myCurYaw=Rd<float>(ad+OFF_AIMDATA_YAW); myCurPitch=Rd<float>(ad+OFF_AIMDATA_PITCH); }

    float best = cfg::aim_fov;
    for (auto& p : g_Players) {
        if (p.isLocal) continue;
        if (cfg::esp_team_check && p.team == myTeam) continue;
        if (cfg::aim_vis_only && !p.visible) continue;
        float sx,sy;
        if (!W2S(p.bones.head, sx, sy)) continue;
        float dx=sx-g_SW*0.5f, dy=sy-g_SH*0.5f;
        float d=sqrtf(dx*dx+dy*dy);
        if (d >= best) continue;
        best = d;
        float oy,op;
        if (!CalculateAngles(myHead, p.bones.head,
                             myCurYaw, myCurPitch,
                             cfg::aim_speed, false, oy, op)) continue;
        g_AimTgt.head  = p.bones.head;
        g_AimTgt.yaw   = oy;
        g_AimTgt.pitch = op;
        g_AimTgt.quat  = FireQuaternion(oy, op);
        g_AimTgt.valid = true;
    }
}

static void F_Aimbot() {
    if (!vp(g_LocalPC) || !vp(g_LocalAim) || !g_AimTgt.valid) return;
    uintptr_t ad = Rp(g_LocalAim + OFF_AIM_CONTROLLER_DATA);
    if (!vp(ad)) return;
    Wr<float>(ad + OFF_AIMDATA_PITCH, g_AimTgt.pitch);
    Wr<float>(ad + OFF_AIMDATA_YAW,   g_AimTgt.yaw);
}

// Silent aim hook: intercepts Transform::get_rotation_Injected
// (confirmed Zenin: WeaponState::HookRotationInjected → same icall)
using RotInjFn = void(*)(void*, Quat*);
static RotInjFn   g_RotOrig      = nullptr;
static uintptr_t  g_RotAddr      = 0;
static uint8_t    g_RotOrigBytes[16];
static uint8_t    g_RotTrampoline[32];

static void HookedGetRotation(void* tr, Quat* out) {
    // Always call original first
    ((RotInjFn)g_RotTrampoline)(tr, out);
    if (!cfg::silent_aim || !g_AimTgt.valid || !g_ShotFired) return;
    // zenin14::ApplyRotationResult pattern (message.txt)
    const auto& state = g_RotState;
    if (state.depth != 0 && tr == state.transform) {
        *out = state.rotation;
    } else {
        *out = g_AimTgt.quat;
    }
}

static bool InstallSilentAim() {
    if (!il2cpp_resolve_icall) return false;
    void* fn = il2cpp_resolve_icall("UnityEngine.Transform::get_rotation_Injected");
    if (!fn) { LOGE("SilentAim: icall not resolved"); return false; }
    g_RotAddr = (uintptr_t)fn;
    memcpy(g_RotOrigBytes, fn, 16);

    // Build trampoline: [0..15]=original bytes, [16..31]=LDR X17,#8; BR X17; <jump_back>
    uintptr_t jb = g_RotAddr + 16;
    memcpy(g_RotTrampoline, g_RotOrigBytes, 16);
    uint32_t ldr=0x58000051u, br=0xD61F0220u;
    memcpy(g_RotTrampoline+16, &ldr, 4);
    memcpy(g_RotTrampoline+20, &br,  4);
    memcpy(g_RotTrampoline+24, &jb,  8);
    mprotect((void*)((uintptr_t)g_RotTrampoline&~0xFFFULL), 0x1000, PROT_READ|PROT_WRITE|PROT_EXEC);
    __builtin___clear_cache((char*)g_RotTrampoline, (char*)(g_RotTrampoline+32));

    mprotect((void*)(g_RotAddr&~0xFFFULL), 0x2000, PROT_READ|PROT_WRITE|PROT_EXEC);
    uintptr_t hook = (uintptr_t)HookedGetRotation;
    uint8_t patch[16];
    memcpy(patch+0, &ldr,  4); memcpy(patch+4, &br, 4); memcpy(patch+8, &hook, 8);
    memcpy((void*)g_RotAddr, patch, 16);
    __builtin___clear_cache((char*)g_RotAddr, (char*)(g_RotAddr+16));
    g_RotOrig = (RotInjFn)g_RotTrampoline;
    LOGI("SilentAim hook @ 0x%llX → 0x%llX", (unsigned long long)g_RotAddr, (unsigned long long)hook);
    return true;
}

// ============================================================
// SECTION 14 — TRIGGERBOT
// ============================================================

namespace trigger_state { static float timer=0.f; static bool pulsing=false; }

static void F_Triggerbot() {
    using namespace trigger_state;
    if (!vp(g_LocalPC)) { pulsing=false; timer=0.f; return; }
    uintptr_t wc = GetLocalWC(); if (!vp(wc)) return;
    uint8_t myTeam = Rd<uint8_t>(g_LocalPC + OFF_PLAYER_TEAM);

    bool can_fire = false;
    for (auto& p : g_Players) {
        if (p.isLocal || p.team == myTeam || !p.visible) continue;
        float sx,sy;
        if (!W2S(p.bones.head, sx, sy)) continue;
        float dx=sx-g_SW*0.5f, dy=sy-g_SH*0.5f;
        if (sqrtf(dx*dx+dy*dy) <= cfg::trigger_fov) { can_fire=true; break; }
    }

    constexpr float dt = 1.f/60.f;
    if (can_fire) {
        if (!pulsing) { timer = cfg::trigger_delay; pulsing = true; }
        if (timer <= 0.f) { Wr<uint8_t>(wc+OFF_WC_FIRE_BUTTON, 1u); timer=TRIGGER_SHOT_DURATION; }
        else timer -= dt;
    } else {
        if (pulsing) { Wr<uint8_t>(wc+OFF_WC_FIRE_BUTTON, 2u); pulsing=false; timer=0.f; }
    }
}

// ============================================================
// SECTION 15 — ANTI-AIM
// ============================================================

static void WriteQuat(uintptr_t tr, const Quat& q) {
    if (!vp(tr)) return;
    uintptr_t n = Rp(tr + OFF_TRANSFORM_NATIVE); if (!vp(n)) return;
    uintptr_t md = Rp(n + OFF_NATIVE_TRANSFORM_DATA); if (!vp(md)) return;
    int idx = Rd<int32_t>(n + OFF_NATIVE_TRANSFORM_INDEX);
    uintptr_t ml = Rp(md + OFF_TRANSFORM_DATA_ARRAY); if (!vp(ml)) return;
    uintptr_t ea = ml + (uintptr_t)(uint32_t)idx * sizeof(TMatrix);
    TMatrix tm = Rd<TMatrix>(ea);
    tm.rotation = q;
    Wr<TMatrix>(ea, tm);
}

static void F_AntiAim() {
    if (!vp(g_LocalPC)) return;
    uintptr_t ac = Rp(g_LocalPC + OFF_PLAYER_AIM_CONTROLLER); if (!vp(ac)) return;
    uintptr_t mc = Rp(ac + OFF_AA_MOV_CTRL); if (!vp(mc)) return;
    uintptr_t tr = Rp(mc + OFF_AA_MOV_TRANSFORM);
    uintptr_t ch = Rp(ac + OFF_AA_CHARACTER);
    for (int i = 0; i < 4; i++) {
        Quat dq = DegeneratQuat();
        WriteQuat(tr, dq);
        WriteQuat(ch, dq);
    }
}

static void F_AntiAFK() {
    if (!vp(g_LocalPC)) return;
    uintptr_t pp = Rp(g_LocalPC + 0x138);
    if (vp(pp)) Wr<bool>(pp + 0x31, false);
}

// ============================================================
// SECTION 16 — MOVEMENT
// ============================================================

static uintptr_t GetJumpParams() {
    if (!vp(g_LocalPC)) return 0;
    uintptr_t mc = Rp(g_LocalPC + OFF_PLAYER_MOVEMENT_CTRL); if (!vp(mc)) return 0;
    uintptr_t tp = Rp(mc + OFF_MC_TRAJECTORY); if (!vp(tp)) return 0;
    return Rp(tp + OFF_TP_JUMP_PARAMS);
}

static void F_AirJump()   { uintptr_t jp=GetJumpParams(); if(vp(jp)) Wr<uint32_t>(jp+OFF_JP_JUMP_SPEED, 5u); }
static void F_BunnyHop()  { uintptr_t jp=GetJumpParams(); if(vp(jp)) { Wr<uint32_t>(jp+OFF_JP_JUMP_SPEED,1081674666u); Wr<uint32_t>(jp+OFF_JP_JUMP_SPEED2,1081674666u); } }
static void F_HighJump()  {
    uintptr_t jp=GetJumpParams(); if(!vp(jp)) return;
    uint32_t b; float f=cfg::hj_force; memcpy(&b,&f,4);
    Wr<uint32_t>(jp+OFF_JP_JUMP_SPEED,b); Wr<uint32_t>(jp+OFF_JP_JUMP_SPEED2,b);
}
static void F_CrouchSpeed() {
    if (!vp(g_LocalPC)) return;
    uintptr_t mc = Rp(g_LocalPC+OFF_PLAYER_MOVEMENT_CTRL); if (!vp(mc)) return;
    uintptr_t tp = Rp(mc+OFF_MC_TRAJECTORY); if (!vp(tp)) return;
    uintptr_t cp = Rp(tp+OFF_TP_CROUCH_PARAMS); if (!vp(cp)) return;
    Wr<float>(cp+OFF_CP_SPEED_MULT, 990.f); Wr<float>(cp+OFF_CP_SPEED_MULT2, 990.f);
}

// Third-person: move PlayerMainCamera transform back behind player
static void F_ThirdPerson() {
    if (!vp(g_LocalPC)) return;
    // Adjust camera FOV offset as cheap third person approximation
    // Full implementation needs Camera position write + smooth follow
    uintptr_t pmc = Rp(g_LocalPC + OFF_PLAYER_MAIN_CAMERA); if (!vp(pmc)) return;
    uintptr_t cam = Rp(pmc + 0x20); if (!vp(cam)) return;
    if (icall_set_fov) icall_set_fov((void*)cam, cfg::fov_value + cfg::tp_dist * 3.f);
}

// Wide FOV
static void F_WideFOV() {
    if (!vp(g_LocalPC)) return;
    uintptr_t pmc = Rp(g_LocalPC + OFF_PLAYER_MAIN_CAMERA); if (!vp(pmc)) return;
    uintptr_t cam = Rp(pmc + 0x20); if (!vp(cam)) return;
    if (icall_set_fov) icall_set_fov((void*)cam, cfg::fov_value);
}

// ============================================================
// SECTION 17 — GFX (Night Mode, Fullbright, Fog)
// ============================================================

// Unity method pointers from libunity.so
using FnSetFog       = void(*)(bool, const void*);
using FnSetFogColor  = void(*)(Color4, const void*);
using FnSetAmbLight  = void(*)(Color4, const void*);
using FnSetAmbInt    = void(*)(float, const void*);
using FnLightSetInt  = void(*)(void*, float, const void*);

static FnSetFog      fn_SetFog     = nullptr;
static FnSetFogColor fn_SetFogClr  = nullptr;
static FnSetAmbLight fn_SetAmbLt   = nullptr;
static FnSetAmbInt   fn_SetAmbInt  = nullptr;

static void InitUnityGFX() {
    if (!g_UnityBase) return;
#define RU(p,rva) p = reinterpret_cast<decltype(p)>(g_UnityBase+(rva))
    RU(fn_SetFog,   RVA_RENDERSETTINGS_SET_FOG);
    RU(fn_SetFogClr,RVA_RENDERSETTINGS_SET_FOG_COLOR);
    RU(fn_SetAmbLt, RVA_RENDERSETTINGS_SET_AMB);
    RU(fn_SetAmbInt,RVA_RENDERSETTINGS_SET_AMB_INTENSITY);
#undef RU
}

static void F_NightMode() {
    if (!fn_SetAmbLt) return;
    Color4 dark{0.02f,0.02f,0.05f,1.f};
    fn_SetAmbLt(dark, nullptr);
    if (fn_SetAmbInt) fn_SetAmbInt(0.05f, nullptr);
}

static void F_Fullbright() {
    if (!fn_SetAmbLt) return;
    Color4 bright{1.f,1.f,1.f,1.f};
    fn_SetAmbLt(bright, nullptr);
    if (fn_SetAmbInt) fn_SetAmbInt(3.f, nullptr);
}

static void F_NoFog() {
    if (fn_SetFog) fn_SetFog(false, nullptr);
}

// ============================================================
// SECTION 18 — BACKTRACK
// ============================================================

struct BacktrackRecord {
    Vec3    head;
    int64_t time_ns;
};
static constexpr int BT_MAX_TICKS = 24;
struct BTHistory {
    std::array<BacktrackRecord, BT_MAX_TICKS> records;
    int head_idx = 0;
};
static std::array<BTHistory, 64> g_BT;
static int64_t NowNS() {
    struct timespec ts; clock_gettime(CLOCK_MONOTONIC, &ts);
    return (int64_t)ts.tv_sec*1000000000LL + ts.tv_nsec;
}

static void BT_Record() {
    int64_t now = NowNS();
    for (int i = 0; i < (int)g_Players.size() && i < 64; i++) {
        auto& h = g_BT[i];
        h.records[h.head_idx] = {g_Players[i].bones.head, now};
        h.head_idx = (h.head_idx + 1) % BT_MAX_TICKS;
    }
}

static Vec3 BT_BestPos(int player_idx) {
    if (player_idx < 0 || player_idx >= 64) return {};
    auto& h = g_BT[player_idx];
    int64_t now = NowNS();
    int64_t target_ns = (int64_t)cfg::bt_ticks * 16666667LL;
    int best = -1; int64_t best_diff = INT64_MAX;
    for (int i = 0; i < BT_MAX_TICKS; i++) {
        if (h.records[i].time_ns == 0) continue;
        int64_t diff = llabs((now - h.records[i].time_ns) - target_ns);
        if (diff < best_diff) { best_diff = diff; best = i; }
    }
    return best >= 0 ? h.records[best].head : Vec3{};
}

// ============================================================
// SECTION 19 — HIT LOG / MARKERS
// ============================================================

struct HitEvent { std::string name; int damage; float time; float sx, sy; };
static std::vector<HitEvent> g_HitLog;
static std::mutex g_HitMtx;
static float g_HitMarkerTimer = 0.f;

static void PushHitEvent(const std::string& name, int dmg, float sx, float sy) {
    std::lock_guard<std::mutex> lk(g_HitMtx);
    float t = (float)ImGui::GetTime();
    g_HitLog.push_back({name, dmg, t, sx, sy});
    g_HitMarkerTimer = 0.15f;
    if ((int)g_HitLog.size() > 20) g_HitLog.erase(g_HitLog.begin());
}

static void DrawHitLog(ImDrawList* dl) {
    if (!cfg::hitlog) return;
    std::lock_guard<std::mutex> lk(g_HitMtx);
    float now = (float)ImGui::GetTime();
    float y = g_SH * 0.5f - 40.f;
    for (auto it = g_HitLog.rbegin(); it != g_HitLog.rend(); ++it) {
        float age = now - it->time;
        if (age > 5.f) continue;
        float alpha = std::min(1.f, 2.f*(5.f-age));
        char buf[64]; snprintf(buf,sizeof(buf),"[HIT] %s -%d", it->name.c_str(), it->damage);
        ImU32 col = IM_COL32(255,80,80,(int)(255*alpha));
        dl->AddText(ImVec2(g_SW-200.f, y), col, buf);
        y -= 14.f;
    }
}

static void DrawHitMarker(ImDrawList* dl) {
    if (!cfg::hitmarker || g_HitMarkerTimer <= 0.f) return;
    float cx=g_SW*0.5f, cy=g_SH*0.5f, s=8.f, t=1.5f;
    ImU32 col = IM_COL32(255,50,50,(int)(255*std::min(1.f,g_HitMarkerTimer/0.1f)));
    dl->AddLine({cx-s,cy-s},{cx+s,cy+s}, col, t);
    dl->AddLine({cx+s,cy-s},{cx-s,cy+s}, col, t);
    g_HitMarkerTimer -= 1.f/60.f;
}

// ============================================================
// SECTION 20 — ESP DRAW
// ============================================================

static ImColor GetCol(const PlayerEntry& p) {
    ImVec4 c = (p.team==0)
        ? (p.visible ? cfg::col_ct_vis : cfg::col_ct_occ)
        : (p.visible ? cfg::col_t_vis  : cfg::col_t_occ);
    return ImColor(c);
}

static void DrawLine2(ImDrawList* dl, const Vec3& a, const Vec3& b, ImColor col, float w=1.5f) {
    float ax,ay,bx,by;
    if (W2S(a,ax,ay) && W2S(b,bx,by)) dl->AddLine({ax,ay},{bx,by},col,w);
}

static void DrawSkeleton(ImDrawList* dl, const PlayerEntry& p, ImColor col) {
    const auto& b = p.bones;
    const float ks=2.f, kb=1.5f;
    DrawLine2(dl,b.head,  b.neck,   col,ks);
    DrawLine2(dl,b.neck,  b.spine2, col,ks);
    DrawLine2(dl,b.spine2,b.spine1, col,ks);
    DrawLine2(dl,b.spine1,b.spine,  col,ks);
    DrawLine2(dl,b.spine, b.hip,    col,ks);
    DrawLine2(dl,b.spine2,b.lShoulder,col,kb); DrawLine2(dl,b.lShoulder,b.lUpperarm,col,kb);
    DrawLine2(dl,b.lUpperarm,b.lElbow,col,kb); DrawLine2(dl,b.lElbow,b.lHand,col,kb);
    DrawLine2(dl,b.spine2,b.rShoulder,col,kb); DrawLine2(dl,b.rShoulder,b.rUpperarm,col,kb);
    DrawLine2(dl,b.rUpperarm,b.rElbow,col,kb); DrawLine2(dl,b.rElbow,b.rHand,col,kb);
    DrawLine2(dl,b.hip,b.lUpLeg,col,kb); DrawLine2(dl,b.lUpLeg,b.lKnee,col,kb); DrawLine2(dl,b.lKnee,b.lFoot,col,kb);
    DrawLine2(dl,b.hip,b.rUpLeg,col,kb); DrawLine2(dl,b.rUpLeg,b.rKnee,col,kb); DrawLine2(dl,b.rKnee,b.rFoot,col,kb);
    DrawLine2(dl,b.lShoulder,b.rShoulder,col,kb);
    DrawLine2(dl,b.lUpLeg,b.rUpLeg,col,kb);
    float hx,hy; if(W2S(b.head,hx,hy)) dl->AddCircle({hx,hy},5.5f,col,12,1.5f);
}

static void DrawBox3D(ImDrawList* dl, const PlayerEntry& p, ImColor edge, float fill_a) {
    constexpr float hw=0.30f, hd=0.22f;
    float foot_y = p.bones.lFoot.y, head_y = p.bones.head.y;
    float height = head_y - foot_y;
    if (height < 0.5f || height > 3.5f) { foot_y = p.pos.y - 0.88f; height = 1.80f; }
    height += 0.06f;
    float yr = p.yawDeg * (3.14159265f/180.f);
    float cy = cosf(yr), sy = sinf(yr);
    float rx[4]={ cy*hw+sy*hd, -cy*hw+sy*hd, -cy*hw-sy*hd,  cy*hw-sy*hd};
    float rz[4]={-sy*hw+cy*hd,  sy*hw+cy*hd,  sy*hw-cy*hd, -sy*hw-cy*hd};
    Vec3 base{p.pos.x, foot_y, p.pos.z};
    Vec3 b[4], t[4];
    for(int i=0;i<4;i++){b[i]={base.x+rx[i],base.y,base.z+rz[i]}; t[i]={base.x+rx[i],base.y+height,base.z+rz[i]};}
    for(int i=0;i<4;i++) DrawLine2(dl,b[i],t[i],edge,1.6f);
    for(int i=0;i<4;i++){DrawLine2(dl,b[i],b[(i+1)%4],edge,1.2f); DrawLine2(dl,t[i],t[(i+1)%4],edge,1.2f);}
}

// Off-screen arrow indicator
static void DrawOffscreen(ImDrawList* dl, const PlayerEntry& p, ImColor col) {
    float sx,sy;
    if (W2S(p.pos,sx,sy) && sx>=0&&sx<g_SW&&sy>=0&&sy<g_SH) return;
    float cx=g_SW*0.5f, cy=g_SH*0.5f;
    float dx=p.pos.x-cx, dy=p.pos.y-cy;  // approx
    // Use raw screen projection delta
    float ang=atan2f(sy-cy, sx-cx);
    float margin=40.f;
    float ax=cx+cosf(ang)*(g_SW*0.5f-margin);
    float ay=cy+sinf(ang)*(g_SH*0.5f-margin);
    // Arrow triangle
    float ar=10.f;
    ImVec2 p0{ax+cosf(ang)*ar, ay+sinf(ang)*ar};
    ImVec2 p1{ax+cosf(ang+2.4f)*ar*0.6f, ay+sinf(ang+2.4f)*ar*0.6f};
    ImVec2 p2{ax+cosf(ang-2.4f)*ar*0.6f, ay+sinf(ang-2.4f)*ar*0.6f};
    dl->AddTriangleFilled(p0,p1,p2,col);
}

// Custom crosshair
static void DrawCrosshair(ImDrawList* dl) {
    if (!cfg::custom_crosshair) return;
    float cx=g_SW*0.5f, cy=g_SH*0.5f, s=cfg::crosshair_size;
    ImU32 col = ImGui::ColorConvertFloat4ToU32(cfg::crosshair_col);
    float gap=3.f;
    dl->AddLine({cx-s,cy},{cx-gap,cy},col,1.5f);
    dl->AddLine({cx+gap,cy},{cx+s,cy},col,1.5f);
    dl->AddLine({cx,cy-s},{cx,cy-gap},col,1.5f);
    dl->AddLine({cx,cy+gap},{cx,cy+s},col,1.5f);
    dl->AddCircle({cx,cy},2.f,col,8,1.5f);
}

// Health bar
static void DrawHealthBar(ImDrawList* dl, float x1,float y1,float x2,float y2, int hp) {
    float h=fabsf(y2-y1); if(h<5.f) return;
    float bx=x1-7.f, bw=4.f;
    float fill=std::clamp((float)hp/100.f,0.f,1.f);
    ImU32 bg=IM_COL32(0,0,0,160);
    ImU32 fg=hp>60?IM_COL32(50,230,50,220):hp>30?IM_COL32(230,200,0,220):IM_COL32(230,50,50,220);
    dl->AddRectFilled({bx,y1},{bx+bw,y2},bg);
    dl->AddRectFilled({bx,y2-h*fill},{bx+bw,y2},fg);
    dl->AddRect({bx,y1},{bx+bw,y2},IM_COL32(0,0,0,255),0.f,0,0.5f);
}

static void DrawESP() {
    if (!cfg::esp_enabled) return;
    ImDrawList* dl = ImGui::GetBackgroundDrawList();
    uint8_t myTeam = g_LocalPC ? Rd<uint8_t>(g_LocalPC+OFF_PLAYER_TEAM) : 255;
    Vec3 myPos{};
    if (vp(g_LocalPC)) {
        uintptr_t bm = GetBM(g_LocalPC);
        if (vp(bm)) myPos = BP(bm, OFF_BONE_HIP);
    }
    for (auto& p : g_Players) {
        if (p.isLocal) continue;
        if (cfg::esp_team_check && p.team == myTeam) continue;
        if (cfg::esp_vis_only && !p.visible) continue;
        ImColor col = GetCol(p);
        if (cfg::esp_offscreen) DrawOffscreen(dl, p, col);
        float hx,hy;
        if (!W2S(p.bones.head,hx,hy)) continue;
        float fx,fy;
        const Vec3& foot = vp((uintptr_t)p.bones.lFoot.x) ? p.bones.lFoot : p.pos;
        bool fok = W2S(p.bones.lFoot, fx, fy);
        if (!fok) W2S(p.pos, fx, fy);
        float height=fabsf(fy-hy), width=height*0.45f;
        float bx=hx-width*0.5f;
        if (cfg::esp_box2d && height>4.f)
            dl->AddRect({bx,hy},{bx+width,hy+height},col,2.f,0,1.8f);
        if (cfg::esp_box3d) DrawBox3D(dl, p, col, 0.08f);
        if (cfg::esp_skeleton) DrawSkeleton(dl, p, col);
        if (cfg::esp_health && height>4.f) DrawHealthBar(dl, bx, hy, bx+width, hy+height, 100);
        if (cfg::esp_name && !p.name.empty()) {
            ImVec2 ts=ImGui::CalcTextSize(p.name.c_str());
            dl->AddText({hx-ts.x*0.5f,hy-15.f},col,p.name.c_str());
        }
        if (cfg::esp_ammo) {
            char ab[16]; snprintf(ab,sizeof(ab),"%d/%d",p.ammo,p.ammoMax);
            dl->AddText({hx,hy+height+2.f},IM_COL32(255,255,255,200),ab);
        }
        if (cfg::esp_distance) {
            float d = VDist3D(p.pos, myPos);
            char db[16]; snprintf(db,sizeof(db),"%.0fm",d);
            ImVec2 ds=ImGui::CalcTextSize(db);
            dl->AddText({fx-ds.x*0.5f,fy+2.f},col,db);
        }
        if (cfg::esp_snapline) {
            float midx=(bx+bx+width)*0.5f;
            dl->AddLine({g_SW*0.5f,g_SH},{midx,hy+height},col,1.f);
        }
        // Aim FOV circle (always visible when aimbot active)
    }
    // FOV circle
    if (cfg::aimbot || cfg::silent_aim) {
        float r = cfg::aim_fov;
        dl->AddCircle({g_SW*0.5f,g_SH*0.5f},r,IM_COL32(255,255,255,80),64,1.f);
    }
    DrawCrosshair(dl);
    DrawHitMarker(dl);
    DrawHitLog(dl);
}

// ============================================================
// SECTION 21 — MENU
// ============================================================

static bool g_MenuOpen = false;

static void RenderMenu() {
    // Toggle button (small)
    ImGui::SetNextWindowPos({4.f,4.f});
    ImGui::SetNextWindowSize({40.f,24.f});
    ImGui::SetNextWindowBgAlpha(0.55f);
    ImGui::Begin("##tog",nullptr,ImGuiWindowFlags_NoTitleBar|ImGuiWindowFlags_NoResize|
                 ImGuiWindowFlags_NoScrollbar|ImGuiWindowFlags_NoSavedSettings);
    if (ImGui::Button(g_MenuOpen?"X":"M")) g_MenuOpen=!g_MenuOpen;
    ImGui::End();

    if (!g_MenuOpen) return;
    ImGui::SetNextWindowSize({400.f,600.f},ImGuiCond_Once);
    ImGui::SetNextWindowPos({50.f,30.f},ImGuiCond_Once);
    ImGui::Begin("hwidoholy | SO2 v3",nullptr,ImGuiWindowFlags_NoCollapse);

    if (ImGui::BeginTabBar("##t")) {
        // ── ESP ─────────────────────────────────────────────
        if (ImGui::BeginTabItem("ESP")) {
            ImGui::Checkbox("Enable",          &cfg::esp_enabled);
            ImGui::Checkbox("Team Filter",     &cfg::esp_team_check);
            ImGui::Checkbox("Visible Only",    &cfg::esp_vis_only);
            ImGui::Separator();
            ImGui::Checkbox("2D Box",          &cfg::esp_box2d);
            ImGui::Checkbox("3D Box",          &cfg::esp_box3d);
            ImGui::Checkbox("Skeleton",        &cfg::esp_skeleton);
            ImGui::Checkbox("Name",            &cfg::esp_name);
            ImGui::Checkbox("Health",          &cfg::esp_health);
            ImGui::Checkbox("Ammo",            &cfg::esp_ammo);
            ImGui::Checkbox("Distance",        &cfg::esp_distance);
            ImGui::Checkbox("Snapline",        &cfg::esp_snapline);
            ImGui::Checkbox("Offscreen",       &cfg::esp_offscreen);
            ImGui::Separator();
            ImGui::TextUnformatted("CT vis"); ImGui::SameLine();
            ImGui::ColorEdit4("##ctv",&cfg::col_ct_vis.x,ImGuiColorEditFlags_NoInputs|ImGuiColorEditFlags_NoLabel);
            ImGui::SameLine(); ImGui::TextUnformatted("occ"); ImGui::SameLine();
            ImGui::ColorEdit4("##ctiv",&cfg::col_ct_occ.x,ImGuiColorEditFlags_NoInputs|ImGuiColorEditFlags_NoLabel);
            ImGui::TextUnformatted("T  vis"); ImGui::SameLine();
            ImGui::ColorEdit4("##tv",&cfg::col_t_vis.x,ImGuiColorEditFlags_NoInputs|ImGuiColorEditFlags_NoLabel);
            ImGui::SameLine(); ImGui::TextUnformatted("occ"); ImGui::SameLine();
            ImGui::ColorEdit4("##tiv",&cfg::col_t_occ.x,ImGuiColorEditFlags_NoInputs|ImGuiColorEditFlags_NoLabel);
            ImGui::EndTabItem();
        }
        // ── Aim ─────────────────────────────────────────────
        if (ImGui::BeginTabItem("Aim")) {
            if(ImGui::RadioButton("Off",    !cfg::aimbot&&!cfg::silent_aim)){cfg::aimbot=false;cfg::silent_aim=false;}
            ImGui::SameLine();
            if(ImGui::RadioButton("Smooth", cfg::aimbot&&!cfg::silent_aim)){cfg::aimbot=true;cfg::silent_aim=false;}
            ImGui::SameLine();
            if(ImGui::RadioButton("Silent", cfg::silent_aim)){cfg::silent_aim=true;cfg::aimbot=false;
                if(!g_RotAddr) InstallSilentAim();}
            ImGui::SliderFloat("FOV (px)",  &cfg::aim_fov,  10.f, 400.f);
            ImGui::SliderFloat("Speed",     &cfg::aim_speed, 0.02f, 1.f);
            ImGui::Checkbox("Vis Only##a",  &cfg::aim_vis_only);
            ImGui::Separator();
            ImGui::Checkbox("Triggerbot",   &cfg::triggerbot);
            ImGui::SliderFloat("Trig FOV",  &cfg::trigger_fov, 5.f, 150.f);
            ImGui::SliderFloat("Trig Delay",&cfg::trigger_delay, 0.f, 0.2f);
            ImGui::Separator();
            ImGui::Checkbox("Anti-Aim",     &cfg::anti_aim);
            ImGui::Checkbox("Anti-AFK",     &cfg::anti_afk);
            ImGui::Separator();
            ImGui::Checkbox("Backtrack",    &cfg::backtrack);
            ImGui::SliderInt("BT Ticks",    &cfg::bt_ticks, 1, BT_MAX_TICKS);
            ImGui::Separator();
            // Status
            ImGui::TextColored(g_RotAddr?ImVec4(.2f,1.f,.2f,1.f):ImVec4(1.f,.3f,.3f,1.f),
                "Silent hook: %s", g_RotAddr?"INSTALLED":"NOT INSTALLED");
            ImGui::TextColored(g_ShotFired?ImVec4(1.f,.8f,0.f,1.f):ImVec4(.5f,.5f,.5f,1.f),
                "Shot: %s", g_ShotFired?"FIRED":"idle");
            ImGui::Text("Target: %s", g_AimTgt.valid?"LOCKED":"none");
            ImGui::EndTabItem();
        }
        // ── Weapon ──────────────────────────────────────────
        if (ImGui::BeginTabItem("Weapon")) {
            ImGui::Checkbox("No Recoil",    &cfg::no_recoil);
            ImGui::Checkbox("No Spread",    &cfg::no_spread);
            ImGui::Checkbox("Inf Ammo",     &cfg::inf_ammo);
            ImGui::Checkbox("Inf Mag",      &cfg::inf_mag);
            ImGui::Checkbox("Wallshot",     &cfg::wallshot);
            ImGui::Checkbox("Rapid Fire",   &cfg::rapid_fire);
            ImGui::Checkbox("Fast Knife",   &cfg::fast_knife);
            ImGui::Separator();
            // Live ammo display
            uintptr_t wc=GetLocalWC();
            if(vp(wc)) {
                ImGui::Text("Ammo: %d / %d", DecodeSI(wc+OFF_WC_AMMO_CURRENT), DecodeSI(wc+OFF_WC_AMMO_MAX));
                ImGui::Text("RecoilMult: %.3f", Rd<float>(wc+OFF_WC_RECOIL_MULT));
            }
            ImGui::EndTabItem();
        }
        // ── Movement ─────────────────────────────────────────
        if (ImGui::BeginTabItem("Move")) {
            ImGui::Checkbox("Air Jump",     &cfg::air_jump);
            ImGui::Checkbox("Bunny Hop",    &cfg::bunny_hop);
            ImGui::Checkbox("High Jump",    &cfg::high_jump);
            ImGui::SliderFloat("HJ Force",  &cfg::hj_force, 1.f, 30.f);
            ImGui::Checkbox("Crouch Speed", &cfg::crouch_speed);
            ImGui::Checkbox("Noclip",       &cfg::noclip);
            ImGui::Separator();
            ImGui::Checkbox("Third Person", &cfg::third_person);
            ImGui::SliderFloat("TP Dist",   &cfg::tp_dist, 1.f, 8.f);
            ImGui::EndTabItem();
        }
        // ── Visuals ──────────────────────────────────────────
        if (ImGui::BeginTabItem("Visual")) {
            ImGui::Checkbox("Chams Enemies",&cfg::chams_enemies);
            ImGui::Checkbox("Chams Allies", &cfg::chams_allies);
            ImGui::Checkbox("Chams Local",  &cfg::chams_local);
            ImGui::Checkbox("Vis Only##ch", &cfg::chams_visible_only);
            ImGui::Separator();
            ImGui::Checkbox("Wide FOV",     &cfg::wide_fov);
            ImGui::SliderFloat("FOV Value", &cfg::fov_value, 60.f, 150.f);
            ImGui::Checkbox("Night Mode",   &cfg::night_mode);
            ImGui::Checkbox("Fullbright",   &cfg::fullbright);
            ImGui::Checkbox("No Fog",       &cfg::no_fog);
            ImGui::Separator();
            ImGui::Checkbox("Custom Xhair", &cfg::custom_crosshair);
            ImGui::SliderFloat("Xhair Size",&cfg::crosshair_size, 3.f, 25.f);
            ImGui::ColorEdit4("Xhair Col",  &cfg::crosshair_col.x, ImGuiColorEditFlags_NoInputs);
            ImGui::Separator();
            ImGui::Checkbox("Hit Marker",   &cfg::hitmarker);
            ImGui::Checkbox("Hit Log",      &cfg::hitlog);
            ImGui::Checkbox("Dmg Indicator",&cfg::damage_indicator);
            ImGui::Checkbox("Bullet Tracer",&cfg::bullet_tracer);
            ImGui::EndTabItem();
        }
        // ── Info ─────────────────────────────────────────────
        if (ImGui::BeginTabItem("Info")) {
            ImGui::Text("gamex64 @ 0x%llX", (unsigned long long)g_Base);
            ImGui::Text("unity   @ 0x%llX", (unsigned long long)g_UnityBase);
            ImGui::Text("LocalPC  @ 0x%llX",(unsigned long long)g_LocalPC);
            ImGui::Text("Players: %d",      (int)g_Players.size());
            ImGui::Text("Screen:  %.0fx%.0f",g_SW, g_SH);
            ImGui::Separator();
            ImGui::Text("icall_pos:  %s", icall_get_pos    ?"OK":"FAIL");
            ImGui::Text("icall_wv:   %s", icall_get_wv     ?"OK":"FAIL");
            ImGui::Text("icall_proj: %s", icall_get_proj   ?"OK":"FAIL");
            ImGui::Text("icall_fov:  %s", icall_set_fov    ?"OK":"FAIL");
            ImGui::Text("gfx_fog:    %s", fn_SetFog        ?"OK":"FAIL");
            ImGui::Text("gfx_amb:    %s", fn_SetAmbLt      ?"OK":"FAIL");
            ImGui::EndTabItem();
        }
        ImGui::EndTabBar();
    }
    ImGui::End();
}

// ============================================================
// SECTION 22 — EGL HOOK
// ============================================================

using EglSwapFn = EGLBoolean(*)(EGLDisplay,EGLSurface);
static EglSwapFn g_OrigSwap  = nullptr;
static bool      g_ImGuiReady = false;

static EGLBoolean HookedSwap(EGLDisplay dpy, EGLSurface surf) {
    if (!g_ImGuiReady) {
        EGLint w=0,h=0;
        eglQuerySurface(dpy,surf,EGL_WIDTH,&w);
        eglQuerySurface(dpy,surf,EGL_HEIGHT,&h);
        if(w>0)g_SW=(float)w; if(h>0)g_SH=(float)h;
        IMGUI_CHECKVERSION();
        ImGui::CreateContext();
        ImGuiIO& io=ImGui::GetIO();
        io.DisplaySize={g_SW,g_SH}; io.IniFilename=nullptr;
        io.FontGlobalScale=g_SH/1080.f;
        ImGui::StyleColorsDark();
        ImGui_ImplOpenGL3_Init("#version 100");
        if (!icall_get_pos) InitICalls();
        if (!fn_SetFog)     InitUnityGFX();
        if (cfg::silent_aim && !g_RotAddr) InstallSilentAim();
        g_ImGuiReady = true;
        LOGI("ImGui ready %.0fx%.0f", g_SW, g_SH);
    }

    // ── Per-frame update ──────────────────────────────────
    UpdatePlayers();
    DetectShot();

    // ── Aim target ───────────────────────────────────────
    bool any_aim = cfg::aimbot || cfg::silent_aim || cfg::triggerbot;
    if (any_aim) UpdateAimTarget();

    // ── Features ─────────────────────────────────────────
    if (cfg::no_recoil)  F_NoRecoil();
    if (cfg::no_spread)  F_NoSpread();
    if (cfg::inf_ammo)   F_InfAmmo();
    if (cfg::inf_mag)    F_InfMag();
    if (cfg::wallshot)   F_Wallshot();
    if (cfg::rapid_fire) F_RapidFire();
    if (cfg::fast_knife) F_FastKnife();
    if (cfg::wide_fov)   F_WideFOV();
    if (cfg::third_person) F_ThirdPerson();
    if (cfg::aimbot && !cfg::silent_aim) F_Aimbot();
    if (cfg::triggerbot) F_Triggerbot();
    if (cfg::anti_aim)   F_AntiAim();
    if (cfg::anti_afk)   F_AntiAFK();
    if (cfg::air_jump)   F_AirJump();
    if (cfg::bunny_hop)  F_BunnyHop();
    if (cfg::high_jump)  F_HighJump();
    if (cfg::crouch_speed) F_CrouchSpeed();
    if (cfg::backtrack)  BT_Record();
    if (cfg::night_mode) F_NightMode();
    if (cfg::fullbright) F_Fullbright();
    if (cfg::no_fog)     F_NoFog();

    // ── Render ───────────────────────────────────────────
    ImGui_ImplOpenGL3_NewFrame();
    ImGui::NewFrame();

    // ESP overlay
    ImGui::SetNextWindowPos({0,0});
    ImGui::SetNextWindowSize({g_SW,g_SH});
    ImGui::SetNextWindowBgAlpha(0.f);
    ImGui::Begin("##ov",nullptr,
        ImGuiWindowFlags_NoTitleBar|ImGuiWindowFlags_NoInputs|
        ImGuiWindowFlags_NoMove|ImGuiWindowFlags_NoScrollbar|
        ImGuiWindowFlags_NoSavedSettings|ImGuiWindowFlags_NoBackground);
    DrawESP();
    ImGui::End();

    RenderMenu();
    ImGui::Render();
    ImGui_ImplOpenGL3_RenderDrawData(ImGui::GetDrawData());

    return g_OrigSwap(dpy, surf);
}

static bool HookEGL() {
    void* egl = dlopen("libEGL.so", RTLD_NOW|RTLD_NOLOAD);
    if (!egl) egl = dlopen("libEGL.so", RTLD_NOW);
    if (!egl) { LOGE("dlopen libEGL: %s", dlerror()); return false; }
    auto* target = (uint8_t*)dlsym(egl, "eglSwapBuffers");
    if (!target) { dlclose(egl); return false; }
    g_OrigSwap = (EglSwapFn)target;
    uintptr_t page = (uintptr_t)target & ~0xFFFULL;
    mprotect((void*)page, 0x3000, PROT_READ|PROT_WRITE|PROT_EXEC);
    uint32_t ldr=0x58000051u, br=0xD61F0220u;
    uintptr_t hook=(uintptr_t)HookedSwap;
    uint8_t patch[16];
    memcpy(patch+0,&ldr,4); memcpy(patch+4,&br,4); memcpy(patch+8,&hook,8);
    memcpy(target, patch, 16);
    __builtin___clear_cache((char*)target,(char*)(target+16));
    LOGI("EGL hooked @ %p", target);
    dlclose(egl); return true;
}

// ============================================================
// SECTION 23 — CHEAT THREAD & JNI
// ============================================================

static void* CheatThread(void*) {
    // Huawei APK variant: game code in libgamex64.so (same name as standard)
    // libro.so is a pre-injected stub — we ignore it for game access
    while (!g_Base) {
        g_Base = GetLibBase("libgamex64.so");
        if (!g_Base) sleep(1);
    }
    while (!g_UnityBase) {
        g_UnityBase = GetLibBase("libunity.so");
        if (!g_UnityBase) sleep(1);
    }
    // Resolve klasses immediately — needed before scan
    RefreshKlasses();
    LOGI("NJH=0x%llX AKE=0x%llX DWC=0x%llX CAM=0x%llX",
         (unsigned long long)g_NJHKlass, (unsigned long long)g_AKEKlass,
         (unsigned long long)g_DWCKlass, (unsigned long long)g_CAMKlass);
    LOGI("gamex64 @ 0x%llX  unity @ 0x%llX",
         (unsigned long long)g_Base, (unsigned long long)g_UnityBase);
    sleep(2);
    if (!InitIL2CPP()) { LOGE("IL2CPP init failed"); return nullptr; }
    void* domain = il2cpp_domain_get ? il2cpp_domain_get() : nullptr;
    if (domain && il2cpp_thread_attach) il2cpp_thread_attach(domain);
    sleep(3);
    if (!HookEGL()) { LOGE("EGL hook failed"); return nullptr; }
    LOGI("Cheat running. Tap [M] to open menu.");
    while (true) sleep(10);
    return nullptr;
}

JNIEXPORT jint JNICALL JNI_OnLoad(JavaVM* vm, void* reserved) {
    LOGI("JNI_OnLoad: hwidoholy v3");
    pthread_t tid;
    pthread_create(&tid, nullptr, CheatThread, nullptr);
    pthread_detach(tid);
    return JNI_VERSION_1_6;
}
