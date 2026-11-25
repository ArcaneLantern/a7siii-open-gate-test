/* Host-only test of the exact tables and verdict code used by check and dump. */
#include <assert.h>
#include <string.h>
#include "stock_preflight.h"
#include "s3_expected.h"

#define COUNT(rows) (sizeof(rows) / sizeof((rows)[0]))

static void observe_cp(struct preflight_counts *counts, const struct cp_site *site, int st, int tg)
{
    observe_cp_site(counts, site->name, site->soft, site->target != 0, st, tg);
}

static void observe_mp(struct preflight_counts *counts, const struct mp_site *site,
                       const unsigned char *bytes)
{
    int is_header = (site->offset == 0x223cc4UL || site->offset == 0x223d10UL);
    observe_mp_site(counts, is_header,
                    !memcmp(bytes, site->stock, site->length),
                    !memcmp(bytes, site->target, site->length));
}

static struct preflight_counts build_stock(void)
{
    struct preflight_counts c = {0};
    for (size_t i = 0; i < COUNT(cp_sites); i++)
        observe_cp(&c, &cp_sites[i], 1, 0);
    for (size_t i = 0; i < COUNT(lm_sites); i++)
        observe_mp(&c, &lm_sites[i], lm_sites[i].stock);
    for (size_t i = 0; i < COUNT(av_sites); i++)
        observe_mp(&c, &av_sites[i], av_sites[i].stock);
    return c;
}

static struct preflight_counts build_applied(int with_meta, int sr_runtime)
{
    struct preflight_counts c = {0};
    for (size_t i = 0; i < COUNT(cp_sites); i++) {
        const struct cp_site *s = &cp_sites[i];
        if (!s->soft) {
            observe_cp(&c, s, 0, 1);
        } else if (sp_streq(s->name, "stored_record")) {
            observe_cp(&c, s, 0, !sr_runtime);
        } else if (sp_streq(s->name, "outsize")) {
            observe_cp(&c, s, 0, 1);
        } else {
            observe_cp(&c, s, 1, 0);
        }
    }
    for (size_t i = 0; i < COUNT(lm_sites); i++) {
        int is_header = (lm_sites[i].offset == 0x223cc4UL || lm_sites[i].offset == 0x223d10UL);
        const unsigned char *bytes = (is_header && !with_meta) ? lm_sites[i].stock : lm_sites[i].target;
        observe_mp(&c, &lm_sites[i], bytes);
    }
    for (size_t i = 0; i < COUNT(av_sites); i++)
        observe_mp(&c, &av_sites[i], av_sites[i].target);
    return c;
}

