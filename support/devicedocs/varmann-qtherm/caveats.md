# Varmann Qtherm — caveats & limitations

Known limitations of this device file — things that are not (or not yet) fully
supported, or that you should verify against your own hardware.

## Heat/cool mode map may be off by one

Register 0x03 (HeatChill) is documented as 1 = heat, 2 = cool, 3 = heat+cool, but
the device file maps 0 = Heating, 1 = Cooling, 2 = Auto — shifted by one. If mode
selection is off by one on your unit, correct this map against your firmware.

## Inverter-drive registers are block-specific

The frequency / amplitude / motor-current registers (0x14–0x17) are only
meaningful on the inverter-drive control blocks (types 201106 / 201107); on other
blocks they read non-informative values.

## Primary source is Russian-language

The primary source document is Russian-language (Varmann is a Russian brand).
