# Prebuilt firmware images

Firmware images (single file, flashed at offset `0x0`) used by
**Dashboard → Add Node → Flash**. The flasher looks for `<variant>.bin` here and
picks the esptool chip from the name (`*_esp8266` → esp8266, else esp32):

| File | Board |
|------|-------|
| `combo_node.bin` | ESP32 (merged bootloader + partitions + app) |
| `combo_node_esp8266.bin` | ESP8266 / NodeMCU (single Arduino image) |

Build per [../combo_node/README.md](../combo_node/README.md):

```bash
cd firmware/combo_node

# ESP32 — merged image
pio run -e esp32dev
esptool --chip esp32 merge_bin -o ../prebuilt/combo_node.bin \
    0x1000  .pio/build/esp32dev/bootloader.bin \
    0x8000  .pio/build/esp32dev/partitions.bin \
    0x10000 .pio/build/esp32dev/firmware.bin

# ESP8266 — already a single image, just copy
pio run -e esp8266
cp .pio/build/esp8266/firmware.bin ../prebuilt/combo_node_esp8266.bin
```

`*.bin` files are git-ignored (build artifacts). Build them on the server, or
commit a release image deliberately if you want flashing to work without a
toolchain present.
