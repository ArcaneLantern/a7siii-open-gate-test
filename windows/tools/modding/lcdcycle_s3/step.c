/* lcdcycle_s3_v1: the step routine that the C3 hook in the A7S III 5.01 appFw.so calls (build/build_lcdcycle_s3.py). It is the A7 IV's
 * lcdcycle_v6 routine (build/lcdcycle_v6/step.c, works on that camera: F858, F969) with this camera's addresses. Freestanding, position
 * independent: every call is a PC-relative `bl` to an appFw address given to the linker, or through a pointer that dlsym returned.
 *
 * In movie mode, one C3 press steps the rear-screen preview 3:2 -> 2:1 -> 2.4:1 -> 3:2:
 *   - the picture: the VDF fit word and the letterbox constants of the picture-ratio function (9/16, 1/2, 5/12);
 *   - the rectangle the coprocessor's frame widgets expect for a 16:9 picture on the rear panel, in their three tables
 *     ({x, y, w, h} as u16 in a 640x480 grid). The widgets draw no frame unless the live-view rectangle is within 5 units of that entry.
 * Then it asks VDF for a fresh layout (appFw's vdf_set_yuv_layout wrapper, automatic case-0 request).
 *
 * Differences from the A7 IV routine, all forced by where things lie in this image (pool.h, generated from the 5.01 file):
 *   - the constants are `moveq.w lr, #n` and `it eq; moveq r0, #d` (the A7S III function has a second, 100/235 case in front of them);
 *   - the middle table's entry lies across two 64-byte lines, so it is two lines of one word each;
 *   - a guard that would fall outside its line is left out;
 *   - the De-Squeeze model variable is not written (on the A7 IV it was kept for reference only).
 *
 * The state is read from the coprocessor (the letterbox constants) on every press, so any start state works. Every line is read,
 * checked against the bytes it must hold, changed, written back and read again. The picture comes first: the layout is requested when
 * the two picture lines were written and read back, whatever happened to the frame tables (a table that is not as expected is left
 * alone, and the frames then stay hidden in that mode).
 *
 * Returns 1 when the press was taken (movie mode): the hook then turns the key event into the ignored one; 0 otherwise. */
typedef unsigned long u64;
typedef unsigned int u32;

extern void *appfw_dlsym(void *handle, const char *name);       /* appFw .plt stub of dlsym */
extern u32 *appfw_system_mode(void);                            /* the model's system mode, 3 = movie */
extern void appfw_vdf_layout(void *in, void *out);              /* lock, vdf_set_yuv_layout, unlock */

typedef u64 (*alloc_t)(u32 size, u32 *handle);
typedef u64 (*free_t)(u32 handle);
typedef u32 (*xfer_t)(u32 dir, u64 src, u64 dst, u32 size);

#define NONE 9u                /* no state / failed */
#define ANY 8u                 /* any listed candidate may be there */

/* system calls with only the registers each one needs */
static inline long sc1(long n, long a)
{
    register long x8 __asm__("x8") = n, x0 __asm__("x0") = a;
    __asm__ volatile("svc #0" : "+r"(x0) : "r"(x8) : "memory", "cc");
    return x0;
}
static inline long sc2(long n, long a, long b)
{
    register long x8 __asm__("x8") = n, x0 __asm__("x0") = a, x1 __asm__("x1") = b;
    __asm__ volatile("svc #0" : "+r"(x0) : "r"(x8), "r"(x1) : "memory", "cc");
    return x0;
}
static inline long sc3(long n, long a, long b, long c)
{
    register long x8 __asm__("x8") = n, x0 __asm__("x0") = a, x1 __asm__("x1") = b, x2 __asm__("x2") = c;
    __asm__ volatile("svc #0" : "+r"(x0) : "r"(x8), "r"(x1), "r"(x2) : "memory", "cc");
    return x0;
}
static inline long sc6(long n, long a, long b, long c, long d, long e, long f)
{
    register long x8 __asm__("x8") = n, x0 __asm__("x0") = a, x1 __asm__("x1") = b, x2 __asm__("x2") = c;
    register long x3 __asm__("x3") = d, x4 __asm__("x4") = e, x5 __asm__("x5") = f;
    __asm__ volatile("svc #0" : "+r"(x0) : "r"(x8), "r"(x1), "r"(x2), "r"(x3), "r"(x4), "r"(x5) : "memory", "cc");
    return x0;
}

/* The coprocessor lines, as data (no pointers: the routine must have no relocations). POOL holds, for each kind of line, its guards as
 * {word index from the first site word, value} pairs, then its candidates (nw words each). pool.h defines POOL, DESC, D_A, D_B, D_T0,
 * D_SPLIT and D_TLAST from the 5.01 image. */
struct desc { u32 line; unsigned char base, ng, ncand, nw, g, c; };
#include "pool.h"
struct ctx { xfer_t xfer; u64 phys; volatile u32 *buf; };

