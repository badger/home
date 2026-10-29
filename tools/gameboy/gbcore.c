// MicroPython native module that wraps Peanut-GB for the Universe 2026 badge.
// Build with build.py; the result is badge/apps/game_boy/gbcore.mpy.

#define ENABLE_SOUND 0
#define ENABLE_LCD 1
#define PEANUT_GB_12_COLOUR 1
#define PEANUT_GB_IS_LITTLE_ENDIAN 1

#include "py/dynruntime.h"
#include "peanut_gb.h"

#define MODE_1X 0
#define MODE_SHARP 1
#define MODE_SMOOTH 2

typedef struct {
    const uint8_t *rom;
    size_t rom_len;
    uint8_t *ram;
    size_t ram_len;

    uint16_t *fb;
    size_t fb_pixels;
    int stride;
    int x0;
    int y0;
    int mode;
    bool draw;

    uint32_t ram_dirty;
    int error;
    int error_addr;

    uint16_t palette[4][4];
    uint16_t line[LCD_WIDTH];
    uint16_t prev[LCD_WIDTH];
} frontend_t;

// mpy_ld requires zero-initialised globals to be non-static.
struct gb_s gb;
frontend_t fe;
bool loaded;

static uint8_t rom_read(struct gb_s *g, const uint_fast32_t addr) {
    (void)g;
    return addr < fe.rom_len ? fe.rom[addr] : 0xFF;
}

static uint8_t cart_ram_read(struct gb_s *g, const uint_fast32_t addr) {
    (void)g;
    return addr < fe.ram_len ? fe.ram[addr] : 0xFF;
}

static void cart_ram_write(struct gb_s *g, const uint_fast32_t addr, const uint8_t val) {
    (void)g;
    if (addr < fe.ram_len && fe.ram[addr] != val) {
        fe.ram[addr] = val;
        // One bit per 8 KiB cartridge RAM bank.
        fe.ram_dirty |= 1u << ((addr >> 13) & 31);
    }
}

static void on_error(struct gb_s *g, const enum gb_error_e err, const uint16_t addr) {
    (void)g;
    fe.error = (int)err + 1;
    fe.error_addr = addr;
}

// Average two RGB565 pixels without unpacking the channels.
static inline uint16_t blend(uint16_t a, uint16_t b) {
    return (uint16_t)((a & b) + (((a ^ b) & 0xF7DE) >> 1));
}

static void lcd_draw_line(struct gb_s *g, const uint8_t *pixels, const uint_fast8_t y) {
    (void)g;
    if (!fe.draw || fe.fb == NULL || y >= LCD_HEIGHT) {
        return;
    }

    uint16_t *line = fe.line;
    for (int x = 0; x < LCD_WIDTH; x++) {
        uint8_t p = pixels[x];
        line[x] = fe.palette[(p & LCD_PALETTE_ALL) >> 4][p & 3];
    }

    if (fe.mode == MODE_1X) {
        uint16_t *dst = fe.fb + (fe.y0 + y) * fe.stride + fe.x0;
        for (int x = 0; x < LCD_WIDTH; x++) {
            dst[x] = line[x];
        }
        return;
    }

    // 1.5x: every two source pixels become three on screen, both across and down.
    bool smooth = fe.mode == MODE_SMOOTH;
    int pair = y >> 1;
    int base = fe.y0 + pair * 3;

    if ((y & 1) == 0) {
        uint16_t *a = fe.fb + base * fe.stride + fe.x0;
        uint16_t *b = a + fe.stride;
        for (int x = 0; x < LCD_WIDTH; x += 2) {
            uint16_t c0 = line[x];
            uint16_t c1 = line[x + 1];
            uint16_t mid = smooth ? blend(c0, c1) : c0;
            a[0] = c0;
            a[1] = mid;
            a[2] = c1;
            b[0] = c0;
            b[1] = mid;
            b[2] = c1;
            a += 3;
            b += 3;
        }
        if (smooth) {
            uint16_t *prev = fe.prev;
            for (int x = 0; x < LCD_WIDTH; x++) {
                prev[x] = line[x];
            }
        }
    } else {
        uint16_t *b = fe.fb + (base + 1) * fe.stride + fe.x0;
        uint16_t *c = b + fe.stride;
        const uint16_t *prev = fe.prev;
        for (int x = 0; x < LCD_WIDTH; x += 2) {
            uint16_t c0 = line[x];
            uint16_t c1 = line[x + 1];
            uint16_t mid = smooth ? blend(c0, c1) : c0;
            c[0] = c0;
            c[1] = mid;
            c[2] = c1;
            if (smooth) {
                uint16_t p0 = prev[x];
                uint16_t p1 = prev[x + 1];
                b[0] = blend(p0, c0);
                b[1] = blend(blend(p0, p1), mid);
                b[2] = blend(p1, c1);
            }
            b += 3;
            c += 3;
        }
    }
}

