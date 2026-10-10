// milestone 1 — ยืนยันว่า build pipeline + การเรียกฟังก์ชันเกมจริงทำงานได้
//
// สิ่งที่ทำ: รอ 8 วินาทีหลังม็อดถูกโหลด แล้ว spawn "พลเรือน" อีกตัวข้างๆ ผู้เล่น
// (ใช้โมเดล index 0 = โมเดล CJ/player ที่โหลดค้างอยู่เสมอ เพื่อตัดปัญหาโมเดลยังไม่โหลด
//  ออกไปก่อน — ยังไม่ใช่ zombie ของจริง แค่พิสูจน์ว่า "เรียกฟังก์ชันสร้าง ped ของเกมเองได้
//  จากโค้ดของเรา" ซึ่งเป็นก้อนที่ยากที่สุดของทั้งโปรเจกต์)
//
// ที่อยู่ฟังก์ชันทั้งหมดด้านล่าง verify จริงจาก libGTASA.so ที่คุณส่งมา (ไม่ได้เดา)
// รายละเอียดการตรวจสอบอยู่ใน docs/findings.md

#include <cstdint>
#include <cstdio>
#include <cstring>
#include <cstdlib>
#include <pthread.h>
#include <unistd.h>
#include <android/log.h>

#define LOG_TAG "MCZombieMod"
#define LOGI(...) __android_log_print(ANDROID_LOG_INFO, LOG_TAG, __VA_ARGS__)
#define LOGE(...) __android_log_print(ANDROID_LOG_ERROR, LOG_TAG, __VA_ARGS__)

struct CVector {
    float x, y, z;
};

// ค่า enum ยืนยันจาก DWARF debug_info ของ libGTASA.so ตรงๆ (ดู docs/findings.md)
enum ePedType {
    PEDTYPE_PLAYER1 = 0,
    PEDTYPE_PLAYER2 = 1,
    PEDTYPE_PLAYER_NETWORK = 2,
    PEDTYPE_PLAYER_UNUSED = 3,
    PEDTYPE_CIVMALE = 4,
    PEDTYPE_CIVFEMALE = 5,
    PEDTYPE_COP = 6,
};

// --- offset ยืนยันแล้วจาก nm -C libGTASA.so (ของเวอร์ชันเกมที่คุณส่งมาเท่านั้น) ---
static constexpr uintptr_t OFF_FindPlayerPed      = 0x4EFAE0; // ? FindPlayerPed(int)
static constexpr uintptr_t OFF_FindPlayerCoors    = 0x4EFEA8; // CVector FindPlayerCoors(int)
static constexpr uintptr_t OFF_CPopulation_AddPed = 0x5CEB40; // ? CPopulation::AddPed(ePedType, unsigned int, CVector const&, bool)

// ชนิดคืนค่าของ FindPlayerPed / AddPed ไม่ได้ถูกเก็บใน mangled name (C++ ABI ไม่เก็บ
// return type) เลยเขียนเป็น void* ไว้ก่อนตามธรรมเนียมเอนจินตระกูลนี้ (คาดว่าคือ CPed*)
// — ยืนยันจริงได้จากผลเทสเท่านั้น
typedef void*   (*FindPlayerPed_t)(int);
typedef CVector (*FindPlayerCoors_t)(int);
typedef void*   (*CPopulation_AddPed_t)(ePedType, unsigned int, const CVector&, bool);

static uintptr_t get_module_base(const char* soName) {
    FILE* f = fopen("/proc/self/maps", "r");
    if (!f) return 0;

    char line[512];
    uintptr_t base = 0;
    while (fgets(line, sizeof(line), f)) {
        if (strstr(line, soName)) {
            base = (uintptr_t)strtoull(line, nullptr, 16);
            break;
        }
    }
    fclose(f);
    return base;
}

static void* test_spawn_thread(void*) {
    // ให้เวลาเกม init ทุกระบบ + ผู้เล่น spawn เข้าโลกก่อน
    sleep(8);

    uintptr_t base = get_module_base("libGTASA.so");
    if (!base) {
        LOGE("หา base address ของ libGTASA.so ไม่เจอ ยกเลิกการเทส");
        return nullptr;
    }
    LOGI("libGTASA.so base = 0x%lx", (unsigned long)base);

    auto FindPlayerPed      = reinterpret_cast<FindPlayerPed_t>(base + OFF_FindPlayerPed);
    auto FindPlayerCoors    = reinterpret_cast<FindPlayerCoors_t>(base + OFF_FindPlayerCoors);
    auto CPopulation_AddPed = reinterpret_cast<CPopulation_AddPed_t>(base + OFF_CPopulation_AddPed);

    void* playerPed = FindPlayerPed(0);
    if (!playerPed) {
        LOGE("FindPlayerPed(0) คืนค่า null — ผู้เล่นอาจยังไม่ spawn เข้าเกม");
        return nullptr;
    }
    LOGI("playerPed = %p", playerPed);

    CVector pos = FindPlayerCoors(0);
    LOGI("player อยู่ที่ (%.2f, %.2f, %.2f)", pos.x, pos.y, pos.z);

    CVector spawnPos = { pos.x + 3.0f, pos.y, pos.z };

    // modelIndex = 0 (โมเดล CJ/player) แค่สำหรับเทส pipeline — ยังไม่ใช่โมเดล zombie จริง
    void* newPed = CPopulation_AddPed(PEDTYPE_CIVMALE, 0, spawnPos, false);
    LOGI("CPopulation::AddPed คืนค่า %p", newPed);

    if (newPed) {
        LOGI("MILESTONE 1 สำเร็จ: น่าจะมี ped ใหม่โผล่ข้างๆ คุณในเกมแล้ว");
    } else {
        LOGE("MILESTONE 1 ยังไม่สำเร็จ: AddPed คืนค่า null — ส่ง logcat ทั้งหมดกลับมาด้วย");
    }

    return nullptr;
}

__attribute__((constructor))
static void on_mod_load() {
    LOGI("mc-zombie-mod: .so ถูกโหลดแล้ว ตั้งเวลาเทส spawn ใน 8 วินาที");
    pthread_t t;
    pthread_create(&t, nullptr, test_spawn_thread, nullptr);
}
