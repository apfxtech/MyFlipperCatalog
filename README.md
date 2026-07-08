# MyFlipperCatalog

Catalog of Flipper Zero apps kept as git submodules in [apps/](apps/). CI builds every submodule with `ufbt` and regenerates [catalog.bin](catalog.bin) in the repository root from the apps that built successfully.

## Adding an app

```sh
git submodule add <url> apps/<name>
```

The app must contain `application.fam` with `appid`, `name`, `fap_version` and a 10x10 `fap_icon`.

## catalog.bin format

Little-endian. Fixed-size header and records, variable-length strings in a pool at the end. A reader never has to load the whole file: every read is a seek to a computed address.

### Header — 16 bytes at offset 0

| Offset | Size | Field |
|---|---|---|
| 0 | 4 | magic `"FCAT"` |
| 4 | 1 | format version = 1 |
| 5 | 1 | record size = 36 |
| 6 | 2 | u16 app count |
| 8 | 4 | u32 records offset = 16 |
| 12 | 4 | u32 string pool offset |

### Record — 36 bytes at `16 + i * 36`

| Offset | Size | Field |
|---|---|---|
| 0 | 4 | u32 id offset (absolute) |
| 4 | 4 | u32 name offset (absolute) |
| 8 | 4 | u32 version offset (absolute) |
| 12 | 1 | u8 id length |
| 13 | 1 | u8 name length |
| 14 | 1 | u8 version length |
| 15 | 1 | reserved = 0 |
| 16 | 20 | icon 10x10, 1 bpp XBM: 2 bytes per row, LSB first, bit set = pixel on |

### String pool

UTF-8, each string NUL-terminated. Lengths in the record exclude the NUL, so a string occupies `len + 1` bytes at its offset. Offsets are absolute from the start of the file.

### Reading pattern

```c
typedef struct __attribute__((packed)) {
    uint32_t id_off;
    uint32_t name_off;
    uint32_t ver_off;
    uint8_t id_len;
    uint8_t name_len;
    uint8_t ver_len;
    uint8_t reserved;
    uint8_t icon[20];
} CatalogRecord;

seek(16 + i * 36);
read(&rec, sizeof(rec));

char name[256];
seek(rec.name_off);
read(name, rec.name_len + 1);

canvas_draw_xbm(canvas, x, y, 10, 10, rec.icon);
```