static int frame_width(void) {
    return fe.mode == MODE_1X ? LCD_WIDTH : LCD_WIDTH * 3 / 2;
}

static int frame_height(void) {
    return fe.mode == MODE_1X ? LCD_HEIGHT : LCD_HEIGHT * 3 / 2;
}

static void require_loaded(void) {
    if (!loaded) {
        mp_raise_ValueError(MP_ERROR_TEXT("no ROM loaded"));
    }
}

// load(rom) -> 0 on success, 1 unsupported cartridge, 2 bad header checksum
static mp_obj_t gbcore_load(mp_obj_t rom_in) {
    mp_buffer_info_t info;
    mp_get_buffer_raise(rom_in, &info, MP_BUFFER_READ);
    if (info.len < 0x150) {
        mp_raise_ValueError(MP_ERROR_TEXT("ROM too small"));
    }

    loaded = false;
    fe.rom = info.buf;
    fe.rom_len = info.len;
    fe.ram = NULL;
    fe.ram_len = 0;
    fe.ram_dirty = 0;
    fe.error = 0;
    fe.error_addr = 0;

    enum gb_init_error_e ret = gb_init(&gb, rom_read, cart_ram_read, cart_ram_write, on_error, &fe);
    if (ret != GB_INIT_NO_ERROR) {
        return mp_obj_new_int(ret);
    }
    gb_init_lcd(&gb, lcd_draw_line);
    loaded = true;
    return mp_obj_new_int(0);
}
static MP_DEFINE_CONST_FUN_OBJ_1(gbcore_load_obj, gbcore_load);

static mp_obj_t gbcore_save_size(void) {
    require_loaded();
    size_t size = 0;
    if (gb_get_save_size_s(&gb, &size) != 0) {
        return mp_obj_new_int(0);
    }
    return mp_obj_new_int(size);
}
static MP_DEFINE_CONST_FUN_OBJ_0(gbcore_save_size_obj, gbcore_save_size);

// set_ram(bytearray): cartridge RAM the emulator reads and writes in place
static mp_obj_t gbcore_set_ram(mp_obj_t ram_in) {
    mp_buffer_info_t info;
    mp_get_buffer_raise(ram_in, &info, MP_BUFFER_RW);
    fe.ram = info.buf;
    fe.ram_len = info.len;
    fe.ram_dirty = 0;
    return mp_const_none;
}
static MP_DEFINE_CONST_FUN_OBJ_1(gbcore_set_ram_obj, gbcore_set_ram);

// layout(stride_pixels, x, y, mode): where run() draws in the RGB565 screen
static mp_obj_t gbcore_layout(size_t n_args, const mp_obj_t *args) {
    (void)n_args;
    int stride = mp_obj_get_int(args[0]);
    int x0 = mp_obj_get_int(args[1]);
    int y0 = mp_obj_get_int(args[2]);
    int mode = mp_obj_get_int(args[3]);
    if (stride <= 0 || x0 < 0 || y0 < 0 || mode < MODE_1X || mode > MODE_SMOOTH) {
        mp_raise_ValueError(MP_ERROR_TEXT("bad layout"));
    }
    fe.stride = stride;
    fe.x0 = x0;
    fe.y0 = y0;
    fe.mode = mode;
    if (x0 + frame_width() > stride) {
        mp_raise_ValueError(MP_ERROR_TEXT("frame wider than screen"));
    }
    return mp_const_none;
}
static MP_DEFINE_CONST_FUN_OBJ_VAR_BETWEEN(gbcore_layout_obj, 4, 4, gbcore_layout);

