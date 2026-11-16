SECTIONS {
  .hook  0x1e00426 : { *(.hook) }   /* greet(): call vbat_percent (4 B) */
  .combo 0x1e11f34 : { *(.combo) }  /* stock combo detection, up to 0x1e11f82 (78 B) */
  .ef    0x1e13268 : { *(.ef) }     /* stock mode 3 handler, up to bank_now() at 0x1e1337c (276 B) */
  .ef3   0x1e13436 : { *(.ef3) }    /* stock mode 6/7/8 handlers, up to 0x1e1354a (276 B) */
  .ef2   0x1e135b4 : { *(.ef2) }    /* stock mode 10 handler, up to 0x1e1369e (234 B) */
  /DISCARD/ : { *(.text*) }
}
adv_send = 0x1e13184; pedal = 0x1e12aba; bank_now = 0x1e1337c; gpio_read = 0x1e00b9a;
vbat_percent = 0x1e0e4a0; mix_key = 0x1e1369e; disp3 = 0x1e122f6; hid_send = 0x1e12292;
