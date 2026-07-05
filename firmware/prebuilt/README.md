# Prebuilt firmware images

Merged ESP32 images (single file, flashed at offset `0x0`) used by
**Dashboard → Add Node → Flash**. The flasher looks for `<variant>.bin` here.

Build `combo_node.bin` per [../combo_node/README.md](../combo_node/README.md):

```bash
cd firmware/combo_node
pio run
esptool --chip esp32 merge_bin -o ../prebuilt/combo_node.bin \
    0x1000  .pio/build/esp32dev/bootloader.bin \
    0x8000  .pio/build/esp32dev/partitions.bin \
    0x10000 .pio/build/esp32dev/firmware.bin
```

`*.bin` files are git-ignored (build artifacts). Build them on the server, or
commit a release image deliberately if you want flashing to work without a
toolchain present.