// set_palette(buffer of 12 little-endian RGB565 values: OBJ0, OBJ1, BG)
static mp_obj_t gbcore_set_palette(mp_obj_t pal_in) {
    mp_buffer_info_t info;
    mp_get_buffer_raise(pal_in, &info, MP_BUFFER_READ);
    if (info.len < 24) {
        mp_raise_ValueError(MP_ERROR_TEXT("palette needs 12 colours"));
    }
    const uint8_t *src = info.buf;
    for (int p = 0; p < 3; p++) {
        for (int c = 0; c < 4; c++) {
            int i = (p * 4 + c) * 2;
            fe.palette[p][c] = (uint16_t)(src[i] | (src[i + 1] << 8));
        }
    }
    for (int c = 0; c < 4; c++) {
        fe.palette[3][c] = fe.palette[2][c];
    }
    return mp_const_none;
}
static MP_DEFINE_CONST_FUN_OBJ_1(gbcore_set_palette_obj, gbcore_set_palette);

// run(frames, joypad, screen) -> 0, or the Peanut-GB error code + 1.
// Only the final frame is drawn into the screen buffer.
static mp_obj_t gbcore_run(mp_obj_t frames_in, mp_obj_t joypad_in, mp_obj_t screen_in) {
    require_loaded();
    int frames = mp_obj_get_int(frames_in);
    gb.direct.joypad = (uint8_t)mp_obj_get_int(joypad_in);

    fe.fb = NULL;
    if (screen_in != mp_const_none) {
        mp_buffer_info_t info;
        mp_get_buffer_raise(screen_in, &info, MP_BUFFER_RW);
        size_t pixels = info.len / 2;
        size_t needed = (size_t)(fe.y0 + frame_height() - 1) * fe.stride + fe.x0 + frame_width();
        if (fe.stride <= 0 || pixels < needed) {
            mp_raise_ValueError(MP_ERROR_TEXT("screen smaller than layout"));
        }
        fe.fb = info.buf;
        fe.fb_pixels = pixels;
    }

    // Peanut-GB skips rendering entirely when there is no line callback, so
    // frames that will never be displayed cost only CPU emulation.
    for (int i = 0; i < frames && !fe.error; i++) {
        fe.draw = i == frames - 1 && fe.fb != NULL;
        gb.display.lcd_draw_line = fe.draw ? lcd_draw_line : NULL;
        gb_run_frame(&gb);
    }
    gb.display.lcd_draw_line = lcd_draw_line;
    fe.draw = false;
    fe.fb = NULL;
    return mp_obj_new_int(fe.error);
}
static MP_DEFINE_CONST_FUN_OBJ_3(gbcore_run_obj, gbcore_run);

// ram_dirty() -> bit mask of 8 KiB cartridge RAM banks changed since the last call
static mp_obj_t gbcore_ram_dirty(void) {
    uint32_t dirty = fe.ram_dirty;
    fe.ram_dirty = 0;
    return mp_obj_new_int_from_uint(dirty);
}
static MP_DEFINE_CONST_FUN_OBJ_0(gbcore_ram_dirty_obj, gbcore_ram_dirty);

static mp_obj_t gbcore_title(void) {
    require_loaded();
    char title[17];
    gb_get_rom_name(&gb, title);
    size_t len = 0;
    while (len < 16 && title[len]) {
        len++;
    }
    return mp_obj_new_str(title, len);
}
static MP_DEFINE_CONST_FUN_OBJ_0(gbcore_title_obj, gbcore_title);

static mp_obj_t gbcore_colour_hash(void) {
    require_loaded();
    return mp_obj_new_int(gb_colour_hash(&gb));
}
static MP_DEFINE_CONST_FUN_OBJ_0(gbcore_colour_hash_obj, gbcore_colour_hash);

static mp_obj_t gbcore_error_addr(void) {
    return mp_obj_new_int(fe.error_addr);
}
static MP_DEFINE_CONST_FUN_OBJ_0(gbcore_error_addr_obj, gbcore_error_addr);

static mp_obj_t gbcore_reset(void) {
    require_loaded();
    fe.error = 0;
    gb_reset(&gb);
    return mp_const_none;
}
static MP_DEFINE_CONST_FUN_OBJ_0(gbcore_reset_obj, gbcore_reset);

