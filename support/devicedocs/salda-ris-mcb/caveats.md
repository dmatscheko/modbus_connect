# Salda RIS / RIRS (MCB) — caveats & limitations

Known limitations of this device file — things that are not (or not yet) fully
supported, or that you should verify against your own hardware.

## Temperature inputs use a non-documented layout

The four temperature input registers (addresses 0/3/6/9 in the config) do not
match the MCB 1.29 register table, which places T1–T4 at 18–21. The device file
uses a custom/older layout confirmed on a real unit; the documented T1–T4
addresses read 0. If your temperatures read 0 or wrong, your firmware likely uses
the documented (18–21) layout — swap the addresses.

## Humidity is not exposed

Humidity is not exposed over Modbus on this controller.

## Addressing is 0-based

Addressing is 0-based: Modbus PDU = the workbook "Address" column − 1.
