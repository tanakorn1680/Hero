# ข้อมูลจริงที่ยืนยันแล้ว จากไฟล์เกมของคุณ

คุณส่ง `lib/arm64-v8a` ของเกมมาให้ (ไม่ใช่แค่ไฟล์ repo ตัวอย่างที่ผมขอ — **ดีกว่าที่ขอด้วยซ้ำ**)
ข้างใน `libGTASA.so` **ไม่ได้ strip** และยังมี debug info ติดมาเต็มๆ ผมเลยเปิดดูด้วยเครื่องมือ
มาตรฐาน (`nm`, `readelf`) ในแซนด์บ็อกซ์ของผมได้ตรงๆ — ได้ชื่อฟังก์ชัน + ที่อยู่จริง (ของเวอร์ชัน
เกมที่คุณติดตั้งอยู่ ไม่ใช่ของเวอร์ชันอื่น) ไม่ต้องเดาแล้ว

> ข้อควรระวัง: ที่อยู่พวกนี้ผูกกับ **ไฟล์ libGTASA.so ไฟล์นี้ไฟล์เดียว** ถ้าอัปเดตเกมเป็น
> เวอร์ชันใหม่ ที่อยู่อาจขยับ ต้องแตก lib มาเช็กซ้ำ

## ที่อยู่ฟังก์ชันที่ใช้ใน milestone 1 (ยืนยันแล้ว 100%)

| ฟังก์ชัน | offset ใน .so | ซิกเนเจอร์จริง |
|---|---|---|
| `FindPlayerPed` | `0x4EFAE0` | `? FindPlayerPed(int)` — คืนค่า CPed* (รูปแบบมาตรฐานของตระกูลเอนจินนี้ แต่ type คืนค่าไม่ได้เก็บใน mangled name เลยยืนยัน 100% ไม่ได้ ต้องดูผลตอนเทสจริง) |
| `FindPlayerCoors` | `0x4EFEA8` | `CVector FindPlayerCoors(int)` |
| `CPopulation::AddPed` | `0x5CEB40` | `? CPopulation::AddPed(ePedType, unsigned int modelIndex, CVector const&, bool)` — เป็น static method (ไม่มี this) คืนค่าคาดว่าเป็น CPed* เช่นกัน |

ตัวอื่นที่เจอแล้ว เก็บไว้ใช้ milestone ถัดไป:

| ฟังก์ชัน | offset | หมายเหตุ |
|---|---|---|
| `CWorld::Add` | `0x507518` | เผื่อ ped ที่ spawn ไม่โผล่ในโลก (แต่ AddPed น่าจะเรียกให้เองแล้ว ยังไม่ต้องใช้) |
| `CPed::CPed` | `0x594D1C` | constructor ตรง รับ modelIndex |
| `CCivilianPed::CCivilianPed` | `0x593F54` | constructor พลเรือน รับ (ePedType, modelIndex) |
| `CEventHandler::ComputeDamageResponse` | `0x4545F0` | จุดที่ตำรวจ/NPC ตัดสินใจตอบโต้ความเสียหาย — milestone 3-4 |
| `CEventHandler::RegisterKill` | `0x45A298` | บันทึกการฆ่า |
| `CPedDamageResponseCalculator::CPedDamageResponseCalculator` | `0x443B58` | constructor คำนวณความเสียหาย รับ (CEntity const* ผู้ก่อเหตุ, float ดาเมจ, eWeaponType, ePedPieceTypes, bool) |
| `CPedDamageResponseCalculator::ComputeDamageResponse` | `0x443B74` | เรียกหลัง constructor เพื่อได้ผลจริง |

## enum `ePedType` (ยืนยันจาก DWARF debug_info ตรงๆ ไม่ใช่เดา)

```
PEDTYPE_PLAYER1         = 0
PEDTYPE_PLAYER2         = 1
PEDTYPE_PLAYER_NETWORK  = 2
PEDTYPE_PLAYER_UNUSED   = 3
PEDTYPE_CIVMALE         = 4
PEDTYPE_CIVFEMALE       = 5
PEDTYPE_COP             = 6
PEDTYPE_GANG1           = 7
PEDTYPE_GANG2           = 8
PEDTYPE_GANG3           = 9
PEDTYPE_GANG4           = 10
PEDTYPE_GANG5           = 11
```

## API จริงของ AML เอง (จาก libAML.so — `nm -D` เพราะไฟล์นี้ stripped แต่ dynsym ยังอยู่)

มีประโยชน์กับ milestone ถัดไป (ตอนต้อง hook ของจริงแทนที่จะแค่เรียกฟังก์ชันเดิม):

- `AML::Hook(void* target, void* newFunc, void** outOriginal)` — hook แบบมาตรฐาน
- `AML::HookVtableFunc(void* obj, unsigned vtableIndex, void* newFunc, void** outOriginal, bool)` — hook virtual function ผ่าน vtable index (มีประโยชน์มากถ้าฟังก์ชันเกมเป็น virtual)
- `AML::DeHook(void*)`, `AML::ToggleHook(void*, bool)`
- `ARMPatch::GetAddressFromPattern(const char* pattern, const char* lib)` — **pattern scanning ในตัว** แปลว่าในอนาคตไม่ต้อง hardcode address ตายตัวก็ได้ ถ้าอยากให้ม็อดรองรับหลายเวอร์ชันเกม
- `ModInfo::ModInfo(name, author, version, description)` + `Mods::AddNew(ModInfo*, ...)` — ลงทะเบียนม็อดกับ AML (ยังไม่ยืนยัน field order แน่ชัด 100% — milestone 1 นี้เลยเลี่ยงไปใช้ `__attribute__((constructor))` แทน ซึ่งทำงานแน่นอนไม่ว่า AML จะคาดหวัง entry point แบบไหน)
- `InterfaceSys::Register(const char*, void*)` / `InterfaceSys::Get(const char*)` — ระบบแชร์ API ระหว่างม็อด

## ยังไม่รู้ / ต้องเช็กจากการเทสจริง

- path ของโฟลเดอร์ mods ที่ AML อ่าน (`g_szModsDir` มีอยู่ในไบนารี แต่ค่า string จริงต้องดูตอน runtime หรือดูคู่มือ AML)
- modelIndex 0 ที่ใช้ทดสอบ (สมมติว่าคือโมเดล CJ/player ซึ่งโหลดค้างอยู่เสมอ) — ถ้า spawn ไม่ขึ้นหรือเกม crash ให้ดู logcat ส่งกลับมา จะช่วยยืนยัน/แก้ได้ทันที