// set_rtc(day, hour, minute, second) for MBC3 clock cartridges
static mp_obj_t gbcore_set_rtc(size_t n_args, const mp_obj_t *args) {
    (void)n_args;
    require_loaded();
    struct tm t;
    memset(&t, 0, sizeof(t));
    t.tm_yday = mp_obj_get_int(args[0]) & 0x1FF;
    t.tm_hour = mp_obj_get_int(args[1]);
    t.tm_min = mp_obj_get_int(args[2]);
    t.tm_sec = mp_obj_get_int(args[3]);
    gb_set_rtc(&gb, &t);
    return mp_const_none;
}
static MP_DEFINE_CONST_FUN_OBJ_VAR_BETWEEN(gbcore_set_rtc_obj, 4, 4, gbcore_set_rtc);

mp_obj_t mpy_init(mp_obj_fun_bc_t *self, size_t n_args, size_t n_kw, mp_obj_t *args) {
    MP_DYNRUNTIME_INIT_ENTRY

    loaded = false;
    memset(&fe, 0, sizeof(fe));

    mp_store_global(MP_QSTR_load, MP_OBJ_FROM_PTR(&gbcore_load_obj));
    mp_store_global(MP_QSTR_save_size, MP_OBJ_FROM_PTR(&gbcore_save_size_obj));
    mp_store_global(MP_QSTR_set_ram, MP_OBJ_FROM_PTR(&gbcore_set_ram_obj));
    mp_store_global(MP_QSTR_layout, MP_OBJ_FROM_PTR(&gbcore_layout_obj));
    mp_store_global(MP_QSTR_set_palette, MP_OBJ_FROM_PTR(&gbcore_set_palette_obj));
    mp_store_global(MP_QSTR_run, MP_OBJ_FROM_PTR(&gbcore_run_obj));
    mp_store_global(MP_QSTR_ram_dirty, MP_OBJ_FROM_PTR(&gbcore_ram_dirty_obj));
    mp_store_global(MP_QSTR_title, MP_OBJ_FROM_PTR(&gbcore_title_obj));
    mp_store_global(MP_QSTR_colour_hash, MP_OBJ_FROM_PTR(&gbcore_colour_hash_obj));
    mp_store_global(MP_QSTR_error_addr, MP_OBJ_FROM_PTR(&gbcore_error_addr_obj));
    mp_store_global(MP_QSTR_reset, MP_OBJ_FROM_PTR(&gbcore_reset_obj));
    mp_store_global(MP_QSTR_set_rtc, MP_OBJ_FROM_PTR(&gbcore_set_rtc_obj));

    mp_store_global(MP_QSTR_A, MP_OBJ_NEW_SMALL_INT(JOYPAD_A));
    mp_store_global(MP_QSTR_B, MP_OBJ_NEW_SMALL_INT(JOYPAD_B));
    mp_store_global(MP_QSTR_SELECT, MP_OBJ_NEW_SMALL_INT(JOYPAD_SELECT));
    mp_store_global(MP_QSTR_START, MP_OBJ_NEW_SMALL_INT(JOYPAD_START));
    mp_store_global(MP_QSTR_RIGHT, MP_OBJ_NEW_SMALL_INT(JOYPAD_RIGHT));
    mp_store_global(MP_QSTR_LEFT, MP_OBJ_NEW_SMALL_INT(JOYPAD_LEFT));
    mp_store_global(MP_QSTR_UP, MP_OBJ_NEW_SMALL_INT(JOYPAD_UP));
    mp_store_global(MP_QSTR_DOWN, MP_OBJ_NEW_SMALL_INT(JOYPAD_DOWN));
    mp_store_global(MP_QSTR_MODE_1X, MP_OBJ_NEW_SMALL_INT(MODE_1X));
    mp_store_global(MP_QSTR_MODE_SHARP, MP_OBJ_NEW_SMALL_INT(MODE_SHARP));
    mp_store_global(MP_QSTR_MODE_SMOOTH, MP_OBJ_NEW_SMALL_INT(MODE_SMOOTH));
    mp_store_global(MP_QSTR_WIDTH, MP_OBJ_NEW_SMALL_INT(LCD_WIDTH));
    mp_store_global(MP_QSTR_HEIGHT, MP_OBJ_NEW_SMALL_INT(LCD_HEIGHT));

    MP_DYNRUNTIME_INIT_EXIT
}