int main(void)
{
    const unsigned char old_height[] = {0x06, 0x0e, 0x81, 0x52};
    const unsigned char new_height[] = {0x06, 0x40, 0x81, 0x52};
    const unsigned long headers[] = {0x223cc4, 0x223d10};
    const char *ready_stock = "\nVERDICT READY (stock preflight)\n";
    const char *ready_applied = "\nVERDICT READY (open gate applied)\n";
    const char *blocked = "\nVERDICT NOT READY\n";

    /* 1. Coherent stock preflight */
    struct preflight_counts stock = build_stock();
    assert(COUNT(cp_sites) == 25);
    assert(COUNT(lm_sites) == 6 && COUNT(av_sites) == 101);
    assert(stock.cp_og_stock == 21 && stock.cp_og_target == 0);
    assert(stock.mp_base_stock == 105 && stock.mp_hdr_stock == 2 && stock.other == 0);
    assert(!strcmp(preflight_verdict(&stock), ready_stock));

    /* Runtime-filled soft sites on stock remain ready_stock */
    struct preflight_counts stock_rt = {0};
    for (size_t i = 0; i < COUNT(cp_sites); i++)
        observe_cp(&stock_rt, &cp_sites[i], !cp_sites[i].soft, 0);
    for (size_t i = 0; i < COUNT(lm_sites); i++)
        observe_mp(&stock_rt, &lm_sites[i], lm_sites[i].stock);
    for (size_t i = 0; i < COUNT(av_sites); i++)
        observe_mp(&stock_rt, &av_sites[i], av_sites[i].stock);
    assert(stock_rt.sr_runtime == 1 && stock_rt.oz_runtime == 1 && stock_rt.ozg_runtime == 2);
    assert(!strcmp(preflight_verdict(&stock_rt), ready_stock));

    /* 2. Single header or both headers on stock -> blocked */
    for (size_t h = 0; h < COUNT(headers); h++) {
        struct preflight_counts one = {0};
        for (size_t i = 0; i < COUNT(cp_sites); i++)
            observe_cp(&one, &cp_sites[i], 1, 0);
        for (size_t i = 0; i < COUNT(lm_sites); i++) {
            int match = (lm_sites[i].offset == headers[h]);
            if (match) {
                assert(lm_sites[i].length == sizeof(old_height));
                assert(!memcmp(old_height, lm_sites[i].stock, sizeof(old_height)));
                assert(!memcmp(new_height, lm_sites[i].target, sizeof(new_height)));
            }
            observe_mp(&one, &lm_sites[i], match ? new_height : lm_sites[i].stock);
        }
        for (size_t i = 0; i < COUNT(av_sites); i++)
            observe_mp(&one, &av_sites[i], av_sites[i].stock);
        assert(one.mp_hdr_target == 1 && one.mp_hdr_stock == 1);
        assert(!strcmp(preflight_verdict(&one), blocked));
    }

    struct preflight_counts hdrs_only = {0};
    for (size_t i = 0; i < COUNT(cp_sites); i++)
        observe_cp(&hdrs_only, &cp_sites[i], 1, 0);
    for (size_t i = 0; i < COUNT(lm_sites); i++) {
        int is_header = (lm_sites[i].offset == headers[0] || lm_sites[i].offset == headers[1]);
        observe_mp(&hdrs_only, &lm_sites[i], is_header ? lm_sites[i].target : lm_sites[i].stock);
    }
    for (size_t i = 0; i < COUNT(av_sites); i++)
        observe_mp(&hdrs_only, &av_sites[i], av_sites[i].stock);
    assert(hdrs_only.mp_hdr_target == 2 && !strcmp(preflight_verdict(&hdrs_only), blocked));

    /* 3. Warm power switch mixed state (stock sensor + applied encoder, Issue #3) -> blocked */
    struct preflight_counts mixed = {0};
    for (size_t i = 0; i < COUNT(cp_sites); i++)
        observe_cp(&mixed, &cp_sites[i], sp_streq(cp_sites[i].name, "stored_record") ? 0 : 1, 0);
    for (size_t i = 0; i < COUNT(lm_sites); i++)
        observe_mp(&mixed, &lm_sites[i], lm_sites[i].target);
    for (size_t i = 0; i < COUNT(av_sites); i++)
        observe_mp(&mixed, &av_sites[i], av_sites[i].target);
    assert(mixed.mp_base_target == 105 && mixed.mp_hdr_target == 2);
    assert(!strcmp(preflight_verdict(&mixed), blocked));

    /* 4. Partial cp_og -> blocked */
    struct preflight_counts partial_cp = stock;
    partial_cp.cp_og_stock = 20; partial_cp.cp_og_target = 1;
    assert(!strcmp(preflight_verdict(&partial_cp), blocked));

    /* 5. Coherent open-gate applied states (full v2, --no-meta, runtime stored_record) */
    assert(!strcmp(preflight_verdict(&(struct preflight_counts){0}), blocked));
    struct preflight_counts app_full = build_applied(1, 0);
    assert(app_full.cp_og_target == 21 && app_full.mp_base_target == 105 && app_full.mp_hdr_target == 2);
    assert(!strcmp(preflight_verdict(&app_full), ready_applied));
    struct preflight_counts app_rt = build_applied(1, 1);
    assert(app_rt.sr_runtime == 1 && !strcmp(preflight_verdict(&app_rt), ready_applied));
    struct preflight_counts app_nometa = build_applied(0, 0);
    assert(app_nometa.mp_hdr_stock == 2 && !strcmp(preflight_verdict(&app_nometa), ready_applied));

    /* 6. Invalid applied states -> blocked */
    struct preflight_counts bad = app_full;
    bad.mp_hdr_target = 1; bad.mp_hdr_stock = 1;
    assert(!strcmp(preflight_verdict(&bad), blocked));

    bad = app_full;
    bad.ozg_stock = 1; bad.ozg_runtime = 1;
    assert(!strcmp(preflight_verdict(&bad), blocked));

    bad = app_full;
    bad.sr_target = 0; bad.sr_stock = 1;
    assert(!strcmp(preflight_verdict(&bad), blocked));

    bad = app_full;
    bad.oz_target = 0; bad.oz_runtime = 1;
    assert(!strcmp(preflight_verdict(&bad), blocked));

    bad = app_full;
    bad.cp_og_target = 20; bad.cp_og_stock = 1;
    assert(!strcmp(preflight_verdict(&bad), blocked));

    bad = app_full;
    bad.other = 1;
    assert(!strcmp(preflight_verdict(&bad), blocked));

    return 0;
}