/* read one 64-byte line into the buffer; the fill is there so that a transfer that moves nothing cannot pass for a read */
__attribute__((noinline)) static u32 rd(const struct ctx *c, u64 line)
{
    for (u32 k = 0; k < 16; k++) c->buf[k] = 0xeeeeeeeeu;
    return c->xfer(0, line, c->phys, 64);
}

/* One line. The guards must hold; the site words must equal candidate `want` (or any candidate, for ANY). With next == NONE nothing
 * is written and the matching candidate is returned. Otherwise candidate `next` is written, the line read back, and `next` returned.
 * NONE on any failure. (The buffer is 64-byte aligned and every offset a multiple of 4: plain aligned 32-bit accesses.) */
__attribute__((noinline)) static u32 upd(const struct ctx *c, u32 d, u32 want, u32 next)
{
    const struct desc *D = &DESC[d];
    const u32 *g = POOL + D->g, *cand = POOL + D->c;
    volatile u32 *w = c->buf + D->base;
    u32 nw = D->nw, m = NONE;
    if (rd(c, D->line)) return NONE;
    for (u32 k = 0; k < D->ng; k++)
        if (w[(int)g[2 * k]] != g[2 * k + 1]) return NONE;
    for (u32 k = 0; k < D->ncand && m == NONE; k++) {
        u32 same = want == ANY || want == k;
        for (u32 i = 0; i < nw; i++)
            if (w[i] != cand[k * nw + i]) same = 0;
        if (same) m = k;
    }
    if (m == NONE || next == NONE) return m;
    cand += next * nw;
    for (u32 i = 0; i < nw; i++) w[i] = cand[i];
    if (c->xfer(1, c->phys, D->line, 64) || rd(c, D->line)) return NONE;
    for (u32 i = 0; i < nw; i++)
        if (w[i] != cand[i]) return NONE;
    return next;
}

int lcd_step(void)
{
    static const char s_alloc[] = "_Z9dmm_allocjPj", s_free[] = "_Z8dmm_freej", s_xfer[] = "sen_dma_transfer", s_mem[] = "/dev/mem";
    struct ctx c;

    if (*appfw_system_mode() != 3) return 0;
    alloc_t alloc = (alloc_t)appfw_dlsym(0, s_alloc);
    free_t dfree = (free_t)appfw_dlsym(0, s_free);
    c.xfer = (xfer_t)appfw_dlsym(0, s_xfer);
    if (!alloc || !dfree || !c.xfer) return 1;
    u32 handle = 0;
    u64 phys = c.phys = alloc(4096, &handle);
    if (!phys) return 1;
    int ok = 0;
    if (!(phys & 0x3f) && phys >= 0x400000000UL && phys + 4096 <= 0x500000000UL) {
        long fd = sc3(56, -100, (long)s_mem, 2 | 0x101000);              /* openat(AT_FDCWD, "/dev/mem", O_RDWR | O_SYNC) */
        if (fd >= 0) {
            u64 lead = phys & 0xfff, maplen = (lead + 4096 + 0xfff) & ~0xfffUL;
            long m = sc6(222, 0, (long)maplen, 3, 1, fd, (long)(phys - lead));    /* mmap(0, len, READ|WRITE, SHARED, fd, page) */
            if ((m & 0xfff) == 0 && (unsigned long)m < 0xfffffffffffff000UL) {
                c.buf = (volatile u32 *)(m + (long)lead);
                /* the state now, from the coprocessor itself: line B's constants */
                u32 now = upd(&c, D_B, ANY, NONE);
                if (now < 3) {
                    u32 next = now == 2 ? 0 : now + 1;
                    /* line A's fit word must agree with that state (3:2 needs the fill word 0); then line B */
                    if (upd(&c, D_A, now, next) != NONE && upd(&c, D_B, now, next) != NONE) {
                        ok = 1;
                        for (u32 t = D_T0; t <= D_TLAST; t++) {           /* the frame tables: best effort, the picture is already changed */
                            /* the entry that lies across two lines (D_SPLIT and the line after it): both halves or neither */
                            if (t == D_SPLIT && upd(&c, t + 1, ANY, NONE) == NONE) { t++; continue; }
                            if (upd(&c, t, ANY, next) == NONE && t == D_SPLIT) t++;
                        }
                    }
                }
                sc2(215, m, (long)maplen);                                /* munmap */
            }
            sc1(57, fd);                                                  /* close */
        }
    }
    dfree(handle);
    if (ok) {
        volatile u32 in[12], out[4];                                     /* case 0: an automatic layout, as on entering movie mode */
        for (u32 k = 0; k < 12; k++) in[k] = 0;                         /* (a loop, not an initializer: no memset call) */
        for (u32 k = 0; k < 4; k++) out[k] = 0;
        appfw_vdf_layout((void *)in, (void *)out);
    }
    return 1;
}
