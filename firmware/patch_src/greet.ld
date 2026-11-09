SECTIONS {
  .hook          0x1e144ca : { *(.hook) }
  .cave_d        0x1e00406 : { *(.cave_d) }
  .site_a_bank   0x1e1305a : { *(.site_a_bank) }
  .bank_down_fix 0x1e13322 : { *(.bank_down_fix) }
  .bank_up_fix   0x1e13346 : { *(.bank_up_fix) }
  .site_b        0x1e13370 : { *(.site_b) }
  .site_b_tail   0x1e1337c : { *(.site_b_tail) }
  .site_led_on   0x1e129ee : { *(.site_led_on) }
  .site_pwm      0x1e11d78 : { *(.site_pwm) }
  .cave_b        0x1e19308 : { *(.cave_b) }
  .cave_b2       0x1e19318 : { *(.cave_b2) }
  .cave_c        0x1e260a0 : { *(.cave_c) }
}
disp3        = 0x1e122f6;
vbat_percent = 0x1e0e4a0;
orig_call    = 0x1e1286a;
os_time_dly  = 0x2117d78;
site_a_end   = 0x1e13082;
site_b_end   = 0x1e1338e;
led_on_ret   = 0x1e129f6;   /* after the stock DIR = output */
